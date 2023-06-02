"""Cache tests."""

from fnmatch import fnmatch


def assert_create_command(cmd):
    assert fnmatch(cmd, "*conda create*") or fnmatch(cmd, "*conda env create*")


def assert_install_command(cmd):
    assert fnmatch(cmd, "*conda install*")


def test_conda_no_recreate(tox_project, mock_conda_env_runner):
    ini = """
        [testenv:py123]
        skip_install = True
        conda_env = conda-env.yml
        conda_deps =
            asdf
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
    for i in range(2):
        proj = tox_project({"tox.ini": ini})
        (proj.path / "conda-env.yml").write_text(yaml)
        outcome = proj.run("-e", "py123")
        outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    # get_python, create env, install deps, get_python, and nothing else because no changes
    assert len(executed_shell_commands) == 4
    assert_create_command(executed_shell_commands[1])
    assert_install_command(executed_shell_commands[2])


def test_conda_recreate_by_dependency_change(tox_project, mock_conda_env_runner):
    ini = """
        [testenv:py123]
        skip_install = True
        conda_deps =
            asdf
    """
    ini_modified = """
        [testenv:py123]
        skip_install = True
        conda_deps =
            asdf
            black
    """
    outcome = tox_project({"tox.ini": ini}).run("-e", "py123")
    outcome.assert_success()

    outcome = tox_project({"tox.ini": ini_modified}).run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    # get_python, create env, install deps, get_python, create env, install deps
    assert len(executed_shell_commands) == 6

    assert_create_command(executed_shell_commands[1])
    assert_install_command(executed_shell_commands[2])
    assert_create_command(executed_shell_commands[4])
    assert_install_command(executed_shell_commands[5])


def test_conda_recreate_by_env_file_path_change(tox_project, mock_conda_env_runner):
    ini = """
        [testenv:py123]
        skip_install = True
        conda_env = conda-env-1.yml
    """
    ini_modified = """
        [testenv:py123]
        skip_install = True
        conda_env = conda-env-2.yml
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

    proj_1 = tox_project({"tox.ini": ini})
    (proj_1.path / "conda-env-1.yml").write_text(yaml)
    outcome = proj_1.run("-e", "py123")
    outcome.assert_success()

    proj_2 = tox_project({"tox.ini": ini_modified})
    (proj_2.path / "conda-env-2.yml").write_text(yaml)
    outcome = proj_2.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    # get_python, create env, get_python, create env
    assert len(executed_shell_commands) == 4

    assert_create_command(executed_shell_commands[1])
    assert_create_command(executed_shell_commands[3])


def test_conda_recreate_by_env_file_content_change(tox_project, mock_conda_env_runner):
    ini = """
        [testenv:py123]
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
        """
    yaml_modified = """
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
    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    (proj.path / "conda-env.yml").write_text(yaml_modified)
    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    # get_python, create env, get_python, create env
    assert len(executed_shell_commands) == 4

    assert_create_command(executed_shell_commands[1])
    assert_create_command(executed_shell_commands[3])


def test_conda_recreate_by_spec_file_path_change(tox_project, mock_conda_env_runner):
    ini = """
        [testenv:py123]
        skip_install = True
        conda_spec = conda_spec-1.txt
    """
    ini_modified = """
        [testenv:py123]
        skip_install = True
        conda_spec = conda_spec-2.txt
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

    proj_1 = tox_project({"tox.ini": ini})
    (proj_1.path / "conda_spec-1.txt").touch()
    outcome = proj_1.run("-e", "py123")
    outcome.assert_success()

    proj_2 = tox_project({"tox.ini": ini_modified})
    (proj_2.path / "conda_spec-2.txt").touch()
    outcome = proj_2.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    # get_python, create env, install deps, get_python, create env, install deps
    assert len(executed_shell_commands) == 6

    assert_create_command(executed_shell_commands[1])
    assert_install_command(executed_shell_commands[2])
    assert_create_command(executed_shell_commands[4])
    assert_install_command(executed_shell_commands[5])


def test_conda_recreate_by_spec_file_content_change(tox_project, mock_conda_env_runner):
    ini = """
        [testenv:py123]
        skip_install = True
        conda_spec = conda_spec.txt
    """
    txt = """
        black
    """
    txt_modified = """
        black
        numpy
    """

    proj = tox_project({"tox.ini": ini})
    (proj.path / "conda_spec.txt").write_text(txt)
    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    (proj.path / "conda_spec.txt").write_text(txt_modified)
    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    # get_python, create env, install deps, get_python, create env, install deps
    assert len(executed_shell_commands) == 6

    assert_create_command(executed_shell_commands[1])
    assert_install_command(executed_shell_commands[2])
    assert_create_command(executed_shell_commands[4])
    assert_install_command(executed_shell_commands[5])
