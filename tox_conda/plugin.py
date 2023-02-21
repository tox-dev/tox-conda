import copy
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from functools import partial
from io import BytesIO, TextIOWrapper
from pathlib import Path
from time import sleep
from typing import Any, Dict, List

from ruamel.yaml import YAML

from tox.execute.api import Execute, ExecuteInstance, ExecuteOptions, ExecuteRequest, SyncWrite
from tox.execute.local_sub_process import LocalSubProcessExecuteInstance, LocalSubProcessExecutor
from tox.plugin import impl
from tox.plugin.spec import EnvConfigSet, State, ToxEnvRegister
from tox.tox_env.api import StdinSource, ToxEnvCreateArgs
from tox.tox_env.errors import Fail
from tox.tox_env.installer import Installer
from tox.tox_env.python.pip.pip_install import Pip
from tox.tox_env.python.pip.req_file import PythonDeps
from tox.tox_env.python.virtual_env.runner import VirtualEnvRunner

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
        match = re.match(r"python(\d)(?:\.(\d+))?(?:\.?(\d))?", self.conf["base_python"][0])
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

    def python_cache(self) -> Dict[str, Any]:
        conda_dict = {}

        conda_name = getattr(self.options, "conda_name", None)
        if not conda_name:
            conda_name = self.conf["conda_name"]

        if conda_name:
            conda_dict["env_spec"] = "-n"
            conda_dict["env"] = conda_name
        elif self.conf["conda_env"]:
            conda_dict["env_spec"] = "-n"
            env_path = Path(self.conf["conda_env"]).resolve()
            env_file = YAML().load(env_path)
            conda_dict["env"] = env_file["name"]
            conda_dict["env_path"] = str(env_path)
            conda_dict["env_hash"] = hash_file(Path(self.conf["conda_env"]).resolve())
        else:
            conda_dict["env_spec"] = "-p"
            conda_dict["env"] = str(self.env_dir)

        _, conda_deps = self.conf["conda_deps"].unroll()
        if conda_deps:
            conda_dict["deps"] = conda_deps

        conda_spec = self.conf["conda_spec"]
        if conda_spec:
            conda_dict["spec"] = conda_spec
            conda_dict["spec_hash"] = hash_file(Path(conda_spec).resolve())

        conda_channels = self.conf["conda_channels"]
        if conda_channels:
            conda_dict["channels"] = conda_channels

        conda_install_args = self.conf["conda_install_args"]
        if conda_install_args:
            conda_dict["install_args"] = conda_install_args

        conda_create_args = self.conf["conda_create_args"]
        if conda_create_args:
            conda_dict["create_args"] = conda_create_args

        base = super().python_cache()
        base.update(
            {"conda": conda_dict},
        )
        return base

    def create_python_env(self) -> None:
        conda_exe = find_conda()
        python_version = self._get_python_env_version()
        python = f"python={python_version}"
        conda_cache_conf = self.python_cache()["conda"]

        if self.conf["conda_env"]:
            create_command, tear_down = CondaEnvRunner._generate_env_create_command(
                conda_exe, python, conda_cache_conf
            )
        else:
            create_command, tear_down = CondaEnvRunner._generate_create_command(
                conda_exe, python, conda_cache_conf
            )
        try:
            create_command_args = shlex.split(create_command)
            subprocess.run(create_command_args, check=True)
        except subprocess.CalledProcessError as e:
            raise Fail(f"Failed to create '{self.env_dir}' conda environment. Error: {e}")
        finally:
            tear_down()

        install_command = CondaEnvRunner._generate_install_command(
            conda_exe, python, conda_cache_conf
        )
        if install_command:
            try:
                install_command_args = shlex.split(install_command)
                subprocess.run(install_command_args, check=True)
            except subprocess.CalledProcessError as e:
                raise Fail(f"Failed to install dependencies in conda environment. Error: {e}")

    @staticmethod
    def _generate_env_create_command(conda_exe, python, conda_cache_conf):
        env_path = Path(conda_cache_conf["env_path"]).resolve()
        # conda env create does not have a --channel argument nor does it take
        # dependencies specifications (e.g., python=3.8). These must all be specified
        # in the conda-env.yml file
        yaml = YAML()
        env_file = yaml.load(env_path)
        env_file["dependencies"].append(python)

        tmp_env_file = tempfile.NamedTemporaryFile(
            dir=env_path.parent,
            prefix="tox_conda_tmp",
            suffix=".yaml",
            delete=False,
        )
        yaml.dump(env_file, tmp_env_file)
        tmp_env_file.close()

        cmd = f"'{conda_exe}' env create --file '{tmp_env_file.name}' --quiet --force"
        tear_down = lambda: Path(tmp_env_file.name).unlink()

        return cmd, tear_down

    @staticmethod
    def _generate_create_command(conda_exe, python, conda_cache_conf):
        cmd = f"'{conda_exe}' create {conda_cache_conf['env_spec']} '{conda_cache_conf['env']}' {python} --yes --quiet"
        for arg in conda_cache_conf.get("create_args", []):
            cmd += f" '{arg}'"

        tear_down = lambda: None
        return cmd, tear_down

    @staticmethod
    def _generate_install_command(conda_exe, python, conda_cache_conf):
        # Check if there is anything to install
        if "deps" not in conda_cache_conf and "spec" not in conda_cache_conf:
            return None

        cmd = f"'{conda_exe}' install --quiet --yes {conda_cache_conf['env_spec']} '{conda_cache_conf['env']}'"
        for channel in conda_cache_conf.get("channels", []):
            cmd += f" --channel {channel}"

        # Add end-user conda install args
        for arg in conda_cache_conf.get("install_args", []):
            cmd += f" {arg}"

        # We include the python version in the conda requirements in order to make
        # sure that none of the other conda requirements inadvertently downgrade
        # python in this environment. If any of the requirements are in conflict
        # with the installed python version, installation will fail (which is what
        # we want).
        cmd += f" {python}"

        for dep in conda_cache_conf.get("deps", []):
            cmd += f" {dep}"

        if "spec" in conda_cache_conf:
            cmd += f" --file={conda_cache_conf['spec']}"

        return cmd

    @property
    def executor(self) -> Execute:
        def get_conda_command_prefix():
            conda_exe = find_conda()
            cache_conf = self.python_cache()
            cmd = f"'{conda_exe}' run {cache_conf['conda']['env_spec']} '{cache_conf['conda']['env']}' --live-stream"
            return shlex.split(cmd)

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


@impl
def tox_add_env_config(env_conf: EnvConfigSet, state: State) -> None:
    env_conf.add_config(
        "conda_name",
        of_type=str,
        desc="Specifies the name of the conda environment. By default, .tox/<name> is used.",
        default=None,
    )

    env_conf.add_config(
        "conda_env",
        of_type=str,
        desc="specify a conda environment.yml file",
        default=None,
    )

    env_conf.add_config(
        "conda_spec",
        of_type=str,
        desc="specify a conda spec-file.txt file",
        default=None,
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
        "conda_channels",
        of_type=List[str],
        desc="each line specifies a conda channel",
        default=None,
    )

    env_conf.add_config(
        "conda_install_args",
        of_type=List[str],
        desc="each line specifies a conda install argument",
        default=None,
    )

    env_conf.add_config(
        "conda_create_args",
        of_type=List[str],
        desc="each line specifies a conda create argument",
        default=None,
    )


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


def hash_file(file: Path) -> str:
    with open(file.name, "rb") as f:
        sha1 = hashlib.sha1()
        sha1.update(f.read())
        return sha1.hexdigest()
