/*
	              _____ gcnBridge _____
	                   \---------/
	Arduino globalCALCnet-to-CALCnet Bridge Software
	
	(c) 2003-2014 Christopher Mitchell / "Kerm Martian"
 
	http://www.cemetech.net
	christoper@cemetech.net
	 
	Connects PC-side gCn client to one or more TI graphing calculators on
	a CALCnet2.2 network. 
	
 */

//ONLY ONE OF THESE
#define avr328
//#define avr168

//ONLY ONE OF THESE
#define sparkcore
//#define ardubridge
//#define usbhid

#ifdef ardubridge
#include <Arduino.h>
#endif

#ifdef sparkcore            // Spark Core implies Ardubridge
#define ardubridge
#define sparkdebug          // Toggle this as necessary
SYSTEM_MODE(SEMI_AUTOMATIC);

const char* server_host = "gcnhub.cemetech.net";
uint16_t server_port = 4295;
char localhub[17] = "Spark0000";
char remotehub[17] = "IRCHub";
const char* hexstring = "0123456789ABCDEF";

const int TCP_MSG_BUF_SIZE = 300;
uint8_t msg_buf[TCP_MSG_BUF_SIZE];

// LED defines
const int ledtoggle = 7;
uint8_t rgbledmask = 0;
const int ledr = 1 << 0;
const int ledg = 1 << 1;
const int ledb = 1 << 2;

// Commands and addresses
const uint8_t self_addr[5] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
#define EEPROM_MAGIC_OFFSETL 0
#define EEPROM_MAGIC_OFFSETR 1
#define EEPROM_LOCALHUB_OFFSET 2
#define EEPROM_REMOTEHUB_OFFSET 19
#define EEPROM_END_OFFSET 36
#define EEPROM_MAGIC 42
bool connectable = false;                   // Don't even try if we're not configured
#else

const int ledr = 8;
const int ledg = 9;
const int ledb = 10;
#define setRGBLED(mask, state) digitalWrite(mask, state)

#endif

#ifdef usbhid
extern "C" unsigned int usbFunctionSetup(unsigned char data[8]);
extern "C" unsigned char usbFunctionWrite(unsigned char *data, unsigned char len);
#define USB_CFG_DESCR_PROPS_STRING_VENDOR USB_PROP_LENGTH(8)
#define USB_CFG_VENDOR_NAME {'C','e','m','e','t','e','c','h'}
#define USB_CFG_VENDOR_NAME_LEN 8
#define USB_CFG_DESCR_PROPS_STRING_PRODUCT USB_PROP_LENGTH(9)
#define USB_CFG_DEVICE_NAME {'g','C','n','B','r','i','d','g','e'}
#define USB_CFG_DEVICE_NAME_LEN 9
#include "usbconfig_gcnbridge.h"
#include <avr/pgmspace.h>
#include <avr/interrupt.h>
#include <string.h>
#include <avr/io.h>
#include <avr/wdt.h>
#include <avr/interrupt.h>  // for sei()
#include <util/delay.h>     // for _delay_ms()
#include <avr/eeprom.h>

#include <avr/pgmspace.h>   // required by usbdrv.h
//*****CHRISTOPHER'S NOTES: Rename usbdrv_gcnbridge.h to usbdrv.h for this project.
//*****WILL NEED to change name of other usbdrv.h files for other projects.
//*****DITTO with oddebug.h!
#include "usbdrv.h"
#include "oddebug.h"        // This is also an example for using debug macros

uint8_t output_pending;      //1 for a frame, 2 for the reset
uint8_t input_pending;
unsigned char resetstring[4] = {
  ':', 'R', 's', '\n'};
#endif

#ifdef usbhid
const int TIring = 11;
const int TItip = 12;
#else
const int TIring = 5;
const int TItip = 6;
uint8_t led_state = 0;
#endif

//Global frame send/receive data
uint8_t framebuffer[1+256+2+5+5];        //1 byte USB prefix!f
uint8_t* sender = framebuffer + 1+0;  //5 bytes
uint8_t* recipient = framebuffer + 1+5;  //5 bytes
uint8_t* datasizeptr = framebuffer+1+10;  //2 bytes
uint8_t* data = framebuffer + 1+12;    //256 bytesd 

//Global network constituent storage/searching
#ifdef avr328
#define calcstoresize 500
#else
#define calcstoresize 200
#endif

uint8_t* calcsearchptr_recv;
uint8_t* calcsearchptr_send;
uint8_t calcsknown;
uint8_t calcspassed_recv;
uint8_t calcspassed_send;
uint8_t calcsearchstate;
uint8_t calcstore[calcstoresize];

#define TIwhite TIring
#define TIred TItip
#define CN2clock TItip
#define CN2data TIring

#define ERR_READ_TIMEOUT 1000
#define ERR_WRITE_TIMEOUT 2000
#define TIMEOUT 4000
#define GET_ENTER_TIMEOUT 30000

#ifdef sparkcore

#define CN2_GETBYTE1_TIMEOUT 2000 //is 40 oncalc
#define CN2_GETBYTE3_TIMEOUT 2000 //is 40 oncalc
#define CN2_GETBYTE5_TIMEOUT 9000 //is 40 oncalc
#define CN2_RECEIVEFRAMESTARTING_TIMEOUT 9000000 //(55000-6000)/58 oncalc

#define CN2_GETBYTE1_TIMEOUT_US 230
#define CN2_GETBYTE3_TIMEOUT_US 200
#define CN2_GETBYTE5_TIMEOUT_US 430
#define CN2_RECEIVEFRAMESTARTING_TIMEOUT_US 15000

#else

#define CN2_GETBYTE1_TIMEOUT 200 //is 40 oncalc
#define CN2_GETBYTE3_TIMEOUT 200 //is 40 oncalc
#define CN2_GETBYTE5_TIMEOUT 900 //is 40 oncalc
#define CN2_RECEIVEFRAMESTARTING_TIMEOUT 900000 //(55000-6000)/58 oncalc
#define CN2_RECEIVEFRAMESTARTING_TIMEOUT_US 15000

