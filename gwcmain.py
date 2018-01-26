#!/usr/bin/python
# -*- coding: utf-8 -*-s


"""
Read and process history data recorded by Geiger Counter GMC-3xx

Vers 0.7, 2017-03-17 (rimbus)

Software may be free to use according to GPL3
https://www.gnu.org/licenses/gpl-3.0.de.html 
"""


from PyQt4 import QtGui  
import sys  # required for argv to QApplication
import gwcp3  # GUI layout file. Created by: pyuic4 gwcp3.ui >gwcp3.py
from gmcparse6 import *  # basic I/O routines
import os  # directory methods
import time
import serial


class GmcApp(QtGui.QMainWindow, gwcp3.Ui_MainWindow):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.setupUi(self)  # automatically created in gwcp
        
        # define some global variables (might be improved later)
        self.helptextname = "help.md"
        self.data = ''
        self.ser = None
        serialdev = '/dev/ttyUSB0'
        # self.speed = 115200
        self.speedid = 1
        #ser = serial.Serial('/dev/ttyUSB0', 115200, timeout= 3)
        
        self.statusBar().showMessage("...") 
        
        self.menuFile.triggered[QtGui.QAction].connect(self.windowaction)
        self.menuHelp.triggered[QtGui.QAction].connect(self.windowaction)
        self.radioButtonCSV.setChecked(True)
        
        # preselect baud rate
        self.listWidgetspeed.setCurrentRow(self.speedid)
        self.speed = int(self.listWidgetspeed.currentItem().text())
        self.lineEditsetDev.setText(serialdev)
        
        # load bin file
        self.pushButtonLoadBin.clicked.connect(self.readbinfile)
        
        # load data from device
        self.pushButtonLoadDevice.clicked.connect(self.readdev)
        
        # check serial
        self.pushButtonSerialSet.clicked.connect(self.checkserial)
        
        # process data
        self.pushButton.clicked.connect(self.processdata)
        
        # write data
        self.pushButtonwritedata.clicked.connect(self.writedatafile)
        
        # time info
        self.pushButtongetTime.clicked.connect(self.timeinfo)

        # set device time to system time
        self.pushButtonsetTime.clicked.connect(self.setdevicetime)
        
        # live data
        self.pushButtonLiveData.setCheckable(True)
        # self.pushButtonLiveData.setChecked(False)
        self.pushButtonLiveData.clicked.connect(self.livedata)
        
    # menubar
    def windowaction(self, q):
        print "triggered by menubar", q.text()
        if q.text() == "&Quit":
            sys.exit()
        elif q.text() == "Show Helpfile":
            with open(self.helptextname, mode='rb') as f:
                helptext = f.read()
            self.clearplain()
            self.writeplain(helptext)

    def readbinfile(self):
        fname = QtGui.QFileDialog.getOpenFileName(self, 'Open file', '', "Data files (*.*)")
        with open(fname, mode='rb') as f:
            self.data = f.read()
        msg = "{:d} bytes loaded from {:s}".format(len(self.data), fname)
        self.statusBar().showMessage(msg) 
        self.processdata()

    def readdev(self):
        # ser not defined in init in order to process files even if no device connected
        if not self.ser:
            # print "set ser"
            # ser = serial.Serial('/dev/ttyUSB0', 115200, timeout= 3)
            self.serialdev = str(self.lineEditsetDev.text())
            self.speed = int(self.listWidgetspeed.currentItem().text())
            self.ser = serial.Serial(self.serialdev, self.speed, timeout=3)
        self.statusBar().clear()
        self.statusBar().showMessage("loading...") 
        print "loading..."
        self.data = readHIST(self.ser)
        msg = "{:d} bytes read from device".format(len(self.data))
        self.statusBar().showMessage(msg) 
        self.processdata()

    def checkserial(self):
        self.check_serial()
        msg = "Serial interface: {:s} at {:d} baud".format(self.serialdev, self.speed)
        self.statusBar().showMessage(msg)

    def writedatafile(self):
        if len(self.data) > 1:
            fn = QtGui.QFileDialog.getSaveFileName(self, "Save file", "", "*.*")
            if self.radioButtonBin.isChecked():
                print "binary choosen"
                with open(fn, mode='wb') as f:
                    f.write(self.data)
                msgs = "{:d} bytes saved to {:s}".format(len(self.data), fn)
            else:
                analyse(self, self.data, fn, self.checkBox.isChecked())
                msgs = "{:d} bytes converted and saved to {:s}".format(len(self.data), fn)
        else:
            msgs = "No data to save"
        self.statusBar().showMessage(msgs)

    # process data
    def processdata(self):
        self.plainTextEdit.clear()
        msgs = analyse(self, self.data, '', self.checkBox.isChecked())
        if msgs:
            self.plainTextEdit.appendPlainText(msgs)
            self.statusBar().showMessage("Valid data?")
        else:
            pass
            # self.statusBar().showMessage("done")

    def timeinfo(self):
        self.check_serial()
        dtime = getDate(self.ser)
        stime = "{:%Y-%m-%d %H:%M:%S}".format(datetime.datetime.now())
        print "GMC device date:", dtime
        print "(interface date: ", stime
        self.lineEditgetTime.setText(dtime)
        self.lineEditSystemTime.setText(stime)

    def setdevicetime(self):
        self.check_serial()
        nowtime = datetime.datetime.now()
        stime = "{:%Y-%m-%d %H:%M:%S}".format(nowtime)
        print "(interface date: ", stime
        self.lineEditSystemTime.setText(stime)
        setDate(self.ser, nowtime)

    def check_serial(self):
        if not self.ser:
            self.serialdev = str(self.lineEditsetDev.text())
            self.speed = int(self.listWidgetspeed.currentItem().text())
            self.ser = serial.Serial(self.serialdev, self.speed, timeout=3)

    # requires pushButtonLiveData
    def livedata(self):
        self.check_serial()
        if self.pushButtonLiveData.isChecked():
            self.writeplain("* Live data:")
            self.pushButtonLiveData.setStyleSheet("background-color: red")
        else:
            self.pushButtonLiveData.setStyleSheet("background-color: none")
        ta = ''
        while self.pushButtonLiveData.isChecked():
            QtGui.QApplication.processEvents()
            ds = "{:s}  {:d}".format(getDate(self.ser), getCPM(self.ser))
            tn = ds[-6:-4]
            if ta != tn:
                self.writeplain(ds)
                ta = tn
            # print "Checked? ", self.pushButtonLiveData.isChecked()

    def writeplain(self, ln):
        self.plainTextEdit.appendPlainText(ln)
        
    def clearplain(self):
        self.plainTextEdit.clear()
    
    
def main():
    app = QtGui.QApplication(sys.argv)  # instance of QApplication
    #set icon:
    app.setWindowIcon(QtGui.QIcon("gmcicon32.png")) # GUI icon
    form = GmcApp()  
    form.show()  
    app.exec_() 


if __name__ == '__main__': 
    main()  
