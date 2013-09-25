#!/usr/bin/python
from BMaggregator import *

class Tester:
    def __init__(self):
        self.bma = Aggregator()

    def test(self):
        tests = [('Aggregator.getTimeStrings', self.getTimeStrings),
                 ('Aggregator.getText', self.getText),
                 ('Aggregator Reports', self.reports)]
        for label, function in tests:
            print label
            print '='*len(label)
            print
            function()
            print

    def getTimeStrings(self):
        startTimeString, endTimeString = self.bma.getTimeStrings()
        print 'startTimeString', startTimeString
        print 'endTimeString', endTimeString

    def getText(self):
        startTimeString, endTimeString = self.bma.getTimeStrings()
        texts = ['reportheaders/mainReport', 'reportheaders/chanReport',
                 'reportheaders/broadcastReport']
        for text in texts:
            print text
            print '-'*len(text)
            print
            print self.bma.getText(text, startTimeString=startTimeString,
                                   endTimeString=endTimeString, **self.bma.config)

    def reports(self):
        print 'Main:\n-----'
        print self.bma.getMainReport().encode('utf-8')

        print 'Chans:\n-----'
        print self.bma.getChanSubjectReport().encode('utf-8')

        print 'Broadcasts:\n-----'
        print self.bma.getBroadcastSubjectReport().encode('utf-8')

def main():
    tester = Tester()
    tester.test()

if __name__ == '__main__':
    main()

