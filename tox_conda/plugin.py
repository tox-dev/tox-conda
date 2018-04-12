# -*- coding: utf-8 -*-

import logging

from tox import hookimpl

log = logging.getLogger('conda')


@hookimpl
def tox_addoption(parser):
    """Add a command line option for later use"""
    parser.add_argument(
        '--my-opt', action='store', help='my custom option')


@hookimpl
def tox_configure(config):
    """Access your option during configuration"""
    log.info("my option is: '%s'", config.option.my_opt)
