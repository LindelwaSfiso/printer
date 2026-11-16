"""Local dev shim for this Windows machine (not part of the app).

Python 3.14 on Windows applies the requested mode to the new directory's
discretionary access control list. `tempfile.mkdtemp()` creates its scratch
directory with mode 0o700, which drops the inherited write entry that this
machine's restricted (sandboxed) process token relies on. The result is
`PermissionError: [Errno 13]` on the first file written inside any temporary
directory -- which breaks `pip`, `ensurepip`, and anything else that shells out
to them.

This shim forces directories to be created with 0o777, restoring inheritance.
It is copied into `.venv\\Lib\\site-packages\\sitecustomize.py` by
`tools\\bootstrap_dev.ps1`; Python imports `sitecustomize` automatically at
startup when it is importable.

It has no effect on Linux and is not needed there.
"""

import os
import tempfile

_real_mkdir = os.mkdir


def _mkdir_ignoring_mode(path, mode=0o777, *args, **kwargs):
    return _real_mkdir(path, 0o777, *args, **kwargs)


# tempfile._os is the os module itself, so this reaches mkdtemp's internals.
tempfile._os.mkdir = _mkdir_ignoring_mode
