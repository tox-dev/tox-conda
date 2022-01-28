import shutil

import tox

import tox_conda.plugin


def test_conda(cmd, initproj):
    # The path has a blank space on purpose for testing issue #119.
    initproj(
        "pkg 1",
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
                    pip >0,<999
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


def test_missing_conda(cmd, initproj, monkeypatch):
    """Check that an error is shown when the conda executable is not found."""

    initproj(
        "pkg-1",
        filedefs={
            "tox.ini": """
                [tox]
                require = tox-conda
            """,
        },
    )

    # Prevent conda from being found.
    original_which = shutil.which

    def which(path):  # pragma: no cover
        if path.endswith("conda"):
            return None
        return original_which(path)

    monkeypatch.setattr(shutil, "which", which)

    result = cmd()

    assert result.outlines == ["ERROR: {}".format(tox_conda.plugin.MISSING_CONDA_ERROR)]


def test_issue_115(cmd, initproj):
    """Verify that a conda activation script is sourced.

    https://docs.conda.io/projects/conda-build/en/latest/resources/activate-scripts.html
    """
    if tox.INFO.IS_WIN:
        build_script_name = "build.bat"
        build_script = """
            setlocal EnableDelayedExpansion
            mkdir %CONDA_PREFIX%\\etc\\conda\\activate.d
            copy activate.bat %CONDA_PREFIX%\\etc\\conda\\activate.d
        """
        activate_script_name = "activate.bat"
        activate_script = """
            set DUMMY=0
        """
        commands_pre = "build.bat"

    else:
        build_script_name = "build.sh"
        build_script = """
            mkdir -p "${CONDA_PREFIX}/etc/conda/activate.d"
            cp activate.sh "${CONDA_PREFIX}/etc/conda/activate.d"
        """
        activate_script_name = "activate.sh"
        activate_script = """
            export DUMMY=0
        """
        commands_pre = "/bin/sh build.sh"

    initproj(
        "115",
        filedefs={
            build_script_name: build_script,
            activate_script_name: activate_script,
            "tox.ini": """
                [testenv]
                commands_pre = {}
                commands = python -c "import os; assert 'DUMMY' in os.environ"
            """.format(
                commands_pre
            ),
        },
    )

    result = cmd()
    result.assert_success()
