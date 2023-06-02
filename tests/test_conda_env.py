"""Conda environment creation and installation tests."""

import pathlib
from fnmatch import fnmatch
from unittest.mock import patch

from ruamel.yaml import YAML


def test_conda_create(tox_project, mock_conda_env_runner):
    ini = """
    [testenv:py123]
    skip_install = True
    """
    proj = tox_project({"tox.ini": ini})

    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 2
    assert fnmatch(
        executed_shell_commands[1],
        f"*conda create -p {str(proj.path / '.tox' / 'py123')} python=* --yes --quiet*",
    )


def test_conda_create_with_package_install(tox_project, mock_conda_env_runner):
    ini = """
    [testenv:py123]
    """
    proj = tox_project({"tox.ini": ini})

    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 3
    conda_create_command = executed_shell_commands[1]
    pip_install_command = executed_shell_commands[2]

    assert fnmatch(
        conda_create_command,
        f"*conda create -p {str(proj.path / '.tox' / 'py123')} python=* --yes --quiet*",
    )
    assert fnmatch(
        pip_install_command,
        (
            f"*conda run -p {str(proj.path / '.tox' / 'py123')} --live-stream"
            " python -I -m pip install*"
        ),
    )


def test_conda_create_with_name(tox_project, mock_conda_env_runner):
    ini = """
    [testenv:py123]
    skip_install = True
    conda_name = myenv
    """
    proj = tox_project({"tox.ini": ini})

    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 2
    assert fnmatch(executed_shell_commands[1], "*conda create -n myenv python=* --yes --quiet*")


def test_install_deps_no_conda(tox_project, mock_conda_env_runner):
    env_name = "py123"
    ini = f"""
        [testenv:{env_name}]
        skip_install = True
        deps =
            numpy
            -r requirements.txt
            astropy
    """
    proj = tox_project({"tox.ini": ini})
    (proj.path / "requirements.txt").touch()

    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 3

    pip_install_command = executed_shell_commands[2]
    assert fnmatch(
        pip_install_command,
        (
            f"*conda run -p {str(proj.path / '.tox' / env_name)} --live-stream"
            " python -I -m pip install*"
        ),
    )
    assert "numpy" in pip_install_command
    assert "astropy" in pip_install_command
    assert "-r requirements.txt" in pip_install_command


def test_install_conda_no_pip(tox_project, mock_conda_env_runner):
    env_name = "py123"
    ini = f"""
        [testenv:{env_name}]
        skip_install = True
        conda_deps =
            pytest
            asdf
    """
    proj = tox_project({"tox.ini": ini})

    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 3

    conda_install_command = executed_shell_commands[2]
    assert fnmatch(
        conda_install_command,
        f"*conda install --quiet --yes -p {str(proj.path / '.tox' / env_name)}*",
    )
    assert "asdf" in conda_install_command
    assert "pytest" in conda_install_command
    # Make sure that python is explicitly given as part of every conda install
    # in order to avoid inadvertent upgrades of python itself.
    assert "python=" in conda_install_command


def test_install_conda_with_deps(tox_project, mock_conda_env_runner):
    env_name = "py123"
    ini = f"""
        [testenv:{env_name}]
        skip_install = True
        deps =
            numpy
            astropy
        conda_deps =
            pytest
            asdf
    """
    proj = tox_project({"tox.ini": ini})

    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 4

    cmd_conda = executed_shell_commands[2]
    pip_cmd = executed_shell_commands[3]

    assert "conda install --quiet --yes -p" in cmd_conda
    assert "python -I -m pip install" in pip_cmd


def test_conda_spec(tox_project, mock_conda_env_runner):
    env_name = "py123"
    ini = f"""
        [testenv:{env_name}]
        skip_install = True
        conda_deps =
            numpy
            astropy
        conda_spec = conda_spec.txt
    """
    proj = tox_project({"tox.ini": ini})
    (proj.path / "conda_spec.txt").touch()

    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 3

    conda_install_command = executed_shell_commands[2]
    assert fnmatch(
        conda_install_command,
        f"*conda install --quiet --yes -p {str(proj.path / '.tox' / env_name)}*",
    )
    assert "astropy" in conda_install_command
    assert "numpy" in conda_install_command
    assert "python=" in conda_install_command
    assert "--file=conda_spec.txt" in conda_install_command


def test_conda_env(tmp_path, tox_project, mock_conda_env_runner):
    env_name = "py123"
    ini = f"""
        [testenv:{env_name}]
        skip_install = True
        conda_env = conda-env.yml
    """
    yaml = """
         name: tox-conda
         channels:
           - conda-forge
           - nodefaults
         dependencies:
           - numpy
           - astropy
           - pip:
             - pytest
        """
    proj = tox_project({"tox.ini": ini})
    (proj.path / "conda-env.yml").write_text(yaml)

    mock_temp_file = tmp_path / "mock_temp_file.yml"

    def open_mock_temp_file(*args, **kwargs):
        return mock_temp_file.open("w")

    with patch("tox_conda.plugin.tempfile.NamedTemporaryFile", open_mock_temp_file):
        with patch.object(pathlib.Path, "unlink", autospec=True) as mock_unlink:
            outcome = proj.run("-e", "py123")
            outcome.assert_success()

            mock_unlink.assert_called_once

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 2
    assert fnmatch(
        executed_shell_commands[1],
        (
            f"*conda env create -p {str(proj.path / '.tox' / 'py123')}"
            f" --file {str(mock_temp_file)} --quiet --force"
        ),
    )

    # Check that the temporary file has the correct contents
    yaml = YAML()
    tmp_env = yaml.load(mock_temp_file)
    assert tmp_env["dependencies"][-1].startswith("python=")


def test_conda_env_and_spec(tox_project, mock_conda_env_runner):
    env_name = "py123"
    ini = f"""
        [testenv:{env_name}]
        skip_install = True
        conda_env = conda-env.yml
        conda_spec = conda_spec.txt
    """
    yaml = """
         name: tox-conda
         channels:
           - conda-forge
           - nodefaults
         dependencies:
           - numpy
           - astropy
           - pip:
             - pytest
        """
    proj = tox_project({"tox.ini": ini})
    (proj.path / "conda-env.yml").write_text(yaml)
    (proj.path / "conda_spec.txt").touch()

    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 3

    create_env_cmd = executed_shell_commands[1]
    install_cmd = executed_shell_commands[2]
    assert fnmatch(create_env_cmd, "*conda env create*")
    assert fnmatch(install_cmd, "*conda install*")
    assert "--file=conda_spec.txt" in install_cmd


def test_conda_install_args(tox_project, mock_conda_env_runner):
    env_name = "py123"
    ini = f"""
        [testenv:{env_name}]
        skip_install = True
        conda_deps=
            numpy
        conda_install_args = --override-channels
    """

    proj = tox_project({"tox.ini": ini})

    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 3

    install_cmd = executed_shell_commands[2]
    assert fnmatch(install_cmd, "*conda install*")
    assert "--override-channels" in install_cmd


def test_conda_create_args(tox_project, mock_conda_env_runner):
    env_name = "py123"
    ini = f"""
        [testenv:{env_name}]
        skip_install = True
        conda_create_args = --override-channels
    """

    proj = tox_project({"tox.ini": ini})

    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 2

    create_cmd = executed_shell_commands[1]
    assert fnmatch(create_cmd, "*conda create*")
    assert "--override-channels" in create_cmd
