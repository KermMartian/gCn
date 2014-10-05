import urllib
class AppURLopener(urllib.FancyURLopener):
    version = "gCn/1.0 (TI Graphing Calculator; Doors CS 7; Sandpaper)"
urllib._urlopener = AppURLopener()

from calcrepo import info
from calcrepo import repo

class CemetechRepository(repo.CalcRepository):
	baseUrl = "http://www.cemetech.net"
	
	def getRootFldr(self):
		return "/83plus/"

	def formatDownloadUrl(self, url):
		return "http://www.cemetech.net/programs/index.php?mode=file&path=" + url + "&location=archive"

	def updateRepoIndexes(self, verbose=False):
		return NotImplementedError
		
	def getFileInfo(self, fileUrl, fileName):
		#Open the info page and create a file info object
		infoUrl = "http://www.cemetech.net/programs/index.php?mode=file&path=" + fileUrl
		fileInfo = info.FileInfo(fileUrl, fileName, infoUrl)
		infoPage = urllib.urlopen(infoUrl)
		infoText = infoPage.read()
		infoPage.close()
		
		#Fill in all the data provided by Cemetech
		fileInfo.repository = self.name
		fileInfo.fileName = self.getSimpleFileData(infoText, "Download")
		fileInfo.author = self.getSimpleFileData(infoText, "Author")
		fileInfo.category = self.getSimpleFileData(infoText, "Folder")
		fileInfo.description = self.getComplexFileData(infoText, "Description")
		fileInfo.downloads = self.getComplexFileData(infoText, "Statistics")
	
		print fileInfo.printFileData(self.output)
		return fileInfo

	def getSimpleFileData(self, fileInfo, data):
		"""Function to initialize the simple data for file info"""
		result = fileInfo[fileInfo.find(data + "</td>"):]
		result = result[:result.find("</A></td>")]
		result = result[result.rfind(">") + 1:]
		return result
		
	def getComplexFileData(self, fileInfo, data):
		"""Function to initialize the slightly more complicated data for file info"""
		result = fileInfo[fileInfo.find(data + "</td>") + len(data + "</td>"):]
		result = result[:result.find("</td>")]
		result = result[result.rfind(">") + 1:]
		return result
