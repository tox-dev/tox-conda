from tox.pytest import ToxProjectCreator


def test_version() -> None:
    from tox_conda import __version__

    assert __version__


def test_create(tox_project: ToxProjectCreator) -> None:
    project = tox_project({"tox.ini": "[testenv]\nrunner=conda\npackage=skip"})
    project.run("r", "-e", "magic")
