#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import os

from setuptools import find_packages, setup


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding="utf-8").read()


setup(
    name="tox-conda",
    version="0.2.1",
    description="Tox plugin that provides integration with conda",
    long_description=read("README.rst"),
    author="Daniel R. D'Avella",
    author_email="ddavella@stsci.edu",
    maintainer="Oliver Bestwalter",
    maintainer_email="oliver@bestwalter.de",
    url="https://github.com/tox-dev/tox-conda",
    packages=find_packages(exclude=["tests"]),
    python_requires=">=3.3",
    install_requires=["tox>=3.8.1"],
    entry_points={"tox": ["conda = tox_conda.plugin"]},
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Framework :: tox",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
    ],
)
