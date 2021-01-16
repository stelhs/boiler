import time

class TimeCounter():
    def __init__(s, name):
        s._name = name
        s.reset()


    def start(s):
        s._startTime = int(time.time())
        s._endTime = 0


    def stop(s):
        s._endTime = int(time.time())


    def reset(s):
        s._startTime = 0
        s._endTime = 0


    def time(s):
        if not s._startTime:
            return 0

        if s._endTime:
            return s._endTime - s._startTime

        return int(time.time()) - s._startTime


    def name(s):
        return s._name


