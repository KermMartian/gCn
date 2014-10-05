import copy
import os
import tarfile
import urllib2
import zipfile

from calcrepo import index
from calcrepo import output

class CalcRepository:
	"""A class for adding new calcpkg repositories"""
	
	def __init__(self, name, url):
		self.name = name
		self.url = url
		
		self.output = output.CalcpkgOutput(True, False)
		self.index = index.Index(self)
		
		self.searchString = ""
		self.category = ""
		self.extension = ""
		self.math = False
		self.game = False
		self.searchFiles = False
		
		self.downloadDir = os.path.join(os.path.expanduser("~"), "Downloads", "")
		self.data = None
		
	def __repr__(self):
		return self.name + " at " + self.url
		
	def __str__(self):
		return self.name + " at " + self.url

	def setRepoData(self, searchString, category="", extension="", math=False, game=False, searchFiles=False):
		"""Call this function with all the settings to use for future operations on a repository, must be called FIRST"""
		self.searchString = searchString
		self.category = category
		self.math = math
		self.game = game
		self.searchFiles = searchFiles
		self.extension = extension
		
	def setOutputObject(self, newOutput=output.CalcpkgOutput(True, True)):
		"""Set an object where all output from calcpkg will be redirected to for this repository"""
		self.output = newOutput
		
	def searchHierarchy(self, fparent='/'):
		return self.index.searchHierarchy(fparent)

	def searchIndex(self, printData=True):
		"""Search the index with all the repo's specified parameters"""
		backupValue = copy.deepcopy(self.output.printData)
		self.output.printData = printData
		self.data = self.index.search(self.searchString, self.category, self.math, self.game, self.searchFiles, self.extension)
		self.output.printData = backupValue
		return self.data
		
	def countIndex(self):
		"""A wrapper for the count function in calcrepo.index; count using specified parameters"""
		self.data = self.index.count(self.searchString, self.category, self.math, self.game, self.searchFiles, self.extension)
		
	def getDownloadUrls(self):
		"""Return a list of the urls to download from"""
		data = self.searchIndex(False)
		fileUrls = []
		for datum in data:
			fileUrl = self.formatDownloadUrl(datum[0])
			fileUrls.append(fileUrl)
		return fileUrls
		
	def getFileInfos(self):
		"""Return a list of FileInfo objects"""
		data = self.searchIndex(False)
		self.data = data
		self.printd(" ")
		fileInfos = []
		for datum in data:
			fileInfo = self.getFileInfo(datum[0], datum[1])
			fileInfos.append(fileInfo)
		return fileInfos
		
	def downloadFiles(self, prompt=True, extract=False):
		"""Download files from the repository"""
		#First, get the download urls
		data = self.data
		downloadUrls = self.getDownloadUrls()
		
		#Then, confirm the user wants to do this
		if prompt:
			confirm = raw_input("Download files [Y/N]? ")
			if confirm.lower() != 'y':
				self.printd("Operation aborted by user input")
				return
				
		#Now, if they still do, do all this stuff:
		counter = -1
		for datum in data:
			counter += 1
			try:
				download = downloadUrls[counter]
			except:
				pass
				
			#Download the file
			self.printd("Downloading " + datum[0] + " from " + download)
			fileData = urllib2.urlopen(download).read()
			dowName = datum[0]
			dowName = dowName[5:]
			dowName = dowName.replace('/', '-')
			dowName = self.downloadDir + dowName
			try:
				downloaded = open(dowName, 'wb')
			except:
				os.remove(dowName)
			downloaded.write(fileData)
			downloaded.close()
			self.printd("Download complete! Wrote file " + dowName + "\n")

			#Extract them if told to do so
			if extract:
				extractType = ""
				if '.zip' in dowName:
					extractType = "zip"
				elif '.tar' in dowName:
					extractType = "tar"
					specType = ""
					if '.bz2' in dowName:
						specType = ":bz2"
					elif ".gz" in dowName:
						specType = ":gz"
				elif ".tgz" in dowName:
					extractType = "tar"
					specType = ":gz"

				if extractType != "":
					self.printd("Extracting file " + dowName + ", creating directory for extracted files")
					dirName, a, ending = dowName.partition('.')
					dirName = dirName + '-' + ending
					try:
						os.mkdir(dirName)
					except:
						pass
					if extractType == "zip":
						archive = zipfile.ZipFile(dowName, 'r')
					elif extractType == "tar":
						archive = tarfile.open(dowName, "r" + specType)
					else:
						self.printd("An unknown error has occured!")
						return
					archive.extractall(dirName)
					self.printd("All files in archive extracted to " + dirName)
					os.remove(dowName)
					self.printd("The archive file " + dowName + " has been deleted!\n")
		
	def getFileInfo(self):
		"""Return a list of FileInfo objects"""
		raise NotImplementedError
		
	def formatDownloadUrl(self, url):
		"""Format a repository path to be a real, valid download link"""
		raise NotImplementedError

	def updateRepoIndexes(self, verbose=False):
		"""Update the local copies of the repository's master index"""
		raise NotImplementedError
		
	def printd(self, message):
		"""Output function for repository to specific output location"""
		if self.output != None:
			print >> self.output, message

	def downloadFileFromUrl(self, url):
		"""Given a URL, download the specified file"""
		fullurl = self.baseUrl + url
		try:
			urlobj = urllib2.urlopen(fullurl)
			contents = urlobj.read()
		except urllib2.HTTPError, e:
			print "HTTP error:", e.code, url
			return None
		except urllib2.URLError, e:
			print "URL error:", e.code, url
			return None
		print("Fetched '%s' (size %d bytes)" % (fullurl, len(contents)))
		return contents

