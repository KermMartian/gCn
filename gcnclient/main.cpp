//-----------------------------------------//
// gCn Client v1.0                         //
// by Christopher "Kerm Martian" Mitchell  //
// http://www.cemetech.net                 //
// globalCALCnet and CALCnet (c) 2002-2013 //
//-----------------------------------------//
// Version history:                        //
//   v2.0: June 2013                       //
//     - Significant dUSB stability fixes  //
//   v1.8: April 2012                      //
//     - -r now disables persistence       //
//   v0.9: January 2011                    //
//     - Fixes spurious RESET id reports   //
//   v0.8: January 2011                    //
//     - Linux and Mac OS support added    //
//     - More debugging, verbosity added   //
//   v0.5: December 2010                   // 
//     - Original version for Windows      //
//-----------------------------------------//

#if defined(WIN32)
#define WINDOWS
#else
#define UNIX
#define MACOSX
#endif

//Maximum serial chunk size in bytes, allow for 128-byte Arduino serial buffer
#define MAXSERIALCHUNKSIZE 50
//USB contact timeout in seconds
#define USBHID_TIMEOUT 60
#define ARDUACK_TIMEOUT 2

#include <cstdlib>
#include <iostream>
#include <unistd.h>
#include <stdio.h>
#include <getopt.h>
#include <queue>

#include "hiddata.h"

#ifdef WINDOWS
#define _WIN32_WINNT 0x0707
#include "usbconfig_gcnbridge.h"  
	// for device VID, PID, vendor name and product name
#include <windows.h>		// Header File For Windows
#include <winsock2.h>
#include <ws2tcpip.h>
extern "C" {
#include "lusb0_usb.h"
}

#else				// UNIX extra includes
#include "usbconfig_gcnbridge.h"
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <termios.h>
#include <string.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/time.h>			//for gettimeofday
#include <usb.h>
#endif

#ifdef WINDOWS
	#define mymillisleep(X) Sleep(X)
#else
	#define mymillisleep(X) usleep(X)
#endif

//extern "C" {
#include "directusb.c"
//}

int open_ti_usb(usb_dev_handle* &device);
void close_ti_device(usb_dev_handle *device);
int send_ti_buffer(usb_dev_handle *device, char *buffer, int len);
int recv_ti_buffer(usb_dev_handle *device, char *buffer, int len);

#define VENDOR_RQ_WRITE_BUFFER 0x00
#define VENDOR_RQ_READ_BUFFER 0x01

using namespace std;
int main(int argc, char *argv[]);
void print_usage(void);
void checkcalc(unsigned char* sender);
void sendbroadcasttoserver(unsigned char* sender, unsigned char* datalen, short unsigned int datalenval, unsigned char* data);
void sendframetoserver(unsigned char* recipient, unsigned char* sender, unsigned char* datalen, short unsigned int datalenval, unsigned char* data);
static usbDevice_t  *openDevice(char *&vendorname_, char *&productname_);
static char *usbErrorMessage(int errCode);


void cleanupall(void);

//calc tracking
int local_knowncalccount = 0;
int remote_knowncalccount = 0;
struct calcknown {
	unsigned char SID[5];
	struct calcknown* nextcalc;
};
struct calcknown* local_calcs = NULL;
struct calcknown* remote_calcs = NULL;
int verbose = 0;	
#ifdef WINDOWS
SOCKET sd;
#else
int sd;
#endif
enum DeviceTypes { Arduino, USBHID, DirectUSB };
DeviceTypes devicetype = Arduino;
usbDevice_t *devhid;

// Direct USB data structures
static struct usb_dev_handle *devh = NULL;
bool dusb_active;                  //don't activate until data from device received
                                   //to avoid freezing the homescreen

