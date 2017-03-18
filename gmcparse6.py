#!/usr/bin/python
# -*- coding: UTF-8 -*-


# References:
# gq: https://sourceforge.net/projects/gqgmc/files/gqgmc/ ICD and others
# ullix: https://sourceforge.net/projects/geigerlog/ Python routines

# versions:
# vers 2017-03: modified as library for GUI 

import datetime
import struct
import time
import serial       


vers="GMCparse 2017-03-17"
device="GMC-320"
#verbose=1
debug=0
limitlines=80  # limit output lines to screen if not verbose
fullout=True


def getVER(ser):
    # Get hardware model and version
    # send <GETVER>> and read 14 bytes
    # returns total of 14 bytes ASCII chars from GQ GMC unit.
    # includes 7 bytes hardware model and 7 bytes firmware version.
    # e.g.: GMC-300Re 4.20
    # (ullix)
    rec = serialCOMM(ser, b'<GETVER>>', 14, False) # returns ASCII string
    return rec
    
    
def getCPM(ser): 
    # get CPM from device
    ser.write(b'<GETCPM>>')
    rec = ser.read(2)
    try:
        s1= ord(rec[0])<< 8 | ord(rec[1])
    except IndexError:
        s1= ord("\x00")
    return s1
    
    
def getDate(ser):
    """ get device date
    """
    rec = serialCOMM(ser, b'<GETDATETIME>>', 7, False) 
    dsb = [ord(i) for i in rec[:6]]
    dsb[0] +=2000
    return datetime.datetime(*dsb).strftime("%Y-%m-%d %H:%M:%S")


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
  
    
def readHIST(ser):
    """Read history data from device
    """
    # (ullix and mod)
    
    verbose=""
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
        

def analyse(form, data, fn, verbose=True):
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
    msgv='' #verbose message
    msge='' #error message
    fullout=False
    limitlines=30

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
                                msgv= "* Time intv. mod. (0: off, 1: sec, 2: min, 3: hour): {:0d}".format(idcpm)
                            # define time interval
                            if idcpm == 2:
                                tick= datetime.timedelta(minutes=1)
                            elif idcpm == 1:
                                tick=  datetime.timedelta(seconds=1)
                            elif idcpm == 3:
                                tick = datetime.timedelta(minutes=60)
                            elif idcpm == 0:
                                if verbose:
                                    print "Time interval off"
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
                        msgv= "* {:%Y-%m-%d %H:%M:%S} Dev. Timetag;  {:d}".format(datenow, idcpm)
                    ccount=-1
                    # next value: 11 + 1=12; additional single incremented below
                    dp += 11
                else:
                    if verbose:
                        #should not happen
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
                    msgv= "* ID tag: {:s}".format(strg)
                ccount=-1
                #additional single incremented below
                dp = dp+3+strgl

        #print " {:02X}".format(ord(data[dp])),   
        
        ##prepare output
        if ccount>= 0:
            #print "{:02X}".format(ccount),

            #print datenow , ccount
            sp="{:%Y-%m-%d %H:%M:%S} {:5d}".format(datenow, ccount)
            
            # print only a few lines to screen
            #if fullout or (dp<limitlines):

            # print only a few lines to screen
            if fullout or (dp<limitlines):
                print sp
            form.writeplain(sp)
            if fn:
                f.write(sp+ "\n")
            datenow += tick
        else:
            if verbose:
                #** print data **
                print msgv
                form.writeplain(msgv)
                if fn:
                    f.write(msgv+"\n")     
        dp += 1
        if dp>65536:
            msge= "Invalid data file (> 16 * 4096)"
            exit(1)
    if datenow.year<2000:
        msge = "No date/time tag found. Valid data?"
    if fn:
        f.close()
    form.writeplain("*** done ***")
    print msge
    return(msge)
        
