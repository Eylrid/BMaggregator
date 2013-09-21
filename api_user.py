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