int main(int argc, char *argv[])
{
	//Argument-based semiconstants
	char* comport = NULL;
	char* server_hostname = NULL;
	char* server_port = NULL;
	char* hubname = NULL;
	char* localname = NULL;
	int   persist = 1;
	
	//Socket internal vars
#ifdef WINDOWS
	WSADATA w;								/* Used to open Windows connection */
#endif
	sockaddr_in ServAddr;
	struct hostent *hp;						/* Information about the server */
	char host_name[256];					/* Host name of this computer */
	char msgbuf[300];
	
	//USBHID-related stuff
	char *usb_vendorname, *usb_productname;
#ifdef WINDOWS
	DWORD hidtime, hidtime2;
#else
	struct timeval hidtime, hidtime2;
#endif

	//Serial-related stuff
#ifdef WINDOWS
	HANDLE hSerial;
    DWORD dwCommEvent;
    DWORD dwRead,dwBytesRead;
#else
	int hSerial;
	int dwRead,dwBytesRead;
	struct termios oldtio, newtio;
#endif
    char chRead = 0, last = 0;
    char fakestring[2] = {0,0};
    
	//Assorted, including opt parsing
	int index;
	int c,i;     
	int opterr = 0;
	
	while ((c = getopt (argc, argv, "n:l:s:p:c:d:vhr")) != -1)
	{
		switch (c)
		{
			case 'd':
				if (optarg[0] == 'a' || !strcmp(optarg,"arduino") || !strcmp(optarg,"Arduino"))
					devicetype = Arduino;
				else if (optarg[0] == 'u' || !strcmp(optarg,"usb") || !strcmp(optarg,"usbhid") || !strcmp(optarg,"USB"))
					devicetype = USBHID;
				else if (optarg[0] == 'd' || !strcmp(optarg,"direct") || !strcmp(optarg,"directUSB"))
					devicetype = DirectUSB;
				else
					fprintf(stderr,"Option -%c requires a, u, d, arduino, usb, or direct\n",c);
				break;
			case 's':
				server_hostname = optarg;
				break;
			case 'p':
				server_port = optarg;
				break;
			case 'c':
				comport = optarg;
				break;
			case 'v':
				verbose = 1;
				break;
			case 'n':
				hubname = optarg;
				break;
			case 'l':
				localname = optarg;
				break;
			case 'h':
				print_usage();
				return 0;
			case 'r':
				persist = 0;
				break;
			case '?':
				if (optopt == 'c')
#ifdef WINDOWS
					fprintf(stderr,"Option -%c requires a COM port argument (eg, COM6)\n", optopt);
#else
				fprintf(stderr,"Option -%c requires a /dev/tty... serial port argument\n",optopt);
#endif
				else if (optopt == 'p')
					fprintf(stderr,"Option -%c requires a server port number (eg, 1337)\n", optopt);
				else if (optopt == 's')
					fprintf(stderr,"Option -%c requires a server hostname or IP (eg, 164.9.42.237 or gcn.myhost.com)\n", optopt);
				else if (isprint (optopt))
					fprintf(stderr,"Unknown option `-%c'.\n", optopt);
				else
					fprintf(stderr,"Unknown character `\\x%x'.\n", optopt);
				return 1;
				break;
		}
	}
	
	//Make sure all required arguments have been added
	if (server_hostname == NULL) {
		server_hostname = (char*)"gcnhub.cemetech.net";
		fprintf(stdout,"Info: Using default server host %s\n",server_hostname);
	}
	if (server_port == NULL) {
		server_port = (char*)"4295";
		fprintf(stdout,"Info: Using default port %s\n",server_port);
	}
	if (hubname == NULL || localname == NULL) {
		if (hubname == NULL) fprintf(stderr,"Error: Must specify the name of the virtual hub (-n)\n");
		if (localname == NULL) fprintf(stderr,"Error: Must specify the name of the local client (-l)\n");
		print_usage();
		return -1;
	}
	if (comport == NULL && devicetype == Arduino) {
		fprintf(stderr,"Error: Must specify COM/serial port (-c)\n");
		print_usage();
		return -1;
	}	
	
	//Try to open USB HID device
	if (devicetype == USBHID) {
		if (comport != NULL)
            fprintf(stderr,"Warning: -c command-line option ignored for USBHID Bridge\n");
	    if((devhid = openDevice(usb_vendorname, usb_productname)) == NULL) {
			fprintf(stderr,"USB HID device not plugged in or not detected.\n");
    		exit(0);
        } else {
			fprintf(stdout,"USB HID device '%s' by '%s' found and connected!\n",usb_productname,usb_vendorname);
		}
#ifdef WINDOWS
		hidtime = GetTickCount();
#else
		gettimeofday(&hidtime, NULL);
#endif
	} else if (devicetype == Arduino) {
	//Try to open serial port
#ifdef WINDOWS
		char comport2[256] = "\\\\.\\";
		strcat(comport2,comport);
		hSerial = CreateFile(comport2,
							 GENERIC_READ | GENERIC_WRITE,
							 0,
							 0, 
							 OPEN_EXISTING,
							 FILE_ATTRIBUTE_NORMAL,
							 0);
		if(hSerial==INVALID_HANDLE_VALUE){
	    	if(GetLastError()==ERROR_FILE_NOT_FOUND){
	        	//serial port does not exist. Inform user.
	    		fprintf(stderr, "Serial port '%s' does not exist.\n",comport);
	    		exit(0);
	        }
	        //some other error occurred. Inform user.
	    	fprintf(stderr, "Some serial port problem occurred.\n");
	    	exit(0);
		}
#else
		if (0 > (hSerial = open(comport, O_RDWR | O_NOCTTY | O_NONBLOCK ))) {		//
			fprintf(stderr, "Could not open serial port; %s does not exist?\n",comport);
			exit(0);
		}
#endif
	
		//Set serial parameters
#ifdef WINDOWS
		DCB dcbSerialParams = {0};
		if (!GetCommState(hSerial, &dcbSerialParams)) {
		    //error getting serial port state
		    fprintf(stderr, "Unable to get serial port state to set serial parameters.\n");
		    exit(0);
		}
		dcbSerialParams.BaudRate=CBR_115200;
		dcbSerialParams.ByteSize=8;
		dcbSerialParams.StopBits=ONESTOPBIT;
		dcbSerialParams.Parity=NOPARITY;
		dcbSerialParams.fDtrControl = DTR_CONTROL_DISABLE; // disable DTR to avoid reset
		if(!SetCommState(hSerial, &dcbSerialParams)){
		    //error setting serial port state
		    fprintf(stderr, "Unable to set serial parameters.\n");
		    exit(0);
		}
#else
		tcgetattr(hSerial,&oldtio); /* save current serial port settings */
		bzero(&newtio, sizeof(newtio)); /* clear struct for new port settings */
		newtio.c_cflag = B115200 | CS8 | CLOCAL | CREAD ;//|CRTSCTS;// | 
		newtio.c_iflag = ~(IGNBRK | BRKINT | ICRNL | INLCR | ISTRIP | IXON);
		newtio.c_oflag = ~(OCRNL | ONLCR | ONLRET | ONOCR | OFILL | 
						   OPOST);
		newtio.c_lflag = ~(ECHO | ECHONL | ICANON | IEXTEN | ISIG);
		newtio.c_cc[VMIN] = 0;
		newtio.c_cc[VTIME] = 0;
		cfsetispeed(&newtio,B115200);
		cfsetospeed(&newtio, B115200);
		tcflush(hSerial, TCIFLUSH);
		tcsetattr(hSerial,TCSANOW,&newtio);
#endif
	
		//Set serial port timeout limits
#ifdef WINDOWS
		COMMTIMEOUTS timeouts={0};
		timeouts.ReadIntervalTimeout=50;
		timeouts.ReadTotalTimeoutConstant=50;
		timeouts.ReadTotalTimeoutMultiplier=10;
		timeouts.WriteTotalTimeoutConstant=50;
		timeouts.WriteTotalTimeoutMultiplier=10;
		if(!SetCommTimeouts(hSerial, &timeouts)) {
		    //error occureed. Inform user
		    fprintf(stderr, "Unable to set serial timeouts.\n");
		    exit(0);
		}
#endif
	} else if (devicetype == DirectUSB) {
		if (comport != NULL)
            fprintf(stderr,"Warning: -c command-line option ignored for Direct USB\n");
        int r;
		//Try to open direct USB device
		if (persist && verbose)
		    fprintf(stdout,"Info: Attempting to find calculator.  Press CTRL-C to abort.\n");
		do {
            devh = NULL;
			r = open_ti_usb(devh);
         	mymillisleep(20);
		}while (persist && r==-1);
		if (0 > r) {
			if (r==-2) {
				fprintf(stderr,"Calculator found but could not be opened, check permissions.\n");
			}
			fprintf(stderr,"Failed to open Direct USB connection to calculator.\n");
			cleanupall();	//and exits...
		} else {
			fprintf(stderr,"Direct USB connection created successfully.\n");
			dusb_active = true ; //false;
		}
#ifdef WINDOWS
		hidtime = GetTickCount();
#else
		gettimeofday(&hidtime, NULL);
#endif
	}
	
	//Set up socket to server
#ifdef WINDOWS
	// Open windows connection
	if (WSAStartup(0x0101, &w) != 0) {
		fprintf(stderr, "Could not open Windows connection for socket.\n");
		exit(0);
	}
#endif
	// Open a datagram socket
	sd = socket(AF_INET, SOCK_STREAM, 0);
#ifdef WINDOWS
	if (sd == INVALID_SOCKET)
#else
	if (sd < 0)
#endif
	{
		fprintf(stderr,"Unable to create TCP socket [Socket Creation Error]\n");
		cleanupall();
	}
	// Get host name of this computer
	gethostname(host_name, sizeof(host_name));
	if (NULL == (hp = gethostbyname(host_name))) {
		fprintf(stderr,"Unable to get local hostname [DNS Error]\n");
		cleanupall();
	}
	
	// Get IP of remote computer
	struct addrinfo *result = NULL;
	struct addrinfo hints;
	memset(&hints, 0, sizeof(hints));
	hints.ai_family = AF_INET;
	hints.ai_socktype = SOCK_STREAM;
	hints.ai_protocol = IPPROTO_TCP;
	
	if ((i = getaddrinfo(
						 server_hostname,
						 server_port,
						 &hints,
						 &result)) !=0 )
	{
		freeaddrinfo(result);
		cerr << "Server hostname could be be resolved\n" << endl;
		cleanupall();
	}
	switch (i = connect(sd, result->ai_addr, result->ai_addrlen)) {
		case 0:
			cout << "Resolved hostname." << endl;
			if (verbose) fprintf(stderr,"Socket #%d\n",sd);
			break;
#ifdef UNIX
		default:
#else
		case SOCKET_ERROR:
#endif
			fprintf(stderr,"Unable to bind TCP socket to virtual hub [Socket Bind Error]\n");
#ifdef WINDOWS
			i = WSAGetLastError();
			cerr << "Details: " << i << endl;
#endif
			freeaddrinfo(result);
			cleanupall();
			break;
#ifdef WINDOWS
		default:
			cerr << "Fatal connect() error: unexpected "
			"return value." << endl;
			freeaddrinfo(result);
			cleanupall();
			break;
#endif
	}
	mymillisleep(500);

	//Set the socket non-blocking
#ifdef WINDOWS
	ULONG NonBlock = 1;
	if (ioctlsocket(sd, FIONBIO, &NonBlock) == SOCKET_ERROR) {
		fprintf(stderr,"ioctlsocket() failed to set socket as nonblocking\n");
		cleanupall();
	}
#else
	int flags;
	flags = fcntl(sd,F_GETFL,0);
	if (flags < 0) {
		fprintf(stderr,"Could not fcntl() get socket flags\n");
		cleanupall();
	}
	if (0 > fcntl(sd, F_SETFL, flags | O_NONBLOCK)) {
		fprintf(stderr,"Could not fcntl() set socket flags\n");
		cleanupall();
	}
#endif

	//Send join packet
	msgbuf[0] = (char)strlen(hubname)+(char)strlen(localname)+2;
	msgbuf[1] = 0;
	msgbuf[2] = 'j';
	msgbuf[3] = (char)strlen(hubname);
	strcpy(msgbuf+4,hubname);
	msgbuf[4+(int)msgbuf[3]] = (char)strlen(localname);
	strcpy(msgbuf+5+(int)msgbuf[3],localname);
	int totalsent = 0;
	while(totalsent < 3+(int)msgbuf[0]) {
		if ((i = send(sd,msgbuf+totalsent,3+(int)msgbuf[0]-totalsent,0)) < 0) {
			fprintf(stderr,"ERROR writing to socket (%d)\n",errno);
			cleanupall();
		}
		totalsent += i;
	}
	fprintf(stdout,"Wrote %d bytes to socket (join msg)\n",i);
	
	//BEGIN MAIN LOOP
#ifdef WINDOWS
    if (devicetype == Arduino && !SetCommMask(hSerial, EV_RXCHAR)) {
        fprintf(stderr,"Error setting serial mask");
		// Error setting communications event mask
    } else {
#else
	if (1) {
#endif
		int frameindex = 0;
		//FrameIndex:
		//	0 = not in anything
		//	1-5 = sender
		//	6-10 = recipient
		//	11-12 = length
		//	12+ = data or checksum
		unsigned char recipient[5] = {0,0,0,0,0};
		unsigned char sender[5] = {0,0,0,0,0};
		unsigned char datalen[2];
		unsigned char data[256];
		unsigned char checksum[2];
		short unsigned int checksumval;
		short unsigned int datalenval;
		unsigned char tempbyte = 0;
		unsigned short nibble = 1;
		unsigned char broadbyte = 0;
		bool fail = false;
		std::string receivebackbuf;
		
		//USBHID-specific stuff
		unsigned char usbstatusbuf[3];
		unsigned char* usbstatusmask = usbstatusbuf+1;
		unsigned char* usbstatusgetid = usbstatusbuf+2;
		unsigned char usbstatusgetid_local = 0xff;
		
		char recvbuf[1024];
		int pendbufsize = 0;	//used for partial packets, or duped packets
		
		//Clean out the serial buffer
		/*
		 do {
		 if (WaitCommEvent(hSerial, &dwCommEvent, NULL)) {
		 do {
		 ReadFile(hSerial, &chRead, 1, &dwRead, NULL);
		 } while (dwRead);
		 }
		 } while (chRead != '\n');*/
		
		//Begin
		std::queue<char*> sendbuf;
		receivebackbuf.clear();
		for ( ; ; ) {
            
            if (devh == NULL && devicetype == DirectUSB) {
                if (!persist) {
                   fprintf(stderr,"Calculator disconnected or unavailable.\n");
                   cleanupall();
                }
                int r;
                devh = NULL;
    			r = open_ti_usb(devh);
             	mymillisleep(20);
    			if (r != 0)
  			       devh = NULL;
                else
                    fprintf(stderr,"Calculator successfully reconnected.\n");
            }
			if (0 < (i = recv(sd,recvbuf+pendbufsize,1023-pendbufsize,0))) {
				fprintf(stdout,"Received message of length %d from server.\n",i);
				pendbufsize += i;
				while(pendbufsize >= 3+((unsigned char)recvbuf[0]+256*(unsigned char)recvbuf[1])) {
					char* nextmsg = NULL;
					int thisframesize = ((unsigned char)recvbuf[0]+256*(unsigned char)recvbuf[1]);
					switch(recvbuf[2]) {
						case 'b':
						case 'f':
							if (0 >= (nextmsg = (char*)malloc(3+thisframesize))) {
								fprintf(stderr,"Out of memory trying to enqueue a broadcast message\n");
								cleanupall();
							}
							memcpy(nextmsg,recvbuf,3+thisframesize);
							sendbuf.push(nextmsg);
							break;
						default:
							fprintf(stderr,"Unknown frame, type '%c', size '%d', received from server\n",
									recvbuf[2],thisframesize);
							break;
					}
					memcpy(recvbuf,recvbuf+3+thisframesize,1024-(3+thisframesize));
						pendbufsize -= 3+thisframesize;
				}
					
#ifdef WINDOWS
			} else if (i<0 && errno != WSAEWOULDBLOCK && errno != 0) {
#else
			} else if (i<0 && errno != EAGAIN && errno != EWOULDBLOCK) {
#endif
				fprintf(stderr,"Fatal socket error probing for incoming data: %d,%d\n",i,errno);
				cleanupall();
			}
			if (frameindex == 0) {
				while (!sendbuf.empty() && ((devh != NULL && dusb_active == true) || (devicetype != DirectUSB))) {
					
					if (devicetype == USBHID) {
						usbstatusbuf[0] = 1;
				        int err;
				        int len = sizeof(usbstatusbuf);
				        if ((err = usbhidGetReport(devhid, 1, (char*)usbstatusbuf, &len)) != 0)
				            break;		//die if it's busy
#ifdef WINDOWS
						hidtime = GetTickCount();			//update latest USB sighting
#else
						gettimeofday(&hidtime,NULL);
//						usbstatusbuf[0] = usbstatusbuf[1];
//						usbstatusbuf[1] = usbstatusbuf[2];
#endif
				        if (usbstatusbuf[0] != 0)
				        	break;		//die if it has pending data
					}
				
					char* thismsg = sendbuf.front();
					short unsigned int thismsgsize = (unsigned char)thismsg[0]+256*(unsigned char)thismsg[1];
					int oldmsgsize = thismsgsize;
					int totalsent = 0;
					if (devicetype == Arduino) {
						while(totalsent < thismsgsize) {				//bytes
							int thischunksize = thismsgsize-totalsent;	//bytes
							if (thischunksize > MAXSERIALCHUNKSIZE)		//bytes
								thischunksize = MAXSERIALCHUNKSIZE;		//bytes

							char* thisexpandedmsg;
							int thisexpandedchunksize = thischunksize*2 + 1;
							if (0 >= (thisexpandedmsg = (char*)malloc((1+(thischunksize*2)+1)))) {		//nibbles + flow control
								fprintf(stderr,"Failed to reserve memory to unpack message for Arduino\n");
								cleanupall();
							}
							for(i=0; i<thischunksize; i++) {
								sprintf(thisexpandedmsg+2*i,"%02X",(thismsg[3+i+totalsent]&0x000000ff));
							}
							thisexpandedmsg[2*thischunksize] = 's';
							thisexpandedmsg[2*thischunksize+1] = '\0';

#ifdef WINDOWS
							if(!WriteFile(hSerial, thisexpandedmsg, thisexpandedchunksize, &dwBytesRead, NULL) || 
								thisexpandedchunksize != dwBytesRead)
							{
#else
							int thischunksent;
							thischunksent = 0;
							while(thischunksent < thisexpandedchunksize) {
								int temprval;
								if (0 > (temprval = write(hSerial, thisexpandedmsg+thischunksent, thisexpandedchunksize-thischunksent))) {
#endif
									//error occurred. Report to user.
									fprintf(stderr, "Failed to write frame, type '%c', size '%d', to Arduino\n",thismsg[2],thismsgsize);
									cleanupall();
								}
#ifndef WINDOWS
								thischunksent += temprval;
								printf("Wrote %d more (%d total) of %d bytes\n",temprval,thischunksent,thischunksize);
							}
#endif
							if (verbose) {
								fprintf(stdout,">> %s\n",thisexpandedmsg);
								fprintf(stdout,"Sent %d of %d bytes and ack, waiting for ack\n",totalsent+thischunksize,thismsgsize);
							}
							int temprval;
							char ackbytebuf;
							ackbytebuf = '\0';
							bool acked = false;
#ifdef WINDOWS
							hidtime = GetTickCount();			//last sync send
#else
							gettimeofday(&hidtime,NULL);
#endif
							do {
#ifdef WINDOWS
								temprval = ReadFile(hSerial, &ackbytebuf, 1, &dwRead, NULL);
#else
								dwRead = read(hSerial,&ackbytebuf,1);
#endif
								if (dwRead == 1 && 's' == ackbytebuf) acked = true;
								if (dwRead == 1 && 's' != ackbytebuf) {
									receivebackbuf.push_back(ackbytebuf);
									if (verbose)
										fprintf(stdout,"Queued %d bytes of backchannel data (%s)\n",
											receivebackbuf.length(),receivebackbuf.c_str());
								}
								
								// This is a hack to deal with lost ACKs
#ifdef WINDOWS
								hidtime2 = GetTickCount();
								if (hidtime2 - hidtime > ARDUACK_TIMEOUT*1000) {
#else
								gettimeofday(&hidtime2,NULL);
								if (0.5+((hidtime2.tv_sec-hidtime.tv_sec)*1000+
										(hidtime2.tv_usec-hidtime.tv_usec)/1000)
										> ARDUACK_TIMEOUT*1000) {
#endif
										acked = true;
								}
							} while(!acked);
							printf("Received ack (backbuf contains %d characters)\n",receivebackbuf.length());
							free(thisexpandedmsg);
							totalsent += thischunksize;
						}
					} else if (devicetype == USBHID) {
				        int err;
				        unsigned char buffer[300];
				        //int len = 1+2+268;
				        buffer[0] = (unsigned char)(thismsgsize-1 > 32)?3:2;
				        buffer[1] = (unsigned char)((thismsgsize-3+2+1)&0x000000ff);
				        buffer[2] = (unsigned char)(((thismsgsize-3+2+1)&0x0000ff00)>>8);
				        buffer[3] = ++usbstatusgetid_local;
				        memcpy(buffer+4,thismsg+2+3,thismsgsize-3);
				        if (thismsgsize > 3) {
							for(int i=0; i<5;i++) {			//swap sender and recipient
								buffer[4+i]   = buffer[4+i]^buffer[5+4+i];	//USB buffer-copy expects
								buffer[5+4+i] = buffer[4+i]^buffer[5+4+i];	//sender first, but serial
								buffer[4+i]   = buffer[4+i]^buffer[5+4+i];	//does recipient first
							}
							do {
						        err = usbhidSetReport(devhid, (char*)buffer, 300);
								do {
                                	mymillisleep(50);
#ifdef WINDOWS
									hidtime2 = GetTickCount();
									if (hidtime2 - hidtime > USBHID_TIMEOUT*1000) {
#else
									gettimeofday(&hidtime2,NULL);
									if (0.5+((hidtime2.tv_sec-hidtime.tv_sec)*1000+
											(hidtime2.tv_usec-hidtime.tv_usec)/1000)
											> USBHID_TIMEOUT*1000) {
#endif
										fprintf(stderr,"USB HID bridge stopped responding!\n");
										cleanupall();
									}
									usbstatusbuf[0] = 1;
									int len = sizeof(usbstatusbuf);
									err = usbhidGetReport(devhid, 1, (char*)usbstatusbuf, &len);
								} while (err != 0);
							} while (usbstatusgetid_local != usbstatusbuf[1]);
#ifdef WINDOWS
							hidtime = GetTickCount();			//update latest USB sighting
#else
							gettimeofday(&hidtime,NULL);
#endif
						} else {
							fprintf(stderr,"Malformed frame?\n");
						}
					} else {
						//device type is Direct USB
						//need to send thismsgsize bytes starting at thismsg+3+2
						//+3 trims off SBL, SBH, type
						//+2 trims 255, 127
						//length: -2 trims 255, 127; -1 trims 42
						thismsgsize -= 2+1;
						if (0 != send_ti_buffer(devh,thismsg+3+2,thismsgsize)) {
							fprintf(stderr,"Error: Failed to send Direct USB frame\n");
							close_ti_device(devh);
                    		if (verbose)
                               fprintf(stderr, "Nulling device.\n");
							devh = NULL;
							if (!persist)
				               cleanupall();
						} else {
#ifdef WINDOWS
							hidtime = GetTickCount();			//update latest USB sighting
#else
							gettimeofday(&hidtime,NULL);
#endif
						}
					}
					if (verbose) {
						for(i=0;i<oldmsgsize;i++) {
							fprintf(stdout,"%02X",((unsigned char)thismsg[3+i])&0x000000ff);
							if (i==1 || i==6 || i==11 || i==13 || i==oldmsgsize-2) fprintf(stdout," ");
						}
						fprintf(stdout,"\n");
						for(i=0;i<oldmsgsize;i++) {
							if ((unsigned char)thismsg[3+i] > 31 && (unsigned char)thismsg[3+i]<127)
								fprintf(stdout,"%c ",(unsigned char)thismsg[3+i]);
							else
								fprintf(stdout,"? ");
							if (i==1 || i==6 || i==11 || i==13 || i==oldmsgsize-2) fprintf(stdout," ");
						}
						fprintf(stdout,"\nWrote frame, type '%c', size '%d', to bridge\n",thismsg[2],oldmsgsize);
					}
					if ((devh != NULL) || (devicetype != DirectUSB)) {   //don't remove if DUSB is active and disconnected
     					free(thismsg);
     					sendbuf.pop();
                   }
				}
			}

			// Check for incoming USBHID data
			if (devicetype == USBHID) {
              	mymillisleep(30);
				usbstatusbuf[0] = 1;
		        int err;
		        int len = sizeof(usbstatusbuf);
		        err = usbhidGetReport(devhid, 1, (char*)usbstatusbuf, &len);
#ifndef WINDOWS
//				usbstatusbuf[0] = usbstatusbuf[1];
//				usbstatusbuf[1] = usbstatusbuf[2];
#endif
//		        if (!err) printf("%x %x %x\n",usbstatusbuf[0],usbstatusbuf[1],usbstatusbuf[2]);
		        if (err == 0 && usbstatusbuf[0]) {

					unsigned char buffer[300];
					int fulllen;
			        int len = fulllen = sizeof(buffer)-1;
			        int err;
			        memset(buffer,0x00,len);
			        buffer[0] = 3;
			        if((err = usbhidGetReport(devhid, buffer[0], (char*)buffer, &len)) == 0){
//#ifdef WINDOWS
						if ((len < fulllen && len > 1) || buffer[0] == 0x42) {	//data received!
							int buflen = (len < fulllen)?(len):12+(buffer[11])+256*(buffer[12]);
//#else
//						if ((len < fulllen && len > 1) || buffer[1] == 0x42) {
//							int buflen = (len < fulllen)?(len):12+(buffer[12])+256*(buffer[13]);
//#endif
							char tbuf[3];
							for(i=0;i<buflen;i++) {
								if (i==0)
									receivebackbuf.append(1,'|');
								if (i==5)
									receivebackbuf.append(1,'.');
								if (i==10)
									receivebackbuf.append(1,',');
								if (i==12)
									receivebackbuf.append(1,':');
//#ifdef WINDOWS
								sprintf(tbuf,"%02X",((unsigned char)buffer[1+i])&0x000000ff);
//#else
//								sprintf(tbuf,"%02X",buffer[2+i]);
//#endif
								receivebackbuf.append(tbuf,2);
							}
							receivebackbuf.append(">\n");
							//printf("%s",receivebackbuf.c_str());	//no \n plz
#ifdef WINDOWS
							hidtime = GetTickCount();			//update latest USB sighting
#else
							gettimeofday(&hidtime,NULL);
#endif
						}
                       	mymillisleep(20);
			        }
				}
			//Check for incoming Direct USB data
			} else if (devicetype == DirectUSB && devh != NULL) {
              	mymillisleep(30);
				unsigned char buffer[300];
				int fulllen;
		        int len = fulllen = sizeof(buffer)-1;
		        int err;
		        memset(buffer,0x00,len);
		        if ((err = recv_ti_buffer(devh, (char*)buffer, len)) > 0){
					if (err < fulllen && err > 11) {	//data received!
						buffer[11] &= 0x7f;
						int buflen = (err < fulllen)?(err):12+(buffer[10])+256*(buffer[11]);
						char tbuf[3];
						for(i=0;i<5;i++) {
							buffer[i]  = buffer[5+i]^buffer[i];
							buffer[5+i]= buffer[5+i]^buffer[i];
							buffer[i]  = buffer[5+i]^buffer[i];
						}
						for(i=0;i<buflen;i++) {
							if (i==0)
								receivebackbuf.append(1,'|');
							if (i==5)
								receivebackbuf.append(1,'.');
							if (i==10)
								receivebackbuf.append(1,',');
							if (i==12)
								receivebackbuf.append(1,':');;
							sprintf(tbuf,"%02X",((unsigned char)buffer[i])&0x000000ff);
							receivebackbuf.append(tbuf,2);
						}
						receivebackbuf.append(">\n");
						dusb_active = true;                //if previously false, NOW we can send data
						//printf("%s",receivebackbuf.c_str());	//no \n plz
#ifdef WINDOWS
						hidtime = GetTickCount();			//update latest USB sighting
#else
						gettimeofday(&hidtime,NULL);
#endif
					}
                 	mymillisleep(20);
				} else if (err < 0) { //err == -ENODEV || err == -ERANGE) {
					fprintf(stderr,"Direct USB device disconnected!\n");
					close_ti_device(devh);
					devh = NULL;
            		if (verbose)
                       fprintf(stderr, "Nulling device.\n");
                    if (!persist)
                       cleanupall();
				}
			}
			
			//Check for any kind of USB timeout
			if (devicetype == USBHID || devicetype == DirectUSB) {
#ifdef WINDOWS
				hidtime2 = GetTickCount();
				if (hidtime2 - hidtime > USBHID_TIMEOUT*1000) {
#else
				gettimeofday(&hidtime2,NULL);
				if (0.5+((hidtime2.tv_sec-hidtime.tv_sec)*1000+
						(hidtime2.tv_usec-hidtime.tv_usec)/1000)
						> USBHID_TIMEOUT*1000) {
#endif
					if (devicetype == USBHID) {
						fprintf(stderr,"USB HID bridge stopped responding!\n");
      					cleanupall();
                    } else if (devicetype == DirectUSB) {
						fprintf(stderr,"Direct USB device may have stopped responding...\n");		
                        //[15:35:26] <BrandonW> Anyway, send zero for wValue, wIndex, and 2 for wLength, and you'll get back two bytes of status for the device.
                        //[15:35:28] <BrandonW> Ignore them.
                        //[15:35:42] <BrandonW> And send 0x80 for bmRequestType.
                        char controlbuffer[2];
                        if (NULL == devh) {
                                 fprintf(stderr,"Direct USB device disconnected unexpectedly. Check cable and calculator.\n");
                                 if (!persist)
                                      cleanupall();
                        } else {
                            int ctrlstatus = usb_control_msg(devh,0x80,0,0,0,controlbuffer,2,5000);
                            if (0 > ctrlstatus) {
        						fprintf(stderr,"Direct USB device stopped responding: status code %d!\n",ctrlstatus);
                                if (!persist)
                                      cleanupall();
                            } else {
                                fprintf(stderr,"Direct USB device still connected.\n");		
                            }
                        }
#ifdef WINDOWS
    			    hidtime = GetTickCount();
#else
    			    gettimeofday(&hidtime,NULL);
#endif
                    }
				}
			}
			do {
				last = chRead;
				dwRead = 0;
				bool processchar;
				processchar = false;
				if (devicetype == Arduino) {
#ifdef WINDOWS
					if (receivebackbuf.length() == 0 && ReadFile(hSerial, &chRead, 1, &dwRead, NULL) && dwRead)
						processchar = true;
#else
					if (receivebackbuf.length() == 0 && 0 < (dwRead = read(hSerial,&chRead,1)))
						processchar = true;
#endif
				}
				if (receivebackbuf.length() > 0) {
					chRead = receivebackbuf[0];
					processchar = true;
					receivebackbuf.erase(0, 1);
					dwRead = 1;
				}
				if (processchar) {
					if (verbose) {
						fakestring[0] = chRead;
						if (chRead != '\n') fprintf(stdout,"%s",fakestring);
					}
					if (chRead == '|') {
						frameindex = 0;
						nibble = 1;
						fail = false;
						broadbyte = 0;
					} else if (chRead == '.') {
						frameindex = 5;
						nibble = 1;
					} else if (chRead == ',') {
						frameindex = 10;
						nibble = 1;
					} else if (chRead == ':') {
						frameindex = 12;
						nibble = 1;
					} else if (chRead == '>') {
						if (frameindex >= 12) {
							if ( fail == false) checkcalc(sender);
							if (broadbyte == 0 && fail == false) {
								if (!verbose) fprintf(stdout,"Sent broadcast of length %d to server\n",datalenval);
								sendbroadcasttoserver(sender,datalen,datalenval,data);
							} else if (fail == false) {
								if (!verbose) fprintf(stdout,"Sent frame of length %d to server\n",datalenval);
								sendframetoserver(recipient,sender,datalen,datalenval,data);
							}
						}
						frameindex = 0;
						nibble = 1;
					} else if (chRead == '\n') {
						if (frameindex >= 12 && fail == false) checkcalc(sender);
						frameindex = 0;
						nibble = 1;
						for (i=0;i<5;i++)
							sender[i] = recipient[i] = 0;
						if (verbose && last != '\n') fprintf(stdout,"\n");
					} else if (chRead == 'f') {
						frameindex = 0;
						nibble = 1;
						fail = true;
						if (verbose) fprintf(stdout," [FAIL]");
					} else {
						if (nibble == 1) {
							tempbyte = 16*(chRead-'0'*(chRead<='9')-('A'-10)*(chRead>='A'));
							nibble = 0;
						} else {
							tempbyte += (chRead-'0'*(chRead<='9')-('A'-10)*(chRead>='A'));
							nibble = 1;
							if (frameindex < 5) {
								sender[frameindex] = tempbyte;
							} else if (frameindex < 10) {
								broadbyte |= tempbyte;
								recipient[frameindex-5] = tempbyte;
							} else if (frameindex < 12)
								datalen[frameindex-10] = tempbyte;
							else if (frameindex < 12+datalenval)
								data[frameindex-12] = tempbyte;
							else if (frameindex < 12+datalenval+2)
								checksum[frameindex-12-datalenval] = tempbyte;
							else {
								//do nothing
							}
							frameindex++;
							if (frameindex == 12) {
								datalenval = 256*datalen[1]+datalen[0];
								if (datalenval > sizeof(data)) {
									//invalid!
									datalenval = 1;
								}
							}
						}
					}
				}
			} while (dwRead > 0);
			//			}
			
		}
	}
	cleanupall();
}

void print_usage(void)
{
	fprintf(stdout,"gCn Client v2.0\n(c) 2002-2013 Christopher \"Kerm Martian\" and Cemetech\n");
    fprintf(stdout,"With Jon \"Jonimus\" Sturm and Shaun \"Merthsoft\" Mcfall\nhttp://www.cemetech.net\n\n");
	fprintf(stdout,"Syntax: %s -n <hub_name> -l <local_name> -c <COMport> -s <server_hostname> -p <server_port> [-v] [-h]\n","gcnclient");
	fprintf(stdout,"-h                   Print this help message\n");
	fprintf(stdout,"-n <hub_name>        Name of virtual hub to connect to on server\n");
	fprintf(stdout,"-l <local_name>      Name for local endpoint connected to virtual hub\n");
	fprintf(stdout,"-d <device_type>     Must be 'a'/'arduino', 'u'/'usb'/usbhid', or 'd'/'direct'. Default is 'arduino'\n");
	fprintf(stdout,"-c <COMport>         Serial port for CALCnet2.2 connection, eg COM3\n");
	fprintf(stdout,"-s <server_hostname> eg. gcnhub.cemetech.net or 194.24.54.139\n");
	fprintf(stdout,"-p <server_port>     eg. 4295\n");
	fprintf(stdout,"-r                   DO NOT retry USB connection on startup or disconnect\n");
	fprintf(stdout,"\n");
	return;
}

void sendbroadcasttoserver(unsigned char* sender, unsigned char* datalen, short unsigned int datalenval, unsigned char* data) {
	unsigned char msgbuf[300];
	int i;
	
	unsigned short int packetsize = 2+5+5+2+datalenval+1;
	msgbuf[0] = (unsigned char)(packetsize&0x00ff);
	msgbuf[1] = (unsigned char)((packetsize&0xff00)>>8);
	msgbuf[2] = 'b';
	msgbuf[3] = 255;
	msgbuf[4] = 137;
	memset(msgbuf+5,0,5);
	memcpy(msgbuf+5+5,sender,5);
	memcpy(msgbuf+5+5+5,datalen,2);
	//fprintf(stdout,"Outgoing datalen is %d,%d\n",datalen[0],datalen[1]);
	memcpy(msgbuf+5+5+5+2,data,datalenval);
	msgbuf[5+5+5+2+datalenval] = 42;
	if (verbose) {
		fprintf(stdout,"\n ");
		for(i=0;i<5+5+2+datalenval;i++) {
			if (msgbuf[5+i] > 31 && msgbuf[5+i] < 127)
				fprintf(stdout,"%c ",msgbuf[5+i]);
			else
				fprintf(stdout,"? ");
			if (i==4 || i==9 || i==11 || i==5+5+2+datalenval-1) fprintf(stdout," ");
		}
		fprintf(stdout,"\nBroadcasting data of length %d to server\n",datalenval);
	}
	int totalsent = 0;
	int framesize = 3+(int)msgbuf[0]+256*(int)msgbuf[1];
	while(totalsent < framesize) {
		if ((i = send(sd,(char *)(msgbuf+totalsent),framesize-totalsent,0)) < 0) {
			fprintf(stderr,"ERROR writing to socket (%d)\n",errno);
			cleanupall();
		}
		totalsent += i;
	}
	fprintf(stdout,"Wrote %d bytes to socket (broadcast msg)\n",totalsent);
}

void sendframetoserver(unsigned char* recipient, unsigned char* sender, unsigned char* datalen, short unsigned int datalenval, unsigned char* data) {
	unsigned char msgbuf[300];
	int i;
	
	unsigned short int packetsize = 2+5+5+2+datalenval+1;
	msgbuf[0] = (unsigned char)(packetsize&0x00ff);
	msgbuf[1] = (unsigned char)((packetsize&0xff00)>>8);
	msgbuf[2] = 'f';
	msgbuf[3] = 255;
	msgbuf[4] = 137;
	memcpy(msgbuf+5,recipient,5);
	memcpy(msgbuf+5+5,sender,5);
	memcpy(msgbuf+5+5+5,datalen,2);
	//fprintf(stdout,"Outgoing datalen is %d,%d\n",datalen[0],datalen[1]);
	memcpy(msgbuf+5+5+5+2,data,datalenval);
	msgbuf[5+5+5+2+datalenval] = 42;
	if (verbose) {
		fprintf(stdout,"\n ");
		for(i=0;i<5+5+2+datalenval;i++) {
			if (msgbuf[5+i] > 31 && msgbuf[5+i] < 127)
				fprintf(stdout,"%c ",msgbuf[5+i]);
			else
				fprintf(stdout,"  ");
			if (i==4 || i==9 || i==11 || i==5+5+2+datalenval-1) fprintf(stdout," ");
		}
		fprintf(stdout,"Sending frame data of length %d to server\n",datalenval);
	}
	int totalsent = 0;
	int framesize = 3+(int)msgbuf[0]+256*(int)msgbuf[1];
	while(totalsent < framesize) {
		if ((i = send(sd,(char *)(msgbuf+totalsent),framesize-totalsent,0)) < 0) {
			fprintf(stderr,"ERROR writing to socket (%d)\n",errno);
			cleanupall();
		}
		totalsent += i;
	}
	fprintf(stdout,"Wrote %d bytes to socket (frame msg)\n",totalsent);
}

void checkcalc(unsigned char* sender)
{
	int i,j=0;
	struct calcknown* tempptr = local_calcs;
	struct calcknown* prevptr = NULL;
	
	//Check that it's not 0000000000
	for (i=0;i<6;i++) {
		if (i==5) return;	//all zeros!
		if (sender[i] != 0) break;
	}

	//Try to find it
	while (tempptr != NULL) {
		for(i=0;i<6;i++) {
			if (i == 5) return;	//match!
			if (tempptr->SID[i] != sender[i]) break;
		}
		prevptr = tempptr;
		tempptr = tempptr->nextcalc;
		j++;
	}
	if (j == 0) {
		if (0 >= (local_calcs = (struct calcknown*)malloc(sizeof(struct calcknown)))) {
			fprintf(stderr,"Out of memory in checkcalc()!\n");
			exit(-1);
		}
		memcpy(local_calcs->SID,sender,5);
		local_calcs->nextcalc = NULL;
	} else {
		if (0 >= (tempptr = (struct calcknown*)malloc(sizeof(struct calcknown)))) {
			fprintf(stderr,"Out of memory in checkcalc()!\n");
			cleanupall();
		}
		prevptr->nextcalc = tempptr;
		memcpy(tempptr->SID,sender,5);
		tempptr->nextcalc = NULL;
	}
	unsigned char msgbuf[16];
	msgbuf[0] = 10;
	msgbuf[1] = 0;
	msgbuf[2] = 'c';
	sprintf((char*)(msgbuf+3),"%02X%02X%02X%02X%02X",
		sender[0],sender[1],sender[2],sender[3],sender[4]);
	if (verbose) fprintf(stdout,"Sending calc ID %02X%02X%02X%02X%02X to server\n",
		sender[0],sender[1],sender[2],sender[3],sender[4]);
	int totalsent = 0;
	int framesize = 3+(int)msgbuf[0]+256*(int)msgbuf[1];
	while(totalsent < framesize) {
		if ((i = send(sd,(char *)(msgbuf+totalsent),framesize-totalsent,0)) < 0) {
			fprintf(stderr,"ERROR writing to socket (%d)\n",errno);
			cleanupall();
		}
		totalsent += i;
	}
	if (verbose) {
		fprintf(stdout,"Wrote %d bytes to socket (connect msg)\n",i);
	}
	local_knowncalccount++;
}

static char *usbErrorMessage(int errCode)
{
static char buffer[80];

    switch(errCode){
        case USBOPEN_ERR_ACCESS:      strcpy(buffer,"Access to device denied"); break;
        case USBOPEN_ERR_NOTFOUND:    strcpy(buffer,"The specified device was not found"); break;
        case USBOPEN_ERR_IO:          strcpy(buffer,"Communication error with device"); break;
        default:
            sprintf(buffer, "Unknown USB error %d", errCode);
    }
	return buffer;
}

static usbDevice_t  *openDevice(char *&vendorname_, char *&productname_)
{
usbDevice_t     *dev = NULL;
unsigned char   rawVid[2] = {USB_CFG_VENDOR_ID}, rawPid[2] = {USB_CFG_DEVICE_ID};
char            vendorName[] = {USB_CFG_VENDOR_NAME, 0}, productName[] = {USB_CFG_DEVICE_NAME, 0};
int             vid = rawVid[0] + 256 * rawVid[1];
int             pid = rawPid[0] + 256 * rawPid[1];
int             err;

    if((err = usbhidOpenDevice(&dev, vid, vendorName, pid, productName, 1)) != 0){	//uses report IDs!
        fprintf(stderr, "error finding %s: %s\n", productName, usbErrorMessage(err));
        return NULL;
    }
    static char vname_[] = {USB_CFG_VENDOR_NAME, 0};
    static char pname_[] = {USB_CFG_DEVICE_NAME, 0};
	vendorname_ = vname_;
    productname_ = pname_;
    return dev;
}

void cleanupall() {
	if (devicetype == USBHID) {
		if (devhid != NULL)	
			usbhidCloseDevice(devhid);
	} else if (devicetype == DirectUSB ) {
		if (devh != NULL) 
			close_ti_device(devh);
		devh = NULL;
		if (verbose)
           fprintf(stderr, "Nulling device.\n");
	}
	
#ifdef WINDOWS
	WSACleanup();
	closesocket(sd);
#else
	close(sd);
#endif
	exit(-1);
}
