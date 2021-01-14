from Task import *
from common import *
from Syslog import *


class TermoSensor():
    sensorMode = 'real'

    class TermoError(Exception):
        def __init__(s, *args):
            Exception.__init__(s, args)


    def __init__(s, devName, name):
        s._name = name
        s._devName = devName
        s._val = None
        s.log = Syslog("termo_sensor_%s" % name)
        s.error = False

        if s.sensorMode == 'fake':
            s._fileName = 'FAKE/termo_sensor_%s' % name
            if not os.path.exists(s._fileName):
                filePutContent(s._fileName, "18.0")
            return

        s._of = open("/sys/bus/w1/devices/%s/temperature" % devName, "r")

        s._lock = threading.Lock()

        def task():
            while(1):
                val = s.read()
                with s._lock:
                    s._val = val
                Task.sleep(500)

        s._task = Task("termo_sensor_%s" % name)
        s._task.setCb(task)
        s._task.start()


    def read(s):
        while (1):
            try:
                s._of.seek(0)
                val = s._of.read().strip()
            except:
                s.error = True
                s.log.error("Can't read termo sensor")
                return

            if not val:
                Task.sleep(100)
                continue

            return float(int(val) / 1000)


    def val(s):
        if s.error:
            raise TermoSensor.TermoError("Can't read termo sensor %s" % s._name, s._name)

        if s.sensorMode == 'real':
            with s._lock:
                return s._val

        return float(fileGetContent(s._fileName))


    def __str__(s):
        return "%s, TermoSensor %s/%s, temperature: %.1f" % (
                    super().__str__(), s._name, s._devName, s.val())



