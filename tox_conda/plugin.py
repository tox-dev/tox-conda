import logging
import os
import sys
from warnings import warn

import pluggy

hookimpl = pluggy.HookimplMarker("tox")
log = logging.getLogger('conda')


on_win = bool(sys.platform == "win32")


@hookimpl
def tox_get_python_executable(envconfig):

    if on_win:
        return os.path.join(envconfig.envdir, "python.exe")
    else:
        return os.path.join(envconfig.envdir, "python")

    return True


@hookimpl
def tox_configure(config):
    envs = config.envlist[:]
    for env in envs:
        envconfig = config.envconfigs[env]

        basepython = envconfig.basepython
        if not basepython.startswith("python"):
            msg = "Skipping {0}. The conda plugin only supports python basepython.".format(
                env
            )
            warn(RuntimeWarning(msg))
            config.envconfigs.pop(env)
            config.envlist.remove(env)
            continue

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

        if envconfig.conda_deps and not hasattr(envconfig, "channels"):
            envconfig.channels = ["defaults"]

        create_env_yml(envconfig)


@hookimpl
def tox_testenv_create(venv, action):
    """Perform creation action for this venv."""

    env_location = str(venv.path)
    yaml = venv.envconfig.envyaml

    args = ["conda", "env", "update", "-p", env_location, "--file", yaml]
    # Extend conda environment creation with conda dependencies right away.
    redirect = venv.session.config.option.verbose_level < 2
    result = action.popen(args, redirect=redirect)

    return True if result is None else result


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
        - channels
        - conda_deps
        - deps (pip)

    It will store the filepath of the environment.yaml in envconfig.envyaml.
    """

    lines = ["name: " + envconfig.envname]

    lines.append("channels:")
    for channel in envconfig.channels:
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

    os.makedirs(envconfig.envdir, exist_ok=True)
    file_path = os.path.join(envconfig.envdir, envconfig.envname + ".yml")
    envconfig.envyaml = file_path

    with open(file_path, "w") as f:
        f.writelines(lines)
