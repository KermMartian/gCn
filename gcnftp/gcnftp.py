#!/usr/bin/python

# globalCALCnet FTP/Sandpaper Bridge
# Christopher Mitchell, 2011-2014
# Licensed under the BSD 3-Clause License (see LICENSE)

#;===Frame types:===
#;1	[9-byte name payload]				Broadcast for "I am here"
#;2	[no payload]							Request pair (master->slave)
#;3	[no payload]							Accept requested pairing (slave->master)
#;4	[no payload]							Reject requested pairing (slave->master)
#;5  [no payload]								Disconnect (either direction)
#;6	2-byte payload							Request folder list
#;7	variable payload						Folder list, multipart.  First frame is two bytes and holds list size.
#;8 	sz[2],arcd[1],fld[1],t[1],name[8]   Request-to-send (RTO) (master->slave)
#;9  accept/deny[1]							Accept/reject incoming file (slave->master)
#;10 T[1],name[8],loc[1],memfree[2] 	Request-to-get (RTG) (master->slave)
#;11 y/n[1], sz[2]							Success/fail, header (slave->master)
#;12 offset[2],data							Data packet (either direction)
#;13 accept/deny[1],size[2]				Accept/reject outgoing file (slave->master)
#;14
#;15

import os.path
import urllib2
import urllib
import sys
import socket
import string
import sched, time
import threading
import random
import signal
import string
import re
import copy
import zipfile
from htmlentitydefs import name2codepoint as n2cp
from subprocess import *
from logging import *
from filecache import *

# CalcPkg Repos
sys.path.append("./calcpkg")
from calcrepo.cemetech import *
from calcrepo.ticalc import *
from calcrepo.index import ResultType
from calcrepo.info import FileInfo

#gcn info
GCNSERVER = "gcnhub.cemetech.net"
GCNPORT = 4295
GCNREMOTE = "FTPHub"
GCNLOCAL = "FTPHub"

#scheduler
s=sched.scheduler(time.time, time.sleep)

#global variables

t2x= [0x20,0x20,0x20,0x20,0x20,0x20,0x20,0x20,0x20,0x20,0xD6,\
		0x20,0x20,0xD6,0x20,0x20,0x20,0x20,0x20,0x20,0x20,0x20,\
		0x20,0x20,0x20,0x20,0x20,0x20,0x20,0x20,0x20,0x20,0x20,\
		0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x29,0x2A,0x2B,\
		0x2C,0x2D,0x2E,0x2F,0x30,0x31,0x32,0x33,0x34,0x35,0x36,\
		0x37,0x38,0x39,0x3A,0x3B,0x3C,0x3D,0x3E,0x3F,0x40,0x41,\
		0x42,0x43,0x44,0x45,0x46,0x47,0x48,0x49,0x4A,0x4B,0x4C,\
		0x4D,0x4E,0x4F,0x50,0x51,0x52,0x53,0x54,0x55,0x56,0x57,\
		0x58,0x59,0x5A,0xC1,0x5C,0x5D,0x5E,0x5F,0x60,0x61,0x62,\
		0x63,0x64,0x65,0x66,0x67,0x68,0x69,0x6A,0x6B,0x6C,0x6D,\
		0x6E,0x6F,0x70,0x71,0x72,0x73,0x74,0x75,0x76,0x77,0x78,\
		0x79,0x7A,0x7B,0x7C,0x7D,0x7E]
t2xw=[4,6,4,4,4,4,4,5,4,4,4,4,4,4,4,5,\
		4,5,4,4,5,5,4,5,6,5,4,4,5,6,4,4,\
		1,2,4,6,6,4,5,2,3,3,6,4,3,4,2,4,\
		4,4,4,4,4,4,4,4,4,4,2,3,4,4,4,4,\
		6,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,\
		4,4,4,4,4,4,4,4,4,4,4,4,4,3,4,4,\
		3,4,4,4,4,4,3,4,4,2,4,4,3,6,4,4,\
		4,4,4,3,3,4,4,6,4,4,5,4,2,4,5,4,\
		4,3,4,4,4,4,4,4,4,4,4,4,4,4,4,4,\
		4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,\
		4,4,4,4,4,4,3,3,4,4,2,5,4,5,6,4,\
		4,3,4,5,6,5,5,5,5,6,6,4,4,4,3,4,\
		4,4,3,4,4,4,4,4,4,4,4,4,4,4,5,3,\
		3,5,5,6,5,6,5,6,5,6,5,6,5,4,4,4,\
		4,4,6,6,5,4,4,4,4,4,4,4,4,4,4,4]
