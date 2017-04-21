#!/usr/bin/python
# -*- coding: UTF-8 -*-

'''Datalogger
Parse logged data from file or GMC-320 geiger counter.

Examples:
gmcparse.py:                      read USB/serial and print 50 lines of parsed data to screen
gmcparse.py -o file1 -d file2:    pretty print to file1, dump binary to file2
gmcparse.py -f >file3:            full output to file3


Usage:
  gmcparse.py [options] 
  
Options:
  -i FILE, --input FILE    Binary input file (GMC Dump), otherwise via USB/serial
  -o FILE, --output FILE   Pretty output file (time stamp : count rate)
  -d FILE, --dump FILE     Save hex dump, previously loaded via USB/serial
  -v, --verbose            Print more details
  -f, --full               Print all, ie time stamp, location string, changes of recording modes. Use ">file" to save data 
  -h --help                Show help 
  -g --debug               Debug mode
  
'''

# References:
# gq: https://sourceforge.net/projects/gqgmc/files/gqgmc/ ICD and others
# ullix: https://sourceforge.net/projects/geigerlog/ Python routines

# versions:
# vers 2017-02-24b: pointer control removed (it gave wrong reading for last values)
#    unsolved: what happens if data ends with 55  AA  00? Then pointer will check ahead bytes which are missing.


# remarks:
# Like in a web browser try to avoit error messages by assumptions.
# Predefined time string in case the right one is not found in the beginning of data.
# Take care if __doc__ string is changed. Its structure determines variables.



from docopt import docopt
import datetime
import struct
import time
import serial       # the communication with the serial port


vers="GMCparse 2017-02-24b"
device="GMC-320"
verbose=1 
debug=0
limitlines=80  # limit output lines to screen if not verbose

def stime():
    """Return current time as YYYY-MM-DD HH:MM:SS"""
    # by ullix; 
    # not used here, instead: atetime.datetime.now()
    return time.strftime("%Y-%m-%d %H:%M:%S")


def getVER(ser):
    # Get hardware model and version
    # send <GETVER>> and read 14 bytes
    # returns total of 14 bytes ASCII chars from GQ GMC unit.
    # includes 7 bytes hardware model and 7 bytes firmware version.
    # e.g.: GMC-300Re 4.20
    # (ullix)
    rec = serialCOMM(ser, b'<GETVER>>', 14, False) # returns ASCII string
    return rec
    
    
def getDate(ser):
    """ get device date
    """
    # send <GETDATETIME>> and read 7 bytes
    # returns [YY][MM][DD][hh][mm][ss][AA]

    rec = serialCOMM(ser, b'<GETDATETIME>>', 7, False) 
    dsb = [ord(i) for i in rec[:6]]
    dsb[0] +=2000
    return datetime.datetime(*dsb)


def getSPIR(ser, address = 0, datalength = 4096):
    # by ullix
    # Request history data from internal flash memory
    # Command:  <SPIR[A2][A1][A0][L1][L0]>>
    # A2,A1,A0 are three bytes address data, from MSB to LSB.
    # The L1,L0 are the data length requested.
    # L1 is high byte of 16 bit integer and L0 is low byte.
    # The length normally not exceed 4096 bytes in each request.
    # Return: The history data in raw byte array.
    # Comment: The minimum address is 0, and maximum address value is
    # the size of the flash memory of the GQ GMC Geiger count. Check the
    # user manual for particular model flash size.
    # (ullix)

    # address must not exceed 2^(3*8) = 16 777 215 because high byte
    # is clipped off and only lower 3 bytes are used here
    # (but device address is limited to 2^20 - 1 = 1 048 575 = "1M"
    # anyway, or even only 2^16 - 1 = 65 535 = "64K" !)
    
    # datalength must not exceed 2^16 = 65536 or python conversion
    # fails with error; should be less than 4096 anyway

    # device delivers [(datalength modulo 4096) + 1] bytes,
    # e.g. with datalength = 4128 (= 4096 + 32 = 0x0fff + 0x0020)
    # it returns: (4128 modulo 4096) + 1 = 32 + 1 = 33 bytes

    # This contains a WORKAROUND:
    # it asks for only (datalength - 1) bytes,
    # but then reads one more byte, so the original datalength

    # pack address into 4 bytes, big endian; then clip 1st byte = high byte!   
    ad = struct.pack(">I", address)[1:] 
    if debug:
        print "SPIR address:\t\t\t{:5d}, hex chars in SPIR command: {:02x} {:02x} {:02x}".format(address, ord(ad[0]), ord(ad[1]), ord(ad[2]))

    # pack datalength into 2 bytes, big endian; use all bytes
    dl = struct.pack(">H", datalength-1)  
    if debug:
        print "SPIR datalength requested:\t{:5d}, hex chars in SPIR command: {:02x} {:02x}".format(datalength, ord(dl[0]), ord(dl[1]))

    # returns string of characters with each chr-value from 0...255
    # NOT converted into list of int
    rec = serialCOMM(ser, b'<SPIR'+ad+dl+'>>', datalength, False) 
    if debug:
        print "SPIR datalength received:\t{:5d},".format(len(rec)), type(rec)
    
    return rec

    
