import copy
import os
import re
import shutil

import pluggy
import py.path
import tox
from tox.config import DepConfig, DepOption, TestenvConfig
from tox.exception import InvocationError
from tox.venv import VirtualEnv

hookimpl = pluggy.HookimplMarker("tox")


class CondaDepOption(DepOption):
    name = "conda_deps"
    help = "each line specifies a conda dependency in pip/setuptools format"


def get_py_version(envconfig, action):
    # Try to use basepython
    match = re.match(r"python(\d)(?:\.(\d))?(?:\.?(\d))?", envconfig.basepython)
    if match:
        groups = match.groups()
        version = groups[0]
        if groups[1]:
            version += ".{}".format(groups[1])
        if groups[2]:
            version += ".{}".format(groups[2])

    # First fallback
    elif envconfig.python_info.version_info:
        version = "{}.{}".format(*envconfig.python_info.version_info[:2])

    # Second fallback
    else:
        code = "import sys; print('{}.{}'.format(*sys.version_info[:2]))"
        result = action.popen([envconfig.basepython, "-c", code], report_fail=True, returnout=True)
        version = result.decode("utf-8").strip()

    return "python={}".format(version)


@hookimpl
def tox_addoption(parser):
    parser.add_testenv_attribute(
        name="conda_env", type="path", help="specify a conda environment.yml file"
    )
    parser.add_testenv_attribute(
        name="conda_spec", type="path", help="specify a conda spec-file.txt file"
    )

    parser.add_testenv_attribute_obj(CondaDepOption())

    parser.add_testenv_attribute(
        name="conda_channels", type="line-list", help="each line specifies a conda channel"
    )

    parser.add_testenv_attribute(
        name="conda_install_args",
        type="line-list",
        help="each line specifies a conda install argument",
    )

    parser.add_testenv_attribute(
        name="conda_create_args",
        type="line-list",
        help="each line specifies a conda create argument",
    )


@hookimpl
def tox_configure(config):
    # This is a pretty cheesy workaround. It allows tox to consider changes to
    # the conda dependencies when it decides whether an existing environment
    # needs to be updated before being used
    for _, envconfig in config.envconfigs.items():
        # Make sure the right environment is activated. This works because we're
        # creating environments using the `-p/--prefix` option in `tox_testenv_create`
        envconfig.setenv["CONDA_DEFAULT_ENV"] = envconfig.setenv["TOX_ENV_DIR"]

        conda_deps = [DepConfig(str(name)) for name in envconfig.conda_deps]
        # Add the conda-spec.txt file to the end of the conda deps b/c any deps
        # after --file option(s) are ignored
        if envconfig.conda_spec:
            conda_deps.append(DepConfig("--file={}".format(envconfig.conda_spec)))
        envconfig.deps.extend(conda_deps)


def find_conda(action):
    # This should work if we're not already in an environment
    conda_exe = os.environ.get("_CONDA_EXE")
    if conda_exe:
        return conda_exe

    # This should work if we're in an active environment
    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe:
        return conda_exe

    try:
        path = shutil.which("conda")
        action.popen([path, "-h"], report_fail=True, returnout=False)
        return path
    except InvocationError:
        pass

    raise RuntimeError("Can't locate conda executable")


@hookimpl
def tox_testenv_create(venv, action):
    tox.venv.cleanup_for_venv(venv)
    basepath = venv.path.dirpath()

    # Check for venv.envconfig.sitepackages and venv.config.alwayscopy here
    conda_exe = find_conda(action)
    venv.envconfig.conda_exe = conda_exe

    envdir = venv.envconfig.envdir
    python = get_py_version(venv.envconfig, action)

    if venv.envconfig.conda_env:
        # conda env create does not have a --channel argument nor does it take
        # dependencies specifications (e.g., python=3.8). These must all be specified
        # in the conda-env.yml file
        args = [conda_exe, "env", "create", "-p", envdir, "--file", venv.envconfig.conda_env]
    else:
        args = [conda_exe, "create", "--yes", "-p", envdir]
        for channel in venv.envconfig.conda_channels:
            args += ["--channel", channel]

        # Add end-user conda create args
        args += venv.envconfig.conda_create_args

        args += [python]

    venv._pcall(args, venv=False, action=action, cwd=basepath)

    venv.envconfig.conda_python = python

    # let the venv know about the target interpreter just installed in our conda env, otherwise
    # we'll have a mismatch later because tox expects the interpreter to be existing outside of
    # the env
    try:
        del venv.envconfig.config.interpreters.name2executable[venv.name]
    except KeyError:
        pass
    venv.envconfig.config.interpreters.get_executable(venv.envconfig)

    return True


def install_conda_deps(venv, action, basepath, envdir):
    conda_exe = venv.envconfig.conda_exe
    # Account for the fact that we have a list of DepOptions
    conda_deps = [str(dep.name) for dep in venv.envconfig.conda_deps]
    # Add the conda-spec.txt file to the end of the conda deps b/c any deps
    # after --file option(s) are ignored
    if venv.envconfig.conda_spec:
        conda_deps.append("--file={}".format(venv.envconfig.conda_spec))

    action.setactivity("installcondadeps", ", ".join(conda_deps))

    # Install quietly to make the log cleaner
    args = [conda_exe, "install", "--quiet", "--yes", "-p", envdir]
    for channel in venv.envconfig.conda_channels:
        args += ["--channel", channel]

    # Add end-user conda install args
    args += venv.envconfig.conda_install_args

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
    # Save for later : we will need it for the config file
    saved_deps = copy.deepcopy(venv.envconfig.deps)

    num_conda_deps = len(venv.envconfig.conda_deps)
    if venv.envconfig.conda_spec:
        num_conda_deps += 1

    if num_conda_deps > 0:
        install_conda_deps(venv, action, basepath, envdir)
        # Account for the fact that we added the conda_deps to the deps list in
        # tox_configure (see comment there for rationale). We don't want them
        # to be present when we call pip install
        venv.envconfig.deps = venv.envconfig.deps[: -1 * num_conda_deps]

    # Install dependencies from pypi here
    tox.venv.tox_testenv_install_deps(venv=venv, action=action)
    # Restore for the config file
    venv.envconfig.deps = saved_deps
    return True


@hookimpl
def tox_get_python_executable(envconfig):
    if tox.INFO.IS_WIN:
        path = envconfig.envdir.join("python.exe")
    else:
        path = envconfig.envdir.join("bin", "python")
    if path.exists():
        return path


# Monkey patch TestenConfig get_envpython to fix tox behavior with tox-conda under windows
def get_envpython(self):
    """Override get_envpython to handle windows where the interpreter in at the env root dir."""
    original_envpython = self.__get_envpython()
    if original_envpython.exists():
        return original_envpython
    if tox.INFO.IS_WIN:
        return self.envdir.join("python")


TestenvConfig.__get_envpython = TestenvConfig.get_envpython
TestenvConfig.get_envpython = get_envpython


# Monkey patch TestenvConfig _venv_lookup to fix tox behavior with tox-conda under windows
def venv_lookup(self, name):
    """Override venv_lookup to also look at the env root dir under windows."""
    paths = [self.envconfig.envbindir]
    # In Conda environments on Windows, the Python executable is installed in
    # the top-level environment directory, as opposed to virtualenvs, where it
    # is installed in the Scripts directory. Tox assumes that looking in the
    # Scripts directory is sufficient, which is why this workaround is required.
    if tox.INFO.IS_WIN:
        paths += [self.envconfig.envdir]
    return py.path.local.sysfind(name, paths=paths)


VirtualEnv._venv_lookup = venv_lookup
