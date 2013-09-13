#!/usr/bin/python

import xmlrpclib
import json
import time
import os
import sys
import re
LOGPATH = 'handlerLog'

class Handler:
    def __init__(self, apiUser=None, apiPassword=None, apiPort=None):
        config = loadConfig()
        if not apiUser:
            apiUser = config['apiUser']
        if not apiPassword:
            apiPassword = config['apiPassword']
        if not apiPort:
            apiPort = config['apiPort']

        self.logPath = config.get('logPath', LOGPATH)

        apiAddress = "http://%s:%s@localhost:%s/" %(apiUser, apiPassword,
                                                  apiPort)
        self.api = xmlrpclib.ServerProxy(apiAddress)

    def getRawMessages(self):
        inboxMessages = json.loads(self.api.getAllInboxMessages())['inboxMessages']
        return inboxMessages

    def filterMessages(self, messages):
        addresses = json.loads(self.api.listAddresses())['addresses']
        addressDict = dict([(a['address'], a) for a in addresses])
        filteredMessages = []
        for message in messages:
            address = message['toAddress']
            if (address == '[Broadcast subscribers]'
                or addressDict[address]['chan']):
                continue

            filteredMessages.append(message)

        return filteredMessages

    def processMessages(self, messages):
        for message in messages:
            subject =  message['subject'].decode('base64').decode('utf-8')
            self.log('processing message with subject ' + subject)
            command, details = self.parseSubject(subject)
            self.log('command, details: %s, %s' %(command, details))
            if command == 'ignore':
                continue
            elif command == 'subscription':
                encodedLabel = details.encode('utf-8').encode('base64')
                address = message['fromAddress']
                self.log('adding subcription %s as %s' %(address, details))
                result = self.api.addSubscription(address, encodedLabel)
                self.log('addSubscription result %s' %result)
                if 'Added subscription' in result:
                    self.confirmSubscription(address, details)
                elif 'API Error 0016':
                    #Already subscribed
                    self.sendError(address, 'That address is already being tracked.')
                else:
                    #unknown error
                    self.sendError(address)
            elif command == 'subnolabel':
                self.sendError(message['fromAddress'], 'No label specified. Please include a label in the subject. Example: "add broadcast Cat Blog"')
            elif command == 'chan':
                encodedPassphrase = details.encode('utf-8').encode('base64')
                self.log('adding chan %s' %(details))
                address = self.api.getDeterministicAddress(encodedPassphrase,3,1)
                fromAddress = message['fromAddress']
                if details.startswith('<') and details.endswith('>') and address != fromAddress:
                    self.log('striping <>')
                    details = details[1:-1]
                    encodedPassphrase = details.encode('utf-8').encode('base64')
                    address = self.api.getDeterministicAddress(encodedPassphrase,3,1)

                if address != fromAddress:
                    #message sent from address not belonging to chan
                    self.log('message sent from address not belonging to chan')
                    self.sendError(fromAddress, 'Passphrase doesn\'t match address. Please check the passphrase and also make sure you are sending from the chan address')
                else:
                    result = self.api.addChan(encodedPassphrase)
                    self.log('addChan result %s' %result)
                    if 'Added chan' in result:
                        self.confirmChan(address, details)
                    elif 'API Error 0016':
                        #Already tracked
                        self.sendError(address, 'This chan is already being tracked.')
                    else:
                        #unknown error
                        self.sendError(address)
            elif command == 'channoname':
                self.sendError(message['fromAddress'], 'No name specified. Please include the name of the chan in the subject. Example "add chan catpix"')
            else:
                self.log('UNRECOGNIZED COMMAND! ' + command)
                continue

            self.trashMessage(message)

    def confirmSubscription(self, toAddress, label):
        fromAddress = 'BM-2D7Wwe3PNCEM4W5q58r19Xn9P3azHf95rN'
        rawSubject = 'Broadcast Add Confirmation'
        encodedSubject = rawSubject.encode('base64')
        rawMessage = "Address %s added to BMaggregator as a broadcast with label '%s'" %(toAddress, label)
        encodedMessage = rawMessage.encode('utf-8').encode('base64')
        logEntry = '''sending broadcast confirmation
toAddress:%s
fromAddress:%s
subject:%s
message:%s''' %(toAddress, fromAddress, rawSubject, rawMessage)
        self.log(logEntry)
        self.api.sendMessage(toAddress, fromAddress,
                             encodedSubject, encodedMessage)

    def confirmChan(self, toAddress, label):
        fromAddress = 'BM-2D7Wwe3PNCEM4W5q58r19Xn9P3azHf95rN'
        rawSubject = 'Chan Add Confirmation'
        encodedSubject = rawSubject.encode('base64')
        rawMessage = "Added chan %s with address %s to BMaggregator." %(label, toAddress)
        encodedMessage = rawMessage.encode('utf-8').encode('base64')
        logEntry = '''sending chan confirmation
toAddress:%s
fromAddress:%s
subject:%s
message:%s''' %(toAddress, fromAddress, rawSubject, rawMessage)
        self.log(logEntry)
        self.api.sendMessage(toAddress, fromAddress,
                             encodedSubject, encodedMessage)

    def sendError(self, toAddress, rawMessage=None):
        fromAddress = 'BM-2D7Wwe3PNCEM4W5q58r19Xn9P3azHf95rN'
        rawSubject = 'Error'
        encodedSubject = rawSubject.encode('base64')
        if rawMessage == None:
            rawMessage = 'There was an unknown error processing your request.'
        encodedMessage = rawMessage.encode('utf-8').encode('base64')
        logEntry = '''sending error message
toAddress:%s
fromAddress:%s
subject:%s
message:%s''' %(toAddress, fromAddress, rawSubject, rawMessage)
        self.log(logEntry)
        self.api.sendMessage(toAddress, fromAddress,
                             encodedSubject, encodedMessage)

    def trashMessage(self, message):
        msgid = message['msgid']
        self.log('trashing %s' % msgid)
        self.api.trashMessage(msgid)

    def parseSubject(self, subject):
        patterns = [(r'(?i)\s*add\s+broadcast\s+(\S.*?)\s*$', 'subscription'),
                    (r'(?i)\s*add\s+broadcast\s*()$', 'subnolabel'),
                    (r'(?i)\s*add\s+chan\s+(\S.*?)\s*$', 'chan'),
                    (r'(?i)\s*add\s+chan\s*()$', 'channoname')]
        for pattern, command in patterns:
            match = re.match(pattern, subject)
            if match:
                return (command, match.group(1))

        else:
            return ('ignore', '')

    def log(self, message):
        print message
        with open(self.logPath, 'a') as file:
            file.write('\n*************\n%s\n' %time.ctime())
            file.write(message.encode('utf-8'))
            file.write('\n')


def loadConfig():
    with open('handlerconfig', 'r') as file:
        args = {}
        for line in file.readlines():
            if not line.strip(): continue
            key, value = line.split(':')
            key = key.strip()
            value = value.strip()
            args[key]=value

    return args

def main():
    args = sys.argv[1:]
    if len(args):
        arg = args[0]
    else:
        arg = ''

    if arg == 'newMessage':
        handler = Handler()
        handler.log('newMessage')
        allmsgs = handler.getRawMessages()
        filteredmsgs = handler.filterMessages(allmsgs)
        print 'all messages:', len(allmsgs)
        print 'direct messages:', len(filteredmsgs)
        handler.processMessages(filteredmsgs)

if __name__ == '__main__':
    main()
