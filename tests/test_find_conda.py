import subprocess
from pathlib import Path

import pytest
from tox.tox_env.errors import Fail

from tox_conda.conda import find_conda


def test_no_active_env(monkeypatch):
    conda_path = "/path/to/conda"

    monkeypatch.setenv("_CONDA_EXE", conda_path)
    monkeypatch.delenv("CONDA_EXE", raising=False)

    got_conda_path = find_conda()
    assert got_conda_path is not None
    assert got_conda_path.resolve() == Path(conda_path).resolve()


def test_with_active_env(monkeypatch):
    conda_path = "/path/to/conda/env/test/bin/conda"

    monkeypatch.delenv("_CONDA_EXE", raising=False)
    monkeypatch.setenv("CONDA_EXE", conda_path)

    got_conda_path = find_conda()
    assert got_conda_path is not None
    assert got_conda_path.resolve() == Path(conda_path).resolve()


def test_which_success(monkeypatch, mocker):
    conda_path = "/path/to/conda"

    mocker.patch("shutil.which", return_value=conda_path)
    mocker.patch("subprocess.run")

    monkeypatch.delenv("_CONDA_EXE", raising=False)
    monkeypatch.delenv("CONDA_EXE", raising=False)

    got_conda_path = find_conda()
    assert got_conda_path is not None
    assert got_conda_path.resolve() == Path(conda_path).resolve()


def test_which_not_exec(monkeypatch, mocker):
    conda_path = "/path/to/conda"

    mocker.patch("shutil.which", return_value=conda_path)
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "conda"))

    monkeypatch.delenv("_CONDA_EXE", raising=False)
    monkeypatch.delenv("CONDA_EXE", raising=False)

    with pytest.raises(Fail):
        find_conda()


def test_which_not_found(monkeypatch, mocker):
    mocker.patch("shutil.which", return_value=None)

    monkeypatch.delenv("_CONDA_EXE", raising=False)
    monkeypatch.delenv("CONDA_EXE", raising=False)

    with pytest.raises(Fail):
        find_conda()
