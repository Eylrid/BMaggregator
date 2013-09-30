import xmlrpclib
import json
import time
from logger import Logger
ADDRESSVERSIONS = (3,4)

class ApiUser:
    def __init__(self, apiUser=None, apiPassword=None, apiPort=None,
                       configPath=None):
        self.config = loadConfig(configPath)
        logPath = self.config['logPath']
        self.logger = Logger(logPath)

        self.mainAddress = self.config['mainAddress']
        self.bittextAddress = self.config['bittextAddress']
        self.chanAddress = self.config['chanAddress']
        self.broadcastAddress = self.config['broadcastAddress']

        if not apiUser:
            apiUser = self.config['apiUser']
        if not apiPassword:
            apiPassword = self.config['apiPassword']
        if not apiPort:
            apiPort = self.config['apiPort']

        apiAddress = "http://%s:%s@localhost:%s/" %(apiUser, apiPassword,
                                                    apiPort)
        self.api = xmlrpclib.ServerProxy(apiAddress)

    def getRawMessages(self):
        inboxMessages = json.loads(self.api.getAllInboxMessages())['inboxMessages']
        return inboxMessages

    def listAddresses(self):
        return json.loads(self.api.listAddresses())['addresses']

    def listSubscriptions(self):
        return json.loads(self.api.listSubscriptions())['subscriptions']

    def getChanAddresses(self):
        '''return a dict mapping chan address to label'''
        addresses = self.listAddresses()
        return dict([(i['address'], i['label'][6:].strip()) for i in addresses
                      if i['chan']])

    def getChanLabels(self):
        '''return a dict mapping chan labels to addresses'''
        addresses = [i for i in self.listAddresses() if i['chan']]
        addresses.reverse() #list newer addresses first
        labels = {}
        for i in addresses:
            label = i['label'][6:].strip()
            address = i['address']
            if label in labels:
                labels[label].append(address)
            else:
                labels[label] = [address]

        return labels

    def getSubscriptions(self):
        addresses = self.listSubscriptions()
        return dict([(i['address'], i['label'].decode('base64')) for i in addresses])

    def getChansAndSubscriptions(self):
        chans = self.getChanAddresses()
        subs = self.getSubscriptions()
        return chans, subs

    def listChansAndSubscriptions(self):
        lst = '''BMaggregator Tracked Addresses
==============================

'''
        chans, subs = self.getChansAndSubscriptions()
        chans = [(chans[i],i) for i in chans]
        chans.sort(key=lambda x:x[0].lower())
        subs = [(subs[i],i) for i in subs]
        subs.sort(key=lambda x:x[0].lower())
        lst += 'Chans:\n======\n'
        for label, address in chans:
            lst += '%s\t%s\n' %(address, label)

        lst += '\n\nBroadcasts:\n===========\n'
        for label, address in subs:
            lst += '%s\t%s\n' %(address, label)

        return lst

    def decodeAddress(self, address):
        result = self.api.decodeAddress(address)
        print result
        decodedAddress = json.loads(result)
        status = decodedAddress['status']
        addressVersion = decodedAddress['addressVersion']
        streamNumber = decodedAddress['streamNumber']
        ripe = decodedAddress['ripe']
        return status, addressVersion, streamNumber, ripe

    def sendBroadcast(self, fromAddress, subject, message):
        encodedSubject = subject.encode('base64')
        encodedMessage = message.encode('base64')
        self.logger.log('Sending Broadcast, %s, %s'%(fromAddress, subject))
        result = self.api.sendBroadcast(fromAddress, encodedSubject, encodedMessage)
        self.logger.log('Api Result, %s'%result)

    def sendMessage(self, toAddress, fromAddress, subject, message):
        '''Send a message. subject and message should be raw'''
        encodedSubject = subject.encode('base64')
        encodedMessage = message.encode('base64')
        self.logger.log('Sending Message, %s, %s, %s'
                         %(toAddress, fromAddress, subject))
        result = self.api.sendMessage(toAddress, fromAddress, encodedSubject, encodedMessage)
        self.logger.log('Api Result, %s'%result)

    def updateBittext(self, id, subject, message):
        self.logger.log('Updating Bittext, %s, %s' %(id, subject))
        fromAddress = self.mainAddress
        toAddress = self.bittextAddress
        fullSubject = 'mod %s %s' %(id, subject)
        self.sendMessage(toAddress, fromAddress, fullSubject, message)


def loadConfig(configPath=None):
    if not configPath:
        configPath = 'config'

    with open(configPath, 'r') as file:
        args = {}
        for line in file.readlines():
            if not line.strip(): continue
            key, value = line.split(':')
            key = key.strip()
            value = value.strip()
            args[key]=value

    return args

