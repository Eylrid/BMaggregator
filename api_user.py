import xmlrpclib
import json
import time
from logger import Logger

class ApiUser:
    def __init__(self, apiUserName=None, apiPassword=None, apiPort=None,
                       config={}, logger=None):
        self.config = config

        if not apiUserName:
            apiUserName = self.config['apiUserName']
        if not apiPassword:
            apiPassword = self.config['apiPassword']
        if not apiPort:
            apiPort = self.config['apiPort']

        apiAddress = "http://%s:%s@localhost:%s/" %(apiUserName, apiPassword,
                                                    apiPort)
        self.api = xmlrpclib.ServerProxy(apiAddress)

        if logger:
            self.logger = logger
        else:
            logPath = self.config['logPath']
            self.logger = Logger(logPath)

    def getRawMessages(self):
        inboxMessages = json.loads(self.api.getAllInboxMessages())['inboxMessages']
        return inboxMessages

    def listAddresses(self):
        return json.loads(self.api.listAddresses())['addresses']

    def listSubscriptions(self):
        return json.loads(self.api.listSubscriptions())['subscriptions']

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
        return result

    def sendMessage(self, toAddress, fromAddress, subject, message):
        '''Send a message. subject and message should be raw'''
        encodedSubject = subject.encode('base64')
        encodedMessage = message.encode('base64')
        self.logger.log('Sending Message, %s, %s, %s'
                         %(toAddress, fromAddress, subject))
        result = self.api.sendMessage(toAddress, fromAddress, encodedSubject, encodedMessage)
        self.logger.log('Api Result, %s'%result)
        return result

    def trashMessage(self, msgid):
        result=self.api.trashMessage(msgid)
        self.logger.log('Api Result, %s'%result)
        return result

    def addSubscription(self, address, label):
        result=self.api.addSubscription(address, label)
        self.logger.log('Api Result, %s'%result)
        return result

    def getDeterministicAddress(self, passphrase, addressVersion,
                                streamNumber):
        return self.api.getDeterministicAddress(passphrase, addressVersion,
                                                streamNumber)

    def addChan(self, passphrase, address=None, addressVersion=0, streamNumber=0):
        if address:
            result = self.api.addChan(passphrase, address)
        else:
            result = self.api.addChan(passphrase, addressVersion, streamNumber)

        self.logger.log('Api Result, %s'%result)
        return result

