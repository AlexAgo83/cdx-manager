import os
import shutil
import stat


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
    def onerror(func, failing_path, _exc_info):
        parent = os.path.dirname(failing_path)
        if parent:
            _make_user_writable(parent)
        _make_user_writable(failing_path)
        try:
            func(failing_path)
        except OSError:
            if not ignore_errors:
                raise

    _make_tree_user_writable(path)
    shutil.rmtree(path, ignore_errors=ignore_errors, onerror=onerror)
