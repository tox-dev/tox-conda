import os

from tox.venv import VirtualEnv

from tox_conda.plugin import tox_testenv_create, tox_testenv_install_deps


def test_conda_create(newconfig, mocksession):
    config = newconfig(
        [],
        """
        [testenv:py123]
    """,
    )

    venv = VirtualEnv(config.envconfigs["py123"])
    assert venv.path == config.envconfigs["py123"].envdir

    with mocksession.newaction(venv.name, "getenv") as action:
        tox_testenv_create(action=action, venv=venv)
    pcalls = mocksession._pcalls
    assert len(pcalls) >= 1
    call = pcalls[-1]
    assert "conda" in call.args[0]
    assert "create" == call.args[1]
    assert "--yes" == call.args[2]
    assert "-p" == call.args[3]
    assert venv.path == call.args[4]
    assert call.args[5].startswith("python=")


def create_test_env(config, mocksession, envname):

    venv = VirtualEnv(config.envconfigs[envname])
    with mocksession.newaction(venv.name, "getenv") as action:
        tox_testenv_create(action=action, venv=venv)
    pcalls = mocksession._pcalls
    assert len(pcalls) >= 1
    pcalls[:] = []

    return venv, action, pcalls


def test_install_deps_no_conda(newconfig, mocksession):
    """Test installation using conda when no conda_deps are given"""
    config = newconfig(
        [],
        """
        [testenv:py123]
        deps=
            numpy
            astropy
    """,
    )

    venv, action, pcalls = create_test_env(config, mocksession, "py123")

    assert len(venv.envconfig.deps) == 2
    assert len(venv.envconfig.conda_deps) == 0

    tox_testenv_install_deps(action=action, venv=venv)
    assert len(pcalls) >= 1
    call = pcalls[-1]
    cmd = call.args
    assert cmd[1:4] == ["-m", "pip", "install"]


def test_install_conda_deps(newconfig, mocksession):
    config = newconfig(
        [],
        """
        [testenv:py123]
        deps=
            numpy
            astropy
        conda_deps=
            pytest
            asdf
    """,
    )

    venv, action, pcalls = create_test_env(config, mocksession, "py123")

    assert len(venv.envconfig.conda_deps) == 2
    assert len(venv.envconfig.deps) == 2 + len(venv.envconfig.conda_deps)

    tox_testenv_install_deps(action=action, venv=venv)
    # We expect two calls: one for conda deps, and one for pip deps
    assert len(pcalls) >= 2
    call = pcalls[-2]
    conda_cmd = call.args
    assert "conda" in os.path.split(conda_cmd[0])[-1]
    assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]
    # Make sure that python is explicitly given as part of every conda install
    # in order to avoid inadvertant upgrades of python itself.
    assert conda_cmd[6].startswith("python=")
    assert conda_cmd[7:9] == ["pytest", "asdf"]

    pip_cmd = pcalls[-1].args
    assert pip_cmd[1:4] == ["-m", "pip", "install"]
    assert pip_cmd[4:6] == ["numpy", "astropy"]


def test_install_conda_no_pip(newconfig, mocksession):
    config = newconfig(
        [],
        """
        [testenv:py123]
        conda_deps=
            pytest
            asdf
    """,
    )

    venv, action, pcalls = create_test_env(config, mocksession, "py123")

    assert len(venv.envconfig.conda_deps) == 2
    assert len(venv.envconfig.deps) == len(venv.envconfig.conda_deps)

    tox_testenv_install_deps(action=action, venv=venv)
    # We expect only one call since there are no true pip dependencies
    assert len(pcalls) >= 1

    # Just a quick sanity check for the conda install command
    call = pcalls[-1]
    conda_cmd = call.args
    assert "conda" in os.path.split(conda_cmd[0])[-1]
    assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]


def test_update(tmpdir, newconfig, mocksession):
    pkg = tmpdir.ensure("package.tar.gz")
    config = newconfig(
        [],
        """
        [testenv:py123]
        deps=
            numpy
            astropy
        conda_deps=
            pytest
            asdf
    """,
    )

    venv, action, pcalls = create_test_env(config, mocksession, "py123")
    tox_testenv_install_deps(action=action, venv=venv)

    venv.hook.tox_testenv_create = tox_testenv_create
    venv.hook.tox_testenv_install_deps = tox_testenv_install_deps
    with mocksession.newaction(venv.name, "update") as action:
        venv.update(action)
        venv.installpkg(pkg, action)


