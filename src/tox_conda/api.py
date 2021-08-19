import json
import logging
import re
import sys
from abc import ABC
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from tox.execute.api import Execute
from tox.execute.local_sub_process import LocalSubProcessExecutor
from tox.execute.request import StdinSource
from tox.tox_env.api import ToxEnvCreateArgs
from tox.tox_env.errors import Fail
from tox.tox_env.python.api import Python, PythonInfo, VersionInfo
from virtualenv.discovery.py_spec import PythonSpec

from .cache import Cache
from .installer import CondaInstaller
from .util import conda_exe


class Conda(Python, ABC):
    """A python executor that uses the virtualenv project with pip"""

    def __init__(self, create_args: ToxEnvCreateArgs) -> None:
        self._executor: Optional[Execute] = None
        self._installer: Optional[CondaInstaller] = None
        self._conda_env_created = False
        self._app_cache = Cache()
        super().__init__(create_args)

    def register_config(self) -> None:
        super().register_config()
        self.conf.add_config(
            keys=["conda_create_args"],
            of_type=List[str],
            default=[],
            desc="additional arguments passed to conda on environment creation",
        )
        self.conf.add_config(
            keys=["conda_channels"],
            of_type=List[str],
            default=["default"],
            desc="channels to use for resolving conda dependencies",
        )
        # TODO: conda_spec, conda_env

    @property
    def executor(self) -> Execute:
        if self._executor is None:  # runs on the local sub-process
            self._executor = LocalSubProcessExecutor(self.options.is_colored)
        return self._executor

    @property
    def runs_on_platform(self) -> str:
        return sys.platform  # same as host

    @property
    def _allow_externals(self) -> List[str]:
        base = super(Conda, self)._allow_externals
        base.append(str(conda_exe()))
        return base

    @property
    def installer(self) -> CondaInstaller:
        if self._installer is None:
            self._installer = CondaInstaller(self)
        return self._installer

    def _default_pass_env(self) -> List[str]:
        env = super()._default_pass_env()
        env.append("CONDA_*")
        env.append("PIP_*")
        return env

    @property
    def conda_info(self) -> Dict[str, Any]:
        cached_value: Optional[Dict[str, Any]] = self._app_cache.get_ttl_value("conda", "info")
        if cached_value is None:
            cmd = ["conda", "info", "--json"]
            result = self.execute(cmd, stdin=StdinSource.OFF, show=False, run_id="conda-info")
            cached_value = json.loads(result.out)
            self._app_cache.set_ttl_value(cached_value, timedelta(days=1), "info")
        return cached_value

    def _get_python(self, base_python: List[str]) -> Optional[PythonInfo]:  # noqa: U100
        for base in base_python:
            if base == sys.executable:  # default to local version
                return self._get_default_python_info()
            else:
                spec = PythonSpec.from_string_spec(base)
                if spec.implementation == "CPython":
                    result = self.get_c_python_info(spec)
                    if result is not None:
                        return result
                elif spec.implementation == "PyPy":
                    raise NotImplementedError
        return None

    def _get_default_python_info(self) -> PythonInfo:
        py_ver = self.conda_info["python_version"]
        ver = VersionInfo(*(i if at == 3 else int(i) for at, i in enumerate(py_ver.split("."))))
        return PythonInfo(
            implementation="CPython",
            version_info=ver,
            version=".".join(str(i) for i in ver[0:3]),
            is_64=True,
            platform=sys.platform,
            extra={},
        )

    def get_c_python_info(self, spec: PythonSpec) -> Optional[PythonInfo]:
        py_ver = r"\.".join(r"(\d+)" if v is None else f"({v})" for v in (spec.major, spec.minor, spec.micro))
        version_regex = re.compile(f"{py_ver}(.*)")
        for available in self.available_cpython():
            matched = version_regex.match(available)
            if matched is None:
                continue
            groups = matched.groups()
            ending = groups[3]
            if ending == "":
                level: str = "final"
                serial: int = 0
            else:
                if ending[0] == "a":
                    level = "alpha"
                    serial = int(ending[1:])
                elif ending[0] == "b":
                    level = "beta"
                    serial = int(ending[1:])
                elif ending[0:2] == "rc":
                    level = "releasecandidate"
                    serial = int(ending[2:])
                else:
                    logging.warning("corrupt version %s ignored", available)
                    continue
            return PythonInfo(
                implementation="CPython",
                version_info=VersionInfo(int(groups[0]), int(groups[1]), int(groups[2]), level, serial),
                version=available,
                is_64=True,
                platform=sys.platform,
                extra={},
            )
        return None

    def available_cpython(self) -> List[str]:
        cached_value: Optional[List[str]] = self._app_cache.get_ttl_value("python", "versions")
        if cached_value is None:
            # handle architecture via passing --subdir linux-32 linux-64 etc ?
            cmd = ["conda", "search", "python", "-f", "--json"]
            result = self.execute(cmd, stdin=StdinSource.OFF, show=False, run_id="python-versions")
            response = json.loads(result.out)
            cached_value = sorted({r["version"] for r in response["python"]}, reverse=True)
            self._app_cache.set_ttl_value(cached_value, timedelta(days=1), "python", "versions")
        return cached_value

    def create_python_env(self) -> None:
        # TODO: conda create -y --prefix pypy36 pypy3.6 && conda create -y --prefix pypy37 pypy3.7
        if self._conda_env_created:
            return
        if self.base_python.implementation not in ("CPython", "PyPy"):
            raise Fail(f"cannot create {self.base_python.implementation}")
        if self.base_python.implementation == "PyPy":
            raise NotImplementedError  # conda create -y --prefix pypy36 pypy3.6
        cmd = ["conda", "create", "-y", "--prefix", str(self.env_dir), f"python={self.base_python.version}"]
        cmd.extend(self.conf["conda_create_args"])
        for channel in self.conf["conda_channels"]:
            cmd.extend(("-c", channel))
        result = self.execute(cmd, stdin=StdinSource.OFF, show=True, run_id="create")
        result.assert_success()
        self._conda_env_created = True

    def python_cache(self) -> Dict[str, Any]:
        sub = super().python_cache()
        sub.update(
            {
                "conda_create_args": self.conf["conda_create_args"],
                "conda_channels": self.conf["conda_channels"],
            }
        )
        return sub

    def prepend_env_var_path(self) -> List[Path]:
        """Paths to add to the executable"""
        return [self.env_bin_dir()]

    def env_site_package_dir(self) -> Path:
        return Path(self.get_sysconfig(schema="purelib"))

    def env_python(self) -> Path:
        return self.env_bin_dir() / f"python{'.exe' if sys.platform == 'win32' else ''}"

    def env_bin_dir(self) -> Path:
        return Path(self.get_sysconfig(schema="scripts"))

    @property
    def sysconfig_info(self) -> Dict[str, Dict[str, str]]:
        key = f"schema-{self.base_python.implementation}-{self.base_python.version}"
        cached_value = cast(Dict[str, Dict[str, str]], self._app_cache.get_ttl_value("python", key))
        if cached_value is None:
            self.ensure_python_env()  # ensure the python environment exists
            sub_cmd = (
                "import sysconfig; import json;"
                "print(json.dumps({'vars': sysconfig.get_config_vars(), 'schema': sysconfig.get_paths(expand=False)}))"
            )
            prefix = str(self.env_dir)
            cmd = ["conda", "run", "--prefix", prefix, "python", "-c", sub_cmd]
            result = self.execute(cmd, stdin=StdinSource.OFF, show=False, run_id=key)
            result.assert_success()
            cached_value = json.loads(result.out)
            cached_value["vars"] = {
                k: v.replace(prefix, "{prefix}") if isinstance(v, str) else v for k, v in cached_value["vars"].items()
            }
            self._app_cache.set_ttl_value(cached_value, timedelta(days=1), "python", key)
        return cached_value

    def get_sysconfig(self, schema: str) -> str:
        sys_info, prefix = self.sysconfig_info, str(self.env_dir)
        variables = {k: v.replace("{prefix}", prefix) if isinstance(v, str) else v for k, v in sys_info["vars"].items()}
        template = sys_info["schema"][schema]
        result = template.format(**variables)
        return result


__all__ = [
    "Conda",
]
