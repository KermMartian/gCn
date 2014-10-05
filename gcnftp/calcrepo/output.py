import datetime
import os
import sys

class CalcpkgOutput:
	"""Writable object used as output for the printd() function- the default place for stuff to be outputted"""

	def __init__(self, printData, logData):
		self.printData = printData
		self.logData = logData
		self.logFile = ""

		#Configure logging
		pathRoot = self.getLoggingLocation()
		if pathRoot != "":
			self.logFile = pathRoot + "/calcpkg.log"
		else:
			self.logData = False

	def __str__(self):
		return self.__repr__()
		
	def __repr__(self):
		output = "Default calcpkg output object"
		if self.printData:
			output += ", printing to stdout"
		if self.logData and self.LogFile != "":
			output += ", logging to "
			output += self.logFile
		return output

	def write(self, string):
		"""The write method for a CalcpkgOutput object- print the string"""
		if ("" == string or '\n' == string or '\r' in string):
			return
		if self.printData:
			print >> sys.__stdout__, string
		if self.logData:
			self.logWrite(string)

	def logWrite(self, string):
		"""Only write text to the log file, do not print"""
		logFile = open(self.logFile, 'at')
		logFile.write(string + '\n')
		logFile.close()

	def setupLogFile(self):
		"""Set up the logging file for a new session- include date and some whitespace"""
		self.logWrite("\n###############################################")
		self.logWrite("calcpkg.py log from " + str(datetime.datetime.now()))
		self.changeLogging(True)

	def getLoggingLocation(self):
		"""Return the path for the calcpkg.log file - at the moment, only use a Linux path since I don't know where Windows thinks logs should go."""
		if sys.platform == "win32":
			modulePath = os.path.realpath(__file__)
			modulePath = modulePath[:modulePath.rfind("/")]
			return modulePath
		else:
			return "/tmp"
		return ""

