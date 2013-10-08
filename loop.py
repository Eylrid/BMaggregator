#!/usr/bin/python
from BMaggregator import *
from logger import Logger
import time

def check():
    bma = Aggregator()
    return bma.check(addNewMessages=False)

def logerror(exception):
    logger = Logger('logloopexceptions')
    args = [str(i) for i in exception.args]
    logger.log('loop Error!!, ' + ', '.join([str(type(exception)),]+args))

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
