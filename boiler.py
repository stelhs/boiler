from math import *
import rlcompleter, readline
readline.parse_and_bind('tab:complete')
from Boiler import *


boiler = Boiler()


def s():
    boiler.io.waterPumpEnable()
    boiler.io.airFunEnable()
    boiler.io.ignitionRelayEnable()
    Task.sleep(2000)
    boiler.io.fuelPumpEnable()
    Task.sleep(5000)
    boiler.io.ignitionRelayDisable()




def e():
    boiler.io.fuelPumpDisable()
    boiler.io.ignitionRelayDisable()
    Task.sleep(20000)
    boiler.io.airFunDisable()


def p():
    while 1:
        boiler.io.print()
        Task.sleep(1000)


def bp():
    while 1:
        boiler.print()
        Task.sleep(1000)
