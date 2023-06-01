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


def test_conda_create(tox_project, mock_conda_env_runner):
    ini = "[testenv:py123]"
    proj = tox_project({"tox.ini": ini})

    outcome = proj.run("-e", "py123")
    outcome.assert_success()

    executed_shell_commands = mock_conda_env_runner
    assert len(executed_shell_commands) == 3

    create_env_cmd = executed_shell_commands[1]

    assert "conda" in create_env_cmd[0]
    assert "create" == create_env_cmd[1]
    assert "-p" == create_env_cmd[2]
    assert str(proj.path / ".tox" / "py123") == create_env_cmd[3]
    assert create_env_cmd[4].startswith("python=")
    assert "--yes" == create_env_cmd[5]
    assert "--quiet" == create_env_cmd[6]

def test_install_deps_no_conda(tox_project, mock_conda_env_runner):
    """Test installation using conda when no conda_deps are given"""
    env_name = "py123"
    ini = f"""
        [testenv:{env_name}]
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
    assert len(executed_shell_commands) == 4

    cmd = executed_shell_commands[2]
    cmd_conda_prefix = " ".join(cmd[:5])
    cmd_pip_install = " ".join(cmd[5:])

    assert f"conda run -p {str(proj.path / '.tox' / env_name)} --live-stream" in cmd_conda_prefix

    assert cmd_pip_install.startswith("python -I -m pip install")
    assert "numpy" in cmd_pip_install
    assert "astropy" in cmd_pip_install
    assert "-r requirements.txt" in cmd_pip_install

    # config.toxinidir.join("requirements.txt").write("")

    # venv, action, pcalls = create_test_env(config, mocksession, env_name)

    # assert len(venv.envconfig.deps) == 3
    # assert len(venv.envconfig.conda_deps) == 0

    # tox_testenv_install_deps(action=action, venv=venv)

    # assert len(pcalls) >= 1

    # call = pcalls[-1]

    # if tox.INFO.IS_WIN:
    #     script_lines = " ".join(call.args).split(" && ", maxsplit=1)
    #     pattern = r"conda\.bat activate .*{}".format(re.escape(env_name))
    # else:
    #     # Get the cmd args from the script.
    #     shell, cmd_script = call.args
    #     assert shell == "/bin/sh"
    #     with open(cmd_script) as stream:
    #         script_lines = stream.readlines()
    #     pattern = r"eval \"\$\(/.*/conda shell\.posix activate /.*/{}\)\"".format(env_name)

    # assert re.match(pattern, script_lines[0])

    # cmd = script_lines[1].split()
    # assert cmd[-6:] == ["-m", "pip", "install", "numpy", "-rrequirements.txt", "astropy"]


# def test_install_conda_deps(newconfig, mocksession):
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         deps=
#             numpy
#             astropy
#         conda_deps=
#             pytest
#             asdf
#     """,
#     )

#     venv, action, pcalls = create_test_env(config, mocksession, "py123")

#     assert len(venv.envconfig.conda_deps) == 2
#     assert len(venv.envconfig.deps) == 2 + len(venv.envconfig.conda_deps)

#     tox_testenv_install_deps(action=action, venv=venv)
#     # We expect two calls: one for conda deps, and one for pip deps
#     assert len(pcalls) >= 2
#     call = pcalls[-2]
#     conda_cmd = call.args
#     assert "conda" in os.path.split(conda_cmd[0])[-1]
#     assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]
#     # Make sure that python is explicitly given as part of every conda install
#     # in order to avoid inadvertent upgrades of python itself.
#     assert conda_cmd[6].startswith("python=")
#     assert conda_cmd[7:9] == ["pytest", "asdf"]


# def test_install_conda_no_pip(newconfig, mocksession):
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_deps=
#             pytest
#             asdf
#     """,
#     )

#     venv, action, pcalls = create_test_env(config, mocksession, "py123")

#     assert len(venv.envconfig.conda_deps) == 2
#     assert len(venv.envconfig.deps) == len(venv.envconfig.conda_deps)

#     tox_testenv_install_deps(action=action, venv=venv)
#     # We expect only one call since there are no true pip dependencies
#     assert len(pcalls) >= 1

#     # Just a quick sanity check for the conda install command
#     call = pcalls[-1]
#     conda_cmd = call.args
#     assert "conda" in os.path.split(conda_cmd[0])[-1]
#     assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]


# def test_update(tmpdir, newconfig, mocksession):
#     pkg = tmpdir.ensure("package.tar.gz")
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         deps=
#             numpy
#             astropy
#         conda_deps=
#             pytest
#             asdf
#     """,
#     )

