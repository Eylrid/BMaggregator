#!/usr/bin/python

import xmlrpclib
import json
import time
import os
import pickle
import re

class Message:
    def __init__(self, rawmsg):
        self.fromAddress = rawmsg['fromAddress']
        self.toAddress = rawmsg['toAddress']
        self.msgid = rawmsg['msgid']
        self.receivedTime = rawmsg['receivedTime']

        self.subject = rawmsg['subject'].decode('base64').decode('utf-8')
        if self.subject.lower().startswith('re:'):
            self.subject = self.subject[3:]
        self.subject = self.subject.strip()

        self.firstChars = rawmsg['message'].decode('base64')[:150]
        self.trashed = False

class Aggregator:
    SEPERATOR = u'~'
    CHECKINTERVAL = 3600
    def __init__(self, apiUser=None, apiPassword=None, apiPort=None):
        config = loadConfig()
        if not apiUser:
            apiUser = config['apiUser']
        if not apiPassword:
            apiPassword = config['apiPassword']
        if not apiPort:
            apiPort = config['apiPort']

        apiAddress = "http://%s:%s@localhost:%s/" %(apiUser, apiPassword,
                                                    apiPort)
        self.api = xmlrpclib.ServerProxy(apiAddress)
        self.publishTimeFilePath = 'data/publishTime'
        self.messageFilePath = 'data/messages.pkl'
        self.idFilePath = 'data/ids.pkl'
        self.subjectFilePath = 'data/subjects.pkl'
        self.addressFilePath = 'data/addresses.pkl'
        self.loadPublishTime()
        self.loadMessages()
        self.loadIds()
        self.loadSubjects()
        self.loadAddresses()
        self.addNewMessages()

    def getRawMessages(self):
        inboxMessages = json.loads(self.api.getAllInboxMessages())['inboxMessages']
        return inboxMessages

    def getMessages(self):
        rawMessages = self.getRawMessages()
        messages = [Message(i) for i in rawMessages]
        return [i for i in messages if self.getAddressFromMessage(i)]

    def getNewMessages(self):
        inboxMessages = self.getMessages()
        return [msg for msg in inboxMessages if msg.msgid not in self.ids]

    def addNewMessages(self):
        print 'Adding New Messages'
        inboxMessages = self.getNewMessages()
        for message in inboxMessages:
            self.messages.append(message)
            self.ids[message.msgid] = message
            self.addMessageToSubject(message.subject, message)
            self.addMessageToAddress(message)

        self.trashMessages()

    def loadPublishTime(self):
        if os.path.isfile(self.publishTimeFilePath):
            with open(self.publishTimeFilePath, 'r') as file:
                self.publishTime = float(file.read().strip())
        else:
            self.publishTime = 0

    def loadMessages(self):
        if os.path.isfile(self.messageFilePath):
            with open(self.messageFilePath, 'r') as file:
                self.messages = pickle.load(file)
        else:
            self.messages = []

    def loadIds(self):
        if os.path.isfile(self.idFilePath):
            with open(self.idFilePath, 'r') as file:
                self.ids = pickle.load(file)
        else:
            self.ids = {}
            for message in self.messages:
                self.ids[message.msgid] = message

    def loadSubjects(self):
        if os.path.isfile(self.subjectFilePath):
            with open(self.subjectFilePath, 'r') as file:
                self.subjects = pickle.load(file)
        else:
            self.subjects = {}
            for message in self.messages:
                self.addMessageToSubject(message.subject, message)

    def addMessageToSubject(self, subject, message):
        if subject in self.subjects:
            self.subjects[subject].append(message)
        else:
            self.subjects[subject] = [message]

    def loadAddresses(self):
        if os.path.isfile(self.addressFilePath):
            with open(self.addressFilePath, 'r') as file:
                self.addresses = pickle.load(file)
        else:
            self.addresses = {}
            for message in self.messages:
                self.addMessageToAddress(message)

    def saveEverything(self):
        saveData = [(self.messageFilePath, self.messages, True),
                    (self.idFilePath, self.ids, True),
                    (self.subjectFilePath, self.subjects, True),
                    (self.addressFilePath, self.addresses, True),
                    (self.publishTimeFilePath, str(self.publishTime), False)]

        for filename, data, isPickled in saveData:
            with open(filename, 'w') as file:
                if isPickled:
                    pickle.dump(data, file)
                else:
                    file.write(data)

    def trashMessages(self):
        self.saveEverything()
        for msg in self.messages:
            if msg.trashed: continue
            self.api.trashMessage(msg.msgid)
            msg.trashed = True
        self.saveEverything()
        print 'messages trashed'

    def getAddressFromMessage(self, message):
        if self.addressType(message.toAddress) == 'CHAN':
            return message.toAddress
        elif (self.addressType(message.fromAddress) == 'SUBSCRIPTION'
              and message.toAddress == '[Broadcast subscribers]'):
            return message.fromAddress
        else:
            return None

    def addMessageToAddress(self, message):
        address = self.getAddressFromMessage(message)
        if not address:
            raise ValueError('This message isn\'t from a tracked address')

        if address in self.addresses:
            self.addresses[address].append(message)
        else:
            self.addresses[address] = [message]

    def getChanAddresses(self):
        addresses = json.loads(self.api.listAddresses())['addresses']
        return dict([(i['address'], i['label'][6:].strip()) for i in addresses
                      if i['chan']])

    def getSubscriptions(self):
        addresses = json.loads(self.api.listSubscriptions())['subscriptions']
        return dict([(i['address'], i['label'].decode('base64')) for i in addresses])

    def addressType(self, address):
        chans = self.getChanAddresses()
        subscriptions = self.getSubscriptions()
        if address in chans:
            return 'CHAN'
        elif address in subscriptions:
            return 'SUBSCRIPTION'
        else:
            return 'UNKNOWN'

    def getMessagesInTimeFrame(self, messages=None,
                               startTime=0, endTime=''):
        if messages == None: messages = self.messages[:]
        messages = [msg for msg in messages
                    if int(msg.receivedTime) >= startTime
                    and int(msg.receivedTime) <= endTime]
        return messages

    def getMessageCounts(self, addresses, startTime=0, endTime=''):
        counts = []
        for address in addresses:
            if address not in self.addresses: continue
            messages = self.getMessagesInTimeFrame(self.addresses[address],
                                                   startTime, endTime)
            if messages:
                counts.append((len(messages), address, addresses[address]))

        return counts

    def publishAllReports(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)

        self.publishMainReport(startTime=None, endTime=None)
        self.publishChanReport(startTime=None, endTime=None)
        self.publishBroadcastReport(startTime=None, endTime=None)

        self.publishTime = time.time()
        self.saveEverything()

    def publishMainReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        report = self.getMainReport(startTime, endTime).encode('utf-8').encode('base64')
        self.broadcastMainReport(report, startTime, endTime)
        self.updateMainBittext(report, startTime, endTime)
        self.saveReport(report, startTime, endTime, 'lastreport')

    def publishChanReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        report = self.getChanSubjectReport(startTime, endTime).encode('utf-8').encode('base64')
        self.broadcastChanReport(report, startTime, endTime)
        self.updateChanBittext(report, startTime, endTime)
        self.saveReport(report, startTime, endTime, 'lastChanReport')

    def publishBroadcastReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        report = self.getBroadcastSubjectReport(startTime, endTime).encode('utf-8').encode('base64')
        self.broadcastBroadcastReport(report, startTime, endTime)
        self.updateBroadcastBittext(report, startTime, endTime)
        self.saveReport(report, startTime, endTime, 'lastBroadcastReport')

    def broadcastMainReport(self, report=None, startTime=None, endTime=None):
        if report==None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getMainReport(startTime, endTime).encode('utf-8').encode('base64')

        subject = 'BMaggregator Report'.encode('base64')
        address = 'BM-2D7Wwe3PNCEM4W5q58r19Xn9P3azHf95rN'
        print self.api.sendBroadcast(address, subject, report)

    def broadcastChanReport(self, report=None, startTime=None, endTime=None):
        if report==None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getChanSubjectReport(startTime, endTime).encode('utf-8').encode('base64')

        subject = 'BMaggregator Chan Report'.encode('base64')
        address = 'BM-GtmZH9PQ7DdhhrxtTeCrBhnEbuSK9Atp'
        print self.api.sendBroadcast(address, subject, report)

    def broadcastBroadcastReport(self, report=None, startTime=None, endTime=None):
        if report==None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getBroadcastSubjectReport(startTime, endTime).encode('utf-8').encode('base64')

        subject = 'BMaggregator Broadcast Report'.encode('base64')
        address = 'BM-Gtzu1qGn8jhZkNCnG2j7nVgt645k29H8'
        print self.api.sendBroadcast(address, subject, report)

    def updateMainBittext(self, report=None, startTime=None, endTime=None):
        if report == None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getMainReport(startTime, endTime).encode('utf-8').encode('base64')

        fromAddress = 'BM-2D7Wwe3PNCEM4W5q58r19Xn9P3azHf95rN'
        toAddress = 'BM-GtkZoid3xpTUnwxezDfpWtYAfY6vgyHd'
        subject = 'mod dOe7aAIVnZ BMaggregator Report'.encode('base64')
        print self.api.sendMessage(toAddress, fromAddress, subject, report)

    def updateChanBittext(self, report=None, startTime=None, endTime=None):
        if report == None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getChanSubjectReport(startTime, endTime).encode('utf-8').encode('base64')

        fromAddress = 'BM-2D7Wwe3PNCEM4W5q58r19Xn9P3azHf95rN'
        toAddress = 'BM-GtkZoid3xpTUnwxezDfpWtYAfY6vgyHd'
        subject = 'mod N3Z4fiuSFW BMaggregator Chan Report'.encode('base64')
        print self.api.sendMessage(toAddress, fromAddress, subject, report)

    def updateBroadcastBittext(self, report=None, startTime=None, endTime=None):
        if report == None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getChanSubjectReport(startTime, endTime).encode('utf-8').encode('base64')

        fromAddress = 'BM-2D7Wwe3PNCEM4W5q58r19Xn9P3azHf95rN'
        toAddress = 'BM-GtkZoid3xpTUnwxezDfpWtYAfY6vgyHd'
        subject = 'mod HqdIvnnxI1 BMaggregator Broadcast Report'.encode('base64')
        print self.api.sendMessage(toAddress, fromAddress, subject, report)

    def saveReport(self, report=None, startTime=None, endTime=None, filename='report'):
        if report == None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getMainReport(startTime, endTime).encode('utf-8').encode('base64')

        with open(filename, 'w') as file:
            file.write(report.decode('base64'))

    def getMainReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        startTimeString = time.asctime(time.gmtime(startTime)).decode('utf-8') + u' UTC'
        endTimeString = time.asctime(time.gmtime(endTime)).decode('utf-8') + u' UTC'

        report = u'''Activity of known chans and broadcasts
======================================

Number of messages seen from chans and broadcast addresses by subject between %s and %s. Addresses that didn't send in this time frame are not listed. This report was generated by BMaggregator. Subscribe to BM-2D7Wwe3PNCEM4W5q58r19Xn9P3azHf95rN for more. The latest version of this report can also be found at bittext.ch/dOe7aAIVnZ.

To get chan only reports subscribe to BM-GtmZH9PQ7DdhhrxtTeCrBhnEbuSK9Atp or see bittext.ch/N3Z4fiuSFW
To get broadcast/mailing list reports subscribe to BM-Gtzu1qGn8jhZkNCnG2j7nVgt645k29H8 or see bittext.ch/HqdIvnnxI1

More info about BMaggregator can be found at bittext.ch/btDiTl8V_d
''' %(startTimeString, endTimeString)

        report += u'\n\nChans:\n======\n'
        report += self.getRawChanSubjectReport(startTime, endTime)
        report += u'\n\nBroadcasts:\n===========\n'
        report += self.getRawBroadcastSubjectReport(startTime, endTime)

        return report

    def getHourlyReport(self, startTime=None, endTime=None,
                        interval=3600):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        report = ''
        for hourStart in range(int(startTime), int(endTime), int(interval)):
            hourEnd = min((hourStart+3600, endTime))
            count = 0
            for msg in self.messages:
                receivedTime = int(msg.receivedTime)
                if receivedTime >= hourStart and receivedTime < hourEnd:
                    count += 1

            hourStartString = time.asctime(time.gmtime(hourStart)) + ' UTC'
            hourEndString = time.asctime(time.gmtime(hourEnd)) + ' UTC'

            report += '%d\t%s\t%s\n' %(count, hourStartString, hourEndString)

        return report

    def getChanSubjectReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        return (self.getChanSubjectHeader(startTime, endTime) +
                self.getRawChanSubjectReport(startTime, endTime))

    def getRawChanSubjectReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        report = u''

        chans = self.getMessageCounts(self.getChanAddresses(), startTime, endTime)
        chans.sort(reverse = True)

        for count, address, label in chans:
            chanHeader = u'%d    %s    %s' %(count, address, label)
            lines = Aggregator.SEPERATOR*len(chanHeader)
            report += u'\n%s\n%s\n' %(chanHeader, lines)

            messages = self.getMessagesInTimeFrame(self.addresses[address],
                                                   startTime, endTime)
            subjects = set([msg.subject for msg in messages])
            subjectCounts = []
            for subject in subjects:
                count = len([msg for msg in messages
                             if msg.subject==subject])
                subjectCounts.append((count, subject))

            subjectCounts.sort(key = lambda x: x[1])
            subjectCounts.sort(key = lambda x: x[0], reverse=True)

            for count, subject in subjectCounts:
                report += u'%d\t%s\n' %(count, subject)

            report += u'\n'

        return report

    def getChanSubjectHeader(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        startTimeString = time.asctime(time.gmtime(startTime)) + ' UTC'
        endTimeString = time.asctime(time.gmtime(endTime)) + ' UTC'

        return u'''BMaggregator Chan Subject Report
================================

Number of messages seen from chans by subject between %s and %s. Chans without posts in this time frame are not listed. This report was generated by BMaggregator. Subscribe to  BM-GtmZH9PQ7DdhhrxtTeCrBhnEbuSK9Atp for more. The latest version of this report can also be found at bittext.ch/N3Z4fiuSFW.

To get broadcast/mailing list reports subscribe to BM-Gtzu1qGn8jhZkNCnG2j7nVgt645k29H8 or see bittext.ch/HqdIvnnxI1
To get reports for all address types subscribe to BM-2D7Wwe3PNCEM4W5q58r19Xn9P3azHf95rN or see bittext.ch/dOe7aAIVnZ

More info about BMaggregator can be found at bittext.ch/btDiTl8V_d

''' %(startTimeString, endTimeString)


    def getBroadcastSubjectReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        return (self.getBroadcastSubjectHeader(startTime, endTime) +
                self.getRawBroadcastSubjectReport(startTime, endTime))

    def getRawBroadcastSubjectReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        report = u''

        broadcasts = self.getMessageCounts(self.getSubscriptions(),
                                           startTime, endTime)
        broadcasts.sort(reverse = True)

        for count, address, label in broadcasts:
            broadcastHeader = u'%d    %s    %s' %(count, address, label)
            lines = Aggregator.SEPERATOR*len(broadcastHeader)
            report += u'\n%s\n%s\n' %(broadcastHeader, lines)

            messages = self.getMessagesInTimeFrame(self.addresses[address],
                                                   startTime, endTime)
            subjects = set([msg.subject for msg in messages])
            subjectCounts = []
            for subject in subjects:
                count = len([msg for msg in messages
                             if msg.subject==subject])
                subjectCounts.append((count, subject))

            subjectCounts.sort(key = lambda x: x[1])
            subjectCounts.sort(key = lambda x: x[0], reverse=True)

            for count, subject in subjectCounts:
                report += u'%d\t%s\n' %(count, subject)

            report += u'\n'

        return report

    def getBroadcastSubjectHeader(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        startTimeString = time.asctime(time.gmtime(startTime)) + ' UTC'
        endTimeString = time.asctime(time.gmtime(endTime)) + ' UTC'

        return u'''BMaggregator Broadcast Subject Report
=====================================

Number of messages seen from broadcast addresses and mailing lists by subject between %s and %s. Addresses that didn't send in this time frame are not listed. This report was generated by BMaggregator. Subscribe to BM-Gtzu1qGn8jhZkNCnG2j7nVgt645k29H8 for more. The latest version of this report can also be found at bittext.ch/HqdIvnnxI1.

To get chan reports subscribe to BM-GtmZH9PQ7DdhhrxtTeCrBhnEbuSK9Atp or see bittext.ch/N3Z4fiuSFW
To get reports for all address types subscribe to BM-2D7Wwe3PNCEM4W5q58r19Xn9P3azHf95rN or see bittext.ch/dOe7aAIVnZ

More info about BMaggregator can be found at bittext.ch/btDiTl8V_d

''' %(startTimeString, endTimeString)


    def getDefaultTimeWindow(self, startTime=None, endTime=None):
        if endTime == None:
            #use now as the end time
            endTime = time.time()
        if startTime == None:
            #use a 24 hour window
            startTime = endTime - 86400

        return startTime, endTime

    def check(self):
        nextPublishTime = self.publishTime + 86400
        now = time.time()
        self.addNewMessages()
        if now >= nextPublishTime:
            self.publishAllReports()
            print 'Reports Published'

        timeToNextCheck = Aggregator.CHECKINTERVAL-time.time()%Aggregator.CHECKINTERVAL
        return timeToNextCheck

    def loop(self):
        while True:
            result = self.check()
            if result:
                time.sleep(result)

def loadConfig():
    with open('config', 'r') as file:
        args = {}
        for line in file.readlines():
            if not line.strip(): continue
            key, value = line.split(':')
            key = key.strip()
            value = value.strip()
            args[key]=value

    return args

def main():
    args = loadConfig()
    aggregator = Aggregator(**args)
    aggregator.loop()

if __name__ == '__main__':
    main()

