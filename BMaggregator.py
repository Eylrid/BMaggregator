#!/usr/bin/python

import time
import os
import pickle
import re
from bmamaster import BMAMaster

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

class Aggregator(BMAMaster):
    SEPERATOR = u'~'
    CHECKINTERVAL = 3600
    def __init__(self, configPath=None, apiUser=None):
        BMAMaster.__init__(self, configPath, apiUser)
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

    def getMessages(self):
        rawMessages = self.apiUser.getRawMessages()
        messages = [Message(i) for i in rawMessages]
        return [i for i in messages if self.getAddressFromMessage(i)]

    def getNewMessages(self):
        inboxMessages = self.getMessages()
        return [msg for msg in inboxMessages if msg.msgid not in self.ids]

    def addNewMessages(self):
        self.logger.log('Adding New Messages')
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
        self.logger.log('saving')
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
            self.apiUser.trashMessage(msg.msgid)
            msg.trashed = True
        self.saveEverything()
        self.logger.log('messages trashed')

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

    def getLabelCounts(self, labels, startTime=0, endTime=''):
        counts = []
        for label in labels:
            labelCount = 0
            addresses = labels[label]
            for address in labels[label]:
                if address not in self.addresses: continue
                messages = self.getMessagesInTimeFrame(self.addresses[address],
                                                          startTime, endTime)
                labelCount += len(messages)
            if labelCount:
                counts.append((labelCount, addresses, label))

        return counts

    def publishAllReports(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)

        self.publishMainReport(startTime=startTime, endTime=endTime)
        self.publishChanReport(startTime=startTime, endTime=endTime)
        self.publishBroadcastReport(startTime=startTime, endTime=endTime)

        self.publishTime = time.time()
        self.logger.log('Reports Published')
        self.saveEverything()

    def publishMainReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        report = self.getMainReport(startTime, endTime).encode('utf-8')
        self.broadcastMainReport(report, startTime, endTime)
        self.updateMainBittext(report, startTime, endTime)
        self.logger.log('Report Published, Main')
        self.saveReport(report, startTime, endTime, 'lastreport')

    def publishChanReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        report = self.getChanSubjectReport(startTime, endTime).encode('utf-8')
        self.broadcastChanReport(report, startTime, endTime)
        self.updateChanBittext(report, startTime, endTime)
        self.logger.log('Report Published, Chans')
        self.saveReport(report, startTime, endTime, 'lastChanReport')

    def publishBroadcastReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        report = self.getBroadcastSubjectReport(startTime, endTime).encode('utf-8')
        self.broadcastBroadcastReport(report, startTime, endTime)
        self.updateBroadcastBittext(report, startTime, endTime)
        self.logger.log('Report Published, Broadcasts')
        self.saveReport(report, startTime, endTime, 'lastBroadcastReport')

    def broadcastMainReport(self, report=None, startTime=None, endTime=None):
        if report==None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getMainReport(startTime, endTime).encode('utf-8')

        subject = 'BMaggregator Report'
        address = self.mainAddress
        self.apiUser.sendBroadcast(address, subject, report)

    def broadcastChanReport(self, report=None, startTime=None, endTime=None):
        if report==None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getChanSubjectReport(startTime, endTime).encode('utf-8')

        subject = 'BMaggregator Chan Report'
        address = self.chanAddress
        self.apiUser.sendBroadcast(address, subject, report)

    def broadcastBroadcastReport(self, report=None, startTime=None, endTime=None):
        if report==None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getBroadcastSubjectReport(startTime, endTime).encode('utf-8')

        subject = 'BMaggregator Broadcast Report'
        address = self.broadcastAddress
        self.apiUser.sendBroadcast(address, subject, report)

    def updateMainBittext(self, report=None, startTime=None, endTime=None):
        if report == None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getMainReport(startTime, endTime).encode('utf-8')

        bittextId = self.config['bittextMain']
        oldBittextId = self.config['bittextMainOld']

        #old bittext
        deprecationNotice = self.getText('reportheaders/deprecation',
                                         newId=bittextId,
                                         oldId=oldBittextId).encode('utf-8')
        oldreport = deprecationNotice + report
        self.updateBittext(oldBittextId, 'BMaggregator Report',
                           oldreport)

        #new bittext
        self.updateBittext(bittextId, 'BMaggregator Report', report)

    def updateChanBittext(self, report=None, startTime=None, endTime=None):
        if report == None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getChanSubjectReport(startTime, endTime).encode('utf-8')

        bittextId = self.config['bittextChans']
        oldBittextId = self.config['bittextChansOld']

        #old bittext
        deprecationNotice = self.getText('reportheaders/deprecation',
                                         newId=bittextId,
                                         oldId=oldBittextId).encode('utf-8')
        oldreport = deprecationNotice + report
        self.updateBittext(oldBittextId,
                          'BMaggregator Chan Report', oldreport)

        #new bittext
        self.updateBittext(bittextId, 'BMaggregator Chan Report',
                           report)

    def updateBroadcastBittext(self, report=None, startTime=None, endTime=None):
        if report == None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getChanSubjectReport(startTime, endTime).encode('utf-8')

        bittextId = self.config['bittextBroadcasts']
        oldBittextId = self.config['bittextBroadcastsOld']

        #old bittext
        deprecationNotice = self.getText('reportheaders/deprecation',
                                         newId=bittextId,
                                         oldId=oldBittextId).encode('utf-8')
        oldreport = deprecationNotice + report
        self.updateBittext(oldBittextId,
                           'BMaggregator Broadcast Report', oldreport)

        #new bittext
        self.updateBittext(bittextId,
                           'BMaggregator Broadcast Report', report)

    def saveReport(self, report=None, startTime=None, endTime=None, filename='report'):
        if report == None:
            startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
            report = self.getMainReport(startTime, endTime).encode('utf-8')

        with open(filename, 'w') as file:
            file.write(report)

        self.logger.log('Report Saved, filename')

    def getMainReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        startTimeString, endTimeString = self.getTimeStrings(startTime, endTime)

        report = self.getText('reportheaders/mainReport',
                               startTimeString=startTimeString,
                               endTimeString=endTimeString, **self.config)

        report += u'\n\nChans:\n======\n\n'
        report += self.getRawChanSubjectReport(startTime, endTime)
        report += u'\nBroadcasts:\n===========\n\n'
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

            hourStartString, hourEndString = self.getTimeStrings(hourStart, hourEnd)

            report += '%d\t%s\t%s\n' %(count, hourStartString, hourEndString)

        return report

    def getChanSubjectReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        return (self.getChanSubjectHeader(startTime, endTime) + u'\n\n' +
                self.getRawChanSubjectReport(startTime, endTime))

    def getRawChanSubjectReport(self, startTime=None, endTime=None,
                                numberOfSubjectsToList=20):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        report = u''

        chans = self.getLabelCounts(self.getChanLabels(), startTime, endTime)
        chans.sort(reverse = True)

        for count, addresses, label in chans:
            chanSection = u'Name: %s\n' %label
            chanSection += Aggregator.SEPERATOR*(6+len(label))+u'\n'
            chanSection += u'Addresses:\n'

            for address in addresses:
                chanSection += u'  %s\n' %address

            chanSection += u'\nMessages Seen: %d\n\n' %count

            messages = []
            for address in addresses:
                messages += self.getMessagesInTimeFrame(
                                self.addresses.get(address, []),
                                startTime, endTime)

            subjects = set([msg.subject for msg in messages])
            subjectCounts = []
            for subject in subjects:
                count = len([msg for msg in messages
                             if msg.subject==subject])
                subjectCounts.append((count, subject))

            subjectCounts.sort(key = lambda x: x[1].lower())
            subjectCounts.sort(key = lambda x: x[0], reverse=True)

            subjectHeader = ''
            if len(subjectCounts) > numberOfSubjectsToList:
                subjectCounts = subjectCounts[:numberOfSubjectsToList]
                subjectHeader += u'Top %d ' %numberOfSubjectsToList

            subjectHeader += u'Subjects (number of messages, subject):\n'
            chanSection += subjectHeader

            for count, subject in subjectCounts:
                chanSection += u'  %d\t%s\n' %(count, subject)

            report += chanSection + u'\n\n'

        return report

    def getChanSubjectHeader(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        startTimeString, endTimeString = self.getTimeStrings(startTime, endTime)

        return self.getText('reportheaders/chanReport',
                             startTimeString=startTimeString,
                             endTimeString=endTimeString,
                             **self.config)

    def getBroadcastSubjectReport(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        return (self.getBroadcastSubjectHeader(startTime, endTime) + u'\n\n' +
                self.getRawBroadcastSubjectReport(startTime, endTime))

    def getRawBroadcastSubjectReport(self, startTime=None, endTime=None,
                                     numberOfSubjectsToList = 20):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        report = u''

        broadcasts = self.getMessageCounts(self.getSubscriptions(),
                                           startTime, endTime)
        broadcasts.sort(reverse = True)

        for count, address, label in broadcasts:
            broadcastSection = u'Name: %s\n' %label
            broadcastSection += Aggregator.SEPERATOR*(6+len(label))+u'\n'
            broadcastSection += u'Address: %s\n\n' %address

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

            subjectHeader = ''
            if len(subjectCounts) > numberOfSubjectsToList:
                subjectCounts = subjectCounts[:numberOfSubjectsToList]
                subjectHeader += u'Top %d ' %numberOfSubjectsToList

            subjectHeader += u'Subjects (number of messages, subject):\n'
            broadcastSection += subjectHeader

            for count, subject in subjectCounts:
                broadcastSection += u'  %d\t%s\n' %(count, subject)

            report += broadcastSection + u'\n\n'

        return report

    def getBroadcastSubjectHeader(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        startTimeString, endTimeString = self.getTimeStrings(startTime, endTime)

        return self.getText('reportheaders/broadcastReport',
                             startTimeString=startTimeString,
                             endTimeString=endTimeString,
                             **self.config)

    def getDefaultTimeWindow(self, startTime=None, endTime=None):
        if endTime == None:
            #use now as the end time
            endTime = time.time()
        if startTime == None:
            #use a 24 hour window
            startTime = endTime - 86400

        return startTime, endTime

    def getTimeStrings(self, startTime=None, endTime=None):
        startTime, endTime = self.getDefaultTimeWindow(startTime, endTime)
        startTimeString = time.asctime(time.gmtime(startTime)) + ' UTC'
        endTimeString = time.asctime(time.gmtime(endTime)) + ' UTC'
        return startTimeString, endTimeString

    def check(self, addNewMessages=True):
        self.logger.log('check')
        nextPublishTime = self.publishTime + 86400
        print 'nextPublishTime', nextPublishTime
        now = time.time()
        if addNewMessages:
            self.addNewMessages()

        if now >= nextPublishTime:
            self.publishAllReports()
            nextPublishTime = self.publishTime + 86400

        timeToNextHour = Aggregator.CHECKINTERVAL-time.time()%Aggregator.CHECKINTERVAL
        timeToNextPublish = nextPublishTime - now
        timeToNextCheck = min((timeToNextHour,timeToNextPublish))
        return timeToNextCheck

    def loop(self):
        while True:
            result = self.check()
            if result:
                time.sleep(result)

def main():
    aggregator = Aggregator()
    aggregator.loop()

if __name__ == '__main__':
    main()

