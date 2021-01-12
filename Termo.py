from Task import *
from common import *
from Syslog import *


class Termo(Task):
    sensorMode = 'real'

    class TermoError(Exception):
        def __init__(s, *args):
            Exception.__init__(s, args)


    def __init__(s, devName, name):
        Task.__init__(s, "termo_task_%s" % name)
        s._name = name
        s._devName = devName
        s._val = None
        s.log = Syslog("termo_sensor_%s" % name)
        s.error = False

        if s.sensorMode == 'fake':
            filePutContent('termo_sensor_%s' % name, "18.0")
            return

        s._of = open("/sys/bus/w1/devices/%s/temperature" % devName, "r")
        s._lock = threading.Lock()
        s.start()


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


    def do(s):
        while(1):
            val = s.read()
            with s._lock:
                s._val = val
            Task.sleep(500)


    def val(s):
        if s.error:
            raise Termo.TermoError("Can't read termo sensor %s" % s._name, s._name)

        if s.sensorMode == 'real':
            with s._lock:
                return s._val

        return float(fileGetContent('termo_sensor_%s' % s._name))


    def __str__(s):
        return "TermoSensor %s/%s, temperature: %.1f" % (s._name, s._devName, s.val())



class TermoSensors():
    def __init__(s):
        s._boilerTermo = Termo("28-012033e26477", "boiler")
        s._retTermo = Termo("28-012033f3fd8f", "return_water")
        s._roomTermo = Termo("28-012033e45839", "room")
        s._exhaustGasTermo = Termo("28-012033f9c648", "exhaust_gas")


    def boiler_t(s):
        return s._boilerTermo.val()


    def ret_t(s):
        return s._retTermo.val()


    def room_t(s):
        return s._roomTermo.val()


    def exhaustGas_t(s):
        return s._exhaustGasTermo.val()

