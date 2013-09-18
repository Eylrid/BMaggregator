import time

class Logger:
    def __init__(self, logPath):
        self.logPath = logPath

    def log(self, message):
        print message
        with open(self.logPath, 'a') as file:
            file.write('\n*************\n%s\n' %time.ctime())
            file.write(message.encode('utf-8'))
            file.write('\n')

