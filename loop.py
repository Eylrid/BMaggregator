#!/usr/bin/python
from BMaggregator import *
import time

def check():
    bma = Aggregator()
    return bma.check(addNewMessages=False)

def logerror(exception):
    au = ApiUser()
    au.logger.log('loop Error!!, ' + ', '.join((str(type(exception)),)+ exception.args))

def loop():
    while True:
        try:
            result = check()
        except Exception as exception:
            logerror(exception)
            result = Aggregator.CHECKINTERVAL-time.time()%Aggregator.CHECKINTERVAL

        if result:
            print 'sleeping for ' + str(result)
            time.sleep(result)

if __name__ == '__main__':
    loop()
