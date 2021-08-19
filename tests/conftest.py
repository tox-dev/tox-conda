from pathlib import Path

import pytest

pytest_plugins = ("tox.pytest",)

HERE = Path(__file__).absolute().parent


@pytest.fixture(scope="session")
def demo_pkg_inline() -> Path:
    return HERE / "demo_pkg_inline"
