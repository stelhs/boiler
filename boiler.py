from math import *
import rlcompleter, readline
readline.parse_and_bind('tab:complete')
from Boiler import *


boiler = Boiler()


def s():
    boiler.io.waterPumpEnable()
    boiler.io.airFunEnable()
    Task.sleep(2000)
    boiler.io.ignitionRelayEnable()
    boiler.io.fuelPumpEnable()
    Task.sleep(1000)
    boiler.io.ignitionRelayDisable()




def e():
    boiler.io.fuelPumpDisable()
    boiler.io.airFunDisable()
    boiler.io.ignitionRelayDisable()


