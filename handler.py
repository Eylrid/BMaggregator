#!/usr/bin/python
import time
import os
import sys
from BMaggregator import *
LOGPATH = 'handlerLog'

def main():
  config = loadConfig()

  logPath = config.get('logPath', LOGPATH)
  runPath = config.get('runPath', '.')

  cwd = os.getcwd()
  if os.path.abspath(runPath) != cwd:
      os.chdir(runPath)

  args = sys.argv[1:]
  write = '\n*************\n%s\n%s\n' %(time.ctime(), str(args))

  if args[0] != 'startingUp':
    bma = Aggregator()
    result = bma.check()
    write += 'bma checked %f' %result

  with open(logPath, 'a') as file:
    file.write(write)

if __name__ == '__main__':
  main()
