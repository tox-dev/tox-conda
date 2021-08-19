import sys
from abc import ABC
from pathlib import Path
from typing import Any, Dict, List, Optional

from tox.config.cli.parser import Parsed
from tox.config.sets import CoreConfigSet, EnvConfigSet
from tox.execute.api import Execute
from tox.execute.local_sub_process import LocalSubProcessExecutor
from tox.journal import EnvJournal
from tox.report import ToxHandler
from tox.tox_env.python.api import Python, PythonInfo
from virtualenv.discovery.py_spec import PythonSpec

from .installer import CondaInstaller


class Conda(Python, ABC):
    """A python executor that uses the virtualenv project with pip"""

    def __init__(
        self, conf: EnvConfigSet, core: CoreConfigSet, options: Parsed, journal: EnvJournal, log_handler: ToxHandler
    ) -> None:
        self._executor: Optional[Execute] = None
        self._installer: Optional[CondaInstaller] = None
        self._conda_env_created = False
        super().__init__(conf, core, options, journal, log_handler)

    @property
    def executor(self) -> Execute:
        if self._executor is None:
            self._executor = LocalSubProcessExecutor(self.options.is_colored)
        return self._executor

    @property
    def installer(self) -> CondaInstaller:
        if self._installer is None:
            self._installer = CondaInstaller(self)
        return self._installer

    def python_cache(self) -> Dict[str, Any]:
        base = super().python_cache()
        # TODO: do we need to include conda version here?
        return base

    def _default_pass_env(self) -> List[str]:
        env = super()._default_pass_env()
        env.append("CONDA_*")
        env.append("PIP_*")
        return env

    def create_python_env(self) -> None:
        """
        conda create -y --path py35 python=3.5
        conda create -y --path pypy36 pypy3.6
        conda create -y --path pypy37 pypy3.7
        """
        self._conda_env_created = True
        for base in self.base_python:

        pass  # TODO: create conda env

    def _create_conda_env(self, spec):

        self._conda_env_created = True

    def _get_python(self, base_python: List[str]) -> Optional[PythonInfo]:  # noqa: U100
        """
        conda run --path py35 --version
        """
        for base in base_python:
            if base == sys.executable:
                from virtualenv.discovery.py_info import PythonInfo as VirtualEnvPythonInfo

                current = VirtualEnvPythonInfo.current()
                spec = PythonSpec(
                    None,
                    current.implementation,
                    current.version_info.major,
                    current.version_info.minor,
                    current.version_info.micro,
                    current.architecture,
                    None,
                )
            else:
                spec = PythonSpec.from_string_spec(base)
            self.create_python_env()
            assert spec

    def prepend_env_var_path(self) -> List[Path]:
        """Paths to add to the executable"""
        return []

    def env_site_package_dir(self) -> Path:
        return Path.cwd()

    def env_python(self) -> Path:
        return Path.cwd()

    def env_bin_dir(self) -> Path:
        return Path.cwd()

    @property
    def runs_on_platform(self) -> str:
        return sys.platform  # same as host


__all__ = [
    "Conda",
]
