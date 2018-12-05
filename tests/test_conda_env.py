import os
import glob

from tox.venv import VirtualEnv
from tox_conda.plugin import tox_testenv_create, tox_testenv_install_deps


def test_conda_create(newconfig, mocksession):
    config = newconfig(
        [],
        """
        [testenv:py123]
    """,
    )

    venv = VirtualEnv(config.envconfigs["py123"], session=mocksession)
    assert venv.path == config.envconfigs['py123'].envdir

    action = mocksession.newaction(venv, "getenv")
    tox_testenv_create(action=action, venv=venv)
    pcalls = mocksession._pcalls
    assert len(pcalls) == 1
    assert 'conda' in pcalls[0].args[0]
    assert 'create' == pcalls[0].args[1]
    assert '--yes' == pcalls[0].args[2]
    assert '-p' == pcalls[0].args[3]
    assert venv.path == pcalls[0].args[4]
    assert pcalls[0].args[5].startswith('python=')
