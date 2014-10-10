#!/usr/bin/python

# globalCALCnet Guestbook Bridge: gcnirc.py
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
import copy
from htmlentitydefs import name2codepoint as n2cp
from subprocess import *
from logging import *

USESSL = True
#gcn info
GCNSERVER = "gcnhub.cemetech.net"
GCNPORT = 4295
if USESSL:
	GCNPORT = 4296
GCNREMOTE = "IRCHub"
GCNLOCAL = "GuestbookBridge"
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

def fetchandpost(url,lasttime):
	#First grab the page
	req = urllib2.Request(url)
	response = urllib2.urlopen(req)
	the_page = response.read()
	
	newlasttime = lasttime
	lines = the_page.split("\n")
	log_info('gcnguest: got ' + str(len(lines)) + ' lines from URL: ' + '||'.join(lines))
	for line in lines:
		pieces = line.split('|');
		if len(pieces) < 4:
			log_warn('gcnguest: got short line ' + '||'.join(pieces))
			break;
		if lasttime >= int(pieces[4]):
			return newlasttime
		newlasttime = max(int(pieces[4]),newlasttime)
		state = pieces[0]
		email = pieces[1]
		message = pieces[2]
		date = pieces[4]
		outmsg = calcencode('(GUEST)') + chr(0) + calcencode(state) + chr(0) + \
		 calcencode(time.strftime("%H:%M", time.localtime(int(date)))) + chr(0) + \
		 calcencode(message) + chr(0)
		log_info('gcnguest: Sending along "' + outmsg + '"')
		outtoclient(0xAD,outmsg,'AAAAAAAAAA');

		gcnlock.acquire()
		msgindex = 0;
		while msgindex < len(outmsg):
			thisoutmsg = chr(173) + outmsg #outmsg[msgindex:msgindex+min(len(outmsg)-msgindex,240)];
			outmsghdr = chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(len(thisoutmsg)&0x00ff)+chr((len(thisoutmsg)>>8)&0x00ff)
			outmsghdr = outmsghdr + thisoutmsg
			for sid,calc in allcalcs.items():
				#print "Forwarding '"+outmsghdr+"' to '"+calc[0]+"' ("+calc5to10(calc[2])+")"
				thismsg = chr(255)+chr(137)+calc[2]+outmsghdr+chr(42)
				thismsg = chr(len(thismsg)&0x00ff)+chr((len(outmsg)>>8)&0x00ff)+'f'+thismsg
				clientsocket.sendall(thismsg)
			msgindex += 240
		gcnlock.release()
	return newlasttime
	
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

def calcencode(input):
	#newlines
	#input = "\n".join(input)

	#character conversion
	input = ''.join([chr(0xD0) if ord(c)>=len(t2x) else chr(t2x[ord(c)]) for c in input])
	return input

def calcdecode(input):
	input = ''.join(['?' if ord(c) > len(x2t) else x2t[ord(c)] for c in input])
	return input

def outtoclient(type,contents,sid):
	gcnlock.acquire()
	msgindex = 0;
	thisoutmsg = chr(type) + contents
	outmsghdr = chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(len(thisoutmsg)&0x00ff)+chr((len(thisoutmsg)>>8)&0x00ff)
	outmsghdr = outmsghdr + thisoutmsg
	#print "Forwarding '"+outmsghdr+"' to '"+calc5to10(sid)+"'"
	thismsg = chr(255)+chr(137)+sid+outmsghdr+chr(42)
	thismsg = chr(len(thismsg)&0x00ff)+chr((len(thismsg)>>8)&0x00ff)+'f'+thismsg
	clientsocket.sendall(thismsg)
	gcnlock.release()

def start():
	gcnthr = gCnManage()
	log_info('gcnguest: Starting gCn manager')
	gcnthr.start()
	log_info('gcnguest: gCn manager started.')

