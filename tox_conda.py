import os
import pluggy
from tox.venv import VirtualEnv

hookimpl = pluggy.HookimplMarker('tox')


def get_py_version(pystring):
    version = pystring[len('python'):]
    return "python={}".format(version)


@hookimpl
def tox_testenv_create(venv, action):

    venv.session.make_emptydir(venv.path)
    basepath = venv.path.dirpath()

    # Check for venv.envconfig.sitepackages and venv.config.alwayscopy here

    conda_exe = os.environ.get('CONDA_EXE')
    if not conda_exe:
        raise RuntimeError("Can't locate conda executable")

    envdir = venv.envconfig.envdir
    python = get_py_version(venv.envconfig.basepython)

    args = [conda_exe, 'create', '--yes', '-p', envdir, python]
    venv._pcall(args, venv=False, action=action, cwd=basepath)

    return True


@hookimpl
def tox_testenv_install_deps(venv, action):

    deps = venv.get_resolved_dependencies()
    print(deps)
