import inspect
import os
import shutil
import stat
import tempfile


def atomic_write(path, data, mode=None):
    """Write str/bytes via temp file + rename so a crash can't leave a torn file.

    mkstemp creates the temp file 0o600, so the content is never readable by
    other users mid-write; pass mode to set the final permissions before the
    rename makes the file visible.
    """
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    binary = isinstance(data, (bytes, bytearray))
    fd, temp_path = tempfile.mkstemp(prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=directory)
    try:
        if binary:
            handle = os.fdopen(fd, "wb")
        else:
            handle = os.fdopen(fd, "w", encoding="utf-8")
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None and os.name != "nt":
            os.chmod(temp_path, mode)
        os.replace(temp_path, path)
        if os.name != "nt":
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except Exception:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise


def _make_user_writable(path):
    if os.path.islink(path):
        return
    try:
        current = os.stat(path).st_mode
    except OSError:
        return
    mode = current | stat.S_IRUSR | stat.S_IWUSR
    if stat.S_ISDIR(current):
        mode |= stat.S_IXUSR
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _make_tree_user_writable(path):
    if not os.path.exists(path):
        return
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)
            if not os.path.islink(file_path):
                _make_user_writable(file_path)
        for name in dirs:
            dir_path = os.path.join(root, name)
            if not os.path.islink(dir_path):
                _make_user_writable(dir_path)
        _make_user_writable(root)


def remove_tree(path, ignore_errors=False):
    def retry_after_chmod(func, failing_path):
        parent = os.path.dirname(failing_path)
        if parent:
            _make_user_writable(parent)
        _make_user_writable(failing_path)
        try:
            func(failing_path)
        except OSError:
            if not ignore_errors:
                raise

    def onerror(func, failing_path, _exc_info):
        retry_after_chmod(func, failing_path)

    def onexc(func, failing_path, _exc):
        retry_after_chmod(func, failing_path)

    _make_tree_user_writable(path)
    if "onexc" in inspect.signature(shutil.rmtree).parameters:
        shutil.rmtree(path, ignore_errors=ignore_errors, onexc=onexc)
    else:
        shutil.rmtree(path, ignore_errors=ignore_errors, onerror=onerror)
