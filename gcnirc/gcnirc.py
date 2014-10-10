#!/usr/bin/python

# globalCALCnet Metahub (Hub): logging.py
# Christopher Mitchell, 2011-2014
# Licensed under the BSD 3-Clause License (see LICENSE)

import os.path
import urllib2
import urllib
import sys
import socket
import string
import irclib
from irclib import *
import ircbot
from ircbot import *
import sched, time
import threading
import random
import signal
import string
import re
import copy
import ssl
from htmlentitydefs import name2codepoint as n2cp
from logging import *

COOKIEFILE = 'cookies.lwp'

#irc
CHANNEL='#cemetech'
CHANNELS_POSTONLY=[]
HOST="irc.arcti.ca"
HOST2="irc.nac.net"
PORT=6667
NICK="gCnIRCHub"
IDENT="gCnIRCHub"
BOTNET="Melisma"
MYNAME=NICK
REALNAME="Cemetech IRC-gCn linker"
readbuffer=""
highlineid=0
OPBOT="CalcBot"

#quiz
QUIZBOT="Melisma"
quizactive = 0

#phpBB
warnlist = []				# Stores which users have been warned
from hubsecret import *

#gcn info
USESSL = True
GCNSERVER = "gcnhub.cemetech.net"
GCNPORT = 4295
if USESSL:
	GCNPORT = 4296
GCNREMOTE = "IRCHub"
GCNLOCAL = "gCnIRCHub"
allcalcs = dict()

#scheduler
s=sched.scheduler(time.time, time.sleep)
gcnlock = threading.Lock()

# the path and filename to save your cookies in
cj = None
ClientCookie = None
cookielib = None

def hook(signum,frame):
	client.connection.part(CHANNEL,"Disconnecting from gCn")
	client.connection.quit("goodnight cruel world")
	gcnpost(sid,MYNAME,"Disconnecting from IRC",1)
	sys.exit(0)

signal.signal(signal.SIGTERM,hook)
signal.signal(signal.SIGINT,hook)

class ControlRestart(Exception):
	def __init__(self,value):
		self.value = value
	def __str__(self):
		return repr(Self.value)

# Create our bot class