x2t= [' ','n','u','v','w','>',' ','|','|','x','o','+','.','T','3','F','/','-','2','/','o','r','T','<=','!=','>=','-',\
		'E','>','10','[up]','[down]',' ','!','"','#','$','%','%','\'','(',')','*','+',',','-','.','/','0',\
		'1','2','3','4','5','6','7','8','9',':',';','<','=','>','?','@','A','B','C','D','E','F','G','H','I',\
		'J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z','[theta]','\\',']','^','_',\
		'`','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z',\
		'{','|','}','~','=','0','1','2','3','4','5','6','7','8','9','A','A','A','A','a','a','a','a','E','E','E',\
		'E','e','e','e','e','I','I','I','I','i','i','i','i','O','O','O','O','o','o','o','o','U','U','U','U','u','u',\
		'u','u','C','c','N','n','\'','\'',':','?','!','a','B','g','d','d','E','[','s','m','[pi]','p','E','o','T',\
		'o','Q','x','y','x','_','<','o','/','-','2','o','3',"\r\n",'i','p','x','F','e','L','N','a','E','O']
RAMSIZESANE=24000

def calcencode(input):
	#newlines
	#input = "\n".join(input)

	#character conversion
	input = ''.join([chr(0xD0) if ord(c)>=len(t2x) else chr(t2x[ord(c)]) for c in input])
	return input

def calcdecode(input):
	input = ''.join(['?' if ord(c) > len(x2t) else x2t[ord(c)] for c in input])
	return input

def outtoclient(type,seq,contents,sid,gcnlock,clientsocket):
	gcnlock.acquire()
	msgindex = 0;
	if seq == -1:
		thisoutmsg = chr(type) + contents
	else:
		thisoutmsg = chr(type) + chr(seq) + contents
	outmsghdr = chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(0xAA)+\
                chr(len(thisoutmsg)&0x00ff)+chr((len(thisoutmsg)>>8)&0x00ff)
	outmsghdr = outmsghdr + thisoutmsg
	#print "Forwarding '"+outmsghdr+"' to '"+calc5to10(sid)+"'"
	thismsg = chr(255)+chr(137)+sid+outmsghdr+chr(42)
	thismsg = chr(len(thismsg)&0x00ff)+chr((len(thismsg)>>8)&0x00ff)+'f'+thismsg
	clientsocket.sendall(thismsg)
	gcnlock.release()

class ping_thread(threading.Thread):
	def __init__(self,archive,addr,allcalcs,gcnlock,clientsocket):
		 threading.Thread.__init__(self)
		 self.addr_ = addr
		 self.archive_ = archive
		 self.allcalcs_ = allcalcs
		 self.gcnlock_ = gcnlock
		 self.clientsocket_ = clientsocket

	def run(self):
		msg = chr(255)+chr(137)+chr(0)+chr(0)+chr(0)+chr(0)+chr(0)
		for i in xrange(0,5):
			msg = msg + chr(int(self.addr_[2*i:2*(i+1)],16))
		msg = msg + chr(10) + chr(0) + chr(0x01)
		self.archive_ = self.archive_.ljust(8)
		if len(self.archive_) > 8:
			self.archive_ = self.archive_[0:8]
		msg = msg + self.archive_ + chr(0x00) + chr(42)
		msg = chr(len(msg))+chr(0)+'b'+msg
		while 1==1:
			#log_info(self.archive_ + ": sending broadcast of length "+str(len(msg)))

			self.gcnlock_.acquire()
			for sid,calc in self.allcalcs_.items():
				self.allcalcs_[sid][1] = calc[1]-1
				if calc[1] <= 0:
					log_warn('gcnftp: ' + self.archive_+": "+calc[0]+" timed out and left the room")
					del self.allcalcs_[sid]
			self.clientsocket_.sendall(msg)
			self.gcnlock_.release()
			time.sleep(random.randint(5,10))

def start():
	gcnthr = [ gCnManage('Cemetech','AAAAAAAAAA'), gCnManage('ticalc',  'AAAAAAAAAB') ]
	log_info('gcnftp: Created gCn managers for FTP')
	#gcnthr[0].start()		#No Cemetech yet
	gcnthr[1].start()
	log_info('gcnftp: gCn manager(s) started for FTP')
  