def test_conda_spec(tmpdir, newconfig, mocksession):
    """Test environment creation when conda_spec given"""
    txt = tmpdir.join("conda-spec.txt")
    txt.write(
        """
        pytest
        """
    )
    config = newconfig(
        [],
        """
        [testenv:py123]
        conda_deps=
            numpy
            astropy
        conda_spec={}
        """.format(
            str(txt)
        ),
    )
    venv, action, pcalls = create_test_env(config, mocksession, "py123")

    assert venv.envconfig.conda_spec
    assert len(venv.envconfig.conda_deps) == 2

    tox_testenv_install_deps(action=action, venv=venv)
    # We expect conda_spec to be appended to conda deps install
    assert len(pcalls) >= 1
    call = pcalls[-1]
    conda_cmd = call.args
    assert "conda" in os.path.split(conda_cmd[0])[-1]
    assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]
    # Make sure that python is explicitly given as part of every conda install
    # in order to avoid inadvertent upgrades of python itself.
    assert conda_cmd[6].startswith("python=")
    assert conda_cmd[7:9] == ["numpy", "astropy"]
    assert conda_cmd[-1].startswith("--file")
    assert conda_cmd[-1].endswith("conda-spec.txt")


def test_conda_env(tmpdir, newconfig, mocksession):
    """Test environment creation when conda_env given"""
    yml = tmpdir.join("conda-env.yml")
    yml.write(
        """
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
    )
    config = newconfig(
        [],
        """
        [testenv:py123]
        conda_env={}
        """.format(
            str(yml)
        ),
    )

    venv = VirtualEnv(config.envconfigs["py123"])
    assert venv.path == config.envconfigs["py123"].envdir

    venv, action, pcalls = create_test_env(config, mocksession, "py123")
    assert venv.envconfig.conda_env

    with mocksession.newaction(venv.name, "getenv") as action:
        tox_testenv_create(action=action, venv=venv)
    pcalls = mocksession._pcalls
    assert len(pcalls) >= 1
    call = pcalls[-1]
    cmd = call.args
    assert "conda" in os.path.split(cmd[0])[-1]
    assert cmd[1:4] == ["env", "create", "-p"]
    assert venv.path == call.args[4]
    assert call.args[5].startswith("--file")
    assert call.args[6].endswith("conda-env.yml")


def test_conda_env_and_spec(tmpdir, newconfig, mocksession):
    """Test environment creation when conda_env and conda_spec are given"""
    yml = tmpdir.join("conda-env.yml")
    yml.write(
        """
        name: tox-conda
        channels:
          - conda-forge
          - nodefaults
        dependencies:
          - numpy
          - astropy
        """
    )
    txt = tmpdir.join("conda-spec.txt")
    txt.write(
        """
        pytest
        """
    )
    config = newconfig(
        [],
        """
        [testenv:py123]
        conda_env={}
        conda_spec={}
        """.format(
            str(yml), str(txt)
        ),
    )
    venv, action, pcalls = create_test_env(config, mocksession, "py123")

    assert venv.envconfig.conda_env
    assert venv.envconfig.conda_spec

    with mocksession.newaction(venv.name, "getenv") as action:
        tox_testenv_create(action=action, venv=venv)
    pcalls = mocksession._pcalls
    assert len(pcalls) >= 1
    call = pcalls[-1]
    cmd = call.args
    assert "conda" in os.path.split(cmd[0])[-1]
    assert cmd[1:4] == ["env", "create", "-p"]
    assert venv.path == call.args[4]
    assert call.args[5].startswith("--file")
    assert call.args[6].endswith("conda-env.yml")

    with mocksession.newaction(venv.name, "getenv") as action:
        tox_testenv_install_deps(action=action, venv=venv)
    pcalls = mocksession._pcalls
    # We expect conda_spec to be appended to conda deps install
    assert len(pcalls) >= 1
    call = pcalls[-1]
    conda_cmd = call.args
    assert "conda" in os.path.split(conda_cmd[0])[-1]
    assert conda_cmd[1:6] == ["install", "--quiet", "--yes", "-p", venv.path]
    # Make sure that python is explicitly given as part of every conda install
    # in order to avoid inadvertent upgrades of python itself.
    assert conda_cmd[6].startswith("python=")
    assert conda_cmd[-1].startswith("--file")
    assert conda_cmd[-1].endswith("conda-spec.txt")


def test_conda_install_args(newconfig, mocksession):
    config = newconfig(
        [],
        """
        [testenv:py123]
        conda_deps=
            numpy
        conda_install_args=
            --override-channels
    """,
    )

    venv, action, pcalls = create_test_env(config, mocksession, "py123")

    assert len(venv.envconfig.conda_install_args) == 1

    tox_testenv_install_deps(action=action, venv=venv)

    call = pcalls[-1]
    assert call.args[6] == "--override-channels"


def test_conda_create_args(newconfig, mocksession):
    config = newconfig(
        [],
        """
        [testenv:py123]
        conda_create_args=
            --override-channels
    """,
    )

    venv = VirtualEnv(config.envconfigs["py123"])
    assert venv.path == config.envconfigs["py123"].envdir

    with mocksession.newaction(venv.name, "getenv") as action:
        tox_testenv_create(action=action, venv=venv)
    pcalls = mocksession._pcalls
    assert len(pcalls) >= 1
    call = pcalls[-1]
    assert "conda" in call.args[0]
    assert "create" == call.args[1]
    assert "--yes" == call.args[2]
    assert "-p" == call.args[3]
    assert venv.path == call.args[4]
    assert call.args[5] == "--override-channels"
    assert call.args[6].startswith("python=")
