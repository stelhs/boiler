import syslog

class Syslog():
    def __init__(s, subsystemName):
        s._subsystem = subsystemName

    def error(s, msg):
        syslog.syslog(syslog.LOG_ERR, "boiler/%s ERROR: %s" % (s._subsystem, msg))


    def debug(s, msg):
        syslog.syslog(syslog.LOG_DEBUG, "boiler/%s: %s" % (s._subsystem, msg))


    def info(s, msg):
        syslog.syslog(syslog.LOG_INFO, "boiler/%s: %s" % (s._subsystem, msg))