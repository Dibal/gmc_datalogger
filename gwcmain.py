#!/usr/bin/python
# -*- coding: utf-8 -*-s


'''
Read and process history data recorded by Geiger Counter GMC-3xx

Vers 0.7, 2017-03-17 (rimbus)

Software may be free to use according to GPL3
https://www.gnu.org/licenses/gpl-3.0.de.html 
'''


from PyQt4 import QtGui  
import sys  # required for argv to QApplication
import gwcp3  # GUI layout file. Created by: qtuic4 gwcp3.ui >gwcp3.py
from gmcparse6 import *  # basic I/O routines
import os  # directory methods
import time


class GmcApp(QtGui.QMainWindow, gwcp3.Ui_MainWindow):
    
    def __init__(self):
        global data
        global ser
        global serialdev
        global speed
        global helptextname
    
        super(self.__class__, self).__init__()
        self.setupUi(self)  # automatically created in gwcp
        
        # define some global variables (might be improved later)
        helptextname="help.md"
        data =''
        ser=''
        serialdev='/dev/ttyUSB0'
        #speed= 115200
        speedid=0
        #ser=serial.Serial('/dev/ttyUSB0', 115200, timeout= 3)  
        
        self.statusBar().showMessage("...") 
        
        self.menuFile.triggered[QtGui.QAction].connect(self.windowaction)
        self.menuHelp.triggered[QtGui.QAction].connect(self.windowaction)
        self.radioButtonCSV.setChecked(True)
        
        # preselect baud rate
        self.listWidgetspeed.setCurrentRow(speedid)
        speed=int(self.listWidgetspeed.currentItem().text())
        self.lineEditsetDev.setText(serialdev)
        
        #load bin file
        self.pushButtonLoadBin.clicked.connect(self.readbinfile)
        
        #load data from device
        self.pushButtonLoadDevice.clicked.connect(self.readdev)
        
        #check serial
        self.pushButtonSerialSet.clicked.connect(self.checkserial)
        
        #process data
        self.pushButton.clicked.connect(self.processdata)
        
        #write data
        self.pushButtonwritedata.clicked.connect(self.writedatafile)
        
        #time info
        self.pushButtongetTime.clicked.connect(self.timeinfo)
        
        #live data
        self.pushButtonLiveData.setCheckable(True)
        #.pushButtonLiveData.setChecked(False)
        self.pushButtonLiveData.clicked.connect(self.livedata)
        
    #menubar
    def windowaction(self, q):
        global helptextname
        global ser
        
        print "triggered by menubar", q.text()
        if q.text() == "&Quit":
            sys.exit()
        elif q.text() =="Show Helpfile":
            with open(helptextname, mode='rb') as file:  
                helptext = file.read()  
            self.clearplain()
            self.writeplain(helptext)

        
    def readbinfile(self):
        global data
        
        fname = QtGui.QFileDialog.getOpenFileName(self, 'Open file', '',"Data files (*.*)")
        with open(fname, mode='rb') as file:  
            data = file.read() 
        msg= "{:d} bytes loaded from {:s}".format(len(data),fname)
        self.statusBar().showMessage(msg) 
        self.processdata()
    
    
    def readdev(self):
        global ser, data
        
        # ser not defined in init in order to process files even if no device connected
        if not ser:
            #print "set ser"
            #ser = serial.Serial('/dev/ttyUSB0', 115200, timeout= 3) 
            ser = serial.Serial(serialdev, speed, timeout= 3) 
        self.statusBar().clear()
        self.statusBar().showMessage("loading...") 
        print "loading..."
        data = readHIST(ser)
        msg= "{:d} bytes read from device".format(len(data))
        self.statusBar().showMessage(msg) 
        self.processdata()

        
    def checkserial(self):
        global speed
        global serialdev
        global ser
        
        serialdev= self.lineEditsetDev.text().toUtf8()
        #speed= int(self.listWidgetspeed.item(1).text())
        speed=int(self.listWidgetspeed.currentItem().text())
        msg="Serial interface: {:s} at {:d} baud".format(serialdev, speed)
        ser = serial.Serial(serialdev, speed, timeout= 3) 
        self.statusBar().showMessage(msg)
        

    def writedatafile(self):
        global data
        
        if len(data)>1:
            fn= QtGui.QFileDialog.getSaveFileName(self, "Save file", "", "*.*")
            if self.radioButtonBin.isChecked():
                print "binary choosen"
                with open(fn, mode='wb') as file:  
                    file.write(data)  
                msgs= "{:d} bytes saved to {:s}".format(len(data), fn)
            else:
                analyse(self, data, fn, self.checkBox.isChecked())
                msgs= "{:d} bytes converted and saved to {:s}".format(len(data), fn)
        else:
            msgs= "No data to save"
        self.statusBar().showMessage(msgs)
            

    #process data
    def processdata(self):
        self.plainTextEdit.clear()
        msgs= analyse(self, data, '', self.checkBox.isChecked())
        if msgs:
            self.plainTextEdit.appendPlainText(msgs)
            self.statusBar().showMessage("Valid data?")
        else:
            pass
            #self.statusBar().showMessage("done")


    def timeinfo(self):
        global ser
        
        if not ser:
            ser = serial.Serial(serialdev, speed, timeout= 3) 
        dtime=getDate(ser)
        stime= "{:%Y-%m-%d %H:%M:%S}".format(datetime.datetime.now())
        print "GMC device date:", dtime
        print "(interface date: ", stime
        self.lineEditgetTime.setText(dtime)
        self.lineEditSystemTime.setText(stime)
        print "enter demo  loop"
        for i  in range(0,1000000):
            i*i*i
            QtGui.QApplication.processEvents()
        print "demoloop ended"
            
    #requires pushButtonLiveData
    def livedata(self):
        global ser
        
        if not ser:
            ser = serial.Serial(serialdev, speed, timeout= 3)
        if self.pushButtonLiveData.isChecked():
            self.writeplain("* Live data:")
            self.pushButtonLiveData.setStyleSheet("background-color: red")
        else:
            self.pushButtonLiveData.setStyleSheet("background-color: none")
        ta=''
        while self.pushButtonLiveData.isChecked():
            QtGui.QApplication.processEvents()
            ds= "{:s}  {:d}".format(getDate(ser), getCPM(ser))
            tn= ds[-6:-4]
            if ta != tn:
                self.writeplain(ds)
                ta=tn
            #print "Checked? ", self.pushButtonLiveData.isChecked()

    
    def writeplain(self, ln):
        self.plainTextEdit.appendPlainText(ln)
        
    def clearplain(self):
        self.plainTextEdit.clear()
    
    
def main():
    global form
    app = QtGui.QApplication(sys.argv)  # instance of QApplication
    #set icon:
    app.setWindowIcon(QtGui.QIcon("gmcicon32.png")) # GUI icon
    form = GmcApp()  
    form.show()  
    app.exec_() 


if __name__ == '__main__': 
    main()  
