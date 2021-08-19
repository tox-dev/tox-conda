"""
A tox python environment runner that uses the virtualenv project.
"""
from typing import List

from tox.plugin import impl
from tox.tox_env.python.runner import PythonRun
from tox.tox_env.register import ToxEnvRegister

from .api import Conda
from .installer import CondaDep


class CondaEnvRunner(Conda, PythonRun):
    """local file system conda virtual environment"""

    @staticmethod
    def id() -> str:
        return "conda"

    @property
    def _default_package_tox_env_type(self) -> str:
        return "virtualenv-pep-517"  # TODO: use conda environment for this

    def register_config(self) -> None:
        super().register_config()
        self.conf.add_config(
            keys=["conda_deps"],
            of_type=List[CondaDep],
            default=[],
            desc="dependencies to install with conda",
        )

    def _install_deps(self) -> None:
        self.installer.install(self.conf["conda_deps"], CondaEnvRunner.__name__, "conda_deps")
        super()._install_deps()


@impl
def tox_register_tox_env(register: ToxEnvRegister) -> None:
    register.add_run_env(CondaEnvRunner)


__all__ = [
    "CondaEnvRunner",
]
