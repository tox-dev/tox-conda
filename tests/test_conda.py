def test_conda(cmd, initproj):
    initproj(
        "pkg-1",
        filedefs={
            "tox.ini": """
                [tox]
                skipsdist=True
                [testenv]
                commands = python -c 'import sys, os; \
                    print(os.path.exists(os.path.join(sys.prefix, "conda-meta")))'
            """
        },
    )
    result = cmd("-v", "-e", "py")
    result.assert_success()

    def index_of(m):
        return next((i for i, l in enumerate(result.outlines) if l.startswith(m)), None)

    assert any(
        "create --yes -p " in line
        for line in result.outlines[index_of("py create: ") + 1 : index_of("py installed: ")]
    ), result.output()

    assert result.outlines[-4] == "True"


def test_conda_run_command(cmd, initproj):
    """Check that all the commands are run from an activated anaconda env.

    This is done by looking at the CONDA_PREFIX environment variable which contains
    the environment name.
    This variable is dumped to a file because commands_{pre,post} do not redirect
    their outputs.
    """
    env_name = "foobar"
    initproj(
        "pkg-1",
        filedefs={
            "tox.ini": """
                [tox]
                skipsdist=True
                [testenv:{}]
                deps =
                    pip>0,<999
                    -r requirements.txt
                commands_pre = python -c "import os; open('commands_pre', 'w').write(os.environ['CONDA_PREFIX'])"
                commands = python -c "import os; open('commands', 'w').write(os.environ['CONDA_PREFIX'])"
                commands_post = python -c "import os; open('commands_post', 'w').write(os.environ['CONDA_PREFIX'])"
            """.format(  # noqa: E501
                env_name
            ),
            "requirements.txt": "",
        },
    )

    result = cmd("-v", "-e", env_name)
    result.assert_success()

    for filename in ("commands_pre", "commands_post", "commands"):
        assert open(filename).read().endswith(env_name)

    # Run once again when the env creation hooks are not called.
    result = cmd("-v", "-e", env_name)
    result.assert_success()

    for filename in ("commands_pre", "commands_post", "commands"):
        assert open(filename).read().endswith(env_name)
