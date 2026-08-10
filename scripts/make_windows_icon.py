#!/usr/bin/env python3
"""Build the Windows application icon from the macOS one.

Windows takes the icon for a toast, a Start Menu entry, and a taskbar button
from the shortcut, and a shortcut with no icon gets a generic one — which is
what a user sees as "some sort of computer screen" instead of CDX. That is the
gap this closes.

The two platforms want the same artwork in different containers, so the `.ico`
is generated from `CDX.icns` rather than drawn again: two hand-made files would
drift, and the one that drifted would be the one nobody looks at on their own
machine.

PNG payloads are embedded directly, which every Windows since Vista reads. The
alternative is a BMP with a separate AND mask, which is larger and only matters
for XP.
"""
import argparse
import os
import struct
import subprocess
import sys
import tempfile

# What Windows actually asks for: 16 in the notification area and menus, 32 in
# the taskbar, 48 in Explorer, 256 in the large-icon views. The rest is padding
# nobody reads.
SIZES = (16, 32, 48, 64, 128, 256)


def png_size(data):
    """Width and height out of the PNG header, to verify what we were handed."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def build_ico(images):
    """One ICO out of PNG payloads, smallest first.

    Windows picks by size rather than by order, but ordering makes the file
    readable to a human diffing it later.
    """
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)
    directory = b""
    payload = b""
    offset = 6 + 16 * count
    for size, data in images:
        # 256 is stored as 0: the field is one byte, and 256 does not fit.
        stored = 0 if size >= 256 else size
        directory += struct.pack(
            "<BBBBHHII", stored, stored, 0, 0, 1, 32, len(data), offset + len(payload)
        )
        payload += data
    return header + directory + payload


def render(source, size, scratch):
    """One square PNG at this size, via sips, which ships with macOS."""
    out = os.path.join(scratch, f"{size}.png")
    subprocess.run(
        ["sips", "-z", str(size), str(size), source, "--out", out],
        check=True, capture_output=True,
    )
    with open(out, "rb") as handle:
        data = handle.read()
    if png_size(data) != (size, size):
        raise ValueError(f"sips produced {png_size(data)} for a {size} request")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icns", default="tray/assets/icons/CDX.icns")
    parser.add_argument("--out", default="tray/assets/icons/CDX.ico")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="cdx-ico-") as scratch:
        iconset = os.path.join(scratch, "CDX.iconset")
        subprocess.run(
            ["iconutil", "--convert", "iconset", args.icns, "-o", iconset],
            check=True, capture_output=True,
        )
        # The largest available source for every size: downscaling keeps the
        # artwork, upscaling invents it.
        source = os.path.join(iconset, "icon_512x512.png")
        if not os.path.isfile(source):
            source = os.path.join(iconset, "icon_256x256@2x.png")
        images = [(size, render(source, size, scratch)) for size in SIZES]

    with open(args.out, "wb") as handle:
        handle.write(build_ico(images))
    print(f"wrote {args.out} with sizes {', '.join(str(s) for s in SIZES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
