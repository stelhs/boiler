from Task import *
from HwIo import *
from Store import *
from Syslog import *
from Telegram import *
from HttpServer import *
from TimeCounter import *
import json



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
        s.httpServer.setReqCb("GET", "/boiler", s.httpReqStat)
        s.httpServer.setReqCb("GET", "/boiler/setup", s.httpReqSutup)
        s.httpServer.setReqCb("GET", "/boiler/start", s.httpReqStart)
        s.httpServer.setReqCb("GET", "/boiler/stop", s.httpReqStop)
        s.httpServer.setReqCb("GET", "/boiler/enable_power", s.httpReqEnablePower)
        s.httpServer.setReqCb("GET", "/boiler/enable_fun_heater", s.httpReqEnableFunHeater)
        s.httpServer.setReqCb("GET", "/boiler/disable_fun_heater", s.httpReqDisableFunHeater)
        s.io.setFunHeaterButtonCb(s.buttonFunHeaterCb)
        s.io.setHwEnableCb(s.hwEnableCb)
        s.lowReturnWater = False

        s._funHeaterEnable = False
        s._ioFunHeaterStopTriggering = False

        s.tcHeating = TimeCounter('heating_time')
        s._checkOverHeating = Observ(lambda: s.io.isOverHearting(), s.evOverHeating)
        s._checkWaterIsCold = Observ(lambda: s.returnWater_t, s.evWaterIsCold)
        s._checkWaterPressure = Observ(lambda: s.io.isPressureNormal(), s.evWaterPressure)
        s._checkDiffWater_t = Observ(lambda: (s.boiler_t - s.returnWater_t) > 1, s.evDiffWater_t, ignoreFirst=False)


        s.stopBoiler()
        s._task.start()
        s.telegram.send('Котёл перезапущен')


    def funHeaterEnable(s):
        s._funHeaterEnable = True
        if s.state == "HEATING":
            s.io.funHeaterEnable()


    def funHeaterDisable(s):
        s._funHeaterEnable = False
        s.io.funHeaterDisable()


    def isFunHeaterEnabled(s):
        return s._funHeaterEnable


    def buttonFunHeaterCb(s, state, prevState):
        if not (state == 0 and prevState == 1):
            return

        s.log.info('button Fun Heater is pressed')
        if s.isFunHeaterEnabled():
            s.funHeaterDisable()
        else:
            s.funHeaterEnable()


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
        errCnt = 0
        while(1):
            try:
                s.room_t = s.io.room_t()
                s.boiler_t = s.io.boiler_t()
                s.returnWater_t = s.io.retWater_t()
            except TermoSensor.TermoError as e:
                s.stopBoiler()
                s.telegram.send("Ошибка при получении температур: %s, Котёл остановлен" % e.args[1])

            if not s.room_t or not s.boiler_t or not s.returnWater_t:
                if errCnt > 5:
                    s.stopBoiler()
                    s.telegram.send("Датчики температур не работают: %s, Котёл остановлен" % e.args[1])

                errCnt += 1
                Task.sleep(500)
                continue

            s._checkOverHeating()
            s._checkWaterIsCold()
            s._checkWaterPressure()
            s._checkDiffWater_t()
            s.checkTermoSensors()

            if s.state == "WAITING":
                s.doWaiting()
            elif s.state == "HEATING":
                s.doHeating()

            Task.sleep(1000)


    def evOverHeating(s, isOverHearting):
        if not isOverHearting:
            return

        s.log.error("Over Heating!")
        msg = "Пропало питание, возможно перегрев котла!"
        if s.state != "STOPPED":
            s.stopBoiler()
            s.io.funHeaterEnable(5 * 60 * 1000)
            msg += " Котёл остановлен."

        s.telegram.send(msg)


    def evWaterIsCold(s, returnWater_t):
        if returnWater_t <= 3:
            s.telegram.send("Температура теплоносителя упала "
                            "до %.1f градусов!" % returnWater_t)
            s.log.error("returnWater_t failing down to %.1f degree" % returnWater_t)


    def evWaterPressure(s, isWaterPressureNormal):
        if isWaterPressureNormal:
            s.telegram.send("Давление в системе отопления восстановлено")
            s.log.info("Water pressure go to normal")
            return

        s.log.error("Falling water pressure")
        msg = "Упало давление в системе отопления!"
        if s.state != "STOPPED":
            s.stopBoiler()
            msg += " Котёл остановлен."
        s.telegram.send(msg)
        return


    def evDiffWater_t(s, result):
        if result:
            s.io.waterPumpEnable()
        else:
            s.io.waterPumpDisable()


    def checkTermoSensors(s):
        if s.state == "STOPPED":
            return

        if s.room_t < -10 or s.room_t > 30:
            s.log.error("termosensor room_t is not correct, %.1f degree." % s.room_t)
            s.telegram.send("Ошибка термодатчика room_t, "
                            "он показывает температуру: %.1f градусов. "
                            "Котёл остановлен." % s.room_t)
            s.stopBoiler()
            return

        if s.boiler_t < -1 or s.boiler_t > 120:
            s.log.error("termosensor boiler_t is not correct, %.1f degree." % s.room_t)
            s.telegram.send("Ошибка термодатчика boiler_t, "
                            "он показывает температуру: %.1f градусов. "
                            "Котёл остановлен." % s.boiler_t)
            s.stopBoiler()
            return

        if s.returnWater_t < -1 or s.returnWater_t > 120:
            s.log.error("termosensor returnWater_t is not correct, %.1f degree." % s.room_t)
            s.telegram.send("Ошибка термодатчика returnWater_t, "
                            "он показывает температуру: %.1f градусов. "
                            "Котёл остановлен." % s.boiler_t)
            s.stopBoiler()
            return



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


    def heatingTimeTotal(s):
        with s.store.lock:
            return s.store.tree['heating_time']


    def fuelConsumption(s):
        heatingTime = s.heatingTimeTotal()
        return heatingTime * 4.65 / 3600


    def energyConsumption(s):
        heatingTime = s.heatingTimeTotal()
        return heatingTime * 40 / 3600


    def ignitionCounter(s):
        with s.store.lock:
            return s.store.tree['ignition_counter']


    def saveHeatingTime(s):
        heatingTime = s.tcHeating.time()
        if heatingTime:
            with s.store.lock:
                s.store.tree['heating_time'] += heatingTime
                s.store.save()


    def startBoiler(s):
        if s.state != "STOPPED":
            s.log.error("Can't start boiler, boiler already was started")
            return False

        if not s.io.isHwEnabled():
            s.log.error("Can't start boiler, HW power is not present")
            return False

        if not s.io.isPressureNormal():
            s.log.error("Can't start boiler, No water pressure")
            return False


        s.state = "WAITING"
        s.log.info("boiler started")
        s.telegram.send("Котёл включен")
        return True


    def stopBoiler(s):
        s.log.info("boiler stopped")

        if s.state == "HEATING":
            s.stopHeating()

        if s.io.isFuelPumpEnabled():
            s.io.fuelPumpDisable()

        s.io.ignitionRelayDisable()
        s.io.funHeaterDisable()
        s.tcHeating.stop()
        s.saveHeatingTime()
        if s.io.isAirFunEnabled():
            s.io.airFunEnable(10000)
        else:
            s.io.airFunDisable()

        s.state = "STOPPED"


    def startHeating(s):
        if s.state != "WAITING":
            s.log.debug("can't start heating from '%s' state" % s.state)
            return False

        s.log.info("start heating")

        if s.io.isFlameBurning():
            s.log.info("flame is burning, heating already started")
            return False

        s.io.airFunEnable()
        Task.sleep(5000)

        for attemptCnt in range(10):
            s.io.ignitionRelayEnable()
            s.io.fuelPumpEnable()
            Task.sleep(500)
            success = False
            if not s.fake:
                for attempt in range(3):
                    if s.io.isFlameBurning():
                        s.log.debug("flame is started at attempt %d" % attempt)
                        success = True
                        break
                    s.log.error("flame is not burning at attempt %d" % attempt)
                    Task.sleep(1000)
                s.io.ignitionRelayDisable();

            if success:
                break

            if not success and not s.fake:
                s.log.error("can't burn flame, attemptCnt: %d" % attemptCnt)
                s.io.ignitionRelayDisable()
                s.io.fuelPumpDisable()
                s.telegram.send("Не удалось зажечь пламя, попытка: %d" % attemptCnt)
                Task.sleep(3000)
        else:
            s.log.error("Can't start heating. All attempts were exhausted.")
            s.telegram.send("Не удалось зажечь пламя, все попытки исчерпаны. Котёл остановлен.")
            s.stopBoiler()
            return False


        if s._funHeaterEnable:
            s.io.funHeaterEnable()

        s.state = "HEATING"
        s.tcHeating.start()
        with s.store.lock:
            s.store.tree['ignition_counter'] += 1
            s.store.save()
        return True


    def stopHeating(s):
        s.log.info("stop heating")
        s.io.fuelPumpDisable()
        s.tcHeating.stop()
        s.saveHeatingTime()
        s.io.airFunEnable(5000)


    def doWaiting(s):
        if s.boiler_t <= s.targetBoilerMin_t() and s.room_t < s.targetRoom_t():
            s._ioFunHeaterStopTriggering = False
            s.startHeating()
            return

        if s.room_t >= s.targetRoom_t():
            if s._funHeaterEnable and not s._ioFunHeaterStopTriggering:
                s.io.funHeaterEnable(30000)
                s._ioFunHeaterStopTriggering = True


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

        if not s.io.isFlameBurning():
            s.log.error("the flame went out!")
            s.telegram.send("Пламя в котле самопроизвольно погасло!")
            s.tcHeating.stop()
            s.state = "WAITING"
            return False


    def httpReqStat(s, args, body):
        data = {}
        data['state'] = s.state
        data['target_boiler_t_max'] = s.targetBoilerMax_t()
        data['target_boiler_t_min'] = s.targetBoilerMin_t()
        data['total_heating_time'] = s.heatingTimeTotal()
        data['total_fuel_consumption'] = s.fuelConsumption()
        data['total_energy_consumption'] = s.energyConsumption()
        data['ignition_counter'] = s.ignitionCounter()

        if s.state != "STOPPED":
            data['current_boiler_t'] = s.boiler_t
            data['current_return_water_t'] = s.returnWater_t
            data['target_room_t'] = s.targetRoom_t()
            data['current_room_t'] = s.room_t
            data['current_heating_time'] = s.tcHeating.time()
            data['fun_heater_is_enabled'] = s.isFunHeaterEnabled()

        return json.dumps(data)


    def httpReqSutup(s, args, body):
        if not args:
            return json.dumps({"status": "error",
                               "reason": "incorrect arguments"})

        if 'target_boiler_t_max' in args:
            s.setTargetBoilerMax_t(args['target_boiler_t_max'])

        if 'target_boiler_t_min' in args:
            s.setTargetBoilerMin_t(args['target_boiler_t_min'])

        if 'target_room_t' in args:
            s.setTargetRoom_t(args['target_room_t'])

        return json.dumps({"status": "ok"})


    def httpReqStart(s, args, body):
        rc = s.startBoiler()
        if not rc:
            return json.dumps({"status": "error",
                               "reason": "boiler already was started"})
        s.telegram.send('Котёл запущен по REST запросу')
        return json.dumps({"status": "ok"})


    def httpReqStop(s, args, body):
        s.stopBoiler()
        s.telegram.send('Котёл остановлен по REST запросу')
        return json.dumps({"status": "ok"})


    def httpReqEnablePower(s, args, body):
        s.enableMainPower()
        s.telegram.send('Произведена попытка включения питания котла по REST запросу')
        return json.dumps({"status": "ok"})


    def httpReqEnableFunHeater(s, args, body):
        s.telegram.send('Тепло-вентилятор включен по REST запросу')
        s.funHeaterEnable()
        return json.dumps({"status": "ok"})


    def httpReqDisableFunHeater(s, args, body):
        s.funHeaterDisable()
        s.telegram.send('Тепло-вентилятор отключен по REST запросу')
        return json.dumps({"status": "ok"})



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
            str += "total energy consumption: %.3f kW*h\n" % s.energyConsumption()
            str += "ignition counter: %d\n" % s.ignitionCounter()
            str += "fun heater: %s\n" % s.isFunHeaterEnabled()

        return str


    def print(s):
        print(s.__str__())






class Observ():
    def __init__(s, condCb, enentCb, ignoreFirst=True):
        s.condCb = condCb
        s.enentCb = enentCb
        s.state = None
        s.first = True
        s.ignoreFirst = ignoreFirst


    def __call__(s):
        val = s.condCb()
        if s.first and s.ignoreFirst:
            s.state = val
            s.first = False
            return

        if val == s.state:
            return
        s.state = val
        s.enentCb(val)

