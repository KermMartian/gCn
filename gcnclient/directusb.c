
#include <errno.h>
#if not(defined(ETIMEDOUT))
#define ETIMEDOUT 116
#endif
#include <signal.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

//#include <usb.h>

typedef enum 
{
	PID_UNKNOWN		= 0,
	PID_TIGLUSB     = 0xE001,
	PID_TI89TM		= 0xE004,
	PID_TI84P		= 0xE003,
	PID_TI84P_SE    = 0xE008,
	PID_NSPIRE      = 0xE012,
} UsbPid;

#define VID_TI    0x0451
extern int verbose;

//static struct usb_device *device = NULL;
static int inEP = 0x81;
static int outEP = 0x02;


int open_ti_usb(usb_dev_handle* &device)
{
    struct usb_bus    *bus;
    struct usb_device *dev;
    int r;
    static int didUsbInit = 0;
 
    if(!didUsbInit){
        usb_init();
        didUsbInit = 1;
    }
    usb_find_busses();
    usb_find_devices();
 
    r = 0;
 
    /* loop taken from testlibusb.c */
	device = NULL;
    for (bus = usb_busses; bus; bus = bus->next)
    {
		for (dev = bus->devices; dev; dev = dev->next)
		{
		    if ((dev->descriptor.idVendor == VID_TI))
		    {
			    if((dev->descriptor.idProduct == PID_TI84P)||(dev->descriptor.idProduct == PID_TI84P_SE))
			    {
					device = usb_open(dev);
					if (device==NULL) {
						return -2;
					}
					break;
			    }
			}
		}
		if (device != NULL)
			break;
    }
 
    if (!r && device == NULL) {
		r = -1;
		goto out;
	}
 
	r = usb_set_configuration(device, 1);
	if (r < 0)
	{
	     printf("usb_set_configuration (%s).\n", usb_strerror());
	     goto out;
	}
	r = usb_claim_interface(device, 0);
	if (r < 0) {
		fprintf(stderr, "usb_claim_interface error %s\n", usb_strerror());
		goto out;
	}
 
out:
    return r;
}

void close_ti_device(usb_dev_handle *device)
{
    if(device != NULL)
    {
        usb_release_interface(device, 0);
        usb_close((usb_dev_handle *)device);
        mymillisleep(1000);
    }
}

int send_ti_buffer(usb_dev_handle *device, char *buffer, int len){
	int bytesSent;
	int ret = usb_bulk_write(device, outEP, buffer, len, 5000);
	if (ret != len) {
		fprintf(stderr, "usb_bulk_write (%s).\n", usb_strerror());
		return ret;
	}
	return 0;
}

int recv_ti_buffer(usb_dev_handle *device, char* buffer, int len){
	int ret = 0;
		
	ret = usb_bulk_read(device, inEP, buffer, len, 500);
	
	if (ret > 0 && verbose) {
		fprintf(stdout,"Received %d bytes\n",ret);
		for(int i=0;i<ret;i++)
			printf("%02X ",(unsigned int) buffer[i]);
		printf("\n");
	}
	if(ret < 0 && ret != -ETIMEDOUT) {
		if (verbose)
           fprintf(stderr, "usb_bulk_read %d (%s).\n", ret, usb_strerror());
		device = NULL;
		return ret;
	}
	
	if (ret == -116)
		return 0;
	return ret;
}

