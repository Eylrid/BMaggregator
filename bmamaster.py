import os
import api_user
import re
from logger import Logger
ADDRESSVERSIONS = (3,4)

class BMAMaster:
    def __init__(self, configPath=None, apiUser=None):
        self.config = loadConfig(configPath)
        if 'runPath' in self.config:
            os.chdir(self.config['runPath'])

        logPath = self.config['logPath']
        self.logger = Logger(logPath)

        self.mainAddress = self.config['mainAddress']
        self.bittextAddress = self.config['bittextAddress']
        self.chanAddress = self.config['chanAddress']
        self.broadcastAddress = self.config['broadcastAddress']

        if apiUser:
            self.apiUser = apiUser
        else:
            self.apiUser = api_user.ApiUser(config=self.config)

    def getChanAddresses(self):
        '''return a dict mapping chan address to label'''
        addresses = self.apiUser.listAddresses()
        return dict([(i['address'], i['label'][6:].strip()) for i in addresses
                      if i['chan']])

    def getChanLabels(self):
        '''return a dict mapping chan labels to addresses'''
        addresses = [i for i in self.apiUser.listAddresses() if i['chan']]
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
        addresses = self.apiUser.listSubscriptions()
        return dict([(i['address'], i['label'].decode('base64')) for i in addresses])

    def getChansAndSubscriptions(self):
        chans = self.getChanAddresses()
        subs = self.getSubscriptions()
        return chans, subs

    def getAddressListReport(self):
        header = self.getText('reportheaders/addressList', **self.config)
        addressList = self.listChansAndSubscriptions()
        report = header + addressList
        return report

    def listChansAndSubscriptions(self):
        chans, subs = self.getChansAndSubscriptions()
        chans = [(chans[i],i) for i in chans]
        chans.sort(key=lambda x:x[0].lower())
        subs = [(subs[i],i) for i in subs]
        subs.sort(key=lambda x:x[0].lower())
        lst = 'Chans:\n======\n'
        for label, address in chans:
            lst += '%s\t%s\n' %(address, label)

        lst += '\n\nBroadcasts:\n===========\n'
        for label, address in subs:
            lst += '%s\t%s\n' %(address, label)

        return lst

    def updateBittext(self, id, subject, message):
        self.logger.log('Updating Bittext, %s, %s' %(id, subject))
        fromAddress = self.mainAddress
        toAddress = self.bittextAddress
        fullSubject = 'mod %s %s' %(id, subject)
        self.apiUser.sendMessage(toAddress, fromAddress, fullSubject, message)

    def getText(self, filePath, **args):
        def sub(matchobj):
            assert matchobj
            key = matchobj.group(1)
            return args[key]

        with open(filePath, 'r') as file:
            rawText = file.read()

        return re.sub(r'\$(\w+)', sub, rawText)


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