def serialCOMM(ser, sendtxt, returnlength, byteformat = True):
    # write to and read from serial port
    # exit on comm error
    # if byteformat is True, then convert received string to list of int
    # (ullix)
    
    try:
        ser.write(sendtxt)
    except:        
        print "\nERROR in Serial Write", sys.exc_info()
        ser.close()
        sys.exit(1)

    try:
        rec = ser.read(returnlength)
    except:
        print "\nERROR in Serial Read", sys.exc_info()
        ser.close()
        sys.exit(1)

    if byteformat: rec = map(ord,rec) # convert string to list of int
    
    return rec
    
def readHIST():
    """Read history data from device
    """
    # (ullix and mod)
    
    allspir =""
    # read data from device
    for chunk in range(0, 16): # all 64k data
    #for chunk in range(0, 1):   # only first 4096 bytes
        time.sleep(0.5)         # fails occasionally to read all data
                                # when sleep is too short
        allspir += getSPIR(ser, chunk * 4096 , 4096)
        if (ord(allspir[-1])== 0xff) and  (ord(allspir[-2]) == 0xff) and (ord(allspir[-3])== 0xff):
            if verbose:
                print "Device memory: {:02d} pages (4096 each) out of 16 read".format(chunk+1)
            break
    if verbose:
        print "SPIR datalength combined:\t{:5d},".format(len(allspir)), type(allspir)
    #print "last bytes: {:0X} {:0X} {:0X}".format(ord(allspir[-1]), ord(allspir[-2]), ord(allspir[-3]))

    # remove all trailing 0xff (= missing data at the end)
    allspir = allspir.rstrip(chr(0xff)) 
    l = len(allspir)
    if debug:
        print "SPIR all 0xff removed:{:5d},".format(l), type(allspir)
        
    return allspir
        
'''           
    binfile = open(binpath, "w")     # writing trailed data
    binfile.write(allspir)
    binfile.close


    print "The history data are :   \t(Format: dec byte_number: hex value=dec value)"
    allspirInt = map(ord, allspir)  # convert to list of int
    lstfile = open(lstpath, "w")
    for i in range(0, l, 10):
        lstvalueline =""
        for j in range(0,10):
            k  = i + j
            if k >= l: break
            lstvalue = "%5d: %02x=%3d  " % (k, allspirInt[k], allspirInt[k])
            lstvalueline += lstvalue

        lstfile.write(lstvalueline + "\n")
        if i < 55: print "\t\t\t\t", lstvalueline        
    print "\t\t\t\tand more ...\n"

    lstfile.close
'''




