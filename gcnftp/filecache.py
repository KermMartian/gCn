#!/usr/bin/python

# globalCALCnet FTP/Sandpaper Bridge: filecache.py
# Christopher Mitchell, 2011-2014
# Licensed under the BSD 3-Clause License (see LICENSE)

import sys
import string
import time
import os

from logging import *

# This class is responsible for cache files and information
# about those files for a certain amount of time. It is also
# responsible for cleaning up after XX time

class FileCache:
	def __init__(self,folder = "filecache",stale_time = 600):
		self.folder_ = os.path.dirname(os.path.realpath(__file__)) + '/' + folder
		self.staleTime_ = stale_time
		self.cachedItems_ = {}

		# Load existing items
		for filename in os.listdir(self.folder_):
			self.cachedItems_[filename] = [time.time() + self.staleTime_, self.folder_ + '/' + filename]

	def fetchFile(self,url):
		self.updateCache()

		url = self.pathMunge(url)
		if url in self.cachedItems_:
			log_info("fileCache: Cache hit for '%s' in '%s/'" % (url,self.folder_))
			self.cachedItems_[url][0] = time.time() + self.staleTime_
			return self.cachedItems_[url][1]
		log_info("fileCache: Cache miss for '%s' in '%s/'" % (url,self.folder_))
		return None

	def storeFile(self,url,data):
		self.updateCache()

		url = self.pathMunge(url)
		if url in self.cachedItems_:
			self.cachedItems_[url][0] = time.time() + self.staleTime_
			return self.cachedItems_[url][1]
		f = open(self.folder_ + '/' + url,"w")
		f.write(data)
		f.close()
		self.cachedItems_[url] = [time.time() + self.staleTime_, self.folder_ + '/' + url]
		return self.folder_ + '/' + url

	def updateCache(self):
		now = time.time()
		for path in self.cachedItems_.keys():
			if now > self.cachedItems_[path]:
				del self.cachedItems_[path]
				os.remove(path)

	def pathMunge(self, path):
		path = path.replace('.','_dPpX_')
		path = path.replace('/','_fSsX_')
		path = path.replace('\0','_nLlX_')
		return path
		

