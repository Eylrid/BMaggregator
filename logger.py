import time

class Logger:
    def __init__(self, logPath):
        self.logPath = logPath

    def log(self, message):
        print message
        with open(self.logPath, 'a') as file:
            file.write('%s, %s\n' %(time.ctime(), message.encode('utf-8')))

