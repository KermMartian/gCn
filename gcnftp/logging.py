#!/usr/bin/python

# globalCALCnet FTP/Sandpaper Bridge: logging.py
# Christopher Mitchell, 2011-2014
# Licensed under the BSD 3-Clause License (see LICENSE)

import sys
import datetime

SHOWTIME = True

class bcolors:
    OKBLUE = '\033[94m'
    OKGREEN= '\033[92m'
    WARNING= '\033[93m'
    FAIL   = '\033[91m'
    ENDC   = '\033[0m'

def log_fatal(line):
    print rightnow() + bcolors.FAIL + "FATAL: " + str(line) + bcolors.ENDC
    sys.exit(-1)

def log_error(line):
    print rightnow() + bcolors.FAIL + "ERROR: " + str(line) + bcolors.ENDC

def log_info(line):
    print rightnow() + bcolors.OKGREEN + "INFO: " + bcolors.ENDC + str(line)

def log_warn(line):
    print rightnow() + bcolors.WARNING + "WARN: " + bcolors.ENDC + str(line)


def rightnow():
    if not(SHOWTIME):
        return ""
    return bcolors.OKBLUE + "[" + datetime.datetime.now().strftime("%H:%M:%S") + "]" + bcolors.ENDC + " "