#endif

#define CN2_MAX_FRAME_RETRIES 255

#define WAITTIME(datasize) (17+(46*(datasize&0x7fff))/3)

void resetLines();
void mySerialEmptyBuf();
unsigned int mySerialRead();
static int cn2_send();
static void cn2_receive();
static uint16_t cn2_sendbyte(uint8_t);
static uint16_t cn2_recbyte();
static uint16_t cn2_search_FSM(uint16_t);

#ifdef sparkcore
TCPClient client;
#endif

void setup() {
    
    //Initialize pins
    resetLines();
    
    //debugging
#ifndef sparkcore
    pinMode(ledr,OUTPUT);
    pinMode(ledg,OUTPUT);
    pinMode(ledb,OUTPUT);
#else
    // RGB LEDs will be handled by on-board RGB LED
	pinMode(ledtoggle,OUTPUT);
#endif
    
    calcsknown = 0;
    
    // Initialize USB
#ifdef usbhid
    //Was //UsbStream.begin()
    // disable timer 0 overflow interrupt (used for millis)
    TIMSK0&=!(1<<TOIE0);
    cli();
    usbInit();
    usbDeviceDisconnect();
    unsigned char i;
    i = 0;
    while(--i){             // fake USB disconnect for > 250 ms
        _delay_ms(1);
    }
    usbDeviceConnect();
    
    input_pending = 2;
    output_pending = 0;
    sei();
#endif

    // Initialize serial communication
#ifdef ardubridge

#ifdef sparkcore
    WiFi.on();                  // Vital in SEMI_AUTOMATIC mode
    
    Serial.begin(9600);             // Used for logging
#ifdef sparkdebug
    while(!Serial.available()) Spark.process();
    Serial.print("Beginning bridge process with connectable = ");
    Serial.println(connectable);
#endif

    // This is VITAL to copy the array to RAM, because dumb Spark bug
    WiFi.connect();

    // Check if local and remote hub name are not yet saved
    if (EEPROM.read(EEPROM_MAGIC_OFFSETL != EEPROM_MAGIC)) {
        int len = strlen(localhub);
        for(int i=0; i < len; i++) {
            EEPROM.write(EEPROM_LOCALHUB_OFFSET + i, localhub[i]);
        }
        EEPROM.write(EEPROM_LOCALHUB_OFFSET + len, 0);            // Null terminator
        EEPROM.write(EEPROM_MAGIC_OFFSETL, EEPROM_MAGIC);
    }
    if (EEPROM.read(EEPROM_MAGIC_OFFSETR != EEPROM_MAGIC)) {
        int len = strlen(remotehub);
        for(int i=0; i < len; i++) {
            EEPROM.write(EEPROM_REMOTEHUB_OFFSET + i, remotehub[i]);
        }
        EEPROM.write(EEPROM_REMOTEHUB_OFFSET + len, 0);            // Null terminator
        EEPROM.write(EEPROM_MAGIC_OFFSETR, EEPROM_MAGIC);
    }
#ifdef sparkdebug
    Serial.print("Credentials = ");
    Serial.print(WiFi.hasCredentials());
    Serial.print("; magic_offsetl = ");
    Serial.print(EEPROM.read(EEPROM_MAGIC_OFFSETL));
    Serial.print("; magic_offsetr = ");
    Serial.println(EEPROM.read(EEPROM_MAGIC_OFFSETR));
#endif

    // Figure out if we can connect yet
    if (WiFi.hasCredentials() &&
        (EEPROM.read(EEPROM_MAGIC_OFFSETL) == EEPROM_MAGIC) &&
        (EEPROM.read(EEPROM_MAGIC_OFFSETR) == EEPROM_MAGIC))
    {
        connectable = true;
    }

    // Initialize stuff
    if ((EEPROM.read(EEPROM_MAGIC_OFFSETL) == EEPROM_MAGIC) &&
        (EEPROM.read(EEPROM_MAGIC_OFFSETR) == EEPROM_MAGIC))
    {
        copyHubsToRAM();
    }
    if (connectable) {
        connectMetahub();               // At least attempt
    }
#else
    Serial.begin(115200);           // Used to communicate with gCnClient
    Serial.write(":RESETs");
    Serial.write('\n');
#endif
#endif

}

