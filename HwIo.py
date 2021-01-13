from TermoSensor import *
from Gpio import *


class HwIo():
    def __init__(s):
        if os.path.exists("FAKE"):
            Gpio.gpioMode = 'fake'
            TermoSensor.sensorMode = 'fake'

        s._boilerTermo = TermoSensor("28-012033e26477", "boiler")
        s._retTermo = TermoSensor("28-012033f3fd8f", "return_water")
        s._roomTermo = TermoSensor("28-012033e45839", "room")
        s._exhaustGasTermo = TermoSensor("28-012033f9c648", "exhaust_gas")

        s._gpioIn = {"overHearting": Gpio('over_heating', 8, 'in'),
                     "hwEnable": Gpio('hw_enable', 9, 'in'),
                     "flameSensor": Gpio('flame_sensor', 23, 'in'),
                     "pressureSensor": Gpio('pressure_sensor', 10, 'in'),
                     "fanHeaterSwitch": Gpio('fan_heater_switch', 24, 'in')}

        s._gpioOut = {"fuelPump": Gpio('fuel_pump', 21, 'out'),
                      "ignitionCoin": Gpio('ignition_coin', 17, 'out'),
                      "airFun": Gpio('air_fun', 20, 'out'),
                      "waterPump": Gpio('water_pump', 19, 'out'),
                      "funHeater": Gpio('fun_heater', 16, 'out'),
                      "mainPower": Gpio('main_power', 13, 'out')}


    def boiler_t(s):
        return s._boilerTermo.val()


    def retWater_t(s):
        return s._retTermo.val()


    def room_t(s):
        return s._roomTermo.val()


    def exhaustGas_t(s):
        return s._exhaustGasTermo.val()


    def isOverHearting(s):
        return not bool(s._gpioIn['overHearting'].value())


    def isHwEnabled(s):
        return not bool(s._gpioIn['hwEnable'].value())


    def isFlameBurning(s):
        return not bool(s._gpioIn['flameSensor'].value())


    def isPressureNormal(s):
        return not bool(s._gpioIn['pressureSensor'].value())


    def waterPumpEnable(s):
        s._gpioOut['waterPump'].setValue(1)


    def waterPumpDisable(s, timeout = 0):
        g = s._gpioOut['waterPump']
        g.setValue(1)
        if timeout:
            g.setValueTimeout(0, timeout)


    def isWaterPumpEnabled(s):
        return bool(s._gpioOut['waterPump'].value())


    def airFunEnable(s, timeout = 0):
        g = s._gpioOut['airFun']
        g.setValue(1)
        if timeout:
            g.setValueTimeout(0, timeout)


    def airFunDisable(s):
        s._gpioOut['airFun'].setValue(0)


    def isAirFunEnabled(s):
        return bool(s._gpioOut['airFun'].value())


    def fuelPumpEnable(s):
        s._gpioOut['fuelPump'].setValue(1)


    def fuelPumpDisable(s):
        s._gpioOut['fuelPump'].setValue(0)


    def isFuelPumpEnabled(s):
        return bool(s._gpioOut['fuelPump'].value())


    def funHeaterEnable(s, timeout):
        g = s._gpioOut['funHeater']
        g.setValue(1)
        if timeout:
            g.setValueTimeout(0, timeout)


    def funHeaterDisable(s):
        s._gpioOut['funHeater'].setValue(0)


    def isFunHeaterEnabled(s):
        return bool(s._gpioOut['funHeater'].value())


    def ignitionStart(s):
        s._gpioOut['ignitionCoin'].setValue(1)


    def ignitionStop(s):
        s._gpioOut['ignitionCoin'].setValue(0)


    def isIgnitionEnabled(s):
        return bool(s._gpioOut['ignitionCoin'].value())


    def mainPowerRelayEnable(s):
        s._gpioOut['mainPower'].setValue(1)


    def mainPowerRelayDisable(s):
        s._gpioOut['mainPower'].setValue(0)


    def isMainPowerRelayEnabled(s):
        return bool(s._gpioOut['mainPower'].value())


    def __str__(s):
        str = "Boiler temperature: %.1f\n" % s.boiler_t()
        str += "Return water temperature: %.1f\n" % s.retWater_t()
        str += "Room temperature: %.1f\n" % s.room_t()
        str += "Exchause Gas temperature: %.1f\n" % s.exhaustGas_t()

        str += "isOverHearting: %s\n" % s.isOverHearting()
        str += "isHwEnabled: %s\n" % s.isHwEnabled()
        str += "isFlameBurning: %s\n" % s.isFlameBurning()
        str += "isPressureNormal: %s\n" % s.isPressureNormal()

        str += "isWaterPumpEnabled: %s\n" % s.isWaterPumpEnabled()
        str += "isAirFunEnabled: %s\n" % s.isAirFunEnabled()
        str += "isFuelPumpEnabled: %s\n" % s.isFuelPumpEnabled()
        str += "isFunHeaterEnabled: %s\n" % s.isFunHeaterEnabled()
        str += "isIgnitionEnabled: %s\n" % s.isIgnitionEnabled()
        str += "isMainPowerRelayEnabled: %s\n" % s.isMainPowerRelayEnabled()
        return str


    def print(s):
        print(s.__str__())





