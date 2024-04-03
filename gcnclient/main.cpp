//#define LINUX
#define WINDOWS

#include <cstdlib>
#include <iostream>
#include <unistd.h>
#include <stdio.h>
#include <getopt.h>
#include <queue>

#ifdef WINDOWS
#include <windows.h>		// Header File For Windows
#include <winsock2.h>
#include <ws2tcpip.h>
#endif

#ifdef LINUX				// Linux extra includes
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <termios.h>
#include <string.h>
#include <fcntl.h>
#include <errno.h>
#endif

using namespace std;
int main(int argc, char *argv[]);
void print_usage(void);
void checkcalc(unsigned char* sender);
void sendbroadcasttoserver(unsigned char* sender, unsigned char* datalen, short unsigned int datalenval, unsigned char* data);
void sendframetoserver(unsigned char* recipient, unsigned char* sender, unsigned char* datalen, short unsigned int datalenval, unsigned char* data);

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

int main(int argc, char *argv[])
{
	//Argument-based semiconstants
	char* comport = NULL;
	char* server_hostname = NULL;
	char* server_port = NULL;
	char* hubname = NULL;
	char* localname = NULL;

	//Socket internal vars
#ifdef WINDOWS
	WSADATA w;								/* Used to open Windows connection */
#endif
	sockaddr_in ServAddr;
	struct hostent *hp;						/* Information about the server */
	char host_name[256];					/* Host name of this computer */
	char msgbuf[300];
	
	//Serial-related stuff
#ifdef WINDOWS
	HANDLE hSerial;
    DWORD dwCommEvent;
    DWORD dwRead,dwBytesRead;
#else
	int hSerial;
	unsigned int dwRead,dwBytesRead;
	struct termios oldtio, newtio;
#endif
    char chRead = 0, last = 0;
    char fakestring[2] = {0,0};
    
	//Assorted, including opt parsing
	int index;
	int c,i;     
	int opterr = 0;
     
	while ((c = getopt (argc, argv, "n:l:s:p:c:vh")) != -1)
	{
		switch (c)
		{
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
	if (server_hostname == NULL || server_port == NULL || comport == NULL || hubname == NULL || localname == NULL) {
		print_usage();
		return -1;
	}
	
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
	newtio.c_cflag = B115200 | CS8 | CLOCAL | CREAD;	//CRTSCTS | 
	newtio.c_iflag = ~(IGNBRK | BRKINT | ICRNL | INLCR | ISTRIP | IXON);
	newtio.c_oflag = ~(OCRNL | ONLCR | ONLRET | ONOCR | OFILL | OLCUC | OPOST);
	newtio.c_lflag = ~(ECHO | ECHONL | ICANON | IEXTEN | ISIG);
	newtio.c_cc[VMIN] = 0;
	newtio.c_cc[VTIME] = 0;
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
	if(!SetCommTimeouts(hSerial, &timeouts)){
	    //error occureed. Inform user
	    fprintf(stderr, "Unable to set serial timeouts.\n");
	    exit(0);
	}
#endif
	
	//Set up socket to server
#ifdef WINDOWS
	// Open windows connection
	if (WSAStartup(0x0101, &w) != 0)
	{
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
#ifdef WINDOWS
		WSACleanup();
#endif
		exit(0);
	}
	// Get host name of this computer
	gethostname(host_name, sizeof(host_name));
	if (NULL == (hp = gethostbyname(host_name))) {
		fprintf(stderr,"Unable to get local hostname [DNS Error]\n");
#ifdef WINDOWS
		closesocket(sd);
		WSACleanup();
#else
		close(sd);
#endif
		exit(0);
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
#ifdef WINDOWS
		WSACleanup();
		closesocket(sd);
#else
		close(sd);
#endif
		cerr << "Server hostname could be be resolved\n" << endl;
		exit(EXIT_FAILURE);
	}
	switch (i = connect(sd, result->ai_addr, result->ai_addrlen)) {
	        case 0:
	                cout << "Resolved hostname." << endl;
	                if (verbose) fprintf(stderr,"Socket #%d\n",sd);
	                break;
#ifdef LINUX
			default:
#else
	        case SOCKET_ERROR:
#endif
					fprintf(stderr,"Unable to bind TCP socket to virtual hub [Socket Bind Error]\n");
#ifdef WINDOWS
	                i = WSAGetLastError();
	                cerr << "Details: " << i << endl;
					WSACleanup();
					closesocket(sd);
#else
					close(sd);
#endif
	                freeaddrinfo(result);
	                exit(EXIT_FAILURE);
	                break;
#ifdef WINDOWS
	        default:
	                cerr << "Fatal connect() error: unexpected "
	                                "return value." << endl;
					WSACleanup();
					closesocket(sd);
	                freeaddrinfo(result);
	                exit(EXIT_FAILURE);
	                break;
#endif
	}
#ifdef WINDOWS
	Sleep(500);
#else
	usleep(500000);
#endif
	
	//Set the socket non-blocking
#ifdef WINDOWS
	ULONG NonBlock = 1;
	if (ioctlsocket(sd, FIONBIO, &NonBlock) == SOCKET_ERROR) {
		fprintf(stderr,"ioctlsocket() failed to set socket as nonblocking\n");
		WSACleanup();
		closesocket(sd);
		exit(-1);
	}
#else
	int flags;
	flags = fcntl(sd,F_GETFL,0);
	if (flags < 0) {
		fprintf(stderr,"Could not fcntl() get socket flags\n");
		close(sd);
		exit(-1);
	}
	if (0 > fcntl(sd, F_SETFL, flags | O_NONBLOCK)) {
		fprintf(stderr,"Could not fcntl() set socket flags\n");
		close(sd);
		exit(-1);
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
    if ((i = send(sd,msgbuf,3+(int)msgbuf[0],0)) < 0) {
		fprintf(stderr,"ERROR writing to socket (%d)\n",errno);
#ifdef WINDOWS
		WSACleanup();
		closesocket(sd);
#else
		close(sd);
#endif
		exit(0);
	} else if (verbose) {
		fprintf(stdout,"Wrote %d bytes to socket (join msg)\n",i);
	}
	
	//BEGIN MAIN LOOP
#ifdef WINDOWS
    if (!SetCommMask(hSerial, EV_RXCHAR)) {
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
		unsigned char recipient[5];
		unsigned char sender[5];
		unsigned char datalen[2];
		unsigned char data[256];
		unsigned char checksum[2];
		short unsigned int checksumval;
		short unsigned int datalenval;
		unsigned char tempbyte = 0;
		unsigned short nibble = 1;
		unsigned char broadbyte = 0;
		bool fail = false;
		
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
		for ( ; ; ) {
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
#ifdef WINDOWS
								WSACleanup();
								closesocket(sd);
#else
								close(sd);
#endif
								exit(0);
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
#ifdef WINDOWS
				WSACleanup();
				closesocket(sd);
#else
				close(sd);
#endif
				exit(-1);
			}
			if (frameindex == 0) {
				while (!sendbuf.empty()) {
					char* thismsg = sendbuf.front();
					short unsigned int thismsgsize = (unsigned char)thismsg[0]+256*(unsigned char)thismsg[1];
#ifdef WINDOWS
                    if(!WriteFile(hSerial, thismsg+3, thismsgsize, &dwBytesRead, NULL)){
#else
					if (0 >= write(hSerial, thismsg+3, thismsgsize)) {
#endif
                            //error occurred. Report to user.
                            fprintf(stderr, "Failed to write frame, type '%c', size '%d', to Arduino\n",thismsg[2],thismsgsize);
                            return -1;
                    }
                    if (verbose) {
						for(i=0;i<thismsgsize;i++) {
							fprintf(stdout,"%02X",(unsigned char)thismsg[3+i]);
							if (i==1 || i==6 || i==11 || i==13 || i==thismsgsize-2) fprintf(stdout," ");
						}
						fprintf(stdout,"\n");
						for(i=0;i<thismsgsize;i++) {
							if ((unsigned char)thismsg[3+i] != 0)
								fprintf(stdout,"%c ",(unsigned char)thismsg[3+i]);
							else
								fprintf(stdout,"  ");
							if (i==1 || i==6 || i==11 || i==13 || i==thismsgsize-2) fprintf(stdout," ");
						}
                    	fprintf(stdout,"\nWrote frame, type '%c', size '%d', to Arduino\n",thismsg[2],thismsgsize);
					}
                    free(thismsg);
                    sendbuf.pop();
				}
			}
	//		if (WaitCommEvent(hSerial, &dwCommEvent, NULL)) {
				do {
					last = chRead;
#ifdef WINDOWS
					if (ReadFile(hSerial, &chRead, 1, &dwRead, NULL) && dwRead) {
#else
					if (0 < (dwRead = read(hSerial,&chRead,1))) {
#endif
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
							if (frameindex >= 12 && fail == false) checkcalc(sender);
							if (broadbyte == 0 && fail == false) {
								sendbroadcasttoserver(sender,datalen,datalenval,data);
							} else if (fail == false) {
								sendframetoserver(recipient,sender,datalen,datalenval,data);
							}
							frameindex = 0;
							nibble = 1;
						} else if (chRead == '\n') {
							if (frameindex >= 12 && fail == false) checkcalc(sender);
							frameindex = 0;
							nibble = 1;
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
#ifdef WINDOWS
	WSACleanup();
	closesocket(sd);
#else
	close(sd);
#endif
	exit(0);
}

void print_usage(void)
{
	fprintf(stdout,"gCn Client v0.1\n(c) 2002-2010 Christopher \"Kerm Martian\" and Cemetech\nhttp://www.cemetech.net\n\n");
	fprintf(stdout,"Syntax: %s -n <hub_name> -l <local_name> -c <COMport> -s <server_hostname> -p <server_port> [-v] [-h]\n","gcnclient");
	fprintf(stdout,"-n <hub_name>        Name of virtual hub to connect to on server\n");
	fprintf(stdout,"-l <local_name>      Name for local endpoint connected to virtual hub\n");
	fprintf(stdout,"-c <COMport>         Serial port for CALCnet2.2 connection, eg COM3\n");
	fprintf(stdout,"-s <server_hostname> eg. gcnhub.cemetech.net or 194.24.54.139\n");
	fprintf(stdout,"-p <server_port>     eg. 4295\n\n");
	return;
}

void sendbroadcasttoserver(unsigned char* sender, unsigned char* datalen, short unsigned int datalenval, unsigned char* data) {
	char msgbuf[300];
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
	fprintf(stdout,"Outgoing datalen is %d,%d\n",datalen[0],datalen[1]);
	memcpy(msgbuf+5+5+5+2,data,datalenval);
	msgbuf[5+5+5+2+datalenval] = 42;
	if (verbose) {
		for(i=0;i<5+5+2+datalenval;i++) {
			if ((unsigned char)msgbuf[5+i] != 0)
				fprintf(stdout,"%c ",(unsigned char)msgbuf[5+i]);
			else
				fprintf(stdout,"  ");
			if (i==1 || i==6 || i==11 || i==13 || i==5+5+2+datalenval-2) fprintf(stdout," ");
		}
		fprintf(stdout,"Broadcasting data of length %d to server\n",datalenval);
	}
    if ((i = send(sd,msgbuf,3+(int)msgbuf[0],0)) < 0) {
		fprintf(stderr,"ERROR writing to socket (%d)\n",errno);
#ifdef WINDOWS
		WSACleanup();
		closesocket(sd);
#else
		close(sd);
#endif
		exit(0);
	} else if (verbose) {
		fprintf(stdout,"Wrote %d bytes to socket (broadcast msg)\n",i);
	}
}

void sendframetoserver(unsigned char* recipient, unsigned char* sender, unsigned char* datalen, short unsigned int datalenval, unsigned char* data) {
	char msgbuf[300];
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
	fprintf(stdout,"Outgoing datalen is %d,%d\n",datalen[0],datalen[1]);
	memcpy(msgbuf+5+5+5+2,data,datalenval);
	msgbuf[5+5+5+2+datalenval] = 42;
	if (verbose) {
		for(i=0;i<5+5+2+datalenval;i++) {
			if ((unsigned char)msgbuf[5+i] != 0)
				fprintf(stdout,"%c ",(unsigned char)msgbuf[5+i]);
			else
				fprintf(stdout,"  ");
			if (i==1 || i==6 || i==11 || i==13 || i==5+5+2+datalenval-2) fprintf(stdout," ");
		}
		fprintf(stdout,"Sending frame data of length %d to server\n",datalenval);
	}
    if ((i = send(sd,msgbuf,3+(int)msgbuf[0],0)) < 0) {
		fprintf(stderr,"ERROR writing to socket (%d)\n",errno);
#ifdef WINDOWS
		WSACleanup();
		closesocket(sd);
#else
		close(sd);
#endif
		exit(0);
	} else if (verbose) {
		fprintf(stdout,"Wrote %d bytes to socket (frame msg)\n",i);
	}
}

void checkcalc(unsigned char* sender)
{
	int i,j=0;
	struct calcknown* tempptr = local_calcs;
	struct calcknown* prevptr = NULL;
	
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
#ifdef WINDOWS
			WSACleanup();
			closesocket(sd);
#else
			close(sd);
#endif
			exit(-1);
		}
		prevptr->nextcalc = tempptr;
		memcpy(tempptr->SID,sender,5);
		tempptr->nextcalc = NULL;
	}
	char msgbuf[16];
	msgbuf[0] = 10;
	msgbuf[1] = 0;
	msgbuf[2] = 'c';
	sprintf(msgbuf+3,"%02X%02X%02X%02X%02X",sender[0],sender[1],sender[2],sender[3],sender[4]);
	if (verbose) fprintf(stdout,"Sending calc ID %02X%02X%02X%02X%02X to server\n",
		sender[0],sender[1],sender[2],sender[3],sender[4]);
    if ((i = send(sd,msgbuf,3+(int)msgbuf[0],0)) < 0) {
		fprintf(stderr,"ERROR writing to socket (%d)\n",errno);
#ifdef WINDOWS
		WSACleanup();
		closesocket(sd);
#else
		close(sd);
#endif
		exit(0);
	} else if (verbose) {
		fprintf(stdout,"Wrote %d bytes to socket (connect msg)\n",i);
	}
	local_knowncalccount++;
}