void loop() {
    int i,j;
    uint16_t datasize;
    
    resetLines();
#ifdef usbhid
    usbPoll();
#endif
    setRGBLED(ledr, LOW);
    setRGBLED(ledg, LOW);
    setRGBLED(ledb, LOW);
    
#ifdef sparkcore
    if (!client.connected()) {
        setRGBLED(ledr, HIGH);
    }
#endif

#ifdef usbhid
    if (output_pending) {
        j = 0;
        usbPoll();      //try to ack
        do {
            setRGBLED(ledr, HIGH);
            uint8_t oldSREG = SREG;
            cli();
            i = cn2_send();
            SREG = oldSREG;
            if (i != 0) {
                setRGBLED(ledr, LOW);
                if (i == -99) setRGBLED(ledg, HIGH);
                    usbPoll();
                j=40;
                while(--j)             // fake USB disconnect for > 250 ms
                    _delay_ms(1);
                usbPoll();
                j++;
            }
        }
        while (i != 0 && j < CN2_MAX_FRAME_RETRIES);
        output_pending = 0;
        usbEnableAllRequests();
    }

#else
    mySerialEmptyBuf();
    bool doFlush = true;
    int tempval;
#ifndef sparkcore
    if (Serial.available() > 0) {
        if (255 != mySerialRead())
        goto serialFlush;
        if (137 != mySerialRead())
        goto serialFlush;
        
        digitalWrite(CN2clock, LOW); // TEMPORARY - inhibit Cn2.2
        setRGBLED(ledr, LOW);
        setRGBLED(ledg, LOW);
        setRGBLED(ledb, HIGH);
      
        // Fetch the recipient ID
        for(i=0; i<5; i++) {
            if (-1 == (tempval = mySerialRead()))
                goto serialFlush;
            recipient[i] = tempval;
        }
        // Fetch the sender ID
        for(i=0; i<5; i++) {
            if (-1 == (tempval = mySerialRead()))
                goto serialFlush;
            sender[i] = tempval;
        }
        // Get the data size word
        if (-1 == (tempval = mySerialRead()))
            goto serialFlush;
        datasize = datasizeptr[0] = tempval;
        
        if (-1 == (tempval = mySerialRead()))
            goto serialFlush;
        datasizeptr[1] = 0x7f & (tempval);
        datasize += 256*(0x7f & datasizeptr[1]);
        for(i=0; i<datasize; i++) {
            if (-1 == (tempval = mySerialRead()))
                goto serialFlush;
            data[i] = tempval;
        }
        
        // Check if we received the end-of-message marker
        if (mySerialRead() == 42) {
            doFlush = false;
            digitalWrite(CN2clock, HIGH); // TEMPORARY - un-inhibit Cn2.2
            j = 0;
            mySerialEmptyBuf();
            do {
                setRGBLED(ledr, HIGH);
                i = cn2_send();
                if (i != 0) {
                    setRGBLED(ledr, LOW);
                    if (i == -99) setRGBLED(ledg, HIGH);
                    delay(100);
                    j++;
                }
                mySerialEmptyBuf();
            } while (i != 0 && j < CN2_MAX_FRAME_RETRIES);
        } else {
            mySerialEmptyBuf();
        }
    
    serialFlush:
        digitalWrite(CN2clock, HIGH); // TEMPORARY - un-inhibit Cn2.2
        setRGBLED(ledb, LOW);

        do {
            if ('s' == Serial.read()) {
                Serial.write('s');
                break;
            }
        } while(doFlush);
    }
    // Finished reading and handling frame from serial
#else   // sparkcore
    // Try to receive and handle frame from network
    int c;
    int idx = 0;
    int framelen = 3;
    bool valid = true;
    if (client.connected() && (-1 != (c = client.read()))) {
#ifdef sparkdebug
        Serial.println("Receiving frame from gCn...");
#endif
        msg_buf[0] = c;
        idx++;
        while(idx < framelen) {
            do {
                c = client.read();
                if (c == -1) Spark.process();
            } while (c == -1);
            
            //if (idx < 3)
                msg_buf[idx] = c;
            if (idx == 1) {
                framelen = 3 + (((0x7f & msg_buf[1]) << 8) | (msg_buf[0]));
            }
            if (idx == 3 && c != 255) valid = false;
            if (idx == 4 && c != 137) valid = false;
            if (idx == framelen - 1 && c != 42) valid = false;
            
            if (idx >= 5 && idx < 10) {
                recipient[idx - 5] = c;
            }
            if (idx >= 10 && idx < 15) {
                sender[idx - 10] = c;
            }
            if (idx >= 15 && idx < 17) {
                datasizeptr[idx - 15] = c;
            }
            if (idx >= 17 && idx < framelen - 1) {
                data[idx - 17] = c;
            }
            
            idx++;
        }
        
        if (valid && (msg_buf[2] == 'b' || msg_buf[2] == 'f')) {
#ifdef sparkdebug
            Serial.print("Have valid frame to send to Cn2, type ");
            Serial.write(msg_buf[2]);
            Serial.println("");
#endif
            int retries = 0;
            do {
                setRGBLED(ledr, HIGH);
                i = cn2_send();
                if (i != 0) {
                    setRGBLED(ledr, LOW);
                    if (i == -99) setRGBLED(ledg, HIGH);
                    delay(100);
                    retries++;
                }
            } while (i != 0 && retries < CN2_MAX_FRAME_RETRIES);

        } else {
#ifdef sparkdebug
            Serial.print("Have INVALID frame to send to Cn2, type ");
            Serial.write(msg_buf[2]);
            Serial.println("");
#endif
        }
    } else if (!client.connected() && connectable) {
        connectMetahub();
    }
#endif
#endif

    resetLines();
    if (digitalRead(CN2clock) == HIGH)
        return;         // Nothing to read from the network
        
    // Try to read from the network
#ifdef usbhid
    _delay_ms(1);
#else
    delayMicroseconds(1000); //aka 1 millisecond
#endif
    if (digitalRead(CN2clock) == LOW) {
        setRGBLED(ledg, LOW);
#ifdef usbhid
        uint8_t oldSREG = SREG;
        cli();
#endif
        cn2_receive();
#ifdef usbhid
        SREG = oldSREG;
#else
        led_state = 1 - led_state;
        digitalWrite(ledg, led_state);
#endif
    }
}

    
#ifdef ardubridge
unsigned int mySerialRead()  {
    unsigned int received = 0, tempval, val = 0;

SerialReadStart:
    while(Serial.available() <= 0) {}
    if ((tempval = Serial.read()) == 's') {
        setRGBLED(ledr, HIGH);
        setRGBLED(ledg, HIGH);
        setRGBLED(ledb, HIGH);
        Serial.write('s');
        goto SerialReadStart;
    }
    setRGBLED(ledr, LOW);
    setRGBLED(ledg, LOW);
    setRGBLED(ledb, LOW);
    val |= (tempval-'0'*(tempval<='9')-('A'-10)*(tempval>='A'));
    if (received == 0)
        val = ((val << 4) & 0x00f0);
    received++;
    if (received == 1)
        goto SerialReadStart;
    return val;
}
    
void mySerialEmptyBuf() {
    if (0 >= Serial.available())
        return;
    if (Serial.peek() == 's') {
        Serial.read();
        Serial.write('s');
    }
}
#endif
    
void resetLines() {
#ifdef sparkcore
    pinMode(TIring, INPUT_PULLUP);
    pinMode(TItip, INPUT_PULLUP);
#else
    pinMode(TIring, INPUT);           // set pin to input
    digitalWrite(TIring, HIGH);       // turn on pullup resistors
    pinMode(TItip, INPUT);            // set pin to input
    digitalWrite(TItip, HIGH);        // turn on pullup resistors
#endif
}
    
