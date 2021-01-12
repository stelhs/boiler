from math import *
import rlcompleter, readline
readline.parse_and_bind('tab:complete')
import enum

from Task import *
from Gpio import *
from Termo import *
from Store import *
from Syslog import *


class Boiler(Task):
    # states:
    #   SOFT_DISABLED
    #   WAITING
    #   HEATING
    state = "SOFT_DISABLED"

    def __init__(s):
        Task.__init__(s, "boiler")

        if os.path.exists("FAKE"):
            Gpio.gpioMode = 'fake'
            Termo.sensorMode = 'fake'

        s._listGpioInputs = (Gpio('over_heating', 8, 'in'),
                             Gpio('hw_enable', 9, 'in'),
                             Gpio('flame_sensor', 23, 'in'),
                             Gpio('pressure_sensor', 10, 'in'),
                             Gpio('fan_heater_switch', 24, 'in'))

        s._relays = {"fuelPump": Gpio('fuel_pump', 21, 'out'),
                     "ignitionCoin": Gpio('ignition_coin', 17, 'out'),
                     "airFun": Gpio('air_fun', 20, 'out'),
                     "waterPump": Gpio('water_pump', 19, 'out'),
                     "funHeater": Gpio('fun_heater', 16, 'out'),
                     "mainPower": Gpio('main_power', 13, 'out')}

        s.gpioEventTask = GpioEventsTask(s._listGpioInputs, s.gpioChanged)
        s._gpioOverHeating = Gpio.gpioByName("over_heating")
        s._gpioFlameSensor = Gpio.gpioByName("flame_sensor")

        s._termoSensors = TermoSensors()
        s._store = Store()
        s.log = Syslog("main")


    def do(s):
        while(1):
            try:
                s.room_t = s._termoSensors.room_t()
                s.boiler_t = s._termoSensors.boiler_t()
                s.returnWater_t = s._termoSensors.ret_t()
            except Termo.TermoError as e:
                printToTelegram("Не удалось получить температуру: %s" % e.args[1])
                s.stopBoiler()


            s.checkOverHeating()

            if s.state == "WAITING":
                doWaiting()
            elif s.state == "HEATIMG":
                doHeating()

            Task.sleep(1000)


    def gpioChanged(s, gpio, val):
        print("changed gpio %d to val %d" % (gpio.num(), val))


    def checkOverHeating(s):
        val = s._gpioOverHeating.value()
        if val == 1: #if normal
            return

        s.log.error("Over Heating!")
        printToTelegram("Перегрев котла!")

        s.stopBoiler()
        s.funHeaterEnable(5 * 60 * 1000)


    def targetRoom_t(s):
        return s._store.tree['target_room_t']


    def setTargetRoom_t(s, t):
        s._store.tree['target_room_t'] = t
        s._store.save()


    def targetBoilerMin_t(s):
        return s._store.tree['target_boiler_min_t']


    def setTargetBoilerMin_t(s, t):
        s._store.tree['target_boiler_min_t'] = t
        s._store.save()


    def targetBoilerMax_t(s):
        return s._store.tree['target_boiler_max_t']


    def setTargetBoilerMax_t(s, t):
        s._store.tree['target_boiler_max_t'] = t
        s._store.save()


    def waterPumpEnable(s):
        s._relays['waterPump'].setValue(1)


    def waterPumpDisable(s):
        s._relays['waterPump'].setValue(0)


    def isWaterPumpEnabled(s):
        return s._relays['waterPump'].value()


    def airFunEnable(s, timeout = 0):
        s._relays['airFun'].setValue(1)
        if timeout:
            s._relays['airFun'].setValueTimeout(0, timeout)


    def airFunDisable(s):
        s._relays['airFun'].setValue(0)


    def isAirFunEnabled(s):
        return s._relays['airFun'].value()


    def fuelPumpEnable(s):
        s._relays['fuelPump'].setValue(1)


    def fuelPumpDisable(s):
        s._relays['fuelPump'].setValue(0)


    def isFuelPumpEnabled(s):
        return s._relays['fuelPump'].value()


    def funHeaterEnable(s, timeout):
        s._relays['funHeater'].setValue(1)
        if timeout:
            s._relays['funHeater'].setValueTimeout(0, timeout)


    def funHeaterDisable(s):
        s._relays['funHeater'].setValue(0)


    def isFunHeaterEnabled(s):
        return s._relays['funHeater'].value()


    def ignitionStart(s):
        s._relays['ignitionCoin'].setValue(1)


    def ignitionStop(s):
        s._relays['ignitionCoin'].setValue(0)


    def enableMainPower(s):
        s._relays['mainPower'].setValue(1)
        s._relays['mainPower'].setValueTimeout(0, 500)


    def isFlameBurning(s):
        return not s._gpioFlameSensor.value()


    def startBoiler(s):
        s.state = "WAITING"
        s.log.info("boiler started")
        printToTelegram("Котёл запущен")
        s.start()


    def stopBoiler(s):
        s.state = "SOFT_DISABLED"
        s.log.info("boiler stopped")
        printToTelegram("Котёл остановлен")

        s.ignitionStop()
        s.funHeaterDisable()

        if s.isFuelPumpEnabled():
            s.fuelPumpDisable()
            s.log.info("air fun will stoped by timeout")
            s.airFunEnable(5000)
            s.waterPumpDisable(5 * 60 * 1000)
            return

        s.airFunDisable(10000)
        s.waterPumpDisable()
        s.stop()


    def startHeating(s):
        s.log.info("start heating")

        if s.isFlameBurning():
            s.log.info("flame is burning, heating already started")
            return False

        s.airFunEnable()
        Task.sleep(5000)

        s.fuelPumpEnable()
        Task.sleep(500)

        success = False
        s.ignitionStart()
        for attempt in range(3):
            if s.isFlameBurning():
                s.log.debug("flame is started at attempt %d" % attempt)
                success = True
                break
            s.log.error("flame is not burning at attempt %d" % attempt)
            Task.sleep(1000)

        s.ignitionStop();
        return success


    def doWaiting(s):
        if s.room_t >= s.targetRoom_t():
            if not s.isWaterPumpEnabled():
                return

            diff_t = s.boiler_t - s.returnWater_t
            if diff_t < 5:
                s.log.info("water pump was disabled, boiler_t = %.1f, returnWater_t = %.1f" %
                            (s.boiler_t, s.returnWater_t))
                s.waterPumpDisable()
            return

        if s.boiler_t >= s.targetBoilerMin_t():
            return

        s.waterPumpEnable();
        rc = s.startHeating()
        if not rc:
            s.log.error("can't burn flame")
            printToTelegram("Не удалось зажечь пламя")
            s.stopBoiler()

        s.state = "HEATING"


    def stopHeating(s):
        s.log.info("stop heating")
        s.fuelPumpDisable()
        s.airFunEnable(5000)


    def doHeating(s):
        if s.boiler_t < targetBoilerMax_t():
            return

        stop_heating()
        s.state = WAITING


    def __str__(s):
        return "Boiler state: %s" % (s.state)


boiler = Boiler()




