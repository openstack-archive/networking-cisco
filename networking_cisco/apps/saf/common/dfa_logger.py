# Copyright 2015 Cisco Systems, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#


"""DFA logging helper module."""


import logging
import logging.handlers as log_hdlr
import os
import sys

# Rotating file size limit.
ONEK = 1024
ONEMEG = (1024 * 1024)
MAX_BYTES = (5 * ONEMEG)
BACKUP_COUNT = 10
DAYS = 'D'
SECONDS = 'S'
MINUTES = 'M'
HOURS = 'H'
MIDNIGHT = 'MIDNIGHT'

LOG_LEVELS = {'debug': logging.DEBUG,
              'info': logging.INFO,
              'warning': logging.WARNING,
              'error': logging.ERROR,
              'critical': logging.CRITICAL}

_loggers = {}


def getLogger(name):
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    _loggers[name] = logger

    return logger


def setup_logger(project, cfg):

    if _loggers.get(project):
        return

    logger = getLogger(None)

    # Set logging level.
    level = LOG_LEVELS.get(cfg.dfa_log.log_level.lower(), logging.WARNING)
    logger.setLevel(level)

    # Set default log levels for specified modules.
    def_log_levels = cfg.dfa_log.default_log_levels
    for dll in def_log_levels.split(','):
        mod, sep, lvl = dll.partition('=')
        level = LOG_LEVELS.get(lvl.lower(), logging.WARNING)
        logging.getLogger(mod).setLevel(level)

    # Set log file path name.
    log_dir = cfg.dfa_log.log_dir
    log_file = cfg.dfa_log.log_file
    if log_dir and log_file:
        try:
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
        except OSError:
            pass
        else:
            log_file_path = os.path.join(log_dir, log_file)
            handler = log_hdlr.TimedRotatingFileHandler(log_file_path,
                                                        when=DAYS,
                                                        interval=1)
    else:
        handler = logging.StreamHandler(sys.stdout)

    if cfg.dfa_log.use_syslog.lower() == 'true':
        log_fac = cfg.dfa_log.syslog_log_facility
        facility = getattr(log_hdlr.SysLogHandler, log_fac, None)
        handler = log_hdlr.SysLogHandler(address='/dev/log',
                                         facility=facility)

    # Setting log format.
    log_format = cfg.dfa_log.log_format
    date_fowrmat = cfg.dfa_log.log_date_format
    formatter = logging.Formatter(fmt=log_format, datefmt=date_fowrmat)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    _loggers[project] = logger
