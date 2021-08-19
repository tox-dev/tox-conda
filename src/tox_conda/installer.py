from typing import Any, List, Sequence

from tox.config.cli.parser import DEFAULT_VERBOSITY
from tox.config.types import Command
from tox.execute.request import StdinSource
from tox.tox_env.errors import Recreate
from tox.tox_env.installer import Installer
from tox.tox_env.python.api import Python
from tox.tox_env.python.pip.pip_install import Pip

from .util import conda_exe


class CondaDep:
    """
    We should normalize and validate the spec per:

    https://docs.conda.io/projects/conda-build/en/latest/resources/package-spec.html

    But for now just pass it through.
    """

    def __init__(self, spec: str) -> None:
        self.spec: str = spec

    def __repr__(self) -> str:
        return self.spec

    def __lt__(self, other: "CondaDep") -> bool:
        return self.spec < other.spec


class CondaInstaller(Installer[Python]):
    def __init__(self, tox_env: Python) -> None:
        self._pip = Pip(tox_env, with_list_deps=False)  # we'll use conda for this
        super().__init__(tox_env)

    def _register_config(self) -> None:
        self._env.conf.add_config(
            keys=["list_dependencies_command"],
            of_type=Command,
            default=Command([str(conda_exe()), "list", "-e"]),
            desc="install the latest available pre-release (alpha/beta/rc) of dependencies without a specified version",
        )
        self._env.conf.add_config(
            keys=["conda_install_args"],
            of_type=List[str],
            default=[],
            desc="arguments to pass to conda install",
        )

    def installed(self) -> List[str]:
        cmd: Command = self._env.conf["list_dependencies_command"]
        result = self._env.execute(
            cmd=cmd.args + ["--prefix", str(self._env.env_dir)],
            stdin=StdinSource.OFF,
            run_id="freeze",
            show=self._env.options.verbosity > DEFAULT_VERBOSITY,
        )
        result.assert_success()
        return [i for i in result.out.splitlines() if not i.startswith("#")]

    def install(self, arguments: Any, section: str, of_type: str) -> None:
        if isinstance(arguments, Sequence):
            conda_deps: List[CondaDep] = []
            other_deps: List[Any] = []
            for dep in arguments:
                if isinstance(dep, CondaDep):
                    conda_deps.append(dep)
                else:
                    other_deps.append(dep)
            if conda_deps:
                self.conda_install(conda_deps, section, of_type)
            if other_deps:
                self._pip.install(other_deps, section, of_type)
        else:
            self._pip.install(arguments, section, of_type)

    def conda_install(self, conda_deps: List[CondaDep], section: str, of_type: str) -> None:
        info = {
            "install_args": self._env.conf["conda_install_args"],
            "deps": sorted(i.spec for i in conda_deps),
            "channels": self._env.conf["conda_channels"],
        }
        with self._env.cache.compare(info, section, of_type) as (eq, old):
            if not eq:
                old_info = old or {"install_args": None, "deps": [], "channels": None}
                old_deps = set(old_info["deps"])
                miss = sorted(old_deps - set(info["deps"]))
                if miss:  # no way yet to know what to uninstall here (transitive dependencies?)
                    raise Recreate(f"dependencies removed: {', '.join(str(i) for i in miss)}")

                if old_info["install_args"] is not None and info["install_args"] != old_info["install_args"]:
                    msg = f"install arguments changed from {old_info['install_args']} to {info['install_args']}"
                    raise Recreate(msg)

                if old_info["channels"] is not None and info["channels"] != old_info["channels"]:
                    raise Recreate(f"channels changed from {old_info['channels']} to {info['channels']}")

                new_deps = [i for i in info["deps"] if i not in old_deps]
                self._execute_installer(info["install_args"], info["channels"], new_deps, "conda_deps")

    def _execute_installer(self, extra_args: Sequence[str], channels: List[str], deps: List[str], of_type: str) -> None:
        cmd = ["conda", "install", "--prefix", str(self._env.env_dir)]
        cmd.extend(extra_args)
        for channel in channels:
            cmd.extend(("-c", channel))
        cmd.extend(deps)
        outcome = self._env.execute(cmd, stdin=StdinSource.OFF, run_id=f"install_{of_type}")
        outcome.assert_success()


__all__ = [
    "CondaInstaller",
    "CondaDep",
]
