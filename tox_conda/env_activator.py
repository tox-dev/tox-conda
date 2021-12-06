"""Wrap the tox command for subprocess to activate the target anaconda env."""
import abc
import os
import pipes
import tempfile
from contextlib import contextmanager

import tox


class PopenInActivatedEnvBase(abc.ABC):
    """A functor that calls popen in an activated anaconda env."""

    def __init__(self, venv, popen):
        self._venv = venv
        self.__popen = popen

    def __call__(self, cmd_args, **kwargs):
        wrapped_cmd_args = self._wrap_cmd_args(cmd_args)
        return self.__popen(wrapped_cmd_args, **kwargs)

    @abc.abstractmethod
    def _wrap_cmd_args(self, cmd_args):
        ...


class PopenInActivatedEnvPosix(PopenInActivatedEnvBase):
    """Call popen in an activated anaconda env on POSIX platforms.

    The command to be executed are written to a temporary shell script.
    The shell script first activates the env.
    """

    def __init__(self, venv, popen):
        super().__init__(venv, popen)
        self.__tmp_file = None

    def _wrap_cmd_args(self, cmd_args):
        conda_activate_cmd = "eval $({conda_exe} shell.posix activate {envdir})".format(
            conda_exe=self._venv.envconfig.conda_exe, envdir=self._venv.envconfig.envdir
        )

        # Get a temporary file path.
        with tempfile.NamedTemporaryFile() as fp:
            self.__tmp_file = fp.name

        cmd_args_shell = " ".join(map(pipes.quote, cmd_args))

        with open(self.__tmp_file, "w") as fp:
            fp.writelines((conda_activate_cmd, "\n", cmd_args_shell))

        return ["/bin/sh", self.__tmp_file]

    def __del__(self):
        # Delete the eventual temporary script.
        if self.__tmp_file is not None:
            os.remove(self.__tmp_file)


class PopenInActivatedEnvWindows(PopenInActivatedEnvBase):
    """Call popen in an activated anaconda env on Windows.

    The shell is temporary forced to cmd.exe and the env is activated accordingly.
    """

    def __call__(self, cmd_args, **kwargs):
        # Backup COMSPEC before setting it to cmd.exe.
        old_comspec = os.environ.get("COMSPEC")
        self.__ensure_comspecs_is_cmd_exe()

        output = super().__call__(cmd_args, **kwargs)

        # Revert COMSPEC to its initial value.
        if old_comspec is None:
            del os.environ["COMSPEC"]
        else:
            os.environ["COMSPEC"] = old_comspec

        return output

    def _wrap_cmd_args(self, cmd_args):
        conda_activate_cmd = "conda.bat activate {envdir}".format(
            envdir=self._venv.envconfig.envdir
        )
        return conda_activate_cmd.split() + ["&&"] + cmd_args

    def __ensure_comspecs_is_cmd_exe(self):
        if os.path.basename(os.environ.get("COMSPEC", "")).lower() == "cmd.exe":
            return

        for env_var in ("SystemRoot", "windir"):
            root_path = os.environ.get(env_var)
            if root_path is None:
                continue
            cmd_exe = os.path.join(root_path, "System32", "cmd.exe")
            if os.path.isfile(cmd_exe):
                os.environ["COMSPEC"] = cmd_exe
                break
        else:
            tox.reporter.error("cmd.exe cannot be found")
            raise SystemExit(0)


if tox.INFO.IS_WIN:
    PopenInActivatedEnv = PopenInActivatedEnvWindows
else:
    PopenInActivatedEnv = PopenInActivatedEnvPosix


@contextmanager
def activate_env(venv, action=None):
    """Run a command in a temporary activated anaconda env."""
    # Backup popen before setting it with the one in an activated env.
    if action is None:
        initial_popen = venv.popen
        venv.popen = PopenInActivatedEnv(venv, initial_popen)
    else:
        initial_popen = action.via_popen
        action.via_popen = PopenInActivatedEnv(venv, initial_popen)

    yield

    # Revert popen to its initial value.
    if action is None:
        venv.popen = initial_popen
    else:
        action.via_popen = initial_popen
