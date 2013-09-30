#!/usr/bin/python

#This script will join all available address versions for each chan

from api_user import *
STREAMNUMBER = 1

au = ApiUser()
labels = au.getChanLabels()

for label in labels:
    print 'checking', label
    currentAddresses = labels[label]
    encodedPassphrase = label.encode('utf-8').encode('base64')
    for addressVersion in ADDRESSVERSIONS:
        address = au.api.getDeterministicAddress(encodedPassphrase,
                                                           addressVersion,
                                                           STREAMNUMBER)
        if address not in currentAddresses:
            result = au.api.addChan(encodedPassphrase, addressVersion, STREAMNUMBER)
            print result.encode('utf-8')