class gCnManage(threading.Thread):
	def __init__(self,archive,addr):
			threading.Thread.__init__(self)
			self.addr_ = addr
			self.archive_ = archive
			self.allcalcs_ = dict()
			self.gcnlock_ = threading.Lock()
			if archive == "ticalc":
				self.repo_ = TicalcRepository("ticalc", "http://www.ticalc.org")
			elif archive == "Cemetech":
				self.repo_ = CemetechRepository("cemetech", "http://www.cemetech.net/")
			else:
				log_error("gcnftp: "+self.archive_+": No CalcPkg repository for archive.")
				sys.exit(-1)
			self.filecache = FileCache(archive + "_cache")	#ticalc_cache for the cache folder

	def run(self):
		global GCNSERVER
		global GCNPORT
		global GCNLOCAL
		global GCNREMOTE

		#create an INET, STREAMing socket
		log_info("gcnftp: starting gCn client")
		self.clientsocket_ = socket.socket(
		    socket.AF_INET, socket.SOCK_STREAM)
		#bind the socket to a public host,
		# and a well-known port
		self.clientsocket_.connect((GCNSERVER,GCNPORT))

		#gCn join
		joinmsg = chr(2+len(GCNREMOTE)+len(GCNLOCAL))+chr(0)+'j'+chr(len(GCNREMOTE))+\
		          GCNREMOTE+chr(len(GCNLOCAL))+GCNLOCAL
		self.clientsocket_.sendall(joinmsg)
		time.sleep(0.1);

		#gCn calculator
		calcmsg = chr(10)+chr(0)+"c"+self.addr_
		self.clientsocket_.sendall(calcmsg)
		time.sleep(0.1);

		#Ping thread
		pthr = ping_thread(self.archive_,self.addr_,self.allcalcs_,self.gcnlock_,self.clientsocket_)
		pthr.start()

		recbuf = "";
		recbufqueue = 0;
		while 1==1:
			instring = self.clientsocket_.recv(1024)
			recbuf = recbuf + instring
			recbufqueue += len(instring)
			while recbufqueue > 2 and recbufqueue >= 3+ord(recbuf[0])+256*ord(recbuf[1]):
				thismsglen = ord(recbuf[0])+256*ord(recbuf[1])
				thismsgtype = recbuf[2]
				thismsg = recbuf[3:3+thismsglen]
				if thismsgtype != 'f' and thismsgtype != 'b':
					log_warn("gcnftp: "+self.archive_+": Unknown incoming msg type '"+thismsgtype+"'!'")
					#continue;
				else:
					calc5 = thismsg[7:12]
					calc10 = calc5to10(calc5)
					if calc10 in self.allcalcs_:
						self.allcalcs_[calc10][1] = 30				# Keep it alive

					if ord(thismsg[14]) == 1:
						pass

					elif ord(thismsg[14]) == 2:					# Connect Request
						uname = cleanstr(thismsg[15:24])
						log_info("gcnftp: "+self.archive_+": "+calc10+" connected as "+uname)
						outtoclient(3,-1,"",calc5,self.gcnlock_,self.clientsocket_)

						self.gcnlock_.acquire()
						#                         user  ping   address?   fld_hi fld_lo  directory_name      contents history
						self.allcalcs_[calc10] = [uname, 30 ,thismsg[7:12], 0xFF, 0xFF, self.repo_.getRootFldr(), [], [] ]
						self.gcnlock_.release()

					elif ord(thismsg[14]) == 5:					# Disconnect
						try:
							log_info("gcnftp: "+self.archive_+": "+self.allcalcs_[calc10][0]+"("+calc10+") disconnnected.")

							self.gcnlock_.acquire()
							del self.allcalcs_[calc10]
							self.gcnlock_.release()

						except KeyError:
							log_warn("gcnftp: "+self.archive_+": "+calc10+" disconnected without being connected!")

					elif ord(thismsg[14]) == 6:					# Folder request
						try:
							fld_lo = ord(thismsg[15])		#little endian!
							fld_hi = ord(thismsg[16])
							self.HandleFolderRequest(fld_hi, fld_lo, calc5)

						except KeyError:
							log_warn("gcnftp: "+self.archive_+": "+calc10+" asked for a folder without being connected!")

					elif ord(thismsg[14]) == 8:					# Request to Send (RTS)
						try:
							calcinfo = self.allcalcs_[calc10]
							log_warn("gcnftp: "+self.archive_+": "+calc10+" wants to send a file (rejecting)")
							outtoclient(9,-1,chr(0),calc5,self.gcnlock_,self.clientsocket_)		#reject
						except KeyError:
							log_warn("gcnftp: "+self.archive_+": "+calc10+" asked RTS'ed without being connected!")

					elif ord(thismsg[14]) == 10:					# Request to Get (RTG)
						try:
							calcinfo = self.allcalcs_[calc10]

							if not(isinstance(calcinfo[6],FileInfo)):
								log_error("gcnftp: "+self.archive_+": "+calc10+" requested file %s, type %d" \
								          " but wasn't in a (zip) folder" % (calcdecode(thismsg[16:16+8]), thismsg[15]))
							else:
								fileinfo = calcinfo[6]
								log_info("gcnftp: "+self.archive_+": "+calc10+" requesting file %s, type %d" \
								         " from (zip '%s') folder" % (calcdecode(thismsg[16:16+8]), ord(thismsg[15]), fileinfo.fileUrl))
								subpath = fileinfo.fileSubPath
								typedec = ord(thismsg[15])
								typestr = self.fileTypeDec2Str(typedec)

								outline = None
								infilename = ""
								for fileline in fileinfo.fldContents:
									if fileline[2][0:2] == "8x" and fileline[3] == True and fileline[2] == typestr:
										if (subpath == "" and not('/' in fileline[0])) or \
										   (subpath != "" and ('//'+subpath) in ('//'+fileline[0])):
												if len(fileline[4]) > 0x37+0x0F+0x02:		# Minimum size of a sane 83 file
													infilename = fileline[4][0x37+0x05:0x37+0x05+8]
													if infilename == thismsg[16:16+8]:
														print("Candidate '%s' for requested '%s' type %d" % (infilename,thismsg[16:16+8],typedec))
														outline = fileline
														break

								if None == outline:
									log_error("gcnftp: "+self.archive_+": "+calc10+"'s requested file could not be located.")
									outtoclient(13,-1,chr(0)+chr(0xFF)+chr(0xFF)+chr(0xFF)+chr(0xFF),\
									            calc5,self.gcnlock_,self.clientsocket_)		#reject
								else:
									startaddr = 0x37 + ord(fileline[4][0x37]) + 0x02
									varlen = ledestringify(fileline[4][startaddr:startaddr+2])
									if varlen + 32 > ledestringify(thismsg[25:27]):
										outtoclient(13,-1,chr(0)+chr(0xFF)+chr(0xFF)+chr(0xFF)+chr(0xFF),\
										            calc5,self.gcnlock_,self.clientsocket_)     #reject
									else:
										datalen = ledestringify(fileline[4][startaddr:startaddr+2])
										outtoclient(13,-1,chr(1)+fileline[4][startaddr+2:startaddr+4]+\
										            fileline[4][startaddr:startaddr+2],calc5,\
										            self.gcnlock_,self.clientsocket_)     #reject
										data = fileline[4][startaddr+2:startaddr+2+datalen]
										sent = 0
										while sent < datalen:
											chunksize = 250 if (datalen-sent) > 250 else datalen-sent
											chunk = lestringify(sent) + data[sent:sent+chunksize]
											outtoclient(12,-1,chunk,calc5,self.gcnlock_,self.clientsocket_)
											sent += chunksize

						except KeyError:
							log_warn("gcnftp: "+self.archive_+": "+calc10+" asked RTS'ed without being connected!")
					else:
						print "[WARN] Unknown calculator msg type "+str(ord(thismsg[14]))+" received!"
				recbuf = recbuf[3+thismsglen:]
				recbufqueue -= 3+thismsglen
				if recbufqueue != len(recbuf):
					print "[ERROR] buffer length mismatch, discarding buffer"
					recbuf = ""
					recbufqueue = 0

	def HandleFolderRequest(self, fld_hi, fld_lo, calc5, lateral = 0, offset = 0):
		calc10 = calc5to10(calc5)
		filetitle_str = ""
		calcinfo = self.allcalcs_[calc10]
		suppressDescription = False

		if fld_lo == 0xFF and fld_hi == 0xFF and len(calcinfo[7]):	#History
			if len(calcinfo[7]) > 1 and lateral == 0:
				calcinfo[7].pop()		# Lateral/1-item history = stay in folder
			hist = calcinfo[7].pop()
			suppressDescription = True
			if hist[0] == ResultType.FILE:
				fld_lo = hist[1]		#subfolder ID
				calcinfo[5] = hist[2]	#"folder" name
				calcinfo[6] = hist[3]	#"folder" contents
			else:
				fld_hi = hist[1]
				fld_lo = hist[2]
				calcinfo[6] = hist[3]

			self.gcnlock_.acquire()
			self.allcalcs_[calc10][7] = calcinfo[7]
			self.gcnlock_.release()

		hist = None
		if fld_hi == 0xFF and fld_lo == 0xFF:			#Just knocking this case out
			fldname_str  = self.repo_.getRootFldr()
			fldname_type = ResultType.FOLDER
			hist = [ResultType.FOLDER, 0xFF, 0xFF, fldname_str]
		elif fld_hi == 0xFF:							#Folder inside zip
			fldname_str = calcinfo[5]
			fileobj = calcinfo[6]
			fld_lo = fld_lo-1		#-1 because special folder $00 is normal folder $01 oncalc
			fldsubpath = fileobj.fldContents[fld_lo][0]
			fldtitle_str = fileobj.fldContents[fld_lo][1]
			fldname_type = ResultType.FILE
			log_info("gcnftp: "+self.archive_+": "+calc10+" descending into archive '%s' (subpath '%s')" \
					 % (fldname_str,fldsubpath))
			hist = [ResultType.FILE, fld_lo+1, calcinfo[5], calcinfo[6]]
		else:											#File or other folder
			fld_lo0 = fld_lo
			try:
				multipart =  1 if (calcinfo[6][0][0][0:6] == "NEXT_(" or \
				                   calcinfo[6][0][0][0:6] == "PREV_(") else 0
				multipart += 1 if (calcinfo[6][1][0][0:6] == "NEXT_(") else 0
				newoffset = 0
				if calcinfo[6][0][0][0:6] == "PREV_(":
					newoffset = ord(calcinfo[6][0][0][6])-ord('0')
					if fld_lo >= multipart:
						fld_lo += 250*newoffset

				#print("Down into fld_lo = %d, fld_hi = %d" % (fld_lo, fld_hi))
				fldname_str  = calcinfo[6][fld_lo][0]	#path, actually.  name is [1]
				fldtitle_str = calcinfo[6][fld_lo][1]	#name actually
				fldname_type = calcinfo[6][fld_lo][2]

				if fldname_str[0:6] == "NEXT_(":
					log_info("gcnftp: "+self.archive_+": "+calc10+" Using history to go to NEXT page")
					self.HandleFolderRequest(0xFF, 0xFF, calc5, lateral = 1, offset = newoffset+1)
					return
				if fldname_str[0:6] == "PREV_(":
					log_info("gcnftp: "+self.archive_+": "+calc10+" Using history to go to PREV page")
					self.HandleFolderRequest(0xFF, 0xFF, calc5, lateral = -1, offset = newoffset-1)
					return

				fileobj=None
				fldsubpath = ""
			except KeyError, IndexError:
				log_warn("gcnftp: "+self.archive_+": "+calc10+" ("+calcinfo[0]+") requested invalid fldr "+\
					str(fld_hi)+":"+str(fld)+" in "+calcinfo[5]+"(had "+len(calcinfo[6])+")")
				fld_hi = fld_lo = 0xFF
				fldname_str  = self.repo_.getRootFldr()
				fldname_type = ResultType.FOLDER
			finally:
				hist = [ResultType.FOLDER, fld_hi, fld_lo0, calcinfo[6]]

		self.gcnlock_.acquire()
		self.allcalcs_[calc10][7].append(hist)
		self.gcnlock_.release()

		fldname_type_str = ["folder","file"][fldname_type]
		log_info("gcnftp: "+self.archive_+": "+calc10+" requested "+fldname_type_str+" "+str(fld_hi)+":"+str(fld_lo))
		if fldname_type == ResultType.FOLDER:
			self.processFolderRequest(calc5,fldname_str,fld_hi,fld_lo,offset)
		elif fldname_type == ResultType.FILE:
			self.processFileRequest(calc5,fldname_str,fldsubpath,fldtitle_str,fileobj,fld_lo,suppressDescription)
		else:
			log_error("gcnftp: " + self.archive_ + ": Unknown item type")

	def processFolderRequest(self,calc5,fldpath,fld_hi,fld_lo,offset):
		calc10 = calc5to10(calc5)

		# Now we have a folder name in fldpath: fetch it!
		fldinfo = self.repo_.searchHierarchy(fldpath)
		log_info("gcnftp: "+self.archive_+": Found "+str(fldinfo[1])+" folders and "+\
				 str(fldinfo[2])+" files in "+fldpath)
		fldinfo = fldinfo[0]

		multipart = 0
		if len(fldinfo) > 250:
			if (offset+1)*250 < len(fldinfo):
				fldinfo.insert(0,["NEXT_("+chr(0x30+offset+2)+")/", "NEXT_("+chr(0x30+offset+2)+")",ResultType.FOLDER])
				multipart += 1
			if offset > 0:
				fldinfo.insert(0,["PREV_("+chr(0x30+offset)+")/", "PREV_("+chr(0x30+offset)+")",ResultType.FOLDER])
				multipart += 1

		# Update the allcalcs_ structure
		self.gcnlock_.acquire()
		self.allcalcs_[calc10][3] = fld_lo
		self.allcalcs_[calc10][4] = fld_hi
		self.allcalcs_[calc10][5] = fldpath
		self.allcalcs_[calc10][6] = fldinfo
		self.gcnlock_.release()

		# And send!
		if len(fldinfo) > 250:
			log_warn("gcnftp: " + self.archive_ + ": Emitting part %d of multipart large " \
			         "(%d-item) directory" % (offset+1, len(fldinfo)))

		outstr, count = self.foldersToSPFldList(fldinfo,multipart,offset)

		sent = 0
		seqnum = 0
		self.updateRemoteFldName(calc5,fldpath)
		outtoclient(7,-1,lestringify(len(outstr)),calc5,self.gcnlock_,self.clientsocket_)
		while sent<len(outstr):
			chunksize = 250 if (len(outstr)-sent) > 250 else len(outstr)-sent
			chunk = lestringify(sent) + outstr[sent:sent+chunksize]
			outtoclient(7,-1,chunk,calc5,self.gcnlock_,self.clientsocket_)
			sent += chunksize
			seqnum += 1

	def updateRemoteFldName(self,calc5,fldpath):
		if len(fldpath) > 8:
			fldpath = fldpath[0:8]
		fldpath += chr(0)*(9-len(fldpath))
		outtoclient(16,-1,fldpath,calc5,self.gcnlock_,self.clientsocket_)

	def processFileRequest(self,calc5,filepath,subfilepath,filetitle,fileinfo,fld_lo,suppressDescription):

		calc10 = calc5to10(calc5)
		sendChatData = [False]
		doHistUpdate = True

		# 1. Get file from cache or web
		if None == fileinfo:
			log_info("Fetching info for %s (%s)" % (filetitle, filepath))
			fileinfo = self.repo_.getFileInfo(filepath,filetitle)

			zippath = self.filecache.fetchFile(filepath)	#this should extend the cache life XX minutes
			if zippath:
				log_info("Using file from file cache")
			else:
				zipf = self.repo_.downloadFileFromUrl(fileinfo.fileUrl)
				zippath = self.filecache.storeFile(filepath,zipf)
			fldinfo_flds = []	# temporary
			fldinfo = []		# temporary

			# 2. Generate and convert file contents to folder-like listing
			try:
				zipobj = zipfile.ZipFile(zippath,'r')		#open the zip file
				for filename in zipobj.namelist():
					fdata = zipobj.read(filename)
					if filename[-1] == '/':
						fldinfo_flds.append([filename,filename,"FLD",False,''])
					else:
						ftype, calcable = self.zipGetFileType(filename,fdata)
						if ftype == "FLD":
							fldinfo_flds.append([filename,filename,ftype,False,''])
						elif ftype == "TXT":
							fldinfo_flds.append([filename,filename,ftype,False,fdata])
						else:
							fldinfo.append([filename,filename,ftype,calcable,fdata])
			except:
				log_error("gcnftp: " + self.archive_ + ": Cannot extract non-zip. Aborting with appropriate message.")
				fileinfo.description = "[COULD NOT EXTRACT!] " + fileinfo.description

			fldinfo = fldinfo_flds + fldinfo
			fileinfo.fldContents = fldinfo
		else:
			fldinfo = fileinfo.fldContents

		if subfilepath != "" and fldinfo[fld_lo][2] == "TXT" and subfilepath[-1] != '/':
			# Deal with "displaying" text files"
			if '/' in subfilepath[1:]:
				subfilepath = subfilepath[:subfilepath.find('/')+1]	#to include the /
			else:
				subfilepath = ""
			doHistUpdate = False
			sendChatData = [True, fldinfo[fld_lo][1], fldinfo[fld_lo][4]]
			
			self.HandleFolderRequest(0xFF, 0xFF, calc5)
			self.sendChatText(calc5,sendChatData[1],sendChatData[2])	# Destination, title, contents
			return
			#outstr, count = self.itemsToSPFldList(fldinfo,subfilepath)
				
		elif subfilepath == "" or fldinfo[fld_lo][2] == "FLD":
			# Deal with folders
			outstr, count = self.itemsToSPFldList(fldinfo,subfilepath)
		else:
			log_error("gcnftp: " + self.archive_ + ": Can't dive into unknown items '%s' (type '%s')" % (subfilepath, fldinfo[fld_lo][2]))
			return

		# 3. Send listing to client
		sent = 0
		seqnum = 0
		self.updateRemoteFldName(calc5,filepath if subfilepath == "" else subfilepath)
		outtoclient(7,-1,lestringify(len(outstr)),calc5,self.gcnlock_,self.clientsocket_)
		while sent<len(outstr):
			chunksize = 250 if (len(outstr)-sent) > 250 else len(outstr)-sent
			chunk = lestringify(sent) + outstr[sent:sent+chunksize]
			outtoclient(7,-1,chunk,calc5,self.gcnlock_,self.clientsocket_)
			sent += chunksize
			seqnum += 1

		# 4. Update information in self.allcalcs_ (if descending)
		if doHistUpdate:
			fileinfo.fileSubPath = subfilepath		#Needed for RTGs

			self.gcnlock_.acquire()
			self.allcalcs_[calc10][3] = fld_lo
			self.allcalcs_[calc10][4] = 0xFF
			self.allcalcs_[calc10][5] = filepath
			self.allcalcs_[calc10][6] = fileinfo
			self.gcnlock_.release()

		# 5. Generate and send description (only at top level) or for TXT files
		if subfilepath == "" and doHistUpdate and not(suppressDescription):
			sendChatData = [True,fileinfo.fileName,fileinfo.description]

		if sendChatData[0] == True:
			self.sendChatText(calc5,sendChatData[1],sendChatData[2])	# Destination, title, contents

	def sendChatText(self, calc5, title, body):
		sent = 0

		title = calcencode(title)
		title = (title if len(title) < 15 else title[:15]) + chr(0)
		title = '--'+title.strip() # important padding - see sandpapr.asm

		body = calcencode(body)
		body = (body + chr(0)) if len(body) < 1024 else (body[0:1024] + chr(0))

		firstmsg = lestringify(len(body))+lestringify(len(title))+title
		outtoclient(14,-1,firstmsg,calc5,self.gcnlock_,self.clientsocket_)

		while sent<len(body):
			chunksize = 250 if (len(body)-sent) > 250 else len(body) - sent
			chunk = lestringify(sent) + lestringify(chunksize) + body[sent:sent+chunksize]
			outtoclient(15,-1,chunk,calc5,self.gcnlock_,self.clientsocket_)
			sent += chunksize

	def zipGetFileType(self, name, data):			# returns [type, calcable]
		if len(data) < 8:
			return ["UNK", False]
		if data[0:8] == "**TI83F*" or data[0:8] == "**TI83**":		#TI-83/+ file
			try:
				cftype = ord(data[0x37 + 0x04])
				cftypestr = self.fileTypeDec2Str(cftype)
				return [cftypestr, cftypestr != "UNK"]
			except:
				return ["UNK", False]		#Too short
		if data[0:5] == "%PDF-":
			return ["PDF", False]									#PDF
		if data[0:4] == chr(0x89)+"PNG":
			return ["PNG", False]									#PNG
		if data[0:4] == "GIF8":
			return ["GIF", False]									#GIF
		if data[0:2] == chr(0xFF)+chr(0xD8):
			return ["JPG", False]									#JPEG
		return ["TXT", False]

	def fileTypeDec2Str(self,cftype):
		if cftype == 0x01:
			return "8xl"	#Real list
		if cftype == 0x02:
			return "8xm"	#Matrix
		if cftype == 0x04:
			return "8xs"	#String
		if cftype == 0x05:
			return "8xp"	#Prog
		if cftype == 0x06:
			return "8xp"	#Prot Prog
		if cftype == 0x07:
			return "8xi"	#Picture
		if cftype == 0x08:
			return "8xd"	#GDB
		if cftype == 0x0D:
			return "8xl"	#Complex list
		if cftype == 0x15:
			return "8xv"	#Appvar
		if cftype == 0x17:
			return "8xg"	#Group
		return ["UNK", False]		#Fall-through

	def foldersToSPFldList(self, fldinfo, multipart, offset):
		''' Generate Sandpaper-understandable file list from a list of items, treating
		each item like a folder regardless of path format. Each item in the list
		should itself be a [path, name] list.
		'''
		makeData = lambda fileline: chr(5) + chr(0x0A) + chr(min(9,1+len(fileline[1]))) + \
						            chr(count) + fileline[1][0:min(8,len(fileline[1]))]

		outstr = ""
		count = 0
		for fileline in fldinfo[0:multipart]:
			outstr += makeData(fileline)
			count += 1
		for fileline in fldinfo[multipart+250*offset:min(len(fldinfo),multipart+250*(offset+1))]:
			#show folders and zip files
			if fileline[0][-1] == '/' or (len(fileline[0]) >= 4 and fileline[0][-4:] == '.zip'):
				outstr += makeData(fileline)
			count += 1
		return [outstr, count]

	def itemsToSPFldList(self, fldinfo, subfilepath):
		''' Generate Sandpaper-understandable file list from a list of items, treating
		each item like a file or folder based on its path. Each item in the list
		should itself be a [path, name] list.
		Item format: [filepath, filename, type, calcable, contents]
		'''
		outstr = ""
		count = 0
		for fileline in fldinfo:

			#print "Item %s in subfld %s" % (fileline[0],subfilepath)
			if subfilepath != "" and not("//"+subfilepath in "//"+fileline[0]):	#only show items in this folder
				count += 1
				continue

			if subfilepath != "" and fileline[0] == subfilepath:	# don't show this folder in itself
				count += 1
				continue

			if subfilepath == "" and '/' in fileline[0]:			# Don't show too-deep folders in this folder
				if fileline[0][-1] != '/':							# ...or items in other folders
					count += 1
					continue
				else:
					if fileline[0].count('/') > 1:
						count += 1
						continue

			if fileline[0][-1] == '/':				#folder
				fldname = fileline[1][fileline[1].rfind('/',0,-1)+1:]
				if len(fldname) > 8:
					fldname = fldname[0:7] + '/'
				outstr += chr(5) + chr(0x0E) + chr(min(9,1+len(fldname))) + \
				          chr(count+1) + fldname				#+1 because special folder 00 is normal folder 01.

			else:									#file
				if fileline[2][0:2] == "8x" and fileline[3] == True:
					ftypedec = ord(fileline[4][0x37 + 0x04])
					fheadname = fileline[4][(0x37 + 0x05):(0x37 + 0x05 + 8)]

					if ftypedec in [0x01,0x05,0x06,0x0D,0x15,0x17]:		#rlist, prog, prot prog, clist, appvar, group
						while fheadname[-1] == chr(0x00):			#strip off nulls
							fheadname = fheadname[0:-1]
						if len(fheadname) == 1 and fheadname[0] == chr(0x5D):	# tVarLst
							fheadname += chr(0x00)								# tVarList, tL1

						outstr += chr(ftypedec) + chr(0x00) + chr(min(8,len(fheadname))) + \
								  fheadname[0:min(8,len(fheadname))]
						#print "Named type %d with name %s" % (ftypedec,fheadname)
					else:
						outstr += chr(ftypedec) + chr(0x08) + chr(2) + \
								  fheadname[1] + fheadname[0]
						#print "Numbered type %d with name %d %d" % (ftypedec,ord(fheadname[0]),ord(fheadname[1]))

				elif fileline[2] == "TXT" or fileline[2] == "FLD":
					outstr += chr(5) + chr(0x0E) + chr(min(9,1+len(fileline[1]))) + \
							  chr(count+1) + fileline[1][0:min(8,len(fileline[1]))]
					#print "Named folder with name %s" % (fileline[1][0:min(8,len(fileline[1]))])
				#else ignore/skip file
				count += 1
		return [outstr, count]

def lestringify(innum):
	return chr(innum&0x00ff)+chr((innum>>8)&0x00ff)

def ledestringify(instr):
	return ord(instr[0]) + 256*ord(instr[1])

def calc5to10(calc5):
	return "%02X%02X%02X%02X%02X" % (ord(calc5[0]), ord(calc5[1]), ord(calc5[2]), ord(calc5[3]), ord(calc5[4]))

def cleanstr(instr):
	outstr = ""
	for i in range(0,len(instr)-1):
		if ord(instr[i]) <= 0:
			break;
		outstr += instr[i]
	return outstr

start()
