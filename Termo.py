from Task import *
from common import *


class Termo(Task):
    sensorMode = 'real'

    def __init__(s, devName, name):
        Task.__init__(s, "termo_task_%s" % name)
        s._name = name
        s._of = open("/sys/bus/w1/devices/%s/temperature" % devName, "r")
        s._lock = threading.Lock()
        s._val = None
        if s.sensorMode == 'fake':
            filePutContent('termo_sensor_%s' % name, "18.0")
            return

        s.start()


    def read(s):
        while (1):
            s._of.seek(0)
            val = s._of.read().strip()
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
        if s.sensorMode == 'real':
            with s._lock:
                return s._val

        return float(fileGetContent('termo_sensor_%s' % name))





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
