import xmlrpclib
import json
import time
from logger import Logger

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
        addresses = self.listAddresses()
        return dict([(i['address'], i['label'][6:].strip()) for i in addresses
                      if i['chan']])

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

