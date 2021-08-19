from typing import Any

from tox.config.cli.parser import DEFAULT_VERBOSITY
from tox.config.types import Command
from tox.execute.request import StdinSource
from tox.tox_env.installer import Installer


class CondaInstaller(Installer):
    def _register_config(self) -> None:
        pass

    def installed(self) -> Any:
        cmd: Command = self._env.conf["list_dependencies_command"]
        result = self._env.execute(
            cmd=cmd.args,
            stdin=StdinSource.OFF,
            run_id="freeze",
            show=self._env.options.verbosity > DEFAULT_VERBOSITY,
        )
        result.assert_success()
        return result.out.splitlines()

    def install(self, arguments: Any, section: str, of_type: str) -> None:
        pass


__all__ = [
    "CondaInstaller",
]
