import os
import shutil
from fnmatch import fnmatch

import pytest
import tox
from tox.tox_env.errors import Fail

import tox_conda.plugin


def assert_conda_context(proj, env_name, shell_command, expected_command):
    assert fnmatch(
        shell_command,
        f"*conda run -p {str(proj.path / '.tox' / env_name)} --live-stream {expected_command}",
    )


def test_conda(cmd, initproj):
    # The path has a blank space on purpose for testing issue #119.
    initproj(
        "pkg 1",
        filedefs={
            "tox.ini": """
                [tox]
                skipsdist=True
                [testenv]
                commands = python -c 'import sys, os; \
                    print(os.path.exists(os.path.join(sys.prefix, "conda-meta")))'
            """
        },
    )
    result = cmd("-v", "-e", "py")
    result.assert_success()

    def index_of(m):
        return next((i for i, l in enumerate(result.outlines) if l.startswith(m)), None)

    assert any(
        "create --yes -p " in line
        for line in result.outlines[index_of("py create: ") + 1 : index_of("py installed: ")]
    ), result.output()

    assert result.outlines[-4] == "True"


def test_conda_run_command(tox_project, mock_conda_env_runner):
    """Check that all the commands are run from an activated anaconda env."""
    ini = """
    [testenv:py123]
    skip_install = True
    commands_pre = python --version
    commands = pytest
    commands_post = black
    """
    proj = tox_project({"tox.ini": ini})
    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner

    assert len(executed_shell_commands) == 5
    assert_conda_context(proj, "py123", executed_shell_commands[2], "python --version")
    assert_conda_context(proj, "py123", executed_shell_commands[3], "pytest")
    assert_conda_context(proj, "py123", executed_shell_commands[4], "black")


def test_missing_conda(tox_project, mock_conda_env_runner, monkeypatch):
    """Check that an error is shown when the conda executable is not found."""
    ini = """
    [tox]
    require = tox-conda
    [testenv:py123]
    skip_install = True
    """
    # Prevent conda from being found.
    original_which = shutil.which

    def which(cmd, mode=os.F_OK | os.X_OK, path=None):
        if cmd.endswith("conda"):
            return None
        return original_which(cmd, mode, path)

    monkeypatch.setattr(shutil, "which", which)
    monkeypatch.delenv("_CONDA_EXE", raising=False)
    monkeypatch.delenv("CONDA_EXE", raising=False)

    with pytest.raises(Fail) as exc_info:
        tox_project({"tox.ini": ini}).run("-e", "py123")

    assert str(exc_info.value) == "Failed to find 'conda' executable."
