import syslog

class Syslog():
    def __init__(s, subsystemName):
        s._subsystem = subsystemName
        s._muted = []

    def err(s, msg):
        if "error" in s._muted:
            return
        syslog.syslog(syslog.LOG_ERR, "%s ERROR: %s" % (s._subsystem, msg))


    def debug(s, msg):
        if "debug" in s._muted:
            return
        syslog.syslog(syslog.LOG_DEBUG, "%s: %s" % (s._subsystem, msg))


    def info(s, msg):
        if "info" in s._muted:
            return
        syslog.syslog(syslog.LOG_INFO, "%s: %s" % (s._subsystem, msg))


    def mute(s, msgType):
        if not msgType in s._muted:
            s._muted.append(msgType)