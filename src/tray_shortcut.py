"""The Windows Start Menu shortcut a toast needs to exist at all.

Windows shows a toast from a program that is not packaged only when a Start Menu
shortcut carrying its AppUserModelID exists. Without one the notification API
returns success and nothing appears, which is why this is created at install
time rather than left to the user, and why `cdx tray doctor` reports it.

The AppUserModelID cannot be set through `WScript.Shell`: it lives in the
shortcut's property store, reachable only through `IShellLink` plus
`IPropertyStore`. So the work is done by a PowerShell script that declares just
those two interfaces. That is more machinery than a shortcut deserves, and it is
the smallest amount that produces a shortcut a toast will actually use.

Everything here is best-effort by design. A companion that installed correctly
must not be reported as failed because a shortcut could not be written; the
consequence is that notifications will not appear, and doctor says so.
"""
import os
import platform
import subprocess
import tempfile

SHORTCUT_NAME = "CDX.lnk"
# Matches the macOS bundle identifier and what the companion registers with.
# These two have to agree or Windows routes the toast to nothing.
APP_USER_MODEL_ID = "com.cdx.tray"
CREATE_TIMEOUT_SECONDS = 60

# Declared inline rather than shipped as a file: it has to survive a pip install
# of the package, and a one-purpose script beside the code that calls it is
# easier to keep honest than a data file that can go missing.
_PS_SCRIPT = r"""
param([string]$Lnk, [string]$Target, [string]$Aumid)
$ErrorActionPreference = "Stop"
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Sequential, Pack = 4)]
public struct PropertyKey { public Guid fmtid; public uint pid;
  public PropertyKey(Guid g, uint p) { fmtid = g; pid = p; } }

// PROPVARIANT is 24 bytes on x64: vt plus three reserved words, then a union
// whose largest member is 16. Declaring it shorter lets GetValue write past the
// end of the managed struct, and the symptom is a value that silently reads
// back as VT_EMPTY rather than a crash.
[StructLayout(LayoutKind.Explicit, Size = 24)]
public struct PropVariant {
  [FieldOffset(0)] public ushort vt;
  [FieldOffset(8)] public IntPtr p;
  [FieldOffset(16)] public IntPtr p2;
}

[ComImport, Guid("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPropertyStore {
  int GetCount(out uint c);
  int GetAt(uint i, out PropertyKey k);
  int GetValue(ref PropertyKey k, out PropVariant v);
  int SetValue(ref PropertyKey k, ref PropVariant v);
  int Commit();
}

[ComImport, Guid("0000010b-0000-0000-C000-000000000046"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPersistFile {
  int GetClassID(out Guid pClassID);
  int IsDirty();
  int Load([MarshalAs(UnmanagedType.LPWStr)] string f, uint mode);
  int Save([MarshalAs(UnmanagedType.LPWStr)] string f, [MarshalAs(UnmanagedType.Bool)] bool remember);
  int SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string f);
  int GetCurFile([MarshalAs(UnmanagedType.LPWStr)] out string f);
}

[ComImport, Guid("000214F9-0000-0000-C000-000000000046"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IShellLinkW {
  int GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder f, int c, IntPtr fd, uint flags);
  int GetIDList(out IntPtr ppidl);
  int SetIDList(IntPtr pidl);
  int GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder n, int c);
  int SetDescription([MarshalAs(UnmanagedType.LPWStr)] string n);
  int GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder d, int c);
  int SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string d);
  int GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder a, int c);
  int SetArguments([MarshalAs(UnmanagedType.LPWStr)] string a);
  int GetHotkey(out ushort h); int SetHotkey(ushort h);
  int GetShowCmd(out int c); int SetShowCmd(int c);
  int GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] System.Text.StringBuilder i, int c, out int idx);
  int SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string i, int idx);
  int SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string r, uint res);
  int Resolve(IntPtr hwnd, uint flags);
  int SetPath([MarshalAs(UnmanagedType.LPWStr)] string f);
}

[ComImport, Guid("00021401-0000-0000-C000-000000000046")]
public class ShellLink { }

public static class CdxShortcut {
  static readonly Guid AppUserModel = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3");
  const ushort VT_LPWSTR = 31;
  [DllImport("ole32.dll")] static extern int PropVariantClear(ref PropVariant pv);

  public static void Write(string lnk, string target, string aumid) {
    var link = (IShellLinkW)new ShellLink();
    link.SetPath(target);
    link.SetDescription("CDX quota tray");
    var key = new PropertyKey(AppUserModel, 5);
    var pv = new PropVariant();
    pv.vt = VT_LPWSTR;
    pv.p = Marshal.StringToCoTaskMemUni(aumid);
    var store = (IPropertyStore)link;
    Marshal.ThrowExceptionForHR(store.SetValue(ref key, ref pv));
    // Commit before Save: the property store is written into the shortcut, and
    // saving first would persist it without the identifier.
    Marshal.ThrowExceptionForHR(store.Commit());
    PropVariantClear(ref pv);
    Marshal.ThrowExceptionForHR(((IPersistFile)link).Save(lnk, true));
  }

  public static string Read(string lnk) {
    var link = (IShellLinkW)new ShellLink();
    Marshal.ThrowExceptionForHR(((IPersistFile)link).Load(lnk, 0));
    var key = new PropertyKey(AppUserModel, 5);
    PropVariant pv;
    Marshal.ThrowExceptionForHR(((IPropertyStore)link).GetValue(ref key, out pv));
    string value = pv.vt == VT_LPWSTR ? Marshal.PtrToStringUni(pv.p) : "";
    PropVariantClear(ref pv);
    return value;
  }
}
"@
[CdxShortcut]::Write($Lnk, $Target, $Aumid)
Write-Output ([CdxShortcut]::Read($Lnk))
"""


