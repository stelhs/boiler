from TermoSensor import *
from Gpio import *


class HwIo():
    def __init__(s):
        if os.path.isdir("FAKE"):
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

        s.log = Syslog('HwIo')


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


    def waterPumpEnable(s, timeout = 0):
        g = s._gpioOut['waterPump']
        g.setValue(1)
        s.log.info('water pump enable')
        if timeout:
            s.log.info('water pump will disabled by timeout %dmS' % timeout)
            g.setValueTimeout(0, timeout)


    def waterPumpDisable(s):
        s._gpioOut['waterPump'].setValue(0)
        s.log.info('water pump disable')


    def isWaterPumpEnabled(s):
        return bool(s._gpioOut['waterPump'].value())


    def airFunEnable(s, timeout = 0):
        g = s._gpioOut['airFun']
        g.setValue(1)
        s.log.info('air fun enable')
        if timeout:
            s.log.info('air fun disabled by timeout %dmS' % timeout)
            g.setValueTimeout(0, timeout)


    def airFunDisable(s):
        s._gpioOut['airFun'].setValue(0)
        s.log.info('air fun disable')


    def isAirFunEnabled(s):
        return bool(s._gpioOut['airFun'].value())


    def fuelPumpEnable(s):
        s._gpioOut['fuelPump'].setValue(1)
        s.log.info('fuel pump enable')


    def fuelPumpDisable(s):
        s._gpioOut['fuelPump'].setValue(0)
        s.log.info('fuel pump disable')


    def isFuelPumpEnabled(s):
        return bool(s._gpioOut['fuelPump'].value())


    def funHeaterEnable(s, timeout):
        g = s._gpioOut['funHeater']
        g.setValue(1)
        s.log.info('fun heater enable')
        if timeout:
            s.log.info('fun heater disabled by timeout %dmS' % timeout)
            g.setValueTimeout(0, timeout)


    def funHeaterDisable(s):
        s._gpioOut['funHeater'].setValue(0)
        s.log.info('fun heater disable')


    def isFunHeaterEnabled(s):
        return bool(s._gpioOut['funHeater'].value())


    def ignitionStart(s):
        s._gpioOut['ignitionCoin'].setValue(1)
        s.log.info('ignition start')


    def ignitionStop(s):
        s._gpioOut['ignitionCoin'].setValue(0)
        s.log.info('ignition stop')


    def isIgnitionEnabled(s):
        return bool(s._gpioOut['ignitionCoin'].value())


    def mainPowerRelayEnable(s):
        s._gpioOut['mainPower'].setValue(1)
        s.log.info('main power relay enable')


    def mainPowerRelayDisable(s):
        s._gpioOut['mainPower'].setValue(0)
        s.log.info('main power relay disable')


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