def analyse(data, fn):
    """
    Parse data

    Format:

    0) data count: one (char) byte

    1) time: time date marker (12 bytes long): 
    55  AA  00  11  02  0E  15  14  0C  55  AA  02  
    id1 id2 id3 yy  mm  dd  hh  mm  ss  id3 id4 id_cpm
    id_cpm: 0,1,2,3: off, cps, cpm, cpm one per hour

    2) two byte data count: 
    55 AA 01 DH DL

    3) String:
    55 AA 02 str_length chr1 chr2 ...
    """

    idcpm=2 # id_cpm 
    tick= datetime.timedelta(minutes=1)
    dp=0    # data pointer
    ccount=0  # counted events; <0 if no counter value found but date or other control value

    datenow= datetime.datetime(1950,01,22, 11,12, 13)  #  arabitrary time as init value (< 2000)
    
    if fn:
        f=open(fn,"w")

    while dp<len(data):
        
        # test whether data is counter value
        ccount=ord(data[dp])
        if (ord(data[dp])==0x55) and (ord(data[dp+1])==0xaa):
            if ord(data[dp+2])==0x00:
                    
                # date + time found (very likely)
                if (ord(data[dp+9])==0x55) and (ord(data[dp+10])==0xaa):
                    if ord(data[dp+11])<4:
                        if ord(data[dp+11]) != idcpm:
                            idcpm= ord(data[dp+11]) 
                            if verbose:
                                print "* Time interval changed (0: off, 1: sec, 2: min, 3: hour): {:0d}".format(idcpm)
                            # define time interval
                            if idcpm == 2:
                                tick= datetime.timedelta(minutes=1)
                            elif idcpm == 1:
                                tick=  datetime.timedelta(seconds=1)
                            elif idcpm == 3:
                                tick = datetime.timedelta(minutes=60)
                            elif idcpm == 0:
                                if verbose:
                                    print "time interval off"
                                    tick = datetime.timedelta(minutes=0)
                            else: 
                                # should not happen
                                if verbose:
                                    print "Undefined history interval; should be 0,1,2,3; found: {:2d}".format( ord(data[dp+11]) )
                                    print "{:0X}{:0X}{:0X}".format(ord(data[dp+9]), ord(data[dp+10]), ord(data[dp+11]) )
                    #print "*", ord(data[dp+11])
                    ds = data[dp+3:dp+9]
                    dsb = [ord(i) for i in ds]
                    dsb[0] +=2000
                    datenow=datetime.datetime(*dsb)
                    if verbose:
                        print "* Time tag found: {:%Y-%m-%d %H:%M:%S} {:d}".format(datenow, idcpm)
                    ccount=-1
                    # next value: 11 + 1=12; additional single incremented below
                    dp += 11
                else:
                    if verbose:
                        print "No date/time endmarker found; treat markers as counting data"
                    
            # double byte found
            elif ord(data[dp+2])==1:
                # double byte found
                ccount = struct.unpack('>H',data[dp+3]+data[dp+4])[0]
                #print "***", ord(data[dp+2]), ord(data[dp+3]), ord(data[dp+4]), ord(data[dp+5]), getnumber, '***'
                #print ccount, "****",
                #next value: 4+1=5; additional single incremented below
                dp +=4
                        
            # string found
            elif ord(data[dp+2])==2:
                # ascii string found
                strgl=ord(data[dp+3])
                strg=data[dp+4:dp+4+strgl]
                if verbose:
                    print "* Tag found: {:s}".format(strg)
                ccount=-1
                #additional single incremented below
                dp = dp+3+strgl


        #print " {:02X}".format(ord(data[dp])),   
        if ccount>= 0:
            #print "{:02X}".format(ccount),

            #print datenow , ccount
            sp="{:%Y-%m-%d %H:%M:%S} {:5d}".format(datenow, ccount)
            
            # print only a few lines to screen
            if fullout or (dp<limitlines):
                print sp
            if fn:
                f.write(sp+ "\n")
                
            datenow += tick

        dp += 1
        if dp>65536:
            print "Invalid data file (> 16 * 4096)"
            exit(1)
    if datenow.year<2000:
        print "No date/time tag found. Valid data?"
    if fn:
        f.close()
        
        
                        
# fn="d1sstrng.bin" #testdata like d1s.bin, but string inserted at 19:07
#fn="d1s.bin" #testdata (flight cologne <-> Hamburg) 
#fn="d2b.bin"



def main(argv=None):
    global ser
    
    if verbose:
        print "\nGeiger counter: ", device
        print "Software version: ", vers
    
    # get raw data from file or device        
    if inputfile:
        with open(inputfile, mode='rb') as file:  
            data = file.read()  
        print len(data)
    else:
        # no input file given, try serial connection
            
        # open the serial port with baudrate 115200, timeout 3 sec
        # NOTE: baud rate must be set at device first, default is 57600
        ser = serial.Serial('/dev/ttyUSB0', 115200, timeout= 3)
        if verbose:
            if not fullout:
                print "Use -f in order to get all data."
                print "Redirect to file (>file) because the screen can not keep them all.\n"
            print "Serial port: ", ser.name
            print "Settings: \t\t", ser
            # expected output: open=True>(port='/dev/gqgmc', baudrate=115200, bytesize=8, parity='N', stopbits=1, timeout=1, xonxoff=False, rtscts=False, dsrdtr=False)
            # print the firmware version number
            print "The firmware version is : \t",       getVER(ser)
        print "GMC device date:", getDate(ser)
        print "(interface date: {:%Y-%m-%d %H:%M:%S})".format(datetime.datetime.now())
        print ''
        
        
        #fn = "e4.bin"
        #fn = "f3.bin"
        
        data = readHIST()
        if dumpfile:
            with open(dumpfile, mode='wb') as file:
                file.write(data)


    print "Number of data points: ", len(data)
    print " "
    
    
    analyse(data, outputfile)


if __name__ == "__main__":
    '''
    {'--dump': None,
     '--help': False,
     '--input': None,
     '--output': None,
     '--verbose': False,
     '--version': False}
    '''
    
    arguments = docopt(__doc__)
    if debug:
        print(arguments)

    dumpfile=arguments['--dump']
    inputfile=arguments['--input']
    outputfile=arguments['--output']
    verbose=arguments['--verbose']  
    debug=arguments['--debug']  
    fullout=arguments['--full']
    
    main()
    