class ping_thread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)

	def run(self):
		global clientsocket
		msg = chr(255)+chr(137)+chr(0)+chr(0)+chr(0)+chr(0)+chr(0)+chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(0xAA)+chr(9)+chr(0)+chr(171)+"GuestBridge"+chr(0)+chr(0)+chr(0)+chr(0)+chr(0)+chr(42)
		msg = chr(len(msg))+chr(0)+'b'+msg
		while 1==1:
			#print "sending broadcast of length "+str(len(msg))

			gcnlock.acquire()
			for sid,calc in allcalcs.items():
				allcalcs[sid] = (calc[0],calc[1]-1,calc[2])
				if calc[1] <= 0:
					del allcalcs[sid]
			clientsocket.sendall(msg)
			gcnlock.release()
			time.sleep(5.0)

class gCnManage(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)

	def run(self):
		global GCNSERVER
		global GCNPORT
		global GCNLOCAL
		global GCNREMOTE
		global USESSL
		global clientsocket
		global client
		global allcalcs

		#create an INET, STREAMing socket
		log_info('gcnguest: starting gCn client')
		clientsocket = socket.socket(
		    socket.AF_INET, socket.SOCK_STREAM)
		if USESSL:
			clientsocket = ssl.wrap_socket(clientsocket)
		#bind the socket to a public host,
		# and a well-known port
		clientsocket.connect((GCNSERVER,GCNPORT))

		#gCn join
		joinmsg = chr(2+len(GCNREMOTE)+len(GCNLOCAL))+chr(0)+'j'+chr(len(GCNREMOTE))+GCNREMOTE+chr(len(GCNLOCAL))+GCNLOCAL
		clientsocket.sendall(joinmsg)
		time.sleep(0.1);

		#gCn calculator
		calcmsg = chr(10)+chr(0)+"cGE57800C00"
		clientsocket.sendall(calcmsg)
		time.sleep(0.1);

		spt = ping_thread()
		spt.start()

		recbuf = "";
		recbufqueue = 0;
		lasttime = 0
		while 1==1:
			instring = clientsocket.recv(1024)
			recbuf = recbuf + instring
			recbufqueue += len(instring)
			while recbufqueue > 2 and recbufqueue >= 3+ord(recbuf[0])+256*ord(recbuf[1]):
				thismsglen = ord(recbuf[0])+256*ord(recbuf[1])
				thismsgtype = recbuf[2]
				thismsg = recbuf[3:3+thismsglen]
				if thismsgtype != 'f' and thismsgtype != 'b':
					log_warn("gcnguest: Unknown incoming msg type '"+thismsgtype+"'!")
					#continue;
				else:
					calc5 = thismsg[7:12]
					if ord(thismsg[14]) == 171:
						#ping received
						calc10 = calc5to10(thismsg[7:12])
						uname = cleanstr(thismsg[15:])
						log_info("gcnguest: [MSG] Incoming ping from calc '"+calc10+"' ("+uname+")")

						gcnlock.acquire()
						if not(allcalcs.has_key(calc10)):
							#"fullping = "+thismsg
							allcalcs[calc10] = (uname,12,thismsg[7:12])
						if allcalcs[calc10][0] != uname:
							log_info("gcnguest: "+allcalcs[calc10][0]+" changed named to "+uname)
							allcalcs[calc10] = (uname,12,thismsg[7:12])
						allcalcs[calc10] = (allcalcs[calc10][0],12,allcalcs[calc10][2])
						gcnlock.release()

					elif ord(thismsg[14]) == 46:
						pass

					else:
						log_warn("gcnguest: Unknown calculator msg type "+str(ord(thismsg[14]))+" received!")

				recbuf = recbuf[3+thismsglen:]
				recbufqueue -= 3+thismsglen
				if recbufqueue != len(recbuf):
					log_warn("gcnguest: buffer length mismatch, discarding buffer")
					recbuf = ""
					recbufqueue = 0

			time.sleep(8)
			lasttime = fetchandpost('http://www.cemetech.net/gcn/guests_mf14.txt',lasttime);

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
