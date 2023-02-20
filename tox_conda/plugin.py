import copy
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from functools import partial


MISSING_CONDA_ERROR = "Cannot locate the conda executable."


import json
import os
import re
import shlex
import shutil
import subprocess
from io import BytesIO, TextIOWrapper
from pathlib import Path
from time import sleep
from typing import Any, Dict, List

from tox.execute.api import (
    Execute,
    ExecuteInstance,
    ExecuteOptions,
    ExecuteRequest,
    SyncWrite,
)
from tox.execute.local_sub_process import (
    LocalSubProcessExecuteInstance,
    LocalSubProcessExecutor,
)
from tox.plugin import impl
from tox.plugin.spec import EnvConfigSet, State, ToxEnvRegister, ToxParser
from tox.tox_env.api import StdinSource, ToxEnv, ToxEnvCreateArgs
from tox.tox_env.errors import Fail
from tox.tox_env.installer import Installer
from tox.tox_env.python.pip.pip_install import Pip
from tox.tox_env.python.virtual_env.runner import VirtualEnvRunner
from tox.tox_env.python.pip.req_file import PythonDeps


__all__ = []

class CondaEnvRunner(VirtualEnvRunner):
    def __init__(self, create_args: ToxEnvCreateArgs) -> None:
        self._installer = None
        self._executor = None
        self._created = False
        super().__init__(create_args)

    @staticmethod
    def id() -> str:  # noqa A003
        return "conda"

    def _get_python_env_version(self):
        # Try to use base_python config
        match = re.match(
            r"python(\d)(?:\.(\d+))?(?:\.?(\d))?", self.conf["base_python"][0]
        )
        if match:
            groups = match.groups()
            version = groups[0]
            if groups[1]:
                version += ".{}".format(groups[1])
            if groups[2]:
                version += ".{}".format(groups[2])
            return version
        else:
            return self.base_python.version_dot

    def create_python_env(self) -> None:
        conda_exe = find_conda()
        python_version = self._get_python_env_version()
        python = f"python={python_version}"

        cache_conf = self.python_cache()

        if "conda_env" in self.conf:
            env_path = Path(self.conf["conda_env"])
            # conda env create does not have a --channel argument nor does it take
            # dependencies specifications (e.g., python=3.8). These must all be specified
            # in the conda-env.yml file
            yaml = YAML()
            env_file = yaml.load(env_path)
            env_file["dependencies"].append(python)

            tmp_env = tempfile.NamedTemporaryFile(
                dir=env_path.parent,
                prefix="tox_conda_tmp",
                suffix=".yaml",
                delete=False,
            )
            yaml.dump(env_file, tmp_env)
            tmp_env.close()

            cmd = f"'{conda_exe}' create {cache_conf['conda_env_spec']} '{cache_conf['conda_env']}' --yes --quiet --file {tmp_env.name}"
            tear_down = lambda: Path(tmp_env.name).unlink()
        else:
            cmd = f"'{conda_exe}' create {cache_conf['conda_env_spec']} '{cache_conf['conda_env']}' {python} --yes --quiet"

        try:
            cmd_list = shlex.split(cmd)
            subprocess.run(cmd_list, check=True)
        except subprocess.CalledProcessError as e:
            raise Fail(
                f"Failed to create '{self.env_dir}' conda environment. Error: {e}"
            )
        finally:
            if tear_down:
                tear_down()

    def python_cache(self) -> Dict[str, Any]:
        base = super().python_cache()

        conda_name = getattr(self.options, "conda_name", None)
        if not conda_name and "conda_name" in self.conf:
            conda_name = self.conf["conda_name"]

        if conda_name:
            conda_env_spec = "-n"
            conda_env = conda_name
        else:
            conda_env_spec = "-p"
            conda_env = f"{self.env_dir}"

        base.update(
            {"conda_env_spec": conda_env_spec, "conda_env": conda_env},
        )
        return base

    @property
    def executor(self) -> Execute:
        def get_conda_command_prefix():
            conf = self.python_cache()
            return [
                "conda",
                "run",
                conf["conda_env_spec"],
                conf["conda_env"],
                "--live-stream",
            ]

        class CondaExecutor(LocalSubProcessExecutor):
            def build_instance(
                self,
                request: ExecuteRequest,
                options: ExecuteOptions,
                out: SyncWrite,
                err: SyncWrite,
            ) -> ExecuteInstance:
                conda_cmd = get_conda_command_prefix()

                conda_request = ExecuteRequest(
                    conda_cmd + request.cmd,
                    request.cwd,
                    request.env,
                    request.stdin,
                    request.run_id,
                    request.allow,
                )
                return LocalSubProcessExecuteInstance(conda_request, options, out, err)

        if self._executor is None:
            self._executor = CondaExecutor(self.options.is_colored)
        return self._executor

    @property
    def installer(self) -> Installer[Any]:
        if self._installer is None:
            self._installer = Pip(self)
        return self._installer

    def prepend_env_var_path(self) -> List[Path]:
        conda_exe: Path = find_conda()
        return [conda_exe.parent]

    def _default_pass_env(self) -> List[str]:
        env = super()._default_pass_env()
        env.append("*CONDA*")
        return env
    
    def env_site_package_dir(self) -> Path:
        """The site package folder within the tox environment."""
        cmd = 'from sysconfig import get_paths; print(get_paths()["purelib"])'
        path = self._call_python_in_conda_env(cmd, "env_site_package_dir")
        return Path(path).resolve()

    def env_python(self) -> Path:
        """The python executable within the tox environment."""
        cmd = "import sys; print(sys.executable)"
        path = self._call_python_in_conda_env(cmd, "env_python")
        return Path(path).resolve()

    def env_bin_dir(self) -> Path:
        """The binary folder within the tox environment."""
        cmd = 'from sysconfig import get_paths; print(get_paths()["scripts"])'
        path = self._call_python_in_conda_env(cmd, "env_bin_dir")
        return Path(path).resolve()

    def _call_python_in_conda_env(self, cmd: str, run_id: str):
        self._ensure_python_env_exists()

        python_cmd = "python -c".split()

        class NamedBytesIO(BytesIO):
            def __init__(self, name):
                self.name = name
                super().__init__()

        out_buffer = NamedBytesIO("output")
        out = TextIOWrapper(out_buffer, encoding="utf-8")

        err_buffer = NamedBytesIO("error")
        err = TextIOWrapper(err_buffer, encoding="utf-8")

        out_err = out, err

        request = ExecuteRequest(
            python_cmd + [cmd],
            self.conf["change_dir"],
            self.environment_variables,
            StdinSource.API,
            run_id,
        )

        with self.executor.call(request, True, out_err, self) as execute_status:
            while execute_status.wait() is None:
                sleep(0.01)
            if execute_status.exit_code != 0:
                raise Fail(
                    f"Failed to execute operation '{cmd}'. Stderr: {execute_status.err.decode()}"
                )

        return execute_status.out.decode().strip()

    def _ensure_python_env_exists(self) -> None:
        if not Path(self.env_dir).exists():
            self.create_python_env()
            self._created = True
            return

        if self._created:
            return

        conda_exe = find_conda()
        cmd = f"'{conda_exe}' env list --json"
        try:
            cmd_list = shlex.split(cmd)
            result: subprocess.CompletedProcess = subprocess.run(
                cmd_list, check=True, capture_output=True
            )
        except subprocess.CalledProcessError as e:
            raise Fail(f"Failed to list conda environments. Error: {e}")
        envs = json.loads(result.stdout.decode())
        if str(self.env_dir) in envs["envs"]:
            self._created = True
        else:
            raise Fail(
                f"{self.env_dir} already exists, but it is not a conda environment. Delete in manually first."
            )


