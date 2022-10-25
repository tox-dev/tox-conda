tox-conda
=========

.. image:: https://www.repostatus.org/badges/latest/wip.svg
   :alt: Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.
   :target: https://www.repostatus.org/#wip

.. image:: https://img.shields.io/pypi/v/tox-conda.svg
    :target: https://pypi.org/project/tox-conda
    :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/tox-conda.svg
    :target: https://pypi.org/project/tox-conda
    :alt: Python versions

.. image:: https://github.com/tox-dev/tox-conda/workflows/check/badge.svg
    :target: https://github.com/tox-dev/tox-conda/actions?query=workflow%3Acheck+branch%3Amaster
    :alt: CI

.. image:: https://codecov.io/gh/tox-dev/tox-conda/branch/master/graph/badge.svg?token=yYBhrEf4MN
    :target: https://codecov.io/gh/tox-dev/tox-conda
    :alt: Code coverage

``tox-conda`` is a plugin that provides integration with the `conda
<https://conda.io>`_ package and environment manager for the `tox
<https://tox.readthedocs.io>`__ automation tool. It's like having your cake and
eating it, too!

By default, ``tox`` creates isolated environments using `virtualenv
<https://virtualenv.pypa.io>`_ and installs dependencies from ``pip``.

In contrast, when using the ``tox-conda`` plugin ``tox`` will use ``conda`` to create
environments, and will install specified dependencies from ``conda``. This is
useful for developers who rely on ``conda`` for environment management and
package distribution but want to take advantage of the features provided by
``tox`` for test automation.

``tox-conda`` has not been tested with ``conda`` version below 4.5.

Getting Started
---------------

``tox-conda`` can be used in one of two ways: by installing it globally and by
enabling it on a per-project basis. When the plugin is installed globally, the
default behavior of ``tox`` will be to use ``conda`` to create environments. To
use it on a per-project basis instead, use ``tox``'s auto-provisioning feature
to selectively enable the plugin.

To enable the use of ``tox-conda`` by default, follow the `Installation`_
instructions. To use the plugin selectively, do not manually install it, but
instead enable it by adding ``tox-conda`` as a provisioning requirement to a
project's ``tox`` config:

::

    [tox]
    requires = tox-conda

More information on auto-provisioning can be found in the `tox documentation
<https://tox.readthedocs.io/en/latest/example/basic.html#tox-auto-provisioning>`__.

Installation
------------

The ``tox-conda`` package is available on ``pypi``. To install, simply use the
following command:

::

   $ pip install tox-conda

To install from source, first clone the project from `github
<https://github.com/tox-dev/tox-conda>`_:

::

   $ git clone https://github.com/tox-dev/tox-conda

Then install it in your environment:

::

   $ cd tox-conda
   $ pip install .

To install in `development
mode <https://packaging.python.org/tutorials/distributing-packages/#working-in-development-mode>`__::

   $ pip install -e .

The ``tox-conda`` plugin expects that ``tox`` and ``conda`` are already installed and
available in your working environment.

Usage
-----

Details on ``tox`` usage can be found in the `tox documentation
<https://tox.readthedocs.io>`_.

With the plugin enabled and no other changes, the ``tox-conda`` plugin will use
``conda`` to create environments and use ``pip`` to install dependencies that are
given in the ``tox.ini`` configuration file.

``tox-conda`` adds four additional (and optional) settings to the ``[testenv]``
section of configuration files:

* ``conda_deps``, which is used to configure which dependencies are installed
  from ``conda`` instead of from ``pip``. All dependencies in ``conda_deps`` are
  installed before all dependencies in ``deps``. If not given, no dependencies
  will be installed using ``conda``.

* ``conda_channels``, which specifies which channel(s) should be used for
  resolving ``conda`` dependencies. If not given, only the ``default`` channel will
  be used.

* ``conda_spec``, which specifies a ``conda-spec.txt`` file that lists conda
  dependencies to install and will be combined with ``conda_deps`` (if given). These
  dependencies can be in a general from (e.g., ``numpy>=1.17.5``) or an explicit
  form (eg., https://conda.anaconda.org/conda-forge/linux-64/numpy-1.17.5-py38h95a1406_0.tar.bz2),
  *however*, if the ``@EXPLICIT`` header is in ``conda-spec.txt``, *all* general
  dependencies will be ignored, including those given in ``conda_deps``.

* ``conda_env``, which specifies a ``conda-env.yml`` file to create a base conda
  environment for the test. The ``conda-env.yml`` file is self-contained and
  if the desired conda channels to use are not given, the default channels will be used.
  If the ``conda-env.yml`` specifies a python version it must be compatible with the ``basepython``
  set for the tox env. A ``conda-env.yml`` specifying ``python>=3.8`` could for example be
  used with ``basepython`` set to ``py38``, ``py39`` or ``py310``.
  The above ``conda_deps``, ``conda_channels``, and ``conda_spec`` arguments, if used in
  conjunction with a ``conda-env.yml`` file, will be used to *update* the environment *after* the
  initial environment creation.

* ``conda_create_args``, which is used to pass arguments to the command ``conda create``.
  The passed arguments are inserted in the command line before the python package.
  For instance, passing ``--override-channels`` will create more reproducible environments
  because the channels defined in the user's ``.condarc`` will not interfer.

* ``conda_install_args``, which is used to pass arguments to the command ``conda install``.
  The passed arguments are inserted in the command line before the dependencies.
  For instance, passing ``--override-channels`` will create more reproducible environments
  because the channels defined in the user's ``.condarc`` will not interfer.

* If `mamba <https://mamba.readthedocs.io>`_ is installed in the same environment as tox,
  you may use it instead of the ``conda`` executable by setting the environment variable
  ``CONDA_EXE=mamba`` in the shell where ``tox`` is called.

An example configuration file is given below:

::

   [tox]
   envlist =
       {py35,py36,py37}-{stable,dev}

   [testenv]
   deps=
       pytest-sugar
       py35,py36: importlib_resources
       dev: git+git://github.com/numpy/numpy
   conda_deps=
       pytest<=3.8
       stable: numpy=1.15
   conda_channels=
       conda-forge
   conda_install_args=
       --override-channels
   commands=
       pytest {posargs}

More information on ``tox`` configuration files can be found in the
`documentation <https://tox.readthedocs.io/en/latest/config.html>`_.

Contributing
------------
Contributions are very welcome. Tests can be run with `tox`_, please ensure
the coverage at least stays the same before you submit a pull request.

License
-------

Distributed under the terms of the `MIT`_ license, "tox-conda" is free and open source software

Issues
------

If you encounter any problems, please `file an issue`_ along with a detailed description.

.. _`Cookiecutter`: https://github.com/audreyr/cookiecutter
.. _`@obestwalter`: https://github.com/tox-dev
.. _`MIT`: http://opensource.org/licenses/MIT
.. _`BSD-3`: http://opensource.org/licenses/BSD-3-Clause
.. _`GNU GPL v3.0`: http://www.gnu.org/licenses/gpl-3.0.txt
.. _`Apache Software License 2.0`: http://www.apache.org/licenses/LICENSE-2.0
.. _`cookiecutter-tox-plugin`: https://github.com/tox-dev/cookiecutter-tox-plugin
.. _`file an issue`: https://github.com/tox-dev/tox-conda/issues
.. _`pytest`: https://github.com/pytest-dev/pytest
.. _`tox`: https://tox.readthedocs.io/en/latest/
.. _`pip`: https://pypi.org/project/pip/
.. _`PyPI`: https://pypi.org
