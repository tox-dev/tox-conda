import os
from functools import lru_cache
from pathlib import Path
from shutil import which

from tox.tox_env.errors import Fail


@lru_cache(maxsize=1)
def conda_exe() -> Path:
    path = which("conda")
    if path is None:
        raise Fail(f"no conda executable could be found in PATH {os.environ['PATH']}")
    return Path(path)


__all__ = [
    "conda_exe",
]
