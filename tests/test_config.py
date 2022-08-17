def test_conda_deps(tmpdir, newconfig):
    config = newconfig(
        [],
        """
        [tox]
        toxworkdir = {}
        [testenv:py1]
        deps=
            hello
        conda_deps=
            world
            something
    """.format(
            tmpdir
        ),
    )

    assert len(config.envconfigs) == 1
    assert hasattr(config.envconfigs["py1"], "deps")
    assert hasattr(config.envconfigs["py1"], "conda_deps")
    assert len(config.envconfigs["py1"].conda_deps) == 2
    # For now, as a workaround, we temporarily add all conda dependencies to
    # deps as well. This allows tox to know whether an environment needs to be
    # updated or not. Eventually there may be a cleaner solution.
    assert len(config.envconfigs["py1"].deps) == 3
    assert "world" == config.envconfigs["py1"].conda_deps[0].name
    assert "something" == config.envconfigs["py1"].conda_deps[1].name


def test_conda_env_and_spec(tmpdir, newconfig):
    config = newconfig(
        [],
        """
        [tox]
        toxworkdir = {}
        [testenv:py1]
        conda_env = conda_env.yaml
        conda_spec = conda_spec.txt
    """.format(
            tmpdir
        ),
    )

    assert len(config.envconfigs) == 1
    assert config.envconfigs["py1"].conda_env == tmpdir / "conda_env.yaml"
    assert config.envconfigs["py1"].conda_spec == tmpdir / "conda_spec.txt"
    # Conda env and spec files get added to deps to allow tox to detect changes.
    # Similar to conda_deps in the test above.
    assert hasattr(config.envconfigs["py1"], "deps")
    assert len(config.envconfigs["py1"].deps) == 2
    assert any(dep.name == tmpdir / "conda_env.yaml" for dep in config.envconfigs["py1"].deps)
    assert any(dep.name == tmpdir / "conda_spec.txt" for dep in config.envconfigs["py1"].deps)


def test_no_conda_deps(tmpdir, newconfig):
    config = newconfig(
        [],
        """
        [tox]
        toxworkdir = {}
        [testenv:py1]
        deps=
            hello
    """.format(
            tmpdir
        ),
    )

    assert len(config.envconfigs) == 1
    assert hasattr(config.envconfigs["py1"], "deps")
    assert hasattr(config.envconfigs["py1"], "conda_deps")
    assert hasattr(config.envconfigs["py1"], "conda_channels")
    assert len(config.envconfigs["py1"].conda_deps) == 0
    assert len(config.envconfigs["py1"].conda_channels) == 0
    assert len(config.envconfigs["py1"].deps) == 1


def test_conda_channels(tmpdir, newconfig):
    config = newconfig(
        [],
        """
        [tox]
        toxworkdir = {}
        [testenv:py1]
        deps=
            hello
        conda_deps=
            something
            else
        conda_channels=
            conda-forge
    """.format(
            tmpdir
        ),
    )

    assert len(config.envconfigs) == 1
    assert hasattr(config.envconfigs["py1"], "deps")
    assert hasattr(config.envconfigs["py1"], "conda_deps")
    assert hasattr(config.envconfigs["py1"], "conda_channels")
    assert len(config.envconfigs["py1"].conda_channels) == 1
    assert "conda-forge" in config.envconfigs["py1"].conda_channels


def test_conda_force_deps(tmpdir, newconfig):
    config = newconfig(
        ["--force-dep=something<42.1"],
        """
        [tox]
        toxworkdir = {}
        [testenv:py1]
        deps=
            hello
        conda_deps=
            something
            else
        conda_channels=
            conda-forge
    """.format(
            tmpdir
        ),
    )

    assert len(config.envconfigs) == 1
    assert hasattr(config.envconfigs["py1"], "conda_deps")
    assert len(config.envconfigs["py1"].conda_deps) == 2
    assert "something<42.1" == config.envconfigs["py1"].conda_deps[0].name
