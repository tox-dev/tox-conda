import os
from functools import partial
from typing import TYPE_CHECKING, List

from tox.plugin import impl
from tox.tox_env.errors import Fail
from tox.tox_env.python.pip.req_file import PythonDeps

from .conda import CondaEnvRunner, find_conda

if TYPE_CHECKING:
    from tox.config.sets import EnvConfigSet
    from tox.session.state import State
    from tox.tox_env.register import ToxEnvRegister

__all__ = []


@impl
def tox_register_tox_env(register: "ToxEnvRegister") -> None:  # noqa: U100
    register.add_run_env(CondaEnvRunner)
    try:
        # Change the default runner only if conda is available
        find_conda()
        if "CONDA_DEFAULT_ENV" in os.environ:
            register.default_env_runner = "conda"
    except Fail:
        pass


@impl
def tox_add_env_config(env_conf: "EnvConfigSet", state: "State") -> None:
    env_conf.add_config(
        "conda_name",
        of_type=str,
        desc="Specifies the name of the conda environment. By default, .tox/<name> is used.",
        default=None,
    )

    env_conf.add_config(
        "conda_python",
        of_type=str,
        desc="Specifies the name of the Python interpreter (python or pypy) and its version "
        "in the conda environment. By default, it uses the 'python' interpreter and the "
        "currently active version.",
        default=None,
    )

    env_conf.add_config(
        "conda_env",
        of_type=str,
        desc="specify a conda environment.yml file",
        default=None,
    )

    env_conf.add_config(
        "conda_spec",
        of_type=str,
        desc="specify a conda spec-file.txt file",
        default=None,
    )

    root = env_conf._conf.core["tox_root"]
    env_conf.add_config(
        "conda_deps",
        of_type=PythonDeps,
        factory=partial(PythonDeps.factory, root),
        default=PythonDeps("", root),
        desc="each line specifies a conda dependency in pip/setuptools format",
    )

    env_conf.add_config(
        "conda_channels",
        of_type=List[str],
        desc="each line specifies a conda channel",
        default=None,
    )

    env_conf.add_config(
        "conda_install_args",
        of_type=List[str],
        desc="each line specifies a conda install argument",
        default=None,
    )

    env_conf.add_config(
        "conda_create_args",
        of_type=List[str],
        desc="each line specifies a conda create argument",
        default=None,
    )
