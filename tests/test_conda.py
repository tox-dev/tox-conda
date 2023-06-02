import os
import shutil
from fnmatch import fnmatch

import pytest


def assert_conda_context(proj, env_name, shell_command, expected_command):
    assert fnmatch(
        shell_command,
        f"*conda run -p {str(proj.path / '.tox' / env_name)} --live-stream {expected_command}",
    )


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


def test_missing_conda(tox_project, monkeypatch):
    """Check that an error is shown when the conda executable is not found."""
    ini = """
    [testenv:py123]
    skip_install = True
    runner = conda
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

    outcome = tox_project({"tox.ini": ini}).run("-e", "py123")

    outcome.assert_failed()
    assert "Failed to find 'conda' executable." in outcome.out


# This test must run first to avoid collisions with other tests.
@pytest.mark.first
def test_missing_conda_fallback(tox_project, mock_conda_env_runner, monkeypatch):
    ini = """
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
    monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)

    outcome = tox_project({"tox.ini": ini}).run("-e", "py123")

    outcome.assert_success()
    executed_shell_commands = mock_conda_env_runner
    # No conda commands should be run because virtualenv is used as a fallback.
    assert len(executed_shell_commands) == 0


def test_conda_runner_overload(tox_project, mock_conda_env_runner, monkeypatch):
    ini = """
    [testenv:py123]
    skip_install = True
    runner = virtualenv
    """
    outcome = tox_project({"tox.ini": ini}).run("-e", "py123")

    outcome.assert_success()
    executed_shell_commands = mock_conda_env_runner
    # No conda commands should be run because virtualenv is used.
    assert len(executed_shell_commands) == 0
