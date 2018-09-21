import os
import pluggy

import tox.venv
from tox.venv import VirtualEnv

hookimpl = pluggy.HookimplMarker('tox')


def get_py_version(pystring):
    version = pystring[len('python'):]
    return "python={}".format(version)


def parse_condition(dependency):
    components = [x.strip() for x in dependency.split(':')]
    if len(components) > 1:
        conditions, requirement = components[0], components[1]
    else:
        conditions, requirement = '', components[0]

    return conditions.split(','), requirement


@hookimpl
def tox_configure(config):

    # Make sure that each testenv has these attributes no matter what
    for _, envconfig in config.envconfigs.items():
        envconfig.conda_deps = []
        envconfig.conda_channels = []

    conda_str = config._cfg.get('testenv', 'conda')
    config.has_conda_deps = bool(conda_str)
    if not conda_str:
        return True

    deps = conda_str.split('\n')
    channel_str = config._cfg.get('testenv', 'channels')
    channels = channel_str.split('\n') if channel_str else None

    for name, envconfig in config.envconfigs.items():
        conda_deps = set()
        conda_channels = set()

        for dep in deps:
            conditions, requirement = parse_condition(dep)
            for cond in conditions:
                if cond == '' or cond in name:
                    conda_deps.add(requirement)

        for chan in channels:
            conditions, channel = parse_condition(chan)
            for cond in conditions:
                if cond == '' or cond in name:
                    conda_channels.add(channel)

        envconfig.conda_deps = list(conda_deps)
        envconfig.conda_channels = list(conda_channels)

    return True


@hookimpl
def tox_testenv_create(venv, action):

    venv.session.make_emptydir(venv.path)
    basepath = venv.path.dirpath()

    # Check for venv.envconfig.sitepackages and venv.config.alwayscopy here

    conda_exe = os.environ.get('CONDA_EXE')
    if not conda_exe:
        raise RuntimeError("Can't locate conda executable")

    venv.envconfig.conda_exe = conda_exe

    envdir = venv.envconfig.envdir
    python = get_py_version(venv.envconfig.basepython)

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

    if venv.envconfig.config.has_conda_deps and len(venv.envconfig.conda_deps) > 0:
        install_conda_deps(venv, action, basepath, envdir)

    # Install dependencies from pypi here
    tox.venv.tox_testenv_install_deps(venv=venv, action=action)

    return True
