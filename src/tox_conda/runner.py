"""
A tox python environment runner that uses the virtualenv project.
"""
from tox.plugin import impl
from tox.tox_env.python.runner import PythonRun
from tox.tox_env.register import ToxEnvRegister

from .api import Conda


class CondaEnvRunner(Conda, PythonRun):
    """local file system conda virtual environment"""

    @staticmethod
    def id() -> str:
        return "conda"

    @property
    def _default_package_tox_env_type(self) -> str:
        return "virtualenv-pep-517"  # TODO: use conda environment for this


@impl
def tox_register_tox_env(register: ToxEnvRegister) -> None:
    register.add_run_env(CondaEnvRunner)