@impl
def tox_register_tox_env(register: ToxEnvRegister) -> None:  # noqa: U100
    register.add_run_env(CondaEnvRunner)
    try:
        # Change the defaukt runner only if conda is available
        find_conda()
        if "CONDA_DEFAULT_ENV" in os.environ:
            register.default_env_runner = "conda"
    except Fail:
        pass


def postprocess_path_option(testenv_config, value):
    if value == testenv_config.config.toxinidir:
        return None
    return value


@impl
def tox_add_env_config(env_conf: EnvConfigSet, state: State) -> None:
    env_conf.add_config(
        "conda_name",
        of_type=str,
        desc="Specifies the name of the conda environment. By default, .tox/<name> is used.",
        default=None
    )

    env_conf.add_config(
        "conda_env",
        of_type="path",
        desc="specify a conda environment.yml file",
        default=None,
        post_process=postprocess_path_option,
    )
    
    env_conf.add_config(
        "conda_spec",
        of_type="path",
        desc="specify a conda spec-file.txt file",
        default=None,
        post_process=postprocess_path_option,
    )

    root = env_conf._conf.core["tox_root"]
    env_conf.add_config(
        "conda_deps",
        of_type=PythonDeps,
        factory=partial(PythonDeps.factory, root),
        default=PythonDeps("", root),
        desc="each line specifies a conda dependency in pip/setuptools format",
    )

    env_conf.add_config(
        "conda_channels", of_type="line-list", desc="each line specifies a conda channel", default=None,
    )

    env_conf.add_config(
        "conda_install_args",
        of_type="line-list",
        desc="each line specifies a conda install argument",default=None,
    )

    env_conf.add_config(
        "conda_create_args",
        of_type="line-list",
        desc="each line specifies a conda create argument",default=None,
    )


