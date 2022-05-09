from TermoSensor import *
from Gpio import *


class HwIo():
    def __init__(s):
        s.hwEventsCb = None
        if os.path.isdir("FAKE"):
            Gpio.gpioMode = 'fake'
            TermoSensor.sensorMode = 'fake'

        s._boilerTermo = TermoSensor("28-012033e26477", "boiler")
        s._retTermo = TermoSensor("28-012033e45839", "return_water")
        s._roomTermo = TermoSensor("28-012033f3fd8f", "room")
        s._boilerInside = TermoSensor("28-012033f9c648", "boiler_inside")
#        s._exhaustGasTermo = TermoSensor("28-012033f9c640", "exhaust_gas")


        s._gpioIn = {"overHearting": Gpio(8, 'over_heating', 'in'),
                     "hwEnable": Gpio(9, 'hw_enable', 'in'),
                     "flameSensor": Gpio(23, 'flame_sensor', 'in'),
                     "pressureSensor": Gpio(10, 'pressure_sensor', 'in')}

        s._gpioOut = {"fuelPump": Gpio(21, 'fuel_pump', 'out'),
                      "ignitionCoin": Gpio(17, 'ignition_coin', 'out'),
                      "airFun": Gpio(20, 'air_fun', 'out'),
                      "waterPump": Gpio(19, 'water_pump', 'out'),
                      "funHeater": Gpio(16, 'fun_heater', 'out'),
                      "mainPower": Gpio(13, 'main_power', 'out')}

        s.log = Syslog('HwIo')
        Gpio.startEvents()

        s.airFunDisable()
        s.ignitionRelayDisable()
        s.funHeaterDisable()
        s.fuelPumpDisable()



    def setHwEnableCb(s, cb):
        s._gpioIn['hwEnable'].setEventCb(cb)


    def setHwEventsCb(s, cb):
        s.hwEventsCb = cb


    def setFlameBurningCb(s, cb):
        s._gpioIn['flameSensor'].setEventCb(cb)


    def boiler_t(s):
        return s._boilerTermo.t()


    def retWater_t(s):
        return s._retTermo.t()


    def room_t(s):
        return s._roomTermo.t()


    def boilerInside_t(s):
        return s._boilerInside.t()


    def exhaustGas_t(s):
        return 0
        #return s._exhaustGasTermo.t()


    def isOverHearting(s):
        return bool(s._gpioIn['overHearting'].value())


    def isHwEnabled(s):
        return not bool(s._gpioIn['hwEnable'].value())


    def isFlameBurning(s):
        return not bool(s._gpioIn['flameSensor'].value())


    def isPressureNormal(s):
        return bool(s._gpioIn['pressureSensor'].value())


    def waterPumpEnable(s, timeout = 0):
        g = s._gpioOut['waterPump']
        g.setValue(1)
        s.log.info('water pump enable')
        if s.hwEventsCb:
            s.hwEventsCb()
        if timeout:
            s.log.info('water pump will disabled by timeout %dmS' % timeout)
            g.setValueTimeout(0, timeout)


    def waterPumpDisable(s):
        s._gpioOut['waterPump'].setValue(0)
        s.log.info('water pump disable')
        if s.hwEventsCb:
            s.hwEventsCb()


    def isWaterPumpEnabled(s):
        return bool(s._gpioOut['waterPump'].value())


    def airFunEnable(s, timeout = 0):
        g = s._gpioOut['airFun']
        g.setValue(1)
        if timeout:
            s.log.info('air fun enable, timeout = %d' % timeout)
        else:
            s.log.info('air fun enable')

        if s.hwEventsCb:
            s.hwEventsCb()
        if timeout:
            s.log.info('air fun disabled by timeout %dmS' % timeout)
            g.setValueTimeout(0, timeout)


    def airFunDisable(s):
        s._gpioOut['airFun'].setValue(0)
        s.log.info('air fun disable')
        if s.hwEventsCb:
            s.hwEventsCb()


    def isAirFunEnabled(s):
        return bool(s._gpioOut['airFun'].value())


    def fuelPumpEnable(s):
        s._gpioOut['fuelPump'].setValue(1)
        s.log.info('fuel pump enable')
        if s.hwEventsCb:
            s.hwEventsCb()


    def fuelPumpDisable(s):
        s._gpioOut['fuelPump'].setValue(0)
        s.log.info('fuel pump disable')
        if s.hwEventsCb:
            s.hwEventsCb()


    def isFuelPumpEnabled(s):
        return bool(s._gpioOut['fuelPump'].value())


    def funHeaterEnable(s, timeout = 0):
        g = s._gpioOut['funHeater']
        g.setValue(1)
        s.log.info('fun heater enable')
        if s.hwEventsCb:
            s.hwEventsCb()
        if timeout:
            s.log.info('fun heater disabled by timeout %dmS' % timeout)
            g.setValueTimeout(0, timeout)


    def funHeaterDisable(s):
        s._gpioOut['funHeater'].setValue(0)
        s.log.info('fun heater disable')
        if s.hwEventsCb:
            s.hwEventsCb()


    def isFunHeaterEnabled(s):
        return bool(s._gpioOut['funHeater'].value())


    def ignitionRelayEnable(s):
        s._gpioOut['ignitionCoin'].setValue(1)
        s.log.info('ignition relay enable')
        if s.hwEventsCb:
            s.hwEventsCb()


    def ignitionRelayDisable(s):
        s._gpioOut['ignitionCoin'].setValue(0)
        s.log.info('ignition relay disable')
        if s.hwEventsCb:
            s.hwEventsCb()


    def isIgnitionRelayEnabled(s):
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
        str += "Boiler inside temperature: %.1f\n" % s.boilerInside_t()
        str += "Exchause Gas temperature: %.1f\n" % s.exhaustGas_t()

        str += "isOverHearting: %s\n" % s.isOverHearting()
        str += "isHwEnabled: %s\n" % s.isHwEnabled()
        str += "isFlameBurning: %s\n" % s.isFlameBurning()
        str += "isPressureNormal: %s\n" % s.isPressureNormal()

        str += "isWaterPumpEnabled: %s\n" % s.isWaterPumpEnabled()
        str += "isAirFunEnabled: %s\n" % s.isAirFunEnabled()
        str += "isFuelPumpEnabled: %s\n" % s.isFuelPumpEnabled()
        str += "isFunHeaterEnabled: %s\n" % s.isFunHeaterEnabled()
        str += "isIgnitionRelayEnabled: %s\n" % s.isIgnitionRelayEnabled()
        str += "isMainPowerRelayEnabled: %s\n" % s.isMainPowerRelayEnabled()
        return str


    def print(s):
        print(s.__str__())





