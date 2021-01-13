from Task import *
from HwIo import *
from Store import *
from Syslog import *


class Boiler(Task):
    # states:
    #   SOFT_DISABLED
    #   WAITING
    #   HEATING
    state = "SOFT_DISABLED"

    fake = False

    def __init__(s):
        Task.__init__(s, "boiler")

        if os.path.exists("FAKE"):
            s.fake = True

        s.io = HwIo()
        s._store = Store()
        s.log = Syslog("main")


    def do(s):
        while(1):
            try:
                s.room_t = s.io.room_t()
                s.boiler_t = s.io.boiler_t()
                s.returnWater_t = s.io.retWater_t()
            except TermoSensor.TermoError as e:
                printToTelegram("Не удалось получить температуру: %s" % e.args[1])
                s.stopBoiler()


            s.checkOverHeating()

            if s.state == "WAITING":
                doWaiting()
            elif s.state == "HEATIMG":
                doHeating()

            Task.sleep(1000)


    def checkOverHeating(s):
        if not s.io.isOverHearting():
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


    def enableMainPower(s):
        if s.io.isHwEnabled():
            return True

        s.io.mainPowerRelayEnable()
        s.sleep(500)
        s.io.mainPowerRelayDisable()
        s.sleep(500)
        if not s.io.isHwEnabled():
            s.log.error("can't enableMainPower() because HW power is absent")
            return False

        return True


    def startBoiler(s):
        ret = s.enableMainPower()
        if not ret:
            s.log.error("can't start boiler")
            return False

        s.state = "WAITING"
        s.log.info("boiler started")
        printToTelegram("Котёл запущен")
        s.start()
        return True


    def stopBoiler(s):
        s.state = "SOFT_DISABLED"
        s.log.info("boiler stopped")
        printToTelegram("Котёл остановлен")

        s.io.ignitionStop()
        s.io.funHeaterDisable()

        if s.io.isFuelPumpEnabled():
            s.io.fuelPumpDisable()
            s.log.info("air fun will stoped by timeout")
            s.io.airFunEnable(5000)
            s.io.waterPumpDisable(5 * 60 * 1000)
            return

        s.io.airFunDisable(10000)
        s.io.waterPumpDisable()
        s.stop()


    def startHeating(s):
        s.log.info("start heating")

        if s.io.isFlameBurning():
            s.log.info("flame is burning, heating already started")
            return False

        s.io.airFunEnable()
        s.sleep(5000)

        s.io.fuelPumpEnable()
        s.sleep(500)

        success = False
        s.io.ignitionStart()
        for attempt in range(3):
            if s.io.isFlameBurning():
                s.log.debug("flame is started at attempt %d" % attempt)
                success = True
                break
            s.log.error("flame is not burning at attempt %d" % attempt)
            Task.sleep(1000)

        s.io.ignitionStop();
        return success


    def doWaiting(s):
        if s.room_t >= s.targetRoom_t():
            if not s.io.isWaterPumpEnabled():
                return

            diff_t = s.boiler_t - s.returnWater_t
            if diff_t < 5:
                s.log.info("water pump was disabled, boiler_t = %.1f, returnWater_t = %.1f" %
                            (s.boiler_t, s.returnWater_t))
                s.io.waterPumpDisable()
            return

        if s.boiler_t >= s.targetBoilerMin_t():
            return

        s.io.waterPumpEnable();
        rc = s.startHeating()
        if not rc:
            s.log.error("can't burn flame")
            printToTelegram("Не удалось зажечь пламя")
            s.stopBoiler()

        s.state = "HEATING"


    def stopHeating(s):
        s.log.info("stop heating")
        s.io.fuelPumpDisable()
        s.io.airFunEnable(5000)


    def doHeating(s):
        if s.boiler_t < targetBoilerMax_t():
            return

        s.stopHeating()
        s.state = WAITING


    def __str__(s):
        return "%s, Boiler state: %s" % (super().__str__(), s.state)
