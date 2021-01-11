from math import *
import rlcompleter, readline
readline.parse_and_bind('tab:complete')
import enum

from Task import *
from Gpio import *
from Termo import *
#Gpio.gpioMode = 'fake'
#Termo.sensorMode = 'fake'


class Boiler(Task):
    # states:
    #   ALARM_OVER_HEATING
    #   HARD_DISABLED
    #   SOFT_DISABLED
    #   WAITING
    #   HEATING
    _state = "WAITING"

    _listGpioInputs = (Gpio('over_heating', 8, 'in'),
                       Gpio('hw_enable', 9, 'in'),
                       Gpio('flame_sensor', 23, 'in'),
                       Gpio('pressure_sensor', 10, 'in'),
                       Gpio('fan_heater_switch', 24, 'in'))


    def __init__(s):
        Task.__init__(s, "boiler")
        s.gpioEventTask = GpioEventsTask(s._listGpioInputs, s.gpioChanged)
        s._gpioOverHeating = Gpio.gpioByName("over_heating")

        s._termoSensors = TermoSensors()


    def do(s):
        while(1):
            checkOverHeating()

            if s._state == "WAITING":
                doWaiting()
            elif s._state == "HEATIMG":
                doHeating()

            Task.sleep(1000)


    def gpioChanged(s, gpio, val):
        print("changed gpio %d to val %d" % (gpio.num(), val))


    def checkOverHeating(s):
        val = s._gpioOverHeating.value()
        if val == 1: #if normal
            return "NO_OVER_HEATING"
        #Отключить питание, сообщить в телеграм, через 10сек отключить вентилтор
        return "ALARM"


    def doWaiting(s):
        pass

boiler = Boiler()
