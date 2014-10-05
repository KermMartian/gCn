#!/usr/bin/python

# globalCALCnet FTP/Sandpaper Bridge: doupdate.py
# Christopher Mitchell, 2011-2014
# Licensed under the BSD 3-Clause License (see LICENSE)

from calcrepo.ticalc import *
repo = TicalcRepository("ticalc", "http://www.ticalc.org")
repo.updateRepoIndexes(True)
