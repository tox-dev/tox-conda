import copy
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager

import pluggy
import py.path
import tox
from tox.config import DepConfig, DepOption, TestenvConfig
from tox.venv import VirtualEnv

hookimpl = pluggy.HookimplMarker("tox")


class CondaDepOption(DepOption):
    name = "conda_deps"
    help = "each line specifies a conda dependency in pip/setuptools format"


def postprocess_path_option(testenv_config, value):
    if value == testenv_config.config.toxinidir:
        return None
    return value


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


class CondaRunWrapper:
    """A functor that execute a command via conda run.

    It wraps popen so the command is executed in the context of an activated env.
    """

    CONDA_RUN_CMD_PREFIX = "{conda_exe} run --no-capture-output -p {envdir}"

    def __init__(self, venv, popen):
        self.__venv = venv
        self.__popen = popen

    def __call__(self, cmd_args, **kwargs):
        conda_run_cmd_prefix = self.CONDA_RUN_CMD_PREFIX.format(
            conda_exe=self.__venv.envconfig.conda_exe, envdir=self.__venv.envconfig.envdir
        )
        cmd_args = conda_run_cmd_prefix.split() + cmd_args
        return self.__popen(cmd_args, **kwargs)


@contextmanager
def conda_run(venv, action=None):
    """Run a command via conda run."""
    if action is None:
        initial_popen = venv.popen
        venv.popen = CondaRunWrapper(venv, initial_popen)
    else:
        initial_popen = action.via_popen
        action.via_popen = CondaRunWrapper(venv, initial_popen)

    yield

    if action is None:
        venv.popen = initial_popen
    else:
        action.via_popen = initial_popen


@hookimpl
def tox_addoption(parser):
    parser.add_testenv_attribute(
        name="conda_env",
        type="path",
        help="specify a conda environment.yml file",
        postprocess=postprocess_path_option,
    )
    parser.add_testenv_attribute(
        name="conda_spec",
        type="path",
        help="specify a conda spec-file.txt file",
        postprocess=postprocess_path_option,
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
    # needs to be updated before being used.

    # Set path to the conda executable because it cannot be determined once
    # an env has already been created.
    conda_exe = find_conda()

    for envconfig in config.envconfigs.values():
        # Make sure the right environment is activated. This works because we're
        # creating environments using the `-p/--prefix` option in `tox_testenv_create`
        envconfig.setenv["CONDA_DEFAULT_ENV"] = envconfig.setenv["TOX_ENV_DIR"]

        conda_deps = [DepConfig(str(name)) for name in envconfig.conda_deps]
        # Add the conda-spec.txt file to the end of the conda deps b/c any deps
        # after --file option(s) are ignored
        if envconfig.conda_spec is not None:
            conda_deps.append(DepConfig("--file={}".format(envconfig.conda_spec)))
        envconfig.deps.extend(conda_deps)

        envconfig.conda_exe = conda_exe


def find_conda():
    # This should work if we're not already in an environment
    conda_exe = os.environ.get("_CONDA_EXE")
    if conda_exe:
        return conda_exe

    # This should work if we're in an active environment
    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe:
        return conda_exe

    path = shutil.which("conda")

    try:
        subprocess.check_call([str(path), "-h"])
    except subprocess.CalledProcessError:
        raise RuntimeError("Can't locate conda executable")

    return path


@hookimpl
def tox_testenv_create(venv, action):
    tox.venv.cleanup_for_venv(venv)
    basepath = venv.path.dirpath()

    # Check for venv.envconfig.sitepackages and venv.config.alwayscopy here
    envdir = venv.envconfig.envdir
    python = get_py_version(venv.envconfig, action)

    if venv.envconfig.conda_env is not None:
        # conda env create does not have a --channel argument nor does it take
        # dependencies specifications (e.g., python=3.8). These must all be specified
        # in the conda-env.yml file
        args = [
            venv.envconfig.conda_exe,
            "env",
            "create",
            "-p",
            envdir,
            "--file",
            venv.envconfig.conda_env,
        ]
    else:
        args = [venv.envconfig.conda_exe, "create", "--yes", "-p", envdir]
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
    # Account for the fact that we have a list of DepOptions
    conda_deps = [str(dep.name) for dep in venv.envconfig.conda_deps]
    # Add the conda-spec.txt file to the end of the conda deps b/c any deps
    # after --file option(s) are ignored
    if venv.envconfig.conda_spec is not None:
        conda_deps.append("--file={}".format(venv.envconfig.conda_spec))

    action.setactivity("installcondadeps", ", ".join(conda_deps))

    # Install quietly to make the log cleaner
    args = [venv.envconfig.conda_exe, "install", "--quiet", "--yes", "-p", envdir]
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
    # Save the deps before we make temporary changes.
    saved_deps = copy.deepcopy(venv.envconfig.deps)

    num_conda_deps = len(venv.envconfig.conda_deps)
    if venv.envconfig.conda_spec is not None:
        num_conda_deps += 1

    if num_conda_deps > 0:
        install_conda_deps(venv, action, venv.path.dirpath(), venv.envconfig.envdir)
        # Account for the fact that we added the conda_deps to the deps list in
        # tox_configure (see comment there for rationale). We don't want them
        # to be present when we call pip install.
        venv.envconfig.deps = venv.envconfig.deps[: -1 * num_conda_deps]

    if venv.envconfig.deps:
        # As of conda 4.10.1, the conda run command cannot parse a pip command
        # with conditions on the dependencies.
        # The direct dependencies are thus dumped in a temporary requirements file,
        # The dependencies declared in requirements and constraints files
        # are not because this does not work: their path are treated by pip as
        # relative to their parent requirements file directory.
        deps_files_lines = []
        deps_not_files = []

        for dep in venv.envconfig.deps:
            # The requirements and constraints files deps start with -r or -c.
            if dep.name.startswith("-"):
                deps_not_files += [dep]
            else:
                deps_files_lines += ["{}\n".format(dep)]

        venv.envconfig.deps = deps_not_files

        if deps_files_lines:
            # Dump the direct pypi deps to a requirements file.
            _, temp_req_filename = tempfile.mkstemp()

            with open(temp_req_filename, "w") as stream:
                stream.writelines(deps_files_lines)

            venv.envconfig.deps.append(tox.config.DepConfig("-r{}".format(temp_req_filename)))

    with conda_run(venv, action):
        tox.venv.tox_testenv_install_deps(venv=venv, action=action)

    # Restore the deps.
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


@hookimpl(hookwrapper=True)
def tox_runtest_pre(venv):
    with conda_run(venv):
        yield


@hookimpl
def tox_runtest(venv, redirect):
    with conda_run(venv):
        tox.venv.tox_runtest(venv, redirect)
    return True


@hookimpl(hookwrapper=True)
def tox_runtest_post(venv):
    with conda_run(venv):
        yield