#     venv, action, pcalls = create_test_env(config, mocksession, "py123")
#     tox_testenv_install_deps(action=action, venv=venv)

#     venv.hook.tox_testenv_create = tox_testenv_create
#     venv.hook.tox_testenv_install_deps = tox_testenv_install_deps
#     with mocksession.newaction(venv.name, "update") as action:
#         venv.update(action)
#         venv.installpkg(pkg, action)


# def test_conda_spec(tmpdir, newconfig, mocksession):
#     """Test environment creation when conda_spec given"""
#     txt = tmpdir.join("conda-spec.txt")
#     txt.write(
#         """
#         pytest
#         """
#     )
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_deps=
#             numpy
#             astropy
#         conda_spec={}
#         """.format(
#             str(txt)
#         ),
#     )
#     venv, action, pcalls = create_test_env(config, mocksession, "py123")

#     assert venv.envconfig.conda_spec
#     assert len(venv.envconfig.conda_deps) == 2

#     tox_testenv_install_deps(action=action, venv=venv)
#     # We expect conda_spec to be appended to conda deps install
#     assert len(pcalls) >= 1
#     call = pcalls[-1]
#     conda_cmd = call.args
#     assert "conda" in os.path.split(conda_cmd[0])[-1]
#     assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]
#     # Make sure that python is explicitly given as part of every conda install
#     # in order to avoid inadvertent upgrades of python itself.
#     assert conda_cmd[6].startswith("python=")
#     assert conda_cmd[7:9] == ["numpy", "astropy"]
#     assert conda_cmd[-1].startswith("--file")
#     assert conda_cmd[-1].endswith("conda-spec.txt")


# def test_empty_conda_spec_and_env(tmpdir, newconfig, mocksession):
#     """Test environment creation when empty conda_spec and conda_env."""
#     txt = tmpdir.join("conda-spec.txt")
#     txt.write(
#         """
#         pytest
#         """
#     )
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_env=
#           foo: path-to.yml
#         conda_spec=
#           foo: path-to.yml
#         """,
#     )
#     venv, _, _ = create_test_env(config, mocksession, "py123")

#     assert venv.envconfig.conda_spec is None
#     assert venv.envconfig.conda_env is None


# def test_conda_env(tmpdir, newconfig, mocksession):
#     """Test environment creation when conda_env given"""
#     yml = tmpdir.join("conda-env.yml")
#     yml.write(
#         """
#         name: tox-conda
#         channels:
#           - conda-forge
#           - nodefaults
#         dependencies:
#           - numpy
#           - astropy
#           - pip:
#             - pytest
#         """
#     )
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_env={}
#         """.format(
#             str(yml)
#         ),
#     )

#     venv = VirtualEnv(config.envconfigs["py123"])
#     assert venv.path == config.envconfigs["py123"].envdir

#     venv, action, pcalls = create_test_env(config, mocksession, "py123")
#     assert venv.envconfig.conda_env

#     mock_file = mock_open()
#     with patch("tox_conda.plugin.tempfile.NamedTemporaryFile", mock_file):
#         with patch.object(pathlib.Path, "unlink", autospec=True) as mock_unlink:
#             with mocksession.newaction(venv.name, "getenv") as action:
#                 tox_testenv_create(action=action, venv=venv)
#                 mock_unlink.assert_called_once

#     mock_file.assert_called_with(dir=tmpdir, prefix="tox_conda_tmp", suffix=".yaml", delete=False)

#     pcalls = mocksession._pcalls
#     assert len(pcalls) >= 1
#     call = pcalls[-1]
#     cmd = call.args
#     assert "conda" in os.path.split(cmd[0])[-1]
#     assert cmd[1:4] == ["env", "create", "-p"]
#     assert venv.path == call.args[4]
#     assert call.args[5].startswith("--file")
#     assert cmd[6] == str(mock_file().name)

#     yaml = YAML()
#     tmp_env = yaml.load(mock_open_to_string(mock_file))
#     assert tmp_env["dependencies"][-1].startswith("python=")


# def test_conda_env_and_spec(tmpdir, newconfig, mocksession):
#     """Test environment creation when conda_env and conda_spec are given"""
#     yml = tmpdir.join("conda-env.yml")
#     yml.write(
#         """
#         name: tox-conda
#         channels:
#           - conda-forge
#           - nodefaults
#         dependencies:
#           - numpy
#           - astropy
#         """
#     )
#     txt = tmpdir.join("conda-spec.txt")
#     txt.write(
#         """
#         pytest
#         """
#     )
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_env={}
#         conda_spec={}
#         """.format(
#             str(yml), str(txt)
#         ),
#     )
#     venv, action, pcalls = create_test_env(config, mocksession, "py123")

