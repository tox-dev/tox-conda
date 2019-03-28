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