static int cn2_send() {
      int i,j;
      uint16_t datasize;
      uint8_t readytosend;
      uint16_t checksum,checksum2, checksum3;
      uint8_t addror;
    #ifdef usbhid
      uint16_t timerlong, timerlong2;
    #else
      unsigned long timerlong, timerlong2;
    #endif
    
#ifdef sparkdebug
    Serial.print("Sending cn2.2 frame to ");
    for(int i=0; i < 5; i++) {
        Serial.print(recipient[i], HEX);
    }
    Serial.write(" from ");
    for(int i=0; i < 5; i++) {
        Serial.print(sender[i], HEX);
    }
    Serial.print(" length ");
    Serial.print((datasizeptr[1] & 0x007f) * 256 + datasizeptr[0], DEC);
    Serial.println("");
#endif

      resetLines();
      do {
        readytosend = 0;
    #ifdef usbhid
        TCCR1A = 0; //start TIMER1
        TCCR1B = (1 << CS10); //NO prescaling!
        TCNT1 = timerlong = 0;  //reset count
        while((TCNT1-timerlong) < (uint16_t)((F_CPU/1000000)*883) && TCNT1 < (uint16_t)((F_CPU/1000000)*2500)) {
          if (digitalRead(CN2clock) == LOW) timerlong = TCNT1;
        }
        if (TCNT1 < (uint16_t)((F_CPU/1000000)*2500)) readytosend = 1;
        if (!readytosend) _delay_ms(10);
    #else
        timerlong = timerlong2 = micros();
        while(micros()-timerlong < 883 && micros()-timerlong2 < 2500) {
          if (digitalRead(CN2clock) == LOW) timerlong = micros();
        }
        if (micros()-timerlong2 < 2500) readytosend = 1;
        if (!readytosend) delay(10);  //100 attempts per second
    #endif
      } while(!readytosend);
    #ifdef usbhid
      TCCR1A = 0; //start TIMER1
      TCCR1B = (1 << CS11); // div8 prescaling!
      TCNT1 = 0;  //reset count
    #else
      timerlong = micros();
    #endif
      pinMode(TItip, OUTPUT);            // set pin to output
      pinMode(TIring, OUTPUT);           // set pin to output
    #ifdef usbhid
      while(TCNT1 < (uint16_t)((F_CPU/1000000)*(9000/8))) {
    #else
      while(micros()-timerlong < 9000) {
    #endif
        digitalWrite(CN2clock, LOW);
        digitalWrite(CN2data, LOW);
      }
    
        setRGBLED(ledb, HIGH);
        setRGBLED(ledr, LOW);

      addror = 0;
      for (i=0; i<5; i++) {
        addror |= recipient[i];
        j = cn2_sendbyte(recipient[i]);
        if (j < 0) return -1;
      }
    #ifdef usbhid
      _delay_us(44);
    #else
      timerlong = micros();
      while(micros()-timerlong < 44) {
      }
    #endif
      for (i=0; i<5; i++) {
        j = cn2_sendbyte(sender[i]);
        if (j < 0) return -1;
      }
    
        setRGBLED(ledg, HIGH);
        setRGBLED(ledb, LOW);

      if (0 > cn2_sendbyte(datasizeptr[0])) return -1;
      if (0 > cn2_sendbyte(datasizeptr[1])) return -1;
      datasize = (datasizeptr[1] & 0x007f) * 256 + datasizeptr[0];
      checksum = 0;
      for (i=0; i<datasize; i++) {
        checksum += data[i];
        j = cn2_sendbyte(data[i]);
        if (j < 0) return -1;
      }
      if (addror == 0) {
        setRGBLED(ledg, HIGH);
return 0;    //broadcast
      }
    
    #ifdef usbhid
      int waittime = WAITTIME(datasize);
      _delay_us((double)waittime);
    #else
      timerlong = micros();
      int waittime = WAITTIME(datasize);
      while(micros()-timerlong < waittime) {
      }
    #endif
      if (0 > (j = cn2_recbyte())) return j;
      checksum2 = (uint16_t)j;
      if (0 > (j = cn2_recbyte())) return -1;
      checksum2 += 256*(uint16_t)j;
      if (checksum != checksum2) return -1;
      if (0 > cn2_sendbyte(0xaa)) return -1;
        setRGBLED(ledb, HIGH);
return 0;
    }
    
    
static void cn2_receive() {
    uint32_t i;
    uint16_t k, datasize;
    int16_t j;
    
    uint16_t checksum,checksum2, checksum3;
    uint8_t addror;
#ifdef sparkcore
    const uint8_t* selfaddr_offset;     // Check if msg is to us
    bool selfmatch;                     // set if target addr is us
#endif
    unsigned long timerlong, timerlong2;
    
    resetLines();
#ifdef usbhid
    if (input_pending || output_pending)    //don't overwrite input with output!
        return;
#endif
    
    //Initialize searching state machine
    calcsearchptr_recv = calcsearchptr_send = calcstore;
    calcspassed_recv = 0;
    calcspassed_send = 0;
    calcsearchstate = 0;
    
#ifdef sparkdebug
    Serial.println("Receiving frame from Cn2");
#endif

    unsigned long now, then;
    now = then = micros();
    while (digitalRead(CN2clock) != 1 &&
           ((now - then) < CN2_RECEIVEFRAMESTARTING_TIMEOUT_US))
    {
        now = micros();
    }
    if ((now - then) >= CN2_RECEIVEFRAMESTARTING_TIMEOUT_US) {
        return;
    }

    addror = 0;

#ifdef sparkcore
    selfmatch = true;
    selfaddr_offset = self_addr;
#endif

    for(i=0; i<5; i++) {
        j = cn2_recbyte();
        if (j < 0)
            break;
        recipient[i] = (j & 0x00ff);
        addror |= recipient[i];
#ifdef sparkcore
        selfmatch = selfmatch && (recipient[i] == *selfaddr_offset);
        selfaddr_offset++;
#endif
    }

    if (j < 0) {
#ifdef usbhid
//UsbStream.write('f');
//UsbStream.write('\n');
#else
#ifdef sparkdebug
        Serial.print(j);
        Serial.print(' ');
#endif
        Serial.write("f\n");
#endif
        return;
    }
    for(i=0; i<5; i++) {
        j = cn2_recbyte();
        if (j < 0)
            break;
        sender[i] = (j & 0x00ff);
    }

    if (j < 0) {
#ifdef usbhid
        //UsbStream.write('f');
        //UsbStream.write('\n');
#else
#ifdef sparkdebug
        Serial.print(j);
        Serial.print(' ');
#endif
        Serial.write("f\n");
#endif
        return;
    }
    
    datasize = datasizeptr[0] = cn2_recbyte();
    datasizeptr[1] = (cn2_recbyte() & 0x7f);
    datasize += 256 * (0x7f & datasizeptr[1]);
    if (datasize > 255) {
#ifdef usbhid
    //UsbStream.write('f');
    //UsbStream.write('\n');
#else
#ifdef sparkdebug
        Serial.print(j);
        Serial.print(' ');
#endif
        Serial.write("f\n");
#endif
        return;
    }
    setRGBLED(ledb, HIGH);
    checksum = 0;
    for(i=0; i<datasize; i++) {
        j = cn2_recbyte();
        if (j < 0) break;
        data[i] = j;
        checksum += j;
        if (99 == cn2_search_FSM(1)) return;
    }
    setRGBLED(ledr, LOW);
    if (j < 0) {
#ifdef usbhid
        //UsbStream.write('f');
        //UsbStream.write('\n');
#else
#ifdef sparkdebug
        Serial.print(j);
        Serial.print(' ');
#endif
        Serial.write("f\n");
#endif
        return;
    }
    k = 2;
    if (addror != 0) {				//deal with checksumming things
#ifdef usbhid
        TCCR1A = 0; //start TIMER1
        TCCR1B = (1 << CS10); //NO prescaling!
        TCNT1 = 0;  //reset count
        uint16_t waittime = WAITTIME(datasize);
#else
        timerlong = micros();
        int waittime = WAITTIME(datasize);
#endif
        k = cn2_search_FSM(1000);	
        if (k == 99) return;
#ifdef usbhid
        while(TCNT1 < (uint16_t)((F_CPU/1000000)*waittime)) {	
            //up to 4095us = 17+(46/3)*datasize
            //= 4095*(3/46) < 266 bytes -> 265 bytes
#else
        while(micros()-timerlong < waittime) {
#endif
        }
        if (k == 2) {
          if (0 > cn2_sendbyte(checksum & 0x00ff)) {
#ifdef sparkdebug
            Serial.println("Failed to send checksum LSB");
#endif
            return;
          }
          if (0 > cn2_sendbyte((checksum >> 8) & 0x00ff)) {
#ifdef sparkdebug
            Serial.println("Failed to send checksum MSB");
#endif
            return;
          }
          if (0 > (j = cn2_recbyte())) {
#ifdef sparkdebug
            Serial.print("Failed to receive checksum ack: ");
            Serial.println(j);
#endif
            return;
          }
          if (j != 0xAA) {
#ifdef sparkdebug
            Serial.println("Checksum was not acked by calculator.");
#endif
            return;
          }
        }
      }
#ifdef usbhid
    input_pending = 1;
#else
#ifndef sparkcore
    // Arduino serial communication
    Serial.write('|');
    for(i=0; i<5; i++) {
        if (sender[i] < 16)
            Serial.write('0');
        Serial.print(sender[i],HEX);
    }
    Serial.write('.');
    for(i=0; i<5; i++) {
        if (recipient[i] < 16)
            Serial.write('0');
        Serial.print(recipient[i],HEX);
    }
    Serial.write(',');
    if (datasize < 16)
        Serial.write('0');
    Serial.print(datasize & 0x00ff,HEX);
    if (datasize < 4096)
        Serial.write('0');
    Serial.print((datasize>>8) & 0x007f,HEX);
    Serial.write(':');
    for(i=0; i<datasize; i++) {
        if (data[i] < 16)
            Serial.write('0');
        Serial.print(data[i],HEX);
    }
    if (k == 2)
        Serial.write('>');
    Serial.write('\n');
#else
    int framelen = 3 + 12 + datasize;
    // Spark Core communication
    msg_buf[0] = framelen & 0x00ff;
    msg_buf[1] = (framelen >> 8) & 0x00ff;
    msg_buf[2] = (addror != 0)?'f':'b';
    msg_buf[3] = 255;
    msg_buf[4] = 137;
    for(i = 0; i < 5; i++) {
        msg_buf[5 + i] = recipient[i];
    }
    for(i = 0; i < 5; i++) {
        msg_buf[10 + i] = sender[i];
    }
    msg_buf[15] = datasize & 0x00ff;
    msg_buf[16] = (datasize >> 8) & 0x007f;
    for(i = 0; i < datasize; i++) {
        msg_buf[17 + i] = data[i];
    }
    msg_buf[17 + datasize] = 42;
#ifdef sparkdebug
    Serial.print("Have valid frame for gCn, length ");
    Serial.println(3 + framelen);

    Serial.print("Have frame to send to gcn, type ");
    Serial.write(msg_buf[2]);
    Serial.write(" length ");
    Serial.println(3 + framelen);
    for(int i=0; i < 3 + framelen; i++) {
        Serial.print(msg_buf[i], HEX);
        Serial.print(' ');
    }
    Serial.println(";;;");
#endif

    if (selfmatch) {
        // Process message meant for us
        Serial.println("Self-message received");
        sparkProcessCommand();
    } else {
        client.write(msg_buf, 18 + datasize);
    }
#endif
#endif
    return;
}
    
    /*
    #ifdef usbhid
    void UsbHexPrint(uint8_t inbyte) {
      uint16_t outbyte;
      outbyte = (0x000f&(inbyte>>4))+'0';
      if (outbyte > '9') outbyte += 'A'-'9'-1;
      //UsbStream.write(outbyte);
      outbyte = (0x000f&inbyte)+'0';
      if (outbyte > '9') outbyte += 'A'-'9'-1;
      //UsbStream.write(outbyte);
    }
    #endif
    */
    
static uint16_t cn2_search_FSM(uint16_t ticks) {
      //Valid search states:
      // 0 = searching for sender
      // 1 = sender known, searching for receiver
      // 2 = sender known, receiver unknown
      // 3 = both sender & receiver known
    
      int i;
      uint8_t j;
    
      while (ticks > 0) {
        if (calcsearchstate > 1) break;
        else if (calcsearchstate == 0) {		//searching for sender
          if (calcspassed_send >= calcsknown || calcsearchptr_send[0] > sender[0]) {	//unknown
            pinMode(CN2clock, OUTPUT);           // set pin to output
            digitalWrite(CN2clock,LOW);
            if (calcsknown-calcspassed_send > 0) {
              for(i=(5*(calcsknown-calcspassed_send))-1;i>=0;i--)
                calcsearchptr_send[i+5] = calcsearchptr_send[i];
            }
            memcpy(calcsearchptr_send,sender,5);
            calcsknown++;
            
#ifdef sparkcore
            // Notify the gCn metahub
            connectMetahub();
            Serial.println("Detected new calculator");
            msg_buf[0] = 10;
            msg_buf[1] = 0;
            msg_buf[2] = 'c';
            for(int i=0; i < 5; i++) {
                msg_buf[3 + i + i] = hexstring[sender[i] >> 4];
                msg_buf[4 + i + i] = hexstring[sender[i] & 0x0f];
            }
            client.write(msg_buf, 3 + 10);
#endif

            //calcsearchstate = 1;
            setRGBLED(ledr, HIGH);
            setRGBLED(ledg, HIGH);
            setRGBLED(ledb, LOW);
#ifdef usbhid
            usbPoll();
            for(i=0; i<12; i++) {
              j=40;
              while(--j)             // fake USB disconnect for > 250 ms
                _delay_ms(1);
              usbPoll();
            }
#else
            delay(400);
#endif
            digitalWrite(CN2clock,HIGH);
            setRGBLED(ledb, HIGH);
#ifdef usbhid
            for(i=0; i<12; i++) {
              j=40;
              while(--j)             // fake USB disconnect for > 250 ms
                _delay_ms(1);
              usbPoll();
            }
#else
            delay(400);
#endif
            setRGBLED(ledb, LOW);
#ifdef usbhid
            for(i=0; i<12; i++) {
              j=40;
              while(--j)             // fake USB disconnect for > 250 ms
                _delay_ms(1);
              usbPoll();
            }
#else
            delay(400);
#endif
            return calcsearchstate = 99;
          } 
          else {
            for(i=0;i<6;i++) {
              if (i==5) {
                calcsearchstate = 1;
                break;
              }
              if (calcsearchptr_send[i] != sender[i]) break;
            }
            calcspassed_send++;
            calcsearchptr_send+=5;
          }
        } 
        else if (calcsearchstate == 1) {		//searching for receiver
          if (calcspassed_recv >= calcsknown || calcsearchptr_recv[0] > recipient[0]) {	//unknown
            calcsearchstate = 2;
            return 2;
          } 
          else {
            for(i=0;i<6;i++) {
              if (i==5) {
                calcsearchstate = 3;
                return 3;
              }
              if (calcsearchptr_recv[i] != recipient[i]) break;
            }
            calcspassed_recv++;
            calcsearchptr_recv+=5;
          }
        }
        ticks--;
      }
      return calcsearchstate;
}

static uint16_t cn2_sendbyte(uint8_t outbyte) {
      int i;
      int loopcntr;
      uint8_t tempbyte;
      unsigned long timerlong;
    
      pinMode(TIring, OUTPUT);           // set pin to output
      digitalWrite(TIring, HIGH);
      pinMode(TItip, OUTPUT);            // set pin to output
      digitalWrite(TItip, HIGH);
      resetLines();
      tempbyte = 0;
      //Cn2_Int_SendByteRev:
    
      for(i=0; i<8; i++) {
        tempbyte |= (outbyte&0x01);
        if (i !=7) tempbyte<<=1;
        outbyte>>=1;
      }
      outbyte = tempbyte;
    
    #ifdef usbhid
      _delay_us(48);
    #else
      timerlong = micros();
      while(micros()-timerlong < 48) {
      } //52us
    #endif
    
      //Cn2_Int_SendByte1:
    #ifdef usbhid
      TCCR1A = 0; //start TIMER1
      TCCR1B = (1 << CS10); //NO prescaling!
      TCNT1 = 0;  //reset count
      while(TCNT1 < (uint16_t)((F_CPU/1000000)*104)) {
    #else
      timerlong = micros();
      while(micros()-timerlong < 104) {  //108 us
    #endif
        if ((digitalRead(TIring)<<1 | digitalRead(TItip)) != 0x03)
          goto cn2_sendbyte_collide;
      }
    
      //Cn2_Int_SendByte2:
      pinMode(TIring, OUTPUT);           // set pin to output
      digitalWrite(TIring, LOW);
      pinMode(TItip, OUTPUT);            // set pin to output
      digitalWrite(TItip, LOW);
    #ifdef usbhid
      _delay_us(52);
    #else
      timerlong = micros();
      while(micros()-timerlong < 52) {
      } //52us
    #endif
      digitalWrite(CN2clock, HIGH);
      digitalWrite(CN2data, HIGH);
    #ifdef usbhid
      _delay_us(43);
    #else
      timerlong = micros();
      while(micros()-timerlong < 43) {
      } //43us
#endif
    
    for(loopcntr=0; loopcntr<8; loopcntr++) {
        digitalWrite(CN2data, (outbyte&0x01));
        outbyte>>=1;
        digitalWrite(CN2clock, HIGH);
#ifdef usbhid
        _delay_us(17);
#else
        timerlong = micros();
        while(micros()-timerlong < 17) {
        } //52us
#endif
        digitalWrite(CN2clock, LOW);
#ifdef usbhid
        _delay_us(35);
#else
        timerlong = micros();
        while(micros()-timerlong < 35) {
        } //52us
#endif
        digitalWrite(CN2clock, HIGH);
        digitalWrite(CN2data, HIGH);
#ifdef usbhid
        _delay_us(52);
#else
        timerlong = micros();
        while(micros()-timerlong < 52) {
        } //52us
#endif
    }
    return 0;
    
cn2_sendbyte_collide:
    pinMode(TIring, OUTPUT);           // set pin to output
    pinMode(TItip, OUTPUT);            // set pin to output
    
#ifdef usbhid
    TCCR1A = 0; //start TIMER1
    TCCR1B = (1 << CS10); //NO prescaling!
    TCNT1 = 0;  //reset count
    while(TCNT1 < (uint16_t)((F_CPU/1000000)*665)) {
#else
    timerlong = micros();
    while(micros()-timerlong < 665) {
#endif
        digitalWrite(CN2clock, LOW);
        digitalWrite(CN2data, HIGH);
    }
    digitalWrite(CN2clock, HIGH);
    digitalWrite(CN2data, HIGH);
    return -1;
}
    
static uint16_t cn2_recbyte() {
    int i;
    int loopcntr;
    uint8_t inbyte;
    
    resetLines();
    i=0;
    //Cn2_Int_GetByte1:
    while(((digitalRead(TIring)<<1 | digitalRead(TItip)) != 0x00) && i<CN2_GETBYTE1_TIMEOUT) i++;
    if (i>=CN2_GETBYTE1_TIMEOUT) return -99;
    //Cn2_Int_GetByte2:
    
    i=0;
    //Cn2_Int_GetByte3:
    while(((digitalRead(TIring)<<1 | digitalRead(TItip)) != 0x03) && i<CN2_GETBYTE3_TIMEOUT) i++;
    if (i>=CN2_GETBYTE3_TIMEOUT) return -1;
    //Cn2_Int_GetByte4:
    
    inbyte=0;
    loopcntr=0;
    //Cn2_Int_GetByte5:
    while(loopcntr<8 && i<CN2_GETBYTE5_TIMEOUT) {
        i=0;
        while((digitalRead(CN2clock) != 0) && i<CN2_GETBYTE5_TIMEOUT) i++;
        if (i>=CN2_GETBYTE5_TIMEOUT) return -1;
        inbyte |= digitalRead(CN2data);
        if (loopcntr != 7) inbyte <<= 1;
        
        i=0;
        while((digitalRead(CN2clock) != 1) && i<CN2_GETBYTE5_TIMEOUT) i++;
        loopcntr++;
    }
    if (i>=CN2_GETBYTE5_TIMEOUT) return -1;
    return inbyte;
}
    
#ifdef usbhid
#include "gcnbridge2_usb.cpp.inc"
#endif

#ifdef sparkcore
void connectMetahub(void) {
    if (client.connected())
        return;
    
    if (!WiFi.ready()) {
        Serial.println("Connecting to WiFi");
        if (WiFi.connecting())
            return;                     // Wait for it to connect
        if (!WiFi.hasCredentials()) {     // Wait for credentials
            Serial.println("No credentials");
            return;
        }
        Serial.println("Starting connect.");
        WiFi.connect();
        return;                         // We'll get back here eventually
    }
    
    if (!client.connect(server_host, server_port)) {
        Serial.write("Failed to connect.\n");
        return;
    }
    
    // Connected! Introduce ourselves.
    // Construct join message
    int local_len = strlen(localhub);
    int remote_len = strlen(remotehub);
    int msg_len = local_len + remote_len + 2;
    msg_buf[0] = msg_len;
    msg_buf[1] = 0;
    msg_buf[2] = 'j';
    msg_buf[3] = remote_len;
    memcpy(msg_buf + 4, remotehub, remote_len);
    msg_buf[4 + remote_len] = local_len;
    memcpy(msg_buf + 5 + remote_len, localhub, local_len);
    msg_len += 3;       // Size word and type byte
    
    // Send join message
    if (msg_len != client.write(msg_buf, msg_len)) {
        client.stop();
        return;
    }
    Serial.write("Connected as ");
    Serial.write(localhub);
    Serial.write(" to ");
    Serial.write(remotehub);
    Serial.write('\n');
}

void setRGBLED(uint8_t mask, uint8_t state) {
    uint8_t rgbledmask_old = rgbledmask;
    if (state) {
        rgbledmask |= mask;
    } else {
        rgbledmask &= (~mask);
    }
    if (rgbledmask_old == 0 && rgbledmask != 0) {
        RGB.control(true);
    }
    if (rgbledmask_old != 0 && rgbledmask == 0) {
        RGB.control(false);
    }
    if (rgbledmask != 0) {
        RGB.color(
            (rgbledmask & ledr)?255:0,
            (rgbledmask & ledg)?255:0,
            (rgbledmask & ledb)?255:0
        );
    }
    return;
}

void sparkProcessCommand(void) {
    int i;

    if (((msg_buf[16] << 8) | msg_buf[15]) < 3) {
        return;                         // Too short to hold 3-byte Cn2BASIC header
    }
    if (msg_buf[17] != 0x04) {          // tString
        return;                         // Invalid header byte
    }
    int str_len = (msg_buf[19] << 8) | msg_buf[18];
#ifdef sparkdebug
    RGB.control(false);
    Serial.print("Processing command with length ");
    Serial.println(str_len, HEX);
    Serial.flush();
#endif
    if (str_len < 0 || str_len > 252) {
        return;                         // Invalid length
    }
#ifdef sparkdebug
    Serial.print("Processing command type ");
    Serial.println(msg_buf[20], HEX);
    Serial.flush();
#endif
    switch(msg_buf[20]) {               // Type of message
        case 'C': {
            // Swap sender and recipient addresses
            for(int i = 0; i < 5; i++) {
                sender[i] = msg_buf[5 + i];
                recipient[i] = msg_buf[10 + i];
            }
            str_len = 0;
            data[0] = 0x04;     // tString
            
            // Store local hub name into the string
            int llen = strlen(localhub);
            data[3] = llen;
            str_len++;
            for(int i=0; i < llen; i++) {
                if (localhub[i] >= 'a' && localhub[i] <= 'z') {
                    // Translate lowercase letter
                    data[3 + str_len++] = 0xbb;
                    data[3 + str_len++] = 0xb0+(localhub[i]-'a')+(localhub[i]>='l');
                } else {
                    data[3 + str_len++] = localhub[i];
                }
            }
            // Store remote hub name into the string
            int rlen = strlen(remotehub);
            data[3 + str_len] = rlen;
            str_len++;
            for(int i=0; i < rlen; i++) {
                if (remotehub[i] >= 'a' && remotehub[i] <= 'z') {
                    // Translate lowercase letter
                    data[3 + str_len++] = 0xbb;
                    data[3 + str_len++] = 0xb0+(remotehub[i]-'a')+(remotehub[i]>='l');
                } else {
                    data[3 + str_len++] = remotehub[i];
                }
            }

            data[1] = (str_len & 0x0ff);
            data[2] = (str_len >> 8);
            str_len += 3;
            datasizeptr[0] = (str_len & 0x0ff);
            datasizeptr[1] = (str_len >> 8);

            int retries = 0, rval;
            do {
                setRGBLED(ledr, HIGH);
                rval = cn2_send();
                if (rval != 0) {
                    setRGBLED(ledr, LOW);
                    if (rval == -99) setRGBLED(ledg, HIGH);
                    delay(100);
                    retries++;
                }
            } while (rval != 0 && retries < CN2_MAX_FRAME_RETRIES);
            return;
        }
            break;

        case 'W': {                     // WiFi credentials
            int type, SSIDlen, PWDlen, base;
            char ssid[64];
            char pwd[64];
            type = msg_buf[21];
            SSIDlen = msg_buf[22];

            int offset = 23;
            int j = 0;
#ifdef sparkdebug
            Serial.print("Copying SSID, length ");
            Serial.println(SSIDlen);
            Serial.flush();
#endif
            for(base = offset; j < SSIDlen; ) {
                int val = msg_buf[offset++];
                if (val == 0xbb) {
                    val = 'a' + (msg_buf[offset++] - 0xb0);
                    val -= (val > 'k');
                }
                ssid[j++] = val;
            }
            ssid[j] = '\0';
            PWDlen = msg_buf[offset++];
#ifdef sparkdebug
            Serial.print("Copying pass, length ");
            Serial.println(PWDlen);
            Serial.flush();
#endif
            for(j = 0, base = offset; j < PWDlen;) {
                int val = msg_buf[offset++];
                if (val == 0xbb) {
                    val = 'a' + (msg_buf[offset++] - 0xb0);
                    val -= (val > 'k');
                }
                pwd[j++] = val;
            }
            pwd[j] = '\0';

#ifdef sparkdebug
            Serial.print("Setting new credentials: SSID = '");
            Serial.print(ssid);
            Serial.print("', pass='");
            Serial.print(pwd);
            Serial.print("', type=");
            Serial.println(type);
            Serial.flush();
#endif
            if (!WiFi.clearCredentials()) {
#ifdef sparkdebug
                Serial.println("Failed to clear existing credentials!");
#endif
                return;
            }
            switch(type) {
                case 0:     // Open
                    WiFi.setCredentials(ssid);
                    break;
                case 1:     // WEP
                    WiFi.setCredentials(ssid, pwd, WEP);
                    break;
                case 2:     // WPA
                    WiFi.setCredentials(ssid, pwd, WPA);
                    break;
                case 3:
                    WiFi.setCredentials(ssid, pwd, WPA2);
                    break;
                default:
                    return;     // Invalid
            }
#ifdef sparkdebug
            if (WiFi.hasCredentials()) {
                Serial.println("HasCredentials() reported true after set.");
                Serial.flush();
            }
            Serial.print("New credentials saved.");
            Serial.flush();
#endif
        }
            break;
        case 'L': {                     // Local hub name
            int j = 0;
            for(int i = 0; i < (str_len - 1); ) {
                int val = msg_buf[21 + i++];
                if (val == 0xbb) {
                    val = 'a' + (msg_buf[21 + i++] - 0xb0);
                    val -= (val > 'k');
                }
                EEPROM.write(EEPROM_LOCALHUB_OFFSET + j++, val);
            }
            EEPROM.write(EEPROM_LOCALHUB_OFFSET + j++, 0);            // Null terminator
            EEPROM.write(EEPROM_MAGIC_OFFSETL, EEPROM_MAGIC);
            copyHubsToRAM();
        }
            break;
        case 'R': {                     // Remote hub name
            int j = 0;
            for(int i = 0; i < (str_len - 1); ) {
                int val = msg_buf[21 + i++];
                if (val == 0xbb) {
                    val = 'a' + (msg_buf[21 + i++] - 0xb0);
                    val -= (val > 'k');
                }
                EEPROM.write(EEPROM_REMOTEHUB_OFFSET + j++, val);
            }
            EEPROM.write(EEPROM_REMOTEHUB_OFFSET + j++, 0);            // Null terminator
            EEPROM.write(EEPROM_MAGIC_OFFSETR, EEPROM_MAGIC);
            copyHubsToRAM();
        }
            break;
        default:
            return;                     // Nothing doing
    }
    if (client.connected()) {
        client.stop();
    }
    Spark.sleep(SLEEP_MODE_DEEP, 1);    // Reboot the Spark Core after one second
}

void copyHubsToRAM(void) {
    for(int i=0; i < 17; i++) {
        localhub[i] = EEPROM.read(EEPROM_LOCALHUB_OFFSET + i);
    }
    for(int i=0; i < 17; i++) {
        remotehub[i] = EEPROM.read(EEPROM_REMOTEHUB_OFFSET + i);
    }
    return;
}
#endif

