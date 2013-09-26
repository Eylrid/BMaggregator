#!/usr/bin/python

import os
import sys
import re
from api_user import ApiUser
from logger import Logger
CONFIGPATH = 'handlerconfig'

class Handler(ApiUser):
    def __init__(self, apiUser=None, apiPassword=None, apiPort=None,
                       configPath=CONFIGPATH):
        ApiUser.__init__(self, apiUser, apiPassword, apiPort, configPath)

    def filterMessages(self, messages):
        addresses = self.listAddresses()
        addressDict = dict([(a['address'], a) for a in addresses])
        filteredMessages = []
        for message in messages:
            address = message['toAddress']
            if (address == '[Broadcast subscribers]'
                or addressDict.get(address, {'chan':''})['chan']):
                continue

            filteredMessages.append(message)

        return filteredMessages

    def processMessages(self, messages):
        ignoreCount = 0
        for message in messages:
            subject =  message['subject'].decode('base64').decode('utf-8')
            self.logger.log('processing message, ' + subject)
            command, details = self.parseSubject(subject)
            self.logger.log('command, %s, %s' %(command, details))
            if command == 'ignore':
                ignoreCount += 1
                continue
            elif command == 'subscription':
                encodedLabel = details.encode('utf-8').encode('base64')
                address = message['fromAddress']
                self.logger.log('adding subcription, %s, %s' %(address, details))
                result = self.api.addSubscription(address, encodedLabel)
                self.logger.log('addSubscription result, %s' %result)
                if 'Added subscription' in result:
                    self.confirmSubscription(address, details)
                    self.updateAddressBittext()
                elif 'API Error 0016' in result:
                    #Already subscribed
                    self.sendError(address, 'That address is already being tracked.')
                else:
                    #unknown error
                    self.sendError(address)
            elif command == 'subnolabel':
                self.sendError(message['fromAddress'], 'No label specified. Please include a label in the subject. Example: "add broadcast Cat Blog"')
            elif command == 'chan':
                encodedPassphrase = details.encode('utf-8').encode('base64')
                self.logger.log('adding chan, %s' %(details))
                fromAddress = message['fromAddress']
                status, addressVersion, streamNumber, ripe = self.decodeAddress(fromAddress)
                address = self.api.getDeterministicAddress(encodedPassphrase,
                                                           addressVersion,
                                                           streamNumber)
                if details.startswith('<') and details.endswith('>') and address != fromAddress:
                    self.logger.log('striping <>')
                    details = details[1:-1]
                    encodedPassphrase = details.encode('utf-8').encode('base64')
                    address = self.api.getDeterministicAddress(encodedPassphrase,
                                                               addressVersion,
                                                               streamNumber)

                if address != fromAddress:
                    #message sent from address not belonging to chan
                    self.logger.log('message sent from address not belonging to chan')
                    self.sendError(fromAddress, 'Passphrase doesn\'t match address. Please check the passphrase and also make sure you are sending from the chan address')
                else:
                    result = self.api.addChan(encodedPassphrase, fromAddress)
                    self.logger.log('addChan result, %s' %result)
                    if 'Added chan' in result:
                        self.confirmChan(address, details)
                        self.updateAddressBittext()
                    elif 'API Error 0016' in result or 'API Error 0024' in result:
                        #Already tracked
                        self.sendError(address, 'This chan is already being tracked.')
                    else:
                        #unknown error
                        self.sendError(address)
            elif command == 'channoname':
                self.sendError(message['fromAddress'], 'No name specified. Please include the name of the chan in the subject. Example "add chan catpix"')
            elif command == 'btxtmodConf':
                self.logger.log('bittext mod confirmed, ' + details)
            else:
                self.logger.log('UNRECOGNIZED COMMAND!, ' + command)
                continue

            self.trashMessage(message)

        self.logger.log('ignoreCount, ' + str(ignoreCount))

    def confirmSubscription(self, toAddress, label):
        fromAddress = self.mainAddress
        subject = 'Broadcast Add Confirmation'
        message = "Address %s added to BMaggregator as a broadcast with label '%s'" %(toAddress, label)
        self.sendMessage(toAddress, fromAddress, subject, message)

    def confirmChan(self, toAddress, label):
        fromAddress = self.mainAddress
        subject = 'Chan Add Confirmation'
        message = "Added chan %s with address %s to BMaggregator. See bittext.ch/bmaggrinfo for more information." %(label, toAddress)
        self.sendMessage(toAddress, fromAddress, subject, message)

    def sendError(self, toAddress, message=None):
        fromAddress = self.mainAddress
        subject = 'Error'
        if message == None:
            message = 'There was an unknown error processing your request.'
        self.sendMessage(toAddress, fromAddress,
                             subject, message)

    def updateAddressBittext(self):
        self.logger.log('updating bittext, bmaggradrs')
        message = self.listChansAndSubscriptions().encode('utf-8')
        self.updateBittext('bmaggradrs', 'BMaggregator Tracked Addresses',
                           message)

    def trashMessage(self, message):
        msgid = message['msgid']
        subject = message['subject'].decode('base64')
        self.logger.log('trashing, %s, %s' %(msgid, subject))
        self.api.trashMessage(msgid)

    def parseSubject(self, subject):
        patterns = [(r'(?i)\s*add\s+broadcast\s+(\S.*?)\s*$', 'subscription'),
                    (r'(?i)\s*add\s+broadcast\s*()$', 'subnolabel'),
                    (r'(?i)\s*add\s+chan\s+(\S.*?)\s*$', 'chan'),
                    (r'(?i)\s*add\s+chan\s*()$', 'channoname'),
                    (r'BitText (\w+): MOD confirmation', 'btxtmodConf')]
        for pattern, command in patterns:
            match = re.match(pattern, subject)
            if match:
                return (command, match.group(1))

        else:
            return ('ignore', '')


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

    handler = Handler()
    handler.logger.log('arg, ' + arg)

    if arg == 'newMessage':
        allmsgs = handler.getRawMessages()
        filteredmsgs = handler.filterMessages(allmsgs)
        print 'all messages:', len(allmsgs)
        print 'direct messages:', len(filteredmsgs)
        handler.processMessages(filteredmsgs)
    elif arg == 'update':
        handler.updateAddressBittext()

if __name__ == '__main__':
    main()
