from Task import *
from HwIo import *
from Store import *
from Syslog import *
from Telegram import *
from HttpServer import *
from TimeCounter import *


class Boiler():
    # states:
    #   STOPPED
    #   WAITING
    #   HEATING
    state = "STOPPED"

    fake = False

    def __init__(s):
        if os.path.isdir("FAKE"):
            s.fake = True

        s.io = HwIo()
        s.store = Store()
        s.log = Syslog("boiler")
        s._task = Task('boiler')
        s._task.setCb(s.doTask)
        s.telegram = Telegram('boiler')
        s.httpServer = HttpServer('127.0.0.1', 8890)
        s.httpServer.setReqCb("GET", "/stat", s.httpReqStat)
        s.io.setFunHeaterButtonCb(s.buttonFunHeaterCb)
        s.io.setHwEnableCb(s.hwEnableCb)
        s.lowReturnWater = False

        s.tcHeating = TimeCounter('heating_time')

        s.stopBoiler()
        s.telegram.send('Котёл перезапущен')




    def buttonFunHeaterCb(s, state, prevState):
        if not (state == 0 and prevState == 1):
            return

        s.log.info('button Fun Heater is pressed')
        if s.io.isFunHeaterEnabled():
            s.io.funHeaterDisable()
        else:
            s.io.funHeaterEnable()


    def hwEnableCb(s, state, prevState):
        if state == 0 and prevState == 1:
            s.log.info('HW power is enabled')
            s.startBoiler()
            return

        if state == 1 and prevState == 0:
            s.log.info('HW power is disabled')
            if s.state == "STOPPED":
                return

            s.stopBoiler()
            s.telegram.send('Котёл остановлен по нажатию на кнопку Стоп')



    def doTask(s):
        while(1):
            try:
                s.room_t = s.io.room_t()
                s.boiler_t = s.io.boiler_t()
                s.returnWater_t = s.io.retWater_t()
            except TermoSensor.TermoError as e:
                s.stopBoiler()
                s.telegram.send("Не удалось получить температуру: %s, Котёл остановлен" % e.args[1])

            s.checkOverHeating()

            if s.returnWater_t <= 3 and not s.lowReturnWater:
                s.telegram.send("Температура теплоносителя упала "
                                "до %.1f градусов!" % s.returnWater_t)
                s.log.error("returnWater_t failing down to %.1f degree" % s.returnWater_t)
                s.lowReturnWater = True

            if s.returnWater_t > 3 and s.lowReturnWater:
                s.lowReturnWater = False


            if s.state == "WAITING":
                s.doWaiting()
            elif s.state == "HEATING":
                s.doHeating()

            Task.sleep(1000)


    def checkOverHeating(s):
        if not s.io.isOverHearting():
            return

        s.log.error("Over Heating!")
        s.telegram.send("Перегрев котла! Всё остановлено")

        s.stopBoiler()
        s.io.funHeaterEnable(5 * 60 * 1000)


    def targetRoom_t(s):
        with s.store.lock:
            return float(s.store.tree['target_room_t'])


    def setTargetRoom_t(s, t):
        with s.store.lock:
            s.store.tree['target_room_t'] = str(t)
            s.store.save()


    def targetBoilerMin_t(s):
        with s.store.lock:
            return float(s.store.tree['target_boiler_min_t'])


    def setTargetBoilerMin_t(s, t):
        with s.store.lock:
            s.store.tree['target_boiler_min_t'] = str(t)
            s.store.save()


    def targetBoilerMax_t(s):
        with s.store.lock:
            return float(s.store.tree['target_boiler_max_t'])


    def setTargetBoilerMax_t(s, t):
        with s.store.lock:
            s.store.tree['target_boiler_max_t'] = str(t)
            s.store.save()


    def enableMainPower(s):
        s.io.mainPowerRelayEnable()
        Task.sleep(500)
        s.io.mainPowerRelayDisable()


    def startBoiler(s):
        if s.state != "STOPPED":
            s.log.debug("Can't start boiler, boiler already was started")
            return

        s.state = "WAITING"
        s.log.info("boiler started")
        s._task.start()
        s.telegram.send("Котёл включен")
        return True



    def heatingTimeTotal(s):
        with s.store.lock:
            heatingTime = s.store.tree['heating_time']
        return heatingTime + s.tcHeating.time()


    def fuelConsumption(s):
        heatingTime = s.heatingTimeTotal()
        return heatingTime * 4.65 / 3600


    def ignitionCounter(s):
        with s.store.lock:
            return s.store.tree['ignition_counter']


    def saveHeatingTime(s):
        heatingTime = s.tcHeating.time()
        if heatingTime:
            with s.store.lock:
                s.store.tree['heating_time'] += heatingTime
                s.store.save()


    def stopBoiler(s):
        s.log.info("boiler stopped")

        s.io.ignitionRelayDisable()
        s.io.funHeaterDisable()
        s.tcHeating.stop()
        s.saveHeatingTime()

        if s.io.isFuelPumpEnabled():
            s.io.fuelPumpDisable()
            s.log.info("air fun will stoped by timeout")
            s.io.airFunEnable(5000)
            s.io.waterPumpEnable(5 * 60 * 1000)
            return

        s.io.airFunEnable(10000)
        s.io.waterPumpDisable()
        s._task.stop()

        s.state = "STOPPED"
        s._timeHeatingStart = None


    def startHeating(s):
        if s.state != "WAITING":
            s.log.debug("can't start heating from '%s' state" % s.state)
            return

        s.log.info("start heating")

        if s.io.isFlameBurning():
            s.log.info("flame is burning, heating already started")
            return False

        s.io.waterPumpEnable();
        s.io.airFunEnable()
        Task.sleep(5000)

        s.io.fuelPumpEnable()
        Task.sleep(500)

        success = False
        if not s.fake:
            s.io.ignitionRelayEnable()
            for attempt in range(3):
                if s.io.isFlameBurning():
                    s.log.debug("flame is started at attempt %d" % attempt)
                    success = True
                    break
                s.log.error("flame is not burning at attempt %d" % attempt)
                Task.sleep(1000)
            s.io.ignitionRelayDisable();

        if not success and not s.fake:
            s.log.error("can't burn flame")
            s.stopBoiler()
            s.telegram.send("Не удалось зажечь пламя, котёл остановлен")
            return

        s.state = "HEATING"
        s.tcHeating.start()
        with s.store.lock:
            s.store.tree['ignition_counter'] += 1
            s.store.save()



    def doWaiting(s):
        if s.boiler_t <= s.targetBoilerMin_t() and s.room_t < s.targetRoom_t():
            s.startHeating()
            return

        if s.room_t >= s.targetRoom_t() and s.io.isWaterPumpEnabled():
            diff_t = s.boiler_t - s.returnWater_t
            if diff_t < 3:
                s.log.info("water pump was STOPPED, boiler_t = %.1f, returnWater_t = %.1f" %
                            (s.boiler_t, s.returnWater_t))
                s.io.waterPumpDisable()
            return


    def stopHeating(s):
        s.log.info("stop heating")
        s.tcHeating.stop()
        s.saveHeatingTime()
        s.io.fuelPumpDisable()
        s.io.airFunEnable(5000)


    def doHeating(s):
        if s.tcHeating.time() > 10 * 60 and s.boiler_t < 30:
            s.tcHeating.stop()
            s.stopBoiler()
            s.log.error("Boiler stopped by timeout. boiler t: %.1f, "
                        "heating time: %d" % (s.boiler_t, s.tcHeating.time()))
            s.telegram.send("Котёл работает более %d секунд а температура в котле "
                            "так и не превысила 30 градусов. "
                            "Котёл остановлен." % s.tcHeating.time())
            return


        if s.boiler_t >= s.targetBoilerMax_t() or s.room_t >= s.targetRoom_t():
            s.stopHeating()
            s.state = "WAITING"
            if s.room_t < s.targetRoom_t() and s.tcHeating.time() < 60:
                s.tcHeating.stop()
                s.stopBoiler()
                s.log.error("The boiler has reached the temperature %.1f "
                            "is very too quickly" % s.targetBoilerMax_t())
                s.telegram.send("Котёл набрал температуру до %.1f градусов "
                                "слишком быстро (за %d секунд), "
                                "Котёл остановлен." % (s.targetBoilerMax_t(),
                                                       s.tcHeating.time()))


    def httpReqStat(s, args, body):
        return "Good!!!"


    def __str__(s):
        str = "Boiler state: %s\n" % s.state
        if s.state != "STOPPED":
            str += "target boiler t max: %.1f\n" % s.targetBoilerMax_t()
            str += "target boiler t min: %.1f\n" % s.targetBoilerMin_t()
            str += "current boiler t: %.1f\n" % s.boiler_t
            str += "current return water t: %.1f\n" % s.returnWater_t
            str += "target room t: %.1f\n" % s.targetRoom_t()
            str += "current room t: %.1f\n" % s.room_t
            str += "current heating time: %d sec\n" % s.tcHeating.time()
            str += "total heating time: %d sec\n" % s.heatingTimeTotal()
            str += "total fuel consumption: %.3f liters\n" % s.fuelConsumption()
            str += "ignition counter: %d\n" % s.ignitionCounter()

        return str


    def print(s):
        print(s.__str__())
