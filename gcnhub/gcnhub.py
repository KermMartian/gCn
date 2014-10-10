#!/usr/bin/python

# globalCALCnet IRC Bridge: logging.py
# Christopher Mitchell, 2011-2014
# Licensed under the BSD 3-Clause License (see LICENSE)

#cookie item phpbb_sid

import os.path
import urllib2
import urllib
import sys
import socket
import string
import sched, time
import threading, thread
import random
import signal
import string
import re
import copy
import errno
import ssl
from logging import *

#set to 1 for no SAX connection, 0 for normal operation
SILENTMODE = 0

COOKIEFILE = 'cookies.lwp'

#phpBB/SAX-related things
from hubsecret import *

#stats tracking
import sched, time
st_bytesin = 0
st_bytesout = 0
st_calcs = 0
st_maxcalcs = 0
s = sched.scheduler(time.time, time.sleep)

#the path and filename to save your cookies in
cj = None
ClientCookie = None
cookielib = None

#gcn tracking
HOSTNAME = "gcnhub.cemetech.net"
GCNPORT = 4295
SSLPORT = 4296
vhublist = dict()
vhublock = threading.Lock()

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
			output = '('+input[curloc+7:firstslash]+") "+'<a class="saxgray" href="'
			output = output + input[curloc:curloc+length] + '" target="_blank">[Link]</a>'
			print(output)
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
				log_error('gcnhub: We failed to open "%s".' % fetchurl)
				if hasattr(e, 'code'):
					log_error('gcnhub: We failed with error code - %s.' % e.code)
				elif hasattr(e, 'reason'):
					log_error("gcnhub: The error object has the following 'reason' attribute: "+e.reason)
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

	
def saxpost(sid,source,message,type):

	if SILENTMODE:
		return

	#print message
	kickthem = 0
	for badword in BADWORDS:
		if (-1 < message.lower().find(badword.lower())):
			kickthem = 1;
			kickwhy = 'Disallowed word';
	if (-1 < message.find('\x03')):
		kickthem = 1;
		kickwhy = 'Disallowed use of colors';

	if kickthem == 1:
		return

	# Construct the outgoing request and send it
	message = urllib.urlencode({'message' : shortcreateurls(message)})
	who = urllib.urlencode({'who' : source})
	type = urllib.urlencode({'type' : type})
	theurl = SAXHOST + SAXSAY + '?key=' + SAXKEY + '&' + message + '&' + who + '&' + type
	txdata = None
	txheaders =  {'User-agent' : 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
	try:
		req = Request(theurl, txdata, txheaders)
		# create a request object
	
		handle = urlopen(req)
		# and open it to return a handle on the url
	
	except IOError, e:
		log_error('gcnhub: We failed to open "%s".' % theurl)
		if hasattr(e, 'code'):
			log_error('gcnhub: We failed with error code - %s.' % e.code)
		elif hasattr(e, 'reason'):
			log_error("gcnhub: The error object has the following 'reason' attribute :"+e.reason)
			log_error("gcnhub: This usually means the server doesn't exist,',")
			log_error("is down, or we don't have an internet connection.")
		sys.exit()
	else:
		returned = handle.readline()
		if returned[0:2] != 'OK':
			returned = "Cemetech: " + returned
			log_error("gchub: "+returned)
			client.connection.privmsg(CHANNEL,"ERROR: "+returned)
			raise Exception,returned

def statswrite():
	global st_bytesin
	global st_bytesout
	global st_maxcalcs
	saxmsg = "In the last hour, %d bytes received, %d bytes transmitted by this gCn metahub; max %d calcs connected." % (st_bytesin,st_bytesout,st_maxcalcs)
	if st_maxcalcs <= 1 or st_bytesout == 0 or st_bytesin == 0:
		st_bytesin = 0
		st_bytesout = 0
		st_maxcalcs = 0
		return
	st_bytesin = 0
	st_bytesout = 0
	st_maxcalcs = 0
	saxpost(0,"gCn",saxmsg,1);

def startSSL():
	#create an INET, STREAMing socket
	serversslsocket = socket.socket(
	    socket.AF_INET, socket.SOCK_STREAM)
	if KEYFILE:
		serversslsocket = ssl.wrap_socket(serversslsocket, keyfile=KEYFILE, certfile=CERTFILE)
	else :
		serversslsocket = ssl.wrap_socket(serversslsocket, certfile=CERTFILE)
	serversslsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	#bind the socket to a public host,
	# and a well-known port
	serversslsocket.bind((HOSTNAME, SSLPORT))
	
	#become a server socket
	serversslsocket.listen(5)

	while 1==1:
		#accept connections from outside
		(clientsocket, address) = serversslsocket.accept()
		#now do something with the clientsocket
		#in this case, we'll pretend this is a threaded server
		ct = client_thread(clientsocket,address)
		ct.start()

def start():
	global client
	global sid
	vhublist = dict()
	vhublock = threading.Lock()

	ss = stats_thread()
	ss.start()

	#create an INET, STREAMing socket
	serversocket = socket.socket(
	    socket.AF_INET, socket.SOCK_STREAM)
	serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	#bind the socket to a public host,
	# and a well-known port
	serversocket.bind((HOSTNAME, GCNPORT))
	#become a server socket
	serversocket.listen(5)
	thread.start_new_thread(startSSL, ())
	while 1==1:
		#accept connections from outside
		(clientsocket, address) = serversocket.accept()
		#now do something with the clientsocket
		#in this case, we'll pretend this is a threaded server
		ct = client_thread(clientsocket,address)
		ct.start()

class stats_thread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)

	def run(self):
		global st_calcs
		counter = 0;
		while 1:
			counter += 1;
			if counter >= 3600:
				counter = 0;
				statswrite()
			status = urllib.urlencode({'status' : str(st_calcs)+" online calculator" + ('s' if st_calcs != 1 else '')});
			theurl = "http://www.cemetech.net/scripts/netverify.php?"+status+"&name=gCn_Metahub&md5=968a0fd2fae9f02811c49e3bc707e960"
			txdata = None
			txheaders =  {'User-agent' : 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
			try:
				req = Request(theurl, txdata, txheaders)
				handle = urlopen(req)
			except IOError, e:
				 pass;
			time.sleep(60)

class client_thread(threading.Thread):
	def __init__(self,client,address):
		threading.Thread.__init__(self)
		self.client = client
		self.client.setblocking(0)		#set non-blocking
		self.address = address
		self.size = 1024
		self.hubname = ""
		self.localname = ""
		self.addrport = self.address[0]+":"+str(self.address[1])
		self.joined = 0
		self.calclist = list()
		log_info("gcnhub: [THREAD] Init from "+self.address[0]+":"+str(self.address[1])+"")
	def run(self):
		global st_calcs
		running = 1

		recbuf = ""
		recbufqueue = 0
		while running:
			time.sleep(0.02);
			try:
				data = self.client.recv(self.size)
				recbuf = recbuf + data
				recbufqueue += len(data)
			except socket.error as (errnum,errstr):
				if errnum == errno.EWOULDBLOCK:
					continue;
				data = 0
			except ssl.SSLError as e :
				if e.errno == ssl.SSL_ERROR_WANT_READ:
					continue
				data = 0
			if data:
				#self.client.send(data)
				#print "Received data of length "+str(len(data))+" from "+self.hubname+"."+self.localname
				while recbufqueue > 2 and recbufqueue >= 3+ord(recbuf[0])+256*ord(recbuf[1]):
					thismsglen = ord(recbuf[0])+256*ord(recbuf[1])
					thismsg = recbuf[0:3+thismsglen]
					self.handlemsg(thismsg)
					recbuf = recbuf[3+thismsglen:]
					recbufqueue -= 3+thismsglen
					if recbufqueue != len(recbuf):
						log_error("gcnhub: buffer length mismatch, discarding buffer")
						recbuf = ""
						recbufqueue = 0


			else:
				self.client.close()
				log_info("gcnhub: [THREAD] Closing on "+self.address[0]+":"+str(self.address[1])+"")
				if self.joined == 1:
					
					vhublock.acquire()
					try:
						del vhublist[self.hubname][self.addrport]
					except KeyError:
						log_error('gcnhub: Tried to remove non-existent client '+self.addrport+' from hub '+self.hubname);
					st_calcs -= len(self.calclist)
					if (len(vhublist[self.hubname])) == 0:
						del vhublist[self.hubname]
						saxmsg = "lost its final client endpoint '"+self.localname+"' and was destroyed"
					else:
						saxmsg = "lost a client endpoint '"+self.localname+"'"
					vhublock.release()

					#saxpost(0,"gCn virtual hub '"+self.hubname+"'",saxmsg,2);
				running = 0 
	def handlemsg(self,data):
		global st_bytesin
		global st_bytesout
		global st_calcs
		global st_maxcalcs
		st_bytesin += len(data);
		datalen = ord(data[0])+256*ord(data[1])
		msgtype = data[2]
		if datalen > 300:
			log_warn("gcnhub: [MSG] Rejecting message of length "+str(len(data))+", encoded length "+str(datalen)+"")
			return;
		msg = data[3:3+datalen]
		if msgtype == 'j':
			self.hubname = msg[1:1+ord(msg[0])]
			self.localname = msg[2+ord(msg[0]):2+ord(msg[0])+ord(msg[1+ord(msg[0])])]
			if len(self.localname) > 0 and len(self.localname) < 16 and \
			   len(self.hubname) > 0 and len(self.hubname) < 16:
				log_info("gcnhub: [MSG] Join from "+self.addrport+": "+self.localname+"->"+self.hubname)

				vhublock.acquire();
				if (vhublist.has_key(self.hubname)):
					vhublist[self.hubname][self.addrport] = self
					saxmsg = "has a new client endpoint '"+self.localname+"'"
				else:
					thisclientdict = dict()
					thisclientdict[self.addrport] = self
					vhublist[self.hubname] = thisclientdict
					saxmsg = "has been created with a new client endpoint '"+self.localname+"'"
				vhublock.release();
				self.joined = 1
			else:
				log_warn("gcnhub: [MSG] INVALID join from "+self.addrport+": "+self.localname+"->"+self.hubname)

				#saxpost(0,"gCn virtual hub '"+self.hubname+"'",saxmsg,2);
		elif msgtype == 'c':
			#Calculator with SID embedded is present
			if datalen != 10:
				log_warn("gcnhub: [MSG] "+self.addrport+" set a calc add with an invalid SID")
			elif self.joined != 1:
				log_warn("gcnhub: [MSG] "+self.addrport+" tried to add calculator "+msg+" but is not joined to a hub")
			else:
				log_info("gcnhub: [MSG] "+self.addrport+" is adding calculator "+msg+"...")
				sendsax = 0
				vhublock.acquire()
				if not(msg in self.calclist):
					sendsax = 1
					st_calcs+=1
					if st_calcs > st_maxcalcs:
						st_maxcalcs = st_calcs
					self.calclist.append(msg)
				vhublock.release()

				if sendsax == 1:
					saxpost(0,"gCn virtual hub '"+self.hubname+"'","has new calculator "+msg+" from "+self.localname,2)
		elif msgtype == 'b':
			#Broadcast message
			if self.joined != 1:
				log_warn("gcnhub: [MSG] "+self.addrport+" tried to send a broadcast, but is not joined to a hub")
			elif datalen > 256+5+5+2+3:
				log_warn("gcnhub: [MSG] "+self.addrport+" sent an overflow-length broadcast")
			else:
				vhublock.acquire()
				for key in vhublist[self.hubname].keys():
					if vhublist[self.hubname][key] != self:
						#SEND BROADCAST
						#print "{fwding to "+key+"}"
						st_bytesout += len(data);
						try:
							vhublist[self.hubname][key].client.sendall(data)
						except:
							del vhublist[self.hubname][key]
							st_calcs -= len(self.calclist)
							saxmsg = "lost a client endpoint '"+self.localname+"'"
							#saxpost(0,"gCn virtual hub '"+self.hubname+"'",saxmsg,2);
							
						
				vhublock.release()
				#print "[BROADCAST] ("+self.addrport+") "+self.hubname+"."+self.localname+"->"+self.hubname+", "+str(datalen)+" bytes"
		elif msgtype == 'f':
			#Normal directed frame
			if self.joined != 1:
				log_warn("gcnhub: [MSG] "+self.addrport+" tried to send a frame, but is not joined to a hub")
			elif datalen > 256+5+5+2+3:
				log_warn("gcnhub: [MSG] "+self.addrport+" sent an overflow-length frame")
			else:
				desthex = "%02X%02X%02X%02X%02X" % (ord(msg[2]),ord(msg[3]),ord(msg[4]),ord(msg[5]),ord(msg[6]))
				srchex = "%02X%02X%02X%02X%02X" % (ord(msg[7]),ord(msg[8]),ord(msg[9]),ord(msg[10]),ord(msg[11]))
				vhublock.acquire()
				for key in vhublist[self.hubname]:
					if vhublist[self.hubname][key] != self and desthex in vhublist[self.hubname][key].calclist:
						#SEND BROADCAST
						#print "{fwding to "+key+"."+desthex+"}"
						st_bytesout += len(data);
						try:
							vhublist[self.hubname][key].client.sendall(data)
							#print "[FRAME] ("+self.addrport+") "+self.hubname+"."+self.localname+"."+srchex+"->"+self.hubname+"."+vhublist[self.hubname][key].localname+"."+desthex+", "+str(datalen)+" bytes"
						except:
							del vhublist[self.hubname][key]
							st_calcs -= len(self.calclist)
							saxmsg = "lost a client endpoint '"+self.localname+"'"
							#saxpost(0,"gCn virtual hub '"+self.hubname+"'",saxmsg,2);

						break
						
				vhublock.release()
		else:
			log_warn("gcnhub: [MSG] Unknown message of length "+str(len(data))+"")
		return;
		
def signal_handler(signal, frame):
	log_error('gcnhub: You pressed Ctrl+C!')
	sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
start()
