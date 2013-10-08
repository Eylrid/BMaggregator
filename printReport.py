#!/usr/bin/python
import sys
from BMaggregator import *

args = sys.argv[1:]
bma = Aggregator()
if not args or '-main' in args:
    print bma.getMainReport().encode('utf-8')
if '-chans' in args:
    print bma.getChanSubjectReport().encode('utf-8')
if '-broadcasts' in args:
    print bma.getBroadcastSubjectReport().encode('utf-8')
