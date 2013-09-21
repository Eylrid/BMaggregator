#!/usr/bin/python
import sys
from BMaggregator import *

args = sys.argv[1:]
bma = Aggregator()
if not args or '-main' in args:
    print bma.getMainReport()
if '-chans' in args:
    print bma.getChanSubjectReport()
if '-broadcasts' in args:
    print bma.getBroadcastSubjectReport()