class StatBot ( ircbot.SingleServerIRCBot ):

   # Join the channel when welcomed
	def on_welcome ( self, connection, event ):
		log_info('gcnirc: irc started, joining channel "'+CHANNEL+'"')
		connection.join ( CHANNEL )
		if (len(CHANNELS_POSTONLY) > 0):
			for chan in CHANNELS_POSTONLY:
				connection.join(chan)
		log_info('gcnirc: channel "'+CHANNEL+'" joined')

		# Identify
		global BOTNETPASS
		#print 'IDENTING: '+"ident "+BOTNETPASS
		connection.privmsg(BOTNET,"ident "+BOTNETPASS);

	def on_action ( self, connection, event ):
		source = (event.source().split("!"))[0]
		if event.target() != CHANNEL:
			#print "ignoring ctcp action to "+event.target();
			return
		message = str(event.arguments()[0])
		log_info('gcnirc: A CTCP ACTION was seen: *'+source+" "+message)
		message = StripTags(string.replace(message,"+","_-_"))

		gcnpost(sid,source,message,2)

   # React to channel messages
	def on_pubmsg ( self, connection, event ):
		if event.target() != CHANNEL:
			print "ignoring pubmsg to "+event.target();
			return
		source = (event.source().split("!"))[0]
		for ignored in IRCIGNORELIST:
			if source == ignored:
				return
		message = str(event.arguments()[0])
		log_info('gcnirc: Received pubmsg: ' + message)
		#message = StripTags(string.replace(message,"+","_-_"))
		#message = string.replace(message,"+","_-_")
		message = string.replace(message,chr(160)," ");

		#handle quiz
		global QUIZBOT,quizactive
		if source == QUIZBOT:
			if message.find("{MoxQuizz} The question no. ") > -1:
				log_warn("gcnirc: Quiz active, halting IRC->gCn forwarding")
				if quizactive == 0:
					connection.privmsg(CHANNEL,"[NOTE] Quiz active, IRC->gCn forwarding temporarily disabled");
				quizactive = 1
			if message.find("Quiz stopped.") > -1 or message.find("Quiz halted.") > -1:
				log_info("gcnirc: Quiz inactive, restarting IRC->gCn forwarding")
				if quizactive == 1:
					connection.privmsg(CHANNEL,"[NOTE] Quiz inactive, IRC->gCn forwarding resumed");
				quizactive = 0
		if message[:3] == "!me" or message[:3] == "/me":
			message = message[4:]
			#connection.privmsg(CHANNEL,message)
			gcnpost(sid,source,message,2)
		else:
			gcnpost(sid,source,message,1)

	def _on_join(self, c, e):

		"""[Internal]"""
		ch = e.target()
		nick = nm_to_n(e.source())
		if nick == c.get_nickname():
			self.channels[ch] = Channel()

			gcnpost(sid,MYNAME,"has been reconnected",2)

		else:

			gcnpost(sid,nick,"has entered the room",2)

		self.channels[ch].add_user(nick)

	def _on_quit(self, c, e):
		"""[Internal]"""
		nick = nm_to_n(e.source())
		gcnpost(sid,nick,"has left the room",2)
		for ch in self.channels.values():
			if ch.has_user(nick):
				ch.remove_user(nick)

	def _on_part(self, c, e):
		"""[Internal]"""
		ch = e.target()
		nick = nm_to_n(e.source())
		if nick != c.get_nickname():

			gcnpost(sid,nick,"has left the room",2)
			self.channels[ch].remove_user(nick)

	def _on_nick(self, c, e):
		"""[Internal]"""
		before = nm_to_n(e.source())
		after = e.target()
		for ch in self.channels.values():
			if ch.has_user(before):
				ch.change_nick(before, after)

				gcnpost(sid,before,"is now known as "+after,2)



	def randomAdj(self):
		adjs = ['wet','limp','large','big','largish','fat','rotting']
		return adjs[random.randint(0,6)]
	def randomFish(self):
		fish = ['trout','salmon','codfish','halibut','whale','shark']
		return fish[random.randint(0,5)]
		
	def get_version(self):
		return "Miranda IRC v 0.5.1.3, (c) J Persson 2004"
		
	def _on_kick(self, c, e):
		"""[Internal]"""
		nick = e.arguments()[0]
		channel = e.target()

		if nick == c.get_nickname():
			del self.channels[channel]

			gcnpost(sid,MYNAME,"was disconnected",2)

			self.connection.join(CHANNEL)
			
		else:

			gcnpost(sid,nick,"was kicked",2)

			self.channels[channel].remove_user(nick)

def shortcreateurls(input):
	curloc = 0
	while curloc <> -1:
		curloc = string.find(input,"http://",curloc)
		if -1 <> curloc:
			maxend = string.find(input," ",curloc)
			if maxend == -1:
				maxend = len(input)
			length = maxend-curloc
			a = input[curloc+length-1]
			while a == '.' or a == ']' or a == ')' or a == ',' or a == ';':
				length -= 1
				a = input[curloc+length-1]
			firstslash = curloc+7
			while firstslash<len(input) and input[firstslash] <> "/" and firstslash<curloc+length:
				firstslash += 1
			output = '('+input[curloc+7:firstslash]+") "+input[curloc:curloc+length]
			#print(output)
			newlen = len(output)
			if curloc > 0:
				output = input[0:curloc-1] + output
			if curloc + length < len(input):
				output = output + input[curloc+length:-1]
			input = output
			curloc = curloc+newlen
	return shorturls(input,0)

