import logging
import os
import sys
import shutil
from warnings import warn

import pluggy

hookimpl = pluggy.HookimplMarker("tox")
log = logging.getLogger("conda")


on_win = bool(sys.platform == "win32")


@hookimpl
def tox_addoption(parser):
    parser.add_testenv_attribute(
        name="conda_channels",
        type="line-list",
        default=("defaults"),
        help="Conda channels for environment creation.",
    )


@hookimpl
def tox_get_python_executable(envconfig):
    """Return a python executable for the given python base name."""
    if on_win:
        return os.path.join(envconfig.envdir, "python.exe")
    else:
        return os.path.join(envconfig.envdir, "python")

    return True


@hookimpl
def tox_configure(config):
    """Called after command line options are parsed and ini-file has been read."""

    # Directory to store conda files.
    config.conda_workdir = os.path.join(config.toxworkdir, "conda")

    # Override getting python executable.
    envconfig_class = type(config.envconfigs[config.envlist[0]])
    envconfig_class.get_envpython = get_conda_python

    # Set testenv configurations.
    envs = config.envlist[:]
    for env in envs:
        # Get envconfig for this env
        envconfig = config.envconfigs[env]

        # Only set conda to True for supported Python versions, others are created normally.
        basepython = envconfig.basepython
        if not basepython.startswith("python"):
            msg = "{0} will not be created using conda, only Python basepython is supported by tox-conda.".format(
                env
            )
            warn(RuntimeWarning(msg))
            envconfig.conda = False
            continue
        envconfig.conda = True

        # Split Conda dependencies from pip dependencies.
        python_version = basepython[6:]
        conda_deps = ["python={0}".format(python_version)]
        pip_deps = []
        for dep in envconfig.deps:
            dep_str = str(dep)
            if dep_str.startswith(("-r", "-e", "-c", ":")):
                pip_deps.append(dep)
            elif dep_str.startswith("--pip"):
                dep.name = dep_str[5:].strip()
                pip_deps.append(dep)
            else:
                conda_deps.append(dep)

        envconfig.deps = pip_deps
        envconfig.conda_deps = conda_deps

        create_env_yml(envconfig)


@hookimpl
def tox_testenv_create(venv, action):
    """Perform creation action for this venv."""

    if not venv.envconfig.conda:
        return None

    env_location = str(venv.path)
    yaml = venv.envconfig.conda_envyaml
    redirect = venv.session.config.option.verbose_level < 2
    result = []

    # Remove old environment if recreating.
    if venv.envconfig.recreate:
        if os.path.exists(env_location):
            shutil.rmtree(env_location)

    # Create new environment.
    args = ["conda", "env", "update", "-p", env_location, "--file", yaml]
    result.append(action.popen(args, redirect=redirect))

    return True if not result else result


@hookimpl
def tox_testenv_install_deps(venv, action):
    """Perform install dependencies action for this venv."""
    # If created using conda, all pip dependencies are already installed at creation.
    if venv.envconfig.conda:
        return True


def get_conda_python(envconfig):
    return os.path.join(envconfig.envdir, "python")


def is_exe(fpath):
    """Check whether a filepath points to an executable."""
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)


def which(cmd):
    """Try to find command on path and return full path if found."""
    fpath, fname = os.path.split(cmd)
    if fpath:
        if is_exe(cmd):
            return cmd
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, cmd)
            if is_exe(exe_file):
                return exe_file

    return None


def create_env_yml(envconfig):
    """Create a conda environment.yaml file from an envconfig.

    envconfig should contain the following properties:
        - envname
        - conda_channels
        - conda_deps
        - deps (pip)

    It will store the filepath of the environment.yaml in envconfig.envyaml.
    """

    lines = ["name: " + envconfig.envname]

    if envconfig.conda_channels:
        lines.append("channels:")
        for channel in envconfig.conda_channels:
            lines.append("  - {0}".format(channel))

    lines.append("dependencies:")
    if envconfig.conda_deps:
        for dep in envconfig.conda_deps:
            lines.append("  - {0}".format(dep))

    if envconfig.deps:
        lines.append("  - pip:")
        for dep in envconfig.deps:
            lines.append("    - {0}".format(dep))

    # Add line breaks to all lines.
    lines = [line + "\n" for line in lines]

    # Write environment.yaml and store location in envconfig.
    file_path = os.path.join(envconfig.config.conda_workdir, envconfig.envname + ".yml")
    envconfig.conda_envyaml = file_path
    os.makedirs(envconfig.config.conda_workdir, exist_ok=True)

    with open(file_path, "w") as f:
        f.writelines(lines)
