import os

class ResultType:
	FOLDER, FILE = range(2)

class Index:
	"""Index object created for each repository: note, we're assuming that local copies of the indexes will use the same formats"""
	
	def __init__(self, repo):
		modulePath = os.path.realpath(__file__)
		modulePath = modulePath[:modulePath.rfind("/")]
		self.fileIndex = modulePath + "/" + repo.name + ".files.index"
		self.nameIndex = modulePath + "/" + repo.name + ".names.index"
		self.dirIndex = modulePath + "/" + repo.name + ".dirs.index"
		self.repo = repo
		
	def count(self, searchString, category="", math=False, game=False, searchFiles=False, extension=""):
		"""Counts the number of ticalc.org files containing some search term, doesn't return them"""
		fileData = {}
		nameData = {}
		
		#Search the index
		if searchFiles:
			fileData = self.searchNamesIndex(self.fileIndex, fileData, searchString, category, math, game, extension)
		else:
			nameData = self.searchNamesIndex(self.nameIndex, nameData, searchString)
			
		#Now search the other index
		if searchFiles:
			nameData, fileData = self.searchFilesIndex(fileData, nameData, self.nameIndex, searchString)
		else:
			fileData, nameData = self.searchFilesIndex(nameData, fileData, self.fileIndex, searchString, category, math, game, extension)

		#Now obtain a count (exclude "none" elements)
		count = 0
		for element in nameData:
			if not nameData[element] is None:
				count += 1

		self.repo.printd("Search for '" + searchString + "' returned " + str(count) + " result(s) in " + self.repo.name)
		return count
		
	def searchHierarchy(self, fparent):
		"""Core function to search directory structure for child files and folders of a parent"""
		data = []
		returnData = []
		parentslashes = fparent.count('/') 
		filecount = 0
		foldercount = 0

		#open files for folder searching
		try:
			dirFile = open(self.dirIndex, 'rt')
		except IOError:
			self.repo.printd("Error: Unable to read index file " + self.dirIndex)
			return

		#search for folders
		for fldr in dirFile:
			fldr = fldr.split('|')
			fldr = fldr[0]
			if fparent in fldr and parentslashes+1 == fldr.count('/'):
				returnData.append([fldr, fldr[fldr.rfind('/',1,-1):-1], ResultType.FOLDER])
				foldercount += 1

		dirFile.close()

		#open files for file searching
		try:
			fileFile = open(self.fileIndex, 'rt')
		except IOError:
			self.repo.printd("Error: Unable to read index file " + self.fileIndex)
			return

		try:
			nameFile = open(self.nameIndex, 'rt')
		except IOError:
			self.repo.printd("Error: Unable to read index file " + self.nameIndex)
			return

		#search for files
		for (path,name) in zip(fileFile,nameFile):
			if fparent in path and parentslashes == path.count('/'):
				returnData.append([path.strip(), name, ResultType.FILE])
				filecount += 1

		fileFile.close()
		nameFile.close()

		return [returnData, foldercount, filecount]
				

	def search(self, searchString, category="", math=False, game=False, searchFiles=False, extension=""):
		"""Core function to search the indexes and return data"""
		data = []
		nameData = {}
		fileData = {}
		
		#Search the name index
		if searchFiles:
			fileData = self.searchNamesIndex(self.fileIndex, fileData, searchString, category, math, game, extension, searchFiles)
		else:
			nameData = self.searchNamesIndex(self.nameIndex, nameData, searchString)
			
		#Now search the file index
		if searchFiles:
			nameData, fileData = self.searchFilesIndex(fileData, nameData, self.nameIndex, searchString)
		else:
			fileData, nameData = self.searchFilesIndex(nameData, fileData, self.fileIndex, searchString, category, math, game, extension)
			
		#Prepare output to parse
		for key, value in nameData.iteritems():
			fileValue = fileData[key]
			data.append([fileValue, value])
		
		#Print output
		if len(data) != 0:
			self.repo.printd("Results for repo: " + self.repo.name)
			self.repo.printd(structureOutput("File Category:", "File Name:", False, False))
			self.repo.printd("===========================================================================================")
		else:
			self.repo.printd("No packages found")
		returnData = []
		for datum in data:
			try:
				self.repo.printd(structureOutput(datum[0], datum[1], searchFiles))
				returnData.append([datum[0], datum[1]])
			except:
				pass
		self.repo.printd(" ")
		
		#Return data
		return returnData
		
	def searchFilesIndex(self, nameData, fileData, fileIndex, searchString, category="", math=False, game=False, extension=""):
		"""Search the files index using the namedata and returns the filedata"""
		try:
			fileFile = open(fileIndex, 'rt')
		except IOError:
			self.repo.printd("Error: Unable to read index file " + self.fileIndex)
			return
			
		count = 1
		for line in fileFile:
			count += 1
			try:
				if nameData[count] != None:
					#category argument
					if category in line:
						fileData[count] = line[:len(line) - 1]
					else:
						nameData[count] = None
						fileData[count] = None
					#extension argument
					if extension in line:
						fileData[count] = line[:len(line) - 1]
					else:
						nameData[count] = None
						fileData[count] = None
					#Both game and math
					if (game and math):
						if ("/games/" in line or "/math/" in line or "/science" in line):
							nameData[count] = line[:len(line) - 1]
						else:
							nameData[count] = None
					#game option switch
					elif game:
						if "/games/" in line:
							fileData[count] = line[:len(line) - 1]
						else:
							nameData[count] = None
							fileData[count] = None
					#math option switch
					elif math:
						if ("/math/" in line or "/science/" in line):
							fileData[count] = line[:len(line) - 1]
						else:
							nameData[count] = None
							fileData[count] = None
			except:
				pass
				
		#Close the file and return
		fileFile.close()
		return fileData, nameData
		
	def searchNamesIndex(self, nameIndex, nameData, searchString, category="", math=False, game=False, extension="", searchFiles=False):
		"""Search the names index for a string and returns the namedata"""
		nameData = {}
		try:
			nameFile = open(nameIndex, 'rt')
		except IOError:
			self.repo.printd("Error: Unable to read index file " + self.fileIndex)
			return
			
		count = 1
		for line in nameFile:
			count += 1
			if searchString.lower() in line.lower():
				#Extension argument
				if extension in line:
					nameData[count] = line[:len(line) - 1]
				else:
					nameData[count] = None
				#category arg
				if category in line and extension in line:
					nameData[count] = line[:len(line) - 1]
				else:
					nameData[count] = None
				#Both game and math
				if (game and math):
					if ("/games/" in line or "/math/" in line or "/science" in line):
						nameData[count] = line[:len(line) - 1]
					else:
						nameData[count] = None
				#Game option switch
				elif game:
					if "/games/" in line:
						nameData[count] = line[:len(line) - 1]
					else:
						nameData[count] = None
				#Math option switch
				elif math:
					if ("/math/" in line or "/science/" in line):
						nameData[count] = line[:len(line) - 1]
					else:
						nameData[count] = None

		#Close the name index and return
		nameFile.close()
		return nameData
		
def structureOutput(fileUrl, fileName, searchFiles, format=True):
	"""Formats the output of a list of packages"""
	#First, remove the filename
	if format:
		splitUrls = fileUrl[4:].split('/')
		fileUrl = ""
		for splitUrl in splitUrls:
			if splitUrl != "" and (not "." in splitUrl):
				fileUrl += splitUrl + '/'
			elif "." in splitUrl:
				archiveName = splitUrl

	#Now, format the output
	if searchFiles:
		fileName = archiveName
	output = fileUrl
	if len(output) > 40:
		output += " " + fileName
	else:
		while len(output) <= 40:
			output += " "
		output += fileName
	return output

