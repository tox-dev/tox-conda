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

.. image:: https://travis-ci.org/tox-dev/tox-conda.svg?branch=master
    :target: https://travis-ci.org/tox-dev/tox-conda
    :alt: See Build Status on Travis CI

.. image:: https://ci.appveyor.com/api/projects/status/github/tox-dev/tox-conda?branch=master
    :target: https://ci.appveyor.com/project/tox-dev/tox-conda/branch/master
    :alt: See Build Status on AppVeyor

``tox-conda`` is a plugin that provides integration with the `conda
<https://conda.io>`_ package and environment manager for the `tox
<https://tox.readthedocs.io>`__ automation tool. It's like having your cake and
eating it, too!

By default, ``tox`` creates isolated environments using `virtualenv
<https://virtualenv.pypa.io>`_ and installs dependencies from ``pip``.

With the ``tox-conda`` plugin, ``tox`` can be configured to use ``conda`` to
create environments, and will install specified dependencies from ``conda``.
This is useful for developers who rely on ``conda`` for environment management
and package distribution but want to take advantage of the features provided by
``tox`` for test automation.

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

With the plugin installed, ``tox-conda`` plugin enables using ``conda`` to create
environments and/or to install dependencies.

``tox-conda`` adds three additional (and optional) settings to the ``[testenv]``
section of configuration files:

* ``conda_deps``, which is used to configure which dependencies are installed
  from ``conda`` instead of from ``pip``. All dependencies in ``conda_deps`` are
  installed before all dependencies in ``deps``. If not given, no dependencies
  will be installed using ``conda``.

* ``conda_channels``, which specifies which channel(s) should be used for
  resolving ``conda`` dependencies. If not given, only the ``default`` channel will
  be used.

* ``conda_env``, which can be used to explicitly create environments using ``conda``,
  even if ``conda_deps`` is missing. If ``conda_deps`` is present, it takes precedence
  over ``conda_env`` and ``conda`` will be used for environment creation. Defaults to
  ``False``.

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