# @hookimpl
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
        # Append filenames of additional dependency sources. tox will automatically hash
        # their contents to detect changes.
        if envconfig.conda_spec is not None:
            conda_deps.append(DepConfig(envconfig.conda_spec))
        if envconfig.conda_env is not None:
            conda_deps.append(DepConfig(envconfig.conda_env))
        envconfig.deps.extend(conda_deps)

        envconfig.conda_exe = conda_exe


def find_conda() -> Path:
    # This should work if we're not already in an environment
    conda_exe = os.environ.get("_CONDA_EXE")
    if conda_exe:
        return Path(conda_exe).resolve()

    # This should work if we're in an active environment
    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe:
        return Path(conda_exe).resolve()

    conda_exe = shutil.which("conda")
    if conda_exe:
        conda_exe = Path(conda_exe).resolve()
        try:
            subprocess.run([str(conda_exe), "-h"], stdout=subprocess.DEVNULL)
            return conda_exe
        except subprocess.CalledProcessError:
            pass

    raise Fail("Failed to find 'conda' executable.")


def _run_conda_process(args, venv, action, cwd):
    redirect = tox.reporter.verbosity() < tox.reporter.Verbosity.DEBUG
    venv._pcall(args, venv=False, action=action, cwd=cwd, redirect=redirect)


# @hookimpl
def tox_testenv_create(venv, action):
    tox.venv.cleanup_for_venv(venv)
    basepath = venv.path.dirpath()

    # Check for venv.envconfig.sitepackages and venv.config.alwayscopy here
    envdir = venv.envconfig.envdir
    python = get_py_version(venv.envconfig, action)

    if venv.envconfig.conda_env is not None:
        env_path = Path(venv.envconfig.conda_env)
        # conda env create does not have a --channel argument nor does it take
        # dependencies specifications (e.g., python=3.8). These must all be specified
        # in the conda-env.yml file
        yaml = YAML()
        env_file = yaml.load(env_path)
        env_file["dependencies"].append(python)

        tmp_env = tempfile.NamedTemporaryFile(
            dir=env_path.parent,
            prefix="tox_conda_tmp",
            suffix=".yaml",
            delete=False,
        )
        yaml.dump(env_file, tmp_env)

        args = [
            venv.envconfig.conda_exe,
            "env",
            "create",
            "-p",
            envdir,
            "--file",
            tmp_env.name,
        ]
        tmp_env.close()
        _run_conda_process(args, venv, action, basepath)
        Path(tmp_env.name).unlink()

    else:
        args = [venv.envconfig.conda_exe, "create", "--yes", "-p", envdir]
        for channel in venv.envconfig.conda_channels:
            args += ["--channel", channel]

        # Add end-user conda create args
        args += venv.envconfig.conda_create_args

        args += [python]

        _run_conda_process(args, venv, action, basepath)

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

    _run_conda_process(args, venv, action, basepath)


# @hookimpl
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
    if venv.envconfig.conda_env is not None:
        num_conda_deps += 1
    if num_conda_deps > 0:
        venv.envconfig.deps = venv.envconfig.deps[:-num_conda_deps]

    with activate_env(venv, action):
        tox.venv.tox_testenv_install_deps(venv=venv, action=action)

    # Restore the deps.
    venv.envconfig.deps = saved_deps

    return True


# @hookimpl
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


# TestenvConfig.__get_envpython = TestenvConfig.get_envpython
# TestenvConfig.get_envpython = get_envpython


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


# VirtualEnv._venv_lookup = venv_lookup


# @hookimpl(hookwrapper=True)
def tox_runtest_pre(venv):
    with activate_env(venv):
        yield


# @hookimpl
def tox_runtest(venv, redirect):
    with activate_env(venv):
        tox.venv.tox_runtest(venv, redirect)
    return True


# @hookimpl(hookwrapper=True)
def tox_runtest_post(venv):
    with activate_env(venv):
        yield
