import os
from pathlib import Path

import pytest
from pytest_mock import MockFixture
from tox.pytest import ToxProjectCreator


def test_no_conda(tox_project: ToxProjectCreator, mocker: MockFixture) -> None:
    from tox_conda.util import conda_exe

    conda_exe.cache_clear()
    mocker.patch("tox_conda.util.which", return_value=None)
    project = tox_project({"tox.ini": ""})
    result = project.run("r", "-e", "py")

    result.assert_failed()
    assert not result.err
    error = f"py: failed with no conda executable could be found in PATH {os.environ['PATH']}"
    assert result.out.startswith(error)


@pytest.mark.integration()
def test_create(tox_project: ToxProjectCreator, demo_pkg_inline: Path) -> None:
    ini = """
    [testenv]
    runner = conda
    package = wheel
    commands = pip list
    deps =
        platformdirs

    conda_deps =
        platformdirs
    conda_channels=
        conda-forge
    conda_install_args=
        --override-channels
    conda_create_args=
        --override-channels
    """
    project = tox_project({"tox.ini": ini})
    result = project.run("r", "-e", "magic", "--root", str(demo_pkg_inline))
    result.assert_success()
    assert "demo-pkg-inline 1.0.0" in result.out
