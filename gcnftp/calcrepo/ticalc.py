import urllib
class AppURLopener(urllib.FancyURLopener):
    version = "gCn/1.0 (TI Graphing Calculator; Doors CS 7; Sandpaper)"
urllib._urlopener = AppURLopener()

from calcrepo import info
from calcrepo import repo

class TicalcRepository(repo.CalcRepository):
	baseUrl = "http://www.ticalc.org"

	def getRootFldr(self):
		return "/pub/83plus/"

	def formatDownloadUrl(self, url):
		return "http://www.ticalc.org" + url
		
	def updateRepoIndexes(self, verbose=False):
		self.printd("Reading ticalc.org master index (this will take some time)")
		
		#First read in the text (the only network process involved)
		masterIndex = urllib.urlopen('http://www.ticalc.org/pub/master.index').read()
		self.printd("  Read in ticalc.org master index")

		#Now, try to delete the indexes on system
		try:
			os.remove(self.index.fileIndex)
			self.printd("  Deleted old files index")
		except:
			self.printd("  No files index found")
		try:
			os.remove(self.index.nameIndex)
			self.printd("  Deleted old names index")
		except:
			self.printd("  No names index found")
		try:
			os.remove(self.index.dirIndex)
			self.printd("  Deleted on directory index")
		except:
			self.printd("  No directory index found")
			
		#Now, try to open new indexes to write to
		try:
			files = open(self.index.fileIndex, 'wt')
		except:
			self.printd("Error: Unable to create file " + self.index.fileIndex + " in current folder. Quitting.")
			return
		try:
			names = open(self.index.nameIndex, 'wt')
		except:
			self.printd("Error: Unable to create file " + self.index.fileIndex + " in current folder. Quitting.")
			files.close()
			return
		try:
			dirs = open(self.index.dirIndex, 'wt')
		except:
			self.printd("Error: Unable to create file " + self.index.dirIndex + " in current folder.  Quitting.")
			files.close()
			names.close()

		#Now, parse the enormous data and write index files
		self.printd(" ")
		masterIndex = masterIndex[39:]
		directory = ""
		folders = dict()
		dirwhole = "/"
		while len(masterIndex) > 2:
			line = masterIndex[:masterIndex.find('\n')]
			masterIndex = masterIndex[masterIndex.find('\n') + 1:]
			if line == "":
				continue
			if line[:9] == "Index of ":
				dirData = line[9:]
				directory = dirData[:dirData.find(" ")]
				if verbose:
					self.printd("  Caching " + line[9:])
				dirwhole = "/"
				for dirpiece in directory.split("/"):
					if dirpiece == "":
						continue;
					dirwhole += dirpiece + "/"
					try:
						folders[dirwhole] += 1
					except KeyError:
						folders[dirwhole] = 1
				
			else:
				fileData = line[:line.find(" ")]
				files.write(directory + '/' + fileData + '\n')
				nameData = line[len(fileData)+1:].lstrip()
				names.write(nameData + '\n')
				try:
					folders[dirwhole] += 1
				except:
					self.printd("Error: folder for this file missing")
					files.close()
					names.close()
					dirs.close()
		
		#Close the indexes now
		files.close()
		names.close()

		#Sort the folders and store them
		from operator import itemgetter
		folders = dict(sorted(folders.iteritems(), key=itemgetter(0), reverse=False))
		for folder,count in folders.iteritems():
			dirs.write(folder + '|'+str(count)+'\n')
		dirs.close()

		self.printd("Finished updating ticalc.org repo\n")

	def getFileInfo(self, fileUrl, fileName):
		#Get the category path for the file
		categoryPath = "http://www.ticalc.org/"
		splitUrls = fileUrl.split('/')
		for splitUrl in splitUrls:
			if splitUrl != "" and (not "." in splitUrl):
				categoryPath += splitUrl + '/'

		#Now open the category page and extract the URL for the file info page
		self.printd("Fetching category page url ("+categoryPath+") to search for '"+fileUrl+"'")
		categoryPage = urllib.urlopen(categoryPath, "")
		categoryData = categoryPage.read()
		categoryPage.close()
		index = categoryData.find(fileUrl) - 7
		rIndex = categoryData.rfind('A HREF="', 0, index)
		infoUrl = categoryData[rIndex + 9:]
		infoUrl = "http://www.ticalc.org/" + infoUrl[:infoUrl.find('">')]
		
		#Create a file info object
		self.printd("Fetching info from infourl: "+infoUrl)
		fileInfo = info.FileInfo(fileUrl, fileName, infoUrl)
		infoPage = urllib.urlopen(infoUrl)
		infoText = infoPage.read()
		infoPage.close()

		#Fill in all the data bits
		fileInfo.description = self.getBaseFileData(infoText, "Description")
		fileInfo.fileSize = self.getBaseFileData(infoText, "File Size")
		fileInfo.fileDate = self.getBaseFileData(infoText, "File Date and Time", 47, 2)
		fileInfo.documentation = self.getBaseFileData(infoText, "Documentation&nbsp;Included?")
		fileInfo.sourceCode = self.getBaseFileData(infoText, "Source Code")
		fileInfo.category = self.getFileCategory(infoText)
		fileInfo.author = self.getFileAuthor(infoText)
		fileInfo.downloads = self.getNumDownloads(infoText)
		fileInfo.repository = self.name
		
		#Print the file info object
		fileInfo.printFileData(self.output)
		return fileInfo
	
	def getBaseFileData(self, fileInfo, data, index1 = 47, index2 = 1):
		"""Function to initialize the simple data for file info"""
		result = fileInfo[fileInfo.find(data):]
		result = result[result.find("<FONT ") + index1:]
		result = result[:result.find("</FONT>") - index2]
		return result

	def getFileCategory(self, fileInfo):
		"""Function to get the file category for file info"""
		category = fileInfo[fileInfo.find("Category"):]
		category = category[category.find("<FONT ") + 47:]
		category = category[category.find('">') + 2:]
		category = category[:category.find("</A></B>") - 0]
		return category

	def getFileAuthor(self, fileInfo):
		"""Function to get the file's author for file info, note that we are pretending that multiple authors do not exist here"""
		author = fileInfo[fileInfo.find("Author"):]
		author = author[author.find("<FONT ") + 47:]
		author = author[author.find('<B>') + 3:]
		authormail = author[author.find("mailto:") + 7:]
		authormail = authormail[:authormail.find('"')]
		author = author[:author.find("</B></A>") - 0]
		author = author + " (" + authormail + ")"
		return author

	def getNumDownloads(self, fileInfo):
		"""Function to get the number of times a file has been downloaded"""
		downloads = fileInfo[fileInfo.find("FILE INFORMATION"):]
		if -1 != fileInfo.find("not included in ranking"):
			return "0"
		downloads = downloads[:downloads.find(".<BR>")]
		downloads = downloads[downloads.find("</A> with ") + len("</A> with "):]
		return downloads
