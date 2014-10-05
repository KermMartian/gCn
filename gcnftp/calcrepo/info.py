import sys

class FileInfo:
	"""Class to hold information about a file"""
	
	def __init__(self, fileUrl, fileName, infoUrl):
		"""Constructor for a fileInfo object"""
		self.fileUrl = fileUrl
		self.fileName = fileName
		self.infoUrl = infoUrl

		self.description = ""
		self.repository = ""
		self.category = ""
		self.fileSize = ""
		self.fileDate = ""
		self.sourceCode = ""
		self.author = ""
		self.downloads = ""
		self.documentation = ""

		self.fileinfo = ""

	def __str__(self):
		return self.fileName + " located at " + self.fileUrl
		
	def __repr__(self):
		return self.fileName + " located at " + self.fileUrl

	def printFileDatum(self, text, datum, output = sys.stdout):
		if datum != "":
			print >> output, text + datum

	def printFileData(self, output = sys.stdout):
		"""Output all the file data to the passed in writable stdout"""
		self.printFileDatum("Name          : ", self.fileName, output)
		self.printFileDatum("Author        : ", self.author, output)
		self.printFileDatum("Repository    : ", self.repository, output)
		self.printFileDatum("Category      : ", self.category, output)
		self.printFileDatum("Downloads     : ", self.downloads, output)
		self.printFileDatum("Date Uploaded : ", self.fileDate, output)
		self.printFileDatum("File Size     : ", self.fileSize, output)
		self.printFileDatum("Documentation : ", self.documentation, output)
		self.printFileDatum("Source Code   : ", self.sourceCode, output)
		self.printFileDatum("Description   : ", self.description + "\n", output)
