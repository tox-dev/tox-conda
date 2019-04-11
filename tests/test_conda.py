def test_conda(cmd, initproj):
    initproj(
        "pkg-1",
        filedefs={
            "tox.ini": """
                [tox]
                skipsdist=True
                [testenv]
                conda_env=True
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
        "create --yes -p " in l
        for l in result.outlines[index_of("py create: ") + 1 : index_of("py installed: ")]
    ), result.output()

    assert result.outlines[-4] == "True"
