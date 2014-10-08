#!/usr/bin/python

# globalCALCnet Web Bridge: gcnweb.py
# Christopher Mitchell, 2011-2014
# Licensed under the BSD 3-Clause License (see LICENSE)

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
import ssl
import copy
from htmlentitydefs import name2codepoint as n2cp
from subprocess import *
from logging import *

USINGSSL = True
#gcn info
GCNSERVER = "gcnhub.cemetech.net"
GCNPORT = 4295
if USINGSSL:
	GCNPORT = 4296
GCNREMOTE = "WebHub"
GCNLOCAL = "WebHub"
allcalcs = dict()

#scheduler
s=sched.scheduler(time.time, time.sleep)
gcnlock = threading.Lock()

#global variables
gcnlock = threading.Lock()
LCDWIDTH = 94
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

def getclippedpage(url):
	#First grab the page
	p1 = Popen(["lynx","-width","32767","-center=off","-dump","-noreferer","-notitle","-validate","-useragent","gCn/1.0 (TI Graphing Calculator; Doors CS 7; Lynx)",url], stdout=PIPE)
	p1.wait()
	contents = p1.communicate()[0].split("\n")
	outcontents = []

	#now do some basic cleaning and estimate the size
	for line in contents:
		outcontents.append(line.strip())
	estsize = len("AA".join(outcontents))

	#find the references, if there are any
	refline = len(outcontents)
	for line in reversed(outcontents):
		refline -= 1
		if line == "References":
			break
	if refline == 0:
		refline = -1
	references = ""
	if refline != -1:
		references = outcontents[refline+2:]
		outcontents = outcontents[:refline-1]

	for i in range(len(references)):
		firstspace = references[i].find(' ')
		if -1 != firstspace:
			references[i] = references[i][firstspace+1:]

	#print some basic page debug info
	log_info("PAGE: %s; SIZE %d, REFS %d" % (url, len(outcontents), len(references)))

	#do the encoding
	calcrefs = calcencode(references)
	calctext = calcencode(outcontents)
	calctext = calclineify(calctext)

	#catch problems
	if len(calctext)+len(calcrefs) > RAMSIZESANE:
		return ["Doc too large."+chr(0xD6)+"Love, WebHub"+chr(0), chr(0)]

	#debugprint(calcrefs)
	#debugprint(calctext)

	return [calctext+chr(0), calcrefs+chr(0)]
	
def debugprint(input):
	output = []
	thisline = ""
	for c in input:
		if ord(c) == 0xD6:
			output.append(thisline)
			thisline = ""
		else:
			thisline += c
	for line in output:
		print line

def calclineify(input):
	output = ''
	column = 0
	offset = 0
	for c in input:
		cw = t2xw[ord(c)]
		if column+cw>LCDWIDTH:
			column = cw
			output += chr(0xD6) + c
		else:
			if c=='[':
				#make sure full link fits on one line
				endcol=column
				offoffset = offset
				ifnumref = True
				while True:
					cprime = input[offoffset]
					if cprime != '[' and cprime != ']' and (cprime < '0' or cprime > '9'):
						isnumref = False
						break
					endcol += t2xw[ord(cprme)]
					offoffset += 1
					if cprime == ']' or not(isnumref):
						break

				if endcol>LCDWIDTH and isnumref:
						column = cw
						output += chr(0xD0) + c
				else:
						column += cw
						output += c
			elif ord(c) == 0xD6:
				output += c
				column = 0
			else:		
				column += cw
				output += c
		offset += 1
	return output

def calcencode(input):
	#newlines
	input = "\n".join(input)

	#character conversion
	input = ''.join([chr(0xD0) if ord(c)>=len(t2x) else chr(t2x[ord(c)]) for c in input])
	return input

def calcdecode(input):
	input = ''.join(['?' if ord(c) > len(x2t) else x2t[ord(c)] for c in input])
	return input