#     assert venv.envconfig.conda_env
#     assert venv.envconfig.conda_spec

#     mock_file = mock_open()
#     with patch("tox_conda.plugin.tempfile.NamedTemporaryFile", mock_file):
#         with patch.object(pathlib.Path, "unlink", autospec=True) as mock_unlink:
#             with mocksession.newaction(venv.name, "getenv") as action:
#                 tox_testenv_create(action=action, venv=venv)
#                 mock_unlink.assert_called_once

#     mock_file.assert_called_with(dir=tmpdir, prefix="tox_conda_tmp", suffix=".yaml", delete=False)

#     pcalls = mocksession._pcalls
#     assert len(pcalls) >= 1
#     call = pcalls[-1]
#     cmd = call.args
#     assert "conda" in os.path.split(cmd[0])[-1]
#     assert cmd[1:4] == ["env", "create", "-p"]
#     assert venv.path == call.args[4]
#     assert call.args[5].startswith("--file")
#     assert cmd[6] == str(mock_file().name)

#     yaml = YAML()
#     tmp_env = yaml.load(mock_open_to_string(mock_file))
#     assert tmp_env["dependencies"][-1].startswith("python=")

#     with mocksession.newaction(venv.name, "getenv") as action:
#         tox_testenv_install_deps(action=action, venv=venv)
#     pcalls = mocksession._pcalls
#     # We expect conda_spec to be appended to conda deps install
#     assert len(pcalls) >= 1
#     call = pcalls[-1]
#     conda_cmd = call.args
#     assert "conda" in os.path.split(conda_cmd[0])[-1]
#     assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]
#     # Make sure that python is explicitly given as part of every conda install
#     # in order to avoid inadvertent upgrades of python itself.
#     assert conda_cmd[6].startswith("python=")
#     assert conda_cmd[-1].startswith("--file")
#     assert conda_cmd[-1].endswith("conda-spec.txt")


# def test_conda_install_args(newconfig, mocksession):
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_deps=
#             numpy
#         conda_install_args=
#             --override-channels
#     """,
#     )

#     venv, action, pcalls = create_test_env(config, mocksession, "py123")

#     assert len(venv.envconfig.conda_install_args) == 1

#     tox_testenv_install_deps(action=action, venv=venv)

#     call = pcalls[-1]
#     assert call.args[6] == "--override-channels"


# def test_conda_create_args(newconfig, mocksession):
#     config = newconfig(
#         [],
#         """
#         [testenv:py123]
#         conda_create_args=
#             --override-channels
#     """,
#     )

#     venv = VirtualEnv(config.envconfigs["py123"])
#     assert venv.path == config.envconfigs["py123"].envdir

#     with mocksession.newaction(venv.name, "getenv") as action:
#         tox_testenv_create(action=action, venv=venv)
#     pcalls = mocksession._pcalls
#     assert len(pcalls) >= 1
#     call = pcalls[-1]
#     assert "conda" in call.args[0]
#     assert "create" == call.args[1]
#     assert "--yes" == call.args[2]
#     assert "-p" == call.args[3]
#     assert venv.path == call.args[4]
#     assert call.args[5] == "--override-channels"
#     assert call.args[6].startswith("python=")


# def test_verbosity(newconfig, mocksession):
#     config = newconfig(
#         [],
#         """
#         [testenv:py1]
#         conda_deps=numpy
#         [testenv:py2]
#         conda_deps=numpy
#     """,
#     )

#     venv, action, pcalls = create_test_env(config, mocksession, "py1")
#     tox_testenv_install_deps(action=action, venv=venv)
#     assert len(pcalls) == 1
#     call = pcalls[0]
#     assert "conda" in call.args[0]
#     assert "install" == call.args[1]
#     assert isinstance(call.stdout, io.IOBase)

#     tox.reporter.update_default_reporter(
#         tox.reporter.Verbosity.DEFAULT, tox.reporter.Verbosity.DEBUG
#     )
#     venv, action, pcalls = create_test_env(config, mocksession, "py2")
#     tox_testenv_install_deps(action=action, venv=venv)
#     assert len(pcalls) == 1
#     call = pcalls[0]
#     assert "conda" in call.args[0]
#     assert "install" == call.args[1]
#     assert not isinstance(call.stdout, io.IOBase)


# def mock_open_to_string(mock):
#     return "".join(call.args[0] for call in mock().write.call_args_list)
