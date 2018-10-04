import os
import re
import subprocess as sp

import pluggy

import tox.venv
from tox.venv import VirtualEnv

hookimpl = pluggy.HookimplMarker('tox')


def get_py_version(envconfig):

    # Try to use basepython
    match = re.match(r'python(\d)(?:\.(\d))?', envconfig.basepython)
    if match:
        groups = match.groups()
        version = groups[0]
        if groups[1]:
            version += ".{}".format(groups[1])

    # First fallback
    elif envconfig.python_info.version_info:
        version = '{}.{}'.format(*envconfig.python_info.version_info[:2])

    # Second fallback
    else:
        code = 'import sys; print("{}.{}".format(*sys.version_info[:2]))'
        args = [envconfig.basepython, '-c', code]
        result = sp.check_output(args)
        version = result.decode('utf-8').strip()

    return 'python={}'.format(version)


@hookimpl
def tox_addoption(parser):

    parser.add_testenv_attribute(
        name="conda_deps",
        type="line-list",
        help="each line specifies a conda dependency in conda format"
    )

    parser.add_testenv_attribute(
        name="conda_channels",
        type="line-list",
        help="each line specifies a conda channel"
    )


def find_conda():

    # This should work if we're not already in an environment
    conda_exe = os.environ.get('_CONDA_EXE')
    if conda_exe:
        return conda_exe

    # This should work if we're in an active environment
    conda_exe = os.environ.get('CONDA_EXE')
    if conda_exe:
        return conda_exe

    # Try a simple fallback
    if sp.call(['conda', '-h'], stdout=sp.PIPE, stderr=sp.PIPE) == 0:
        return 'conda'

    raise RuntimeError("Can't locate conda executable")


@hookimpl
def tox_testenv_create(venv, action):

    venv.session.make_emptydir(venv.path)
    basepath = venv.path.dirpath()

    # Check for venv.envconfig.sitepackages and venv.config.alwayscopy here

    conda_exe = find_conda()
    venv.envconfig.conda_exe = conda_exe

    envdir = venv.envconfig.envdir
    python = get_py_version(venv.envconfig)

    args = [conda_exe, 'create', '--yes', '-p', envdir]
    for channel in venv.envconfig.conda_channels:
        args += ['--channel', channel]
    args += [python]
    venv._pcall(args, venv=False, action=action, cwd=basepath)

    venv.envconfig.conda_python = python

    return True


def install_conda_deps(venv, action, basepath, envdir):

    conda_exe = venv.envconfig.conda_exe
    conda_deps = venv.envconfig.conda_deps

    action.setactivity('installcondadeps', ', '.join(conda_deps))

    args = [conda_exe, 'install', '--yes', '-p', envdir]
    for channel in venv.envconfig.conda_channels:
        args += ['--channel', channel]
    # We include the python version in the conda requirements in order to make
    # sure that none of the other conda requirements inadvertently downgrade
    # python in this environment. If any of the requirements are in conflict
    # with the installed python version, installation will fail (which is what
    # we want).
    args += [venv.envconfig.conda_python] + conda_deps
    venv._pcall(args, venv=False, action=action, cwd=basepath)


@hookimpl
def tox_testenv_install_deps(venv, action):

    basepath = venv.path.dirpath()
    envdir = venv.envconfig.envdir

    if len(venv.envconfig.conda_deps) > 0:
        install_conda_deps(venv, action, basepath, envdir)

    # Install dependencies from pypi here
    tox.venv.tox_testenv_install_deps(venv=venv, action=action)

    return True
