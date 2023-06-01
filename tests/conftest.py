import io
import os
import pathlib
import re
import subprocess
from pathlib import Path
from types import ModuleType, TracebackType
from typing import Any, Callable, Dict, Optional, Sequence, Union
from unittest.mock import mock_open, patch

import pytest
import tox
import tox.run
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from ruamel.yaml import YAML
from tox.config.sets import EnvConfigSet
from tox.execute.api import Execute, ExecuteInstance, ExecuteOptions, ExecuteStatus, Outcome
from tox.execute.request import ExecuteRequest, shell_cmd
from tox.execute.stream import SyncWrite
from tox.plugin import manager
from tox.pytest import CaptureFixture, ToxProject, ToxProjectCreator
from tox.report import LOGGER, OutErr
from tox.run import run as tox_run
from tox.run import setup_state as previous_setup_state
from tox.session.cmd.run.parallel import ENV_VAR_KEY
from tox.session.state import State
from tox.tox_env import api as tox_env_api
from tox.tox_env.api import ToxEnv

from tox_conda.plugin import CondaEnvRunner

# from tox_conda.plugin import tox_testenv_create, tox_testenv_install_deps

# pytest_plugins = "tox.pytest"


@pytest.fixture(name="tox_project")
def init_fixture(
    tmp_path: Path,
    capfd: CaptureFixture,
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
) -> ToxProjectCreator:
    def _init(
        files: Dict[str, Any], base: Optional[Path] = None, prj_path: Optional[Path] = None
    ) -> ToxProject:
        """create tox  projects"""
        return ToxProject(files, base, prj_path or tmp_path / "p", capfd, monkeypatch, mocker)

    return _init

@pytest.fixture
def mock_conda_env_runner(request, monkeypatch):
    class MockExecuteStatus(ExecuteStatus):
        def __init__(
            self, options: ExecuteOptions, out: SyncWrite, err: SyncWrite, exit_code: int
        ) -> None:
            super().__init__(options, out, err)
            self._exit_code = exit_code

        @property
        def exit_code(self) -> Optional[int]:
            return self._exit_code

        def wait(self, timeout: Optional[float] = None) -> Optional[int]:  # noqa: U100
            return self._exit_code

        def write_stdin(self, content: str) -> None:  # noqa: U100
            return None  # pragma: no cover

        def interrupt(self) -> None:
            return None  # pragma: no cover

    class MockExecuteInstance(ExecuteInstance):
        def __init__(
            self,
            request: ExecuteRequest,
            options: ExecuteOptions,
            out: SyncWrite,
            err: SyncWrite,
            exit_code: int,
        ) -> None:
            super().__init__(request, options, out, err)
            self.exit_code = exit_code

        def __enter__(self) -> ExecuteStatus:
            return MockExecuteStatus(self.options, self._out, self._err, self.exit_code)

        def __exit__(
            self,
            exc_type: Optional[BaseException],  # noqa: U100
            exc_val: Optional[BaseException],  # noqa: U100
            exc_tb: Optional[TracebackType],  # noqa: U100
        ) -> None:
            pass

        @property
        def cmd(self) -> Sequence[str]:
            return self.request.cmd

    shell_cmds = []
    no_mocked_run_ids = getattr(request, 'param', None)
    if no_mocked_run_ids is None:
        no_mocked_run_ids = ["_get_python"]
    original_execute_instance_factor = CondaEnvRunner._execute_instance_factory

    def mock_execute_instance_factory(
        request: ExecuteRequest, options: ExecuteOptions, out: SyncWrite, err: SyncWrite
    ):
        shell_cmds.append(request.cmd)

        if request.run_id not in no_mocked_run_ids:
            return MockExecuteInstance(request, options, out, err, 0)
        else:
            return original_execute_instance_factor(request, options, out, err)

    monkeypatch.setattr(CondaEnvRunner, "_execute_instance_factory", mock_execute_instance_factory)

    yield shell_cmds

