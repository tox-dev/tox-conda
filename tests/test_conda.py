from fnmatch import fnmatch

import pytest
from tox.tox_env.errors import Fail


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


def test_missing_conda(tox_project, mocker):
    """Check that an error is shown when the conda executable is not found."""
    ini = """
    [testenv:py123]
    skip_install = True
    runner = conda
    """
    mocker.patch("tox_conda.conda.find_conda", side_effect=Fail("not found"))
    outcome = tox_project({"tox.ini": ini}).run("-e", "py123")
    outcome.assert_failed()


# This test must run first to avoid collisions with other tests.
@pytest.mark.order(1)
def test_missing_conda_fallback(tox_project, mock_conda_env_runner, mocker, monkeypatch):
    ini = """
    [testenv:py123]
    skip_install = True
    """
    mocker.patch("tox_conda.conda.find_conda", side_effect=Fail("not found"))
    monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)

    outcome = tox_project({"tox.ini": ini}).run("-e", "py123")

    outcome.assert_success()
    executed_shell_commands = mock_conda_env_runner
    # No conda commands should be run because virtualenv is used as a fallback.
    assert len(executed_shell_commands) == 0


def test_conda_runner_overload(tox_project, mock_conda_env_runner):
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
