#!/usr/bin/python
from BMaggregator import *
import time

def check():
    bma = Aggregator()
    return bma.check(addNewMessages=False)

def loop():
    while True:
        result = check()
        if result:
            print 'sleeping for ' + str(result)
            time.sleep(result)

if __name__ == '__main__':
    loop()
