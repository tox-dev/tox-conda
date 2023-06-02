import pathlib
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

    create_env_cmd = executed_shell_commands[1]

    assert "conda" in create_env_cmd[0]
    assert "create" == create_env_cmd[1]
    assert "-p" == create_env_cmd[2]
    assert str(proj.path / ".tox" / "py123") == create_env_cmd[3]
    assert create_env_cmd[4].startswith("python=")
    assert "--yes" == create_env_cmd[5]
    assert "--quiet" == create_env_cmd[6]


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

    create_env_cmd = executed_shell_commands[1]

    assert "conda" in create_env_cmd[0]
    assert "create" == create_env_cmd[1]
    assert "-n" == create_env_cmd[2]
    assert "myenv" == create_env_cmd[3]
    assert create_env_cmd[4].startswith("python=")
    assert "--yes" == create_env_cmd[5]
    assert "--quiet" == create_env_cmd[6]


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

    cmd = executed_shell_commands[2]
    cmd_conda_prefix = " ".join(cmd[:5])
    cmd_pip_install = " ".join(cmd[5:])

    assert cmd_conda_prefix.endswith(
        f"conda run -p {str(proj.path / '.tox' / env_name)} --live-stream"
    )

    assert cmd_pip_install.startswith("python -I -m pip install")
    assert "numpy" in cmd_pip_install
    assert "astropy" in cmd_pip_install
    assert "-r requirements.txt" in cmd_pip_install


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

    cmd = executed_shell_commands[2]
    cmd_conda_prefix = " ".join(cmd[:6])
    cmd_packages = " ".join(cmd[6:])

    assert cmd_conda_prefix.endswith(
        f"conda install --quiet --yes -p {str(proj.path / '.tox' / env_name)}"
    )

    assert "asdf" in cmd_packages
    assert "pytest" in cmd_packages
    # Make sure that python is explicitly given as part of every conda install
    # in order to avoid inadvertent upgrades of python itself.
    assert "python=" in cmd_packages


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

    cmd_conda = " ".join(executed_shell_commands[2])
    pip_cmd = " ".join(executed_shell_commands[3])

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

    cmd = executed_shell_commands[2]
    cmd_conda_prefix = " ".join(cmd[:6])
    cmd_packages = " ".join(cmd[6:])

    assert cmd_conda_prefix.endswith(
        f"conda install --quiet --yes -p {str(proj.path / '.tox' / env_name)}"
    )

    assert "astropy" in cmd_packages
    assert "numpy" in cmd_packages
    assert "python=" in cmd_packages
    assert "--file=conda_spec.txt" in cmd_packages


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

    create_env_cmd = executed_shell_commands[1]

    assert "conda" in create_env_cmd[0]
    assert "env" == create_env_cmd[1]
    assert "create" == create_env_cmd[2]
    assert "-p" == create_env_cmd[3]
    assert str(proj.path / ".tox" / "py123") == create_env_cmd[4]
    assert "--file" == create_env_cmd[5]
    assert str(mock_temp_file) == create_env_cmd[6]
    assert "--quiet" == create_env_cmd[7]
    assert "--force" == create_env_cmd[8]

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

    assert "conda" in create_env_cmd[0]
    assert "env" == create_env_cmd[1]
    assert "create" == create_env_cmd[2]

    assert "conda" in install_cmd[0]
    assert "install" == install_cmd[1]
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

    assert "conda" in install_cmd[0]
    assert "install" == install_cmd[1]
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

    assert "conda" in create_cmd[0]
    assert "create" == create_cmd[1]
    assert "--override-channels" in create_cmd