def shortcut_path(env=None):
    """Where Windows looks, or None when the Start Menu cannot be resolved."""
    env = os.environ if env is None else env
    appdata = (env.get("APPDATA") or "").strip()
    if not appdata:
        return None
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", SHORTCUT_NAME)


def create(executable, env=None, system=None, run=None):
    """Write the shortcut, and report what happened without ever raising.

    Returns {"created": bool, "path": str|None, "reason": str|None}. A failure
    here must not fail an install that otherwise worked: the companion runs
    either way, only its notifications would not appear, and doctor reports that
    rather than leaving the user to discover silence.
    """
    system = platform.system() if system is None else system
    if system != "Windows":
        return {"created": False, "path": None, "reason": "not required on this platform"}

    path = shortcut_path(env)
    if not path:
        return {"created": False, "path": None, "reason": "APPDATA is unset"}

    runner = run or _run_powershell
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        readback = runner(path, executable, APP_USER_MODEL_ID)
    except Exception as error:  # noqa: BLE001 - never fail an install over this
        return {"created": False, "path": path, "reason": str(error)}

    # Trust the shortcut only if it names the identifier back. A file that
    # exists without one is a shortcut Windows will not route a toast through,
    # and reporting it as created would be the silent failure this exists to end.
    if (readback or "").strip() != APP_USER_MODEL_ID:
        return {
            "created": False,
            "path": path,
            "reason": f"the shortcut was written without its AppUserModelID (read back {readback!r})",
        }
    return {"created": True, "path": path, "reason": None}


def _run_powershell(path, executable, aumid):
    """Run the script from a temporary file, because `param()` needs `-File`.

    Passing the same text to `-Command` runs it, but the arguments after it are
    never bound to the parameters, so the shortcut would be written to an empty
    path — a failure that looks like success from the outside.
    """
    with tempfile.TemporaryDirectory(prefix="cdx-tray-lnk-") as scratch:
        script = os.path.join(scratch, "shortcut.ps1")
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(_PS_SCRIPT)
        completed = subprocess.run(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script,
                "-Lnk", path, "-Target", executable, "-Aumid", aumid,
            ],
            capture_output=True, text=True, timeout=CREATE_TIMEOUT_SECONDS, check=False,
        )
    if completed.returncode != 0:
        raise OSError((completed.stderr or "powershell failed").strip()[:200])
    return completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