def shorturls(input,striphtml):
	urlrepl = True
	maxpos = 0
	while urlrepl:
		urlrepl = False
		urlmatch = re.search(r'<a class="[a-zA-Z0-9_]+" href="([^"]+)"( target="[^"]+")?>([^<]+)</a>',input[maxpos:],re.I)
		if None != urlmatch:
			#print(urlmatch.groups())
			urlparts = string.split(urlmatch.groups()[0],"#")
			fetchurl = "http://tinyurl.com/api-create.php?"+urllib.urlencode({'url' : urlparts[0]})
			txheaders =  {'User-agent' : 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
			try:
				req = Request(fetchurl, None, txheaders)
				handle = urlopen(req)
			
			except IOError, e:
				print 'We failed to open "%s".' % fetchurl
				if hasattr(e, 'code'):
					print 'We failed with error code - %s.' % e.code
				elif hasattr(e, 'reason'):
					print "The error object has the following 'reason' attribute :"
					print e.reason
				return input
			else:
				cur = handle.readline()
				newurl = string.strip(cur)
				if len(urlparts) > 1:
					newurl = newurl+"#"+urlparts[1]
				if striphtml == 1:
					if len(urlmatch.groups()) > 2:
						repl = urlmatch.groups()[2]+" ("+newurl+")"
					else:
						repl = urlmatch.groups()[1]+" ("+newurl+")"
				else:
					if len(urlmatch.groups()) > 2:
						repl = "<a class=\"saxgray\" href=\""+newurl+"\" target=\"_blank\">"+urlmatch.groups()[2]+"</a>"
					else:
						repl = "<a class=\"saxgray\" href=\""+newurl+"\" target=\"_blank\">"+urlmatch.groups()[1]+"</a>"
			inputnew = re.sub(r'(?i)<a class="[a-zA-Z0-9_]+" href="[^"]+"( target="[^"]+")?>[^<]+</a>',repl,input[maxpos:],1)
			if 0 == striphtml:
				maxpos2 = string.find(inputnew,"</a>") + maxpos
				if maxpos > 0:
					input = input[0:maxpos-1] + inputnew
				else:
					input = inputnew
				maxpos = maxpos2
			else:
				if maxpos == 0:
					input = inputnew
			#print(splitline[2])
			if maxpos < len(input):
				urlrepl = True
	return input


# Let's see if cookielib is available
try:
	import cookielib
except ImportError:
	# If importing cookielib fails
	# let's try ClientCookie
	try:
		import ClientCookie
	except ImportError:
		# ClientCookie isn't available either
		urlopen = urllib2.urlopen
		Request = urllib2.Request
	else:
		# imported ClientCookie
		urlopen = ClientCookie.urlopen
		Request = ClientCookie.Request
		cj = ClientCookie.LWPCookieJar()

else:
	# importing cookielib worked
	urlopen = urllib2.urlopen
	Request = urllib2.Request
	cj = cookielib.LWPCookieJar()
	# This is a subclass of FileCookieJar
	# that has useful load and save methods
	
if cj is not None:
# we successfully imported
# one of the two cookie handling modules

	if os.path.isfile(COOKIEFILE):
		# if we have a cookie file already saved
		# then load the cookies into the Cookie Jar
		cj.load(COOKIEFILE)

	# Now we need to get our Cookie Jar
	# installed in the opener;
	# for fetching URLs
	if cookielib is not None:
		# if we use cookielib
		# then we get the HTTPCookieProcessor
		# and install the opener in urllib2
		opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
		urllib2.install_opener(opener)

	else:
		# if we use ClientCookie
		# then we get the HTTPCookieProcessor
		# and install the opener in ClientCookie
		opener = ClientCookie.build_opener(ClientCookie.HTTPCookieProcessor(cj))
		ClientCookie.install_opener(opener)

	
def gcnpost(sid,source,message,type):
	global quizactive;
	global allcalcs
	if quizactive == 1:
		log_warn("gcnirc: [MSG omitted] "+source+": "+message)
		return
	else:
		log_info("gcnirc: [MSG] "+source+": "+message)
	kickthem = 0
	for badword in BADWORDS:
		if (-1 < message.lower().find(badword.lower())):
			kickthem = 1;
			kickwhy = 'Disallowed word';
	if (-1 < message.find('\x03')):
		kickthem = 1;
		kickwhy = 'Disallowed use of colors';

	if kickthem == 1:
		global warnlist, WARNEXPIRETIME;
		print("kick "+source)
		inwarnlist = 0
		warnlevel = 1
		#print("iter start")
		for useritem in copy.copy(warnlist):
			#print(useritem)
			if useritem[2] < time.mktime(time.localtime())-WARNEXPIRETIME:
				warnlist.remove(useritem)
			else:
				if useritem[0] == source:
		#			print("user found")
					warnlist[warnlist.index(useritem)] = [source, useritem[1]+1, time.mktime(time.localtime())]
					warnlevel = useritem[1]+1
					inwarnlist = 1
		#print("iter finish")

		if inwarnlist == 0:
			warnlist.append([source, warnlevel, time.mktime(time.localtime())])

		#print("appended")
		
		if warnlevel > 2:
			client.connection.mode(CHANNEL,"+b "+source);

		#print("kicking")
		return

	message = shortcreateurls(message)

	#WRITE TO gCn NETWORK
	if type == 2:
		outmsg = '*'+source+' '+message
	else:
		outmsg = source+': '+message

	#cleaning
	outmsg = outmsg.replace('_-_','+');
	outmsg = outmsg.replace('[',chr(0xC1));

	#tell everyone
	gcnlock.acquire()
	msgindex = 0;
	while msgindex < len(outmsg):
		thisoutmsg = chr(173) + outmsg[msgindex:msgindex+min(len(outmsg)-msgindex,240)];
		outmsghdr = chr(0xAA) + chr(0xAA) + chr(0xAA) + chr(0xAA) + chr(0xAA) + \
			    chr(len(thisoutmsg)&0x00ff) + \
			    chr((len(thisoutmsg)>>8) & 0x007f)
		outmsghdr = outmsghdr + thisoutmsg
		for sid,calc in allcalcs.items():
			print "Forwarding '"+outmsghdr+"' to '"+calc[0]+"' ("+calc5to10(calc[2])+")"
			thismsg = chr(255) + chr(137) + calc[2] + outmsghdr + chr(42)
			msglen  = len(thismsg)
			thismsg = chr(msglen & 0x00ff) + chr((msglen >> 8) & 0x00ff) + 'f' + thismsg
			clientsocket.sendall(thismsg)
			
		msgindex += 240
	gcnlock.release()

def StripTags(text):
	return text
	
def StripSmiles(text):
	finished = 0
	while not finished:
		finished = 1
		# check if there is an open tag left
		start = text.find('<img src=\"http://www.cemetech.net/img/sidebar/emote/')
		if start >= 0:
			# if there is, check if the tag gets closed
			stop = text[start:].find('alt=\"')
			stop2 = text[start+stop+1:].find('\" />')
			if stop >= 0:
				# if it does, strip it, and continue loop
				text = text[:start] + text[start+stop+5:start+stop+1+stop2] + text[start+stop+5+stop2:]
				finished = 0
	return text
	
def StripBR(text):
	return text.split("<br />")
	
def StripTabs(text):
	finished = 0
	while not finished:
		finished = 1
		# check if there is an open tag left
		start = text.find("&nbsp")
		if start >= 0:
				text = text[:start] + "\t" + text[start+1:]
				finished = 0
	return text

def start():
	global client
	global saxbot
	global sid
	global LOGINPATH
	global PASSWORD
	global BOTNETPASS
	sid = ''

	gcnthr = gCnManage()
	gcnthr.start()

	log_info('gcnirc: Creating irc client')
	client = StatBot([(HOST, PORT)], NICK, REALNAME)
	log_info('gcnirc: Starting irc')
	client.start()

class ping_thread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)

	def run(self):
		global clientsocket
		msg = chr(255) + chr(137) + chr(0) + chr(0) + chr(0) + chr(0) + chr(0) + \
		      chr(0xAA) + chr(0xAA) + chr(0xAA) + chr(0xAA) + chr(0xAA) + chr(9) + chr(0) + \
		      chr(171) + "IRC" + chr(0) + chr(0) + chr(0) + chr(0) + chr(0) + chr(42)
		msg = chr(len(msg))+chr(0)+'b'+msg
		while 1==1:
			#print "sending broadcast of length "+str(len(msg))

			gcnlock.acquire()
			for sid,calc in allcalcs.items():
				allcalcs[sid] = (calc[0],calc[1]-1,calc[2])
				if calc[1] <= 0:
					client.connection.privmsg(CHANNEL,"**"+calc[0]+" timed out and left the room")
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
		global clientsocket
		global client
		global allcalcs

		#create an INET, STREAMing socket
		log_info('gcnirc: Starting gCn client')
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
		calcmsg = chr(10)+chr(0)+"cAAAAAAAAAA"
		clientsocket.sendall(calcmsg)
		time.sleep(0.1);

		spt = ping_thread()
		spt.start()

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
					log_warn("gcnirc: Unknown incoming msg type '"+thismsgtype+"'!")
					#continue;
				elif ord(thismsg[14]) == 171:			# Ping (0xAB)
					#ping received
					calc10 = calc5to10(thismsg[7:12])
					uname = cleanstr(thismsg[15:])
					log_info("gcnirc: [MSG] Incoming ping from calc '"+calc10+"' ("+uname+")")

					gcnlock.acquire()
					if not(allcalcs.has_key(calc10)):
						#"fullping = "+thismsg
						client.connection.privmsg(CHANNEL,"**"+uname+" entered the room")
						allcalcs[calc10] = (uname,12,thismsg[7:12])
					if allcalcs[calc10][0] != uname:
						log_info("gcnirc: "+allcalcs[calc10][0]+" changed named to "+uname)
						client.connection.privmsg(CHANNEL,"**"+allcalcs[calc10][0]+" is now known as "+uname+"")
						allcalcs[calc10] = (uname,12,thismsg[7:12])
					allcalcs[calc10] = (allcalcs[calc10][0],12,allcalcs[calc10][2])
					gcnlock.release()

				elif ord(thismsg[14]) == 172:			# Disconnect (0xAC)
					#disconnect received
					calc10 = calc5to10(thismsg[7:12])
					log_info("gcnirc: [MSG] Incoming disconnect from calc '"+calc10+"'")

					gcnlock.acquire()
					if allcalcs.has_key(calc10):
						client.connection.privmsg(CHANNEL,"**"+allcalcs[calc10][0]+" left the room")
						del allcalcs[calc10]
					gcnlock.release()

				elif ord(thismsg[14]) == 173:		# Message (0xAD)
					#chat msg received
					calc10 = calc5to10(thismsg[7:12])

					gcnlock.acquire()
					if not(allcalcs.has_key(calc10)):
						uname = cleanstr(thismsg[15:])
						client.connection.privmsg(CHANNEL,"**"+uname+" entered the room")
						allcalcs[calc10] = (uname,12,thismsg[7:12])
					allcalcs[calc10] = (allcalcs[calc10][0],12,allcalcs[calc10][2])
					gcnlock.release()

					outmsg = thismsg[15:-1]
					outmsg = outmsg.replace(chr(0xC1),'[')
					outmsg = '['+outmsg.replace(':','] ',1)
					client.connection.privmsg(CHANNEL,outmsg)
				else:
					log_warn("gcnirc: Unknown calculator msg type "+str(ord(thismsg[14]))+" received!")
				recbuf = recbuf[3+thismsglen:]
				recbufqueue -= 3+thismsglen
				if recbufqueue != len(recbuf):
					log_warn("gcnirc: buffer length mismatch, discarding buffer")
					recbuf = ""
					recbufqueue = 0

def calc5to10(calc5):
	return "%02X%02X%02X%02X%02X" % (ord(calc5[0]), ord(calc5[1]), ord(calc5[2]), ord(calc5[3]), ord(calc5[4]))

def cleanstr(instr):
	outstr = ""
	for i in range(0,len(instr)-1):
		if ord(instr[i]) <= 0:
			break;
		outstr += instr[i]
	return outstr

def substitute_entity(match):
	ent = match.group(3)
    
	if match.group(1) == "#":
		if match.group(2) == '':
			return unichr(int(ent))
		elif match.group(2) == 'x':
			return unichr(int('0x'+ent, 16))
	else:
		cp = n2cp.get(ent)

		if cp:
			return unichr(cp)
		else:
			return match.group()

def decode_htmlentities(string):
	entity_re = re.compile(r'&(#?)(x?)(\w+);')
	try:
		retval = entity_re.subn(substitute_entity, string)[0]
	except UnicodeDecodeError:
		return string
	else:
		return retval

while 1==1:
	start()