def outtoclient(type,seq,contents,sid):
	gcnlock.acquire()
	msgindex = 0;
	thisoutmsg = chr(type) + chr(seq) + contents
	outmsghdr = chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(len(thisoutmsg)&0x00ff)+chr((len(thisoutmsg)>>8)&0x00ff)
	outmsghdr = outmsghdr + thisoutmsg
	#print "Forwarding '"+outmsghdr+"' to '"+calc5to10(sid)+"'"
	thismsg = chr(255)+chr(137)+sid+outmsghdr+chr(42)
	thismsg = chr(len(thismsg)&0x00ff)+chr((len(thismsg)>>8)&0x00ff)+'f'+thismsg
	clientsocket.sendall(thismsg)
	gcnlock.release()

def start():
	gcnthr = gCnManage()
	log_info('gcnweb: Starting gCn manager')
	gcnthr.start()
	log_info('gcnweb: gCn manager started.')

class gCnManage(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
	def run(self):
		global GCNSERVER
		global GCNPORT
		global GCNLOCAL
		global GCNREMOTE
		global clientsocket
		global client
		global allcalcs

		#create an INET, STREAMing socket
		log_info('gcnweb: starting gCn client')
		clientsocket = socket.socket(
			socket.AF_INET, socket.SOCK_STREAM)
		if USINGSSL:
			clientsocket = ssl.wrap_socket(clientsocket)
		#bind the socket to a public host,
		# and a well-known port
		clientsocket.connect((GCNSERVER,GCNPORT))

		#gCn join
		joinmsg = chr(2+len(GCNREMOTE)+len(GCNLOCAL))+chr(0)+'j'+chr(len(GCNREMOTE))+GCNREMOTE+chr(len(GCNLOCAL))+GCNLOCAL
		clientsocket.sendall(joinmsg)
		time.sleep(0.1);

		#gCn calculator
		calcmsg = chr(10)+chr(0)+"cAAAAAAAAAA"
		clientsocket.sendall(calcmsg)
		time.sleep(0.1);

		recbuf = "";
		recbufqueue = 0;
		while 1==1:
			instring = clientsocket.recv(1024)
			recbuf = recbuf + instring
			recbufqueue += len(instring)
			while recbufqueue > 2 and recbufqueue >= 3+ord(recbuf[0])+256*ord(recbuf[1]):
				thismsglen = ord(recbuf[0])+256*ord(recbuf[1])
				thismsgtype = recbuf[2]
				thismsg = recbuf[3:3+thismsglen]
				if thismsgtype != 'f' and thismsgtype != 'b':
					log_warn("gcnweb: Unknown incoming msg type '"+thismsgtype+"'!")
					#continue;
				else:
					calc5 = thismsg[7:12]
					if ord(thismsg[14]) == 46:
						#request URL
						inputurl = calcdecode(thismsg[15:-1])
						[calctext, calcrefs] = getclippedpage(inputurl)
						outtoclient(47,0,lestringify(len(calctext))+lestringify(len(calcrefs)),calc5)

						mtype = 48
						for body in [calctext,calcrefs]:
							sent = 0
							seqnum = 0
							while sent<len(body):
								chunksize = 250 if (len(body)-sent) > 250 else len(body)-sent
								chunk = body[sent:sent+chunksize]
								outtoclient(mtype,seqnum,chunk,calc5)
								sent += chunksize
								seqnum += 1

							mtype += 1

					else:
						log_warn("gcnweb: Unknown calculator msg type "+str(ord(thismsg[14]))+" received!")
				recbuf = recbuf[3+thismsglen:]
				recbufqueue -= 3+thismsglen
				if recbufqueue != len(recbuf):
					log_warn("gcnweb: buffer length mismatch, discarding buffer")
					recbuf = ""
					recbufqueue = 0

def lestringify(innum):
	return chr(innum&0x00ff)+chr((innum>>8)&0x00ff)
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
