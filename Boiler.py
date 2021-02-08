from Task import *
from HwIo import *
from Store import *
from Syslog import *
from Telegram import *
from HttpServer import *
from TimeCounter import *
from Integrator import *
import threading
import json
import os, re
import datetime


class Boiler():
    # states:
    #   STOPPED
    #   WAITING
    #   IGNITING
    #   HEATING
    _state = "STOPPED"

    fake = False

    def __init__(s):
        if os.path.isdir("FAKE"):
            s.fake = True

        s.lock = threading.Lock()
        s.io = HwIo()
        s.store = Store()
        s.log = Syslog("boiler")
        s.task = Task('boiler')
        s.task.setCb(s.doTask)
        s.telegram = Telegram('boiler')
        s.httpServer = HttpServer('0.0.0.0', 8890)
        s.httpServer.setReqCb("GET", "/boiler", s.httpReqStat)
        s.httpServer.setReqCb("GET", "/stat", s.httpReqSbioStat)
        s.httpServer.setReqCb("GET", "/boiler/reset_stat", s.httpReqResetStat)
        s.httpServer.setReqCb("GET", "/boiler/setup", s.httpReqSutup)
        s.httpServer.setReqCb("GET", "/boiler/start", s.httpReqStart)
        s.httpServer.setReqCb("GET", "/boiler/stop", s.httpReqStop)
        s.httpServer.setReqCb("GET", "/boiler/enable_power", s.httpReqEnablePower)
        s.httpServer.setReqCb("GET", "/boiler/enable_fun_heater", s.httpReqEnableFunHeater)
        s.httpServer.setReqCb("GET", "/boiler/disable_fun_heater", s.httpReqDisableFunHeater)
        s.io.setFunHeaterButtonCb(s.buttonFunHeaterCb)
        s.io.setHwEnableCb(s.hwEnableCb)
        s.lowReturnWater = False

        s._ignitTask = None

        s.tcBurning = TimeCounter('burning_time')
        s._checkOverHeating = Observ(lambda: s.io.isOverHearting(), s.evOverHeating)
        s._checkWaterIsCold = Observ(lambda: s.returnWater_t, s.evWaterIsCold)
        s._checkWaterPressure = Observ(lambda: s.io.isPressureNormal(), s.evWaterPressure)
        s._checkDiffWater_t = Observ(lambda: (s.boiler_t - s.returnWater_t) > 1, s.evDiffWater_t, ignoreFirst=False)
        s._checkFlameSensor = Observ(lambda: s.io.isFlameBurning(), s.evFlameSensorCheck)
        s._hour = Observ(lambda: datetime.datetime.now().hour, s.evHourTick)
        s._minute = Observ(lambda: datetime.datetime.now().minute, s.evMinuteTick)

        s._room_tIntegrator = Integrator()
        s._retWater_tIntegrator = Integrator()

        s.io.ignitionRelayDisable()
        s.io.funHeaterDisable()
        s.io.fuelPumpDisable()

        s.task.start()
        s.telegram.send('Котёл перезапущен')
        Task.runObserveTasks()

        with s.store.lock:
            enabled = s.store.tree['enabled']
        if enabled:
            s.enableMainPower()
            s.start()


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
            s.start()
            return

        if state == 1 and prevState == 0:
            s.log.info('HW power is disabled')
            if s.state() == "STOPPED":
                return

            s.stop()
            s.telegram.send('Отсуствует питание горелки. Котёл остановлен')


    def doTask(s):
        errCnt = 0
        while(1):
            msg = s.task.message()
            if msg:
                if msg == "stop":
                    s.stop()
                    s.telegram.send("Котёл остановлен")


            try:
                s.room_t = s.io.room_t()
                s.boiler_t = s.io.boiler_t()
                s.returnWater_t = s.io.retWater_t()
            except TermoSensor.TermoError as e:
                s.stop()
                s.telegram.send("Ошибка при получении температур: %s, Котёл остановлен" % e.args[1])

            if not s.room_t or not s.boiler_t or not s.returnWater_t:
                if errCnt > 5:
                    s.stop()
                    s.telegram.send("Датчики температур не работают: %s, Котёл остановлен" % e.args[1])
                    errCnt = 0

                errCnt += 1
                Task.sleep(1000)
                continue

            s._checkOverHeating()
            s._checkWaterIsCold()
            s._checkWaterPressure()
            s._checkDiffWater_t()
            s.checkTermoSensors()
            s._hour()
            s._minute()

            if s.state() == "WAITING":
                s.doWaiting()
            elif s.state() == "HEATING":
                s.doHeating()

            Task.sleep(1000)


    def evOverHeating(s, isOverHearting):
        if not isOverHearting:
            return

        s.log.error("Over Heating!")
        msg = "Пропало питание, возможно перегрев котла!"
        if s.state() != "STOPPED":
            s.stop()
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
        if s.state() != "STOPPED":
            s.stop()
            msg += " Котёл остановлен."
        s.telegram.send(msg)
        return


    def evDiffWater_t(s, result):
        if result:
            s.io.waterPumpEnable()
        else:
            s.io.waterPumpEnable(60000 * 10)


    def evFlameSensorCheck(s, state):
        if state:
            s.telegram.send("Ошибка датчика пламени. Он сигнализирует, что пламя есть "
                            "в то время как его быть недолжно. Котёл остановлен.")
            s.stop()


    def evHourTick(s, hour):
        overageRoom_t = s._room_tIntegrator.overage()
        overageRetWater_t = s._retWater_tIntegrator.overage()

        s._room_tIntegrator.reset()
        s._retWater_tIntegrator.reset()

        with s.store.lock:
            s.store.tree['overage_room_t'][hour] = overageRoom_t
            s.store.tree['overage_return_water_t'][hour] = overageRetWater_t
            s.store.save()


    def evMinuteTick(s, minute):
        s._room_tIntegrator.add(s.room_t)
        s._retWater_tIntegrator.add(s.returnWater_t)


    def room_tOverage(s):
        with s.store.lock:
            queue = list(s.store.tree['overage_room_t'].values())

        it = Integrator()
        it.addQueue(queue)
        it.add(s._room_tIntegrator.overage())
        return it.overage()


    def returnWater_tOverage(s):
        with s.store.lock:
            queue = list(s.store.tree['overage_return_water_t'].values())

        it = Integrator()
        it.addQueue(queue)
        it.add(s._retWater_tIntegrator.overage())
        return it.overage()


    def checkTermoSensors(s):
        if s.state() == "STOPPED":
            return

        if s.room_t < -10 or s.room_t > 40:
            s.log.error("termosensor room_t is not correct, %.1f degree." % s.room_t)
            s.telegram.send("Ошибка термодатчика room_t, "
                            "он показывает температуру: %.1f градусов. "
                            "Котёл остановлен." % s.room_t)
            s.stop()
            return

        if s.boiler_t < -1 or s.boiler_t > 120:
            s.log.error("termosensor boiler_t is not correct, %.1f degree." % s.room_t)
            s.telegram.send("Ошибка термодатчика boiler_t, "
                            "он показывает температуру: %.1f градусов. "
                            "Котёл остановлен." % s.boiler_t)
            s.stop()
            return

        if s.returnWater_t < -1 or s.returnWater_t > 120:
            s.log.error("termosensor returnWater_t is not correct, %.1f degree." % s.room_t)
            s.telegram.send("Ошибка термодатчика returnWater_t, "
                            "он показывает температуру: %.1f градусов. "
                            "Котёл остановлен." % s.boiler_t)
            s.stop()
            return


    def targetRoom_t(s):
        with s.store.lock:
            return float(s.store.tree['target_room_t'])


    def targetRoomMax_t(s):
        with s.store.lock:
            return float(s.store.tree['target_room_t'])


    def targetRoomMin_t(s):
        with s.store.lock:
            return float(s.store.tree['target_room_t']) - 1


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


    def burningTimeTotal(s):
        with s.store.lock:
            return s.store.tree['burning_time']


    def fuelConsumption(s):
        heatingTime = s.burningTimeTotal()
        return heatingTime * 4.925 / 3600


    def energyConsumption(s):
        heatingTime = s.burningTimeTotal()
        return heatingTime * 40 / 3600


    def ignitionCounter(s):
        with s.store.lock:
            return s.store.tree['ignition_counter']


    def saveHeatingTime(s):
        burningTime = s.tcBurning.time()
        s.tcBurning.reset()
        if burningTime:
            with s.store.lock:
                s.store.tree['burning_time'] += burningTime
                s.store.save()


    def start(s):
        if s.state() != "STOPPED":
            s.log.error("Can't start boiler, boiler already was started")
            return False

        if not s.io.isHwEnabled():
            s.log.error("Can't start boiler, HW power is not present")
            return False

        if not s.io.isPressureNormal():
            s.log.error("Can't start boiler, No water pressure")
            return False

        with s.store.lock:
            s.store.tree['enabled'] = 1
            s.store.save()

        s.setState("WAITING")
        s.log.info("boiler started")
        s.telegram.send("Котёл включен")
        return True


    def stop(s):
        if s.state() == "IGNITING":
            s.stopIgnitFlameTask()

        if s.state() == "HEATING":
            s.stopHeating()

        if s.io.isFuelPumpEnabled():
            s.io.fuelPumpDisable()

        s.io.ignitionRelayDisable()
        s.io.funHeaterDisable()
        s.tcBurning.stop()
        s.saveHeatingTime()
        if s.io.isAirFunEnabled():
            s.io.airFunEnable(10000)
        else:
            s.io.airFunDisable()

        with s.store.lock:
            s.store.tree['enabled'] = 0
            s.store.save()

        if s.io.isFunHeaterEnabled():
            s.io.funHeaterDisable()

        s.setState("STOPPED")
        s.log.info("boiler stopped")


    def ignitFlame(s):
        s.log.info("start ignit flame procedure")
        if s.fake:
            Task.sleep(2000)
            s.log.info("the flame was stabilizated")
            return True

        for attemptCnt in range(10):
            s.io.airFunEnable()
            Task.sleep(15000)

            s.io.ignitionRelayEnable()
            s.io.fuelPumpEnable()
            Task.sleep(500)

            success = False
            for attempt in range(16):
                if s.io.isFlameBurning():
                    success = True
                    s.log.debug("flame is first burn")
                    break
                Task.sleep(500)
            s.io.ignitionRelayDisable();

            if not success:
                s.io.fuelPumpDisable()
                s.log.error("can't first burn, attemptCnt: %d" % attemptCnt)
                Task.sleep(15000)
                continue

            s.tcBurning.start()
            s.log.info("Waiting flame stabilization")
            success = False
            for attempt in range(30):
                if s.io.isFlameBurning():
                    Task.sleep(500)
                    continue

                s.io.fuelPumpDisable()
                s.log.error("Can't stabilization: the flame went out, attemptCnt: %d" % attemptCnt)
                Task.sleep(15000)
                break
            else:
                s.log.info("The flame was stabilizated")
                return True

        else:
            s.io.fuelPumpDisable()
            Task.sleep(15000)
            s.io.airFunDisable()
            s.log.error("Can't start heating. All attempts were exhausted.")
            s.telegram.send("Не удалось зажечь пламя, все попытки исчерпаны.")
            s.tcBurning.reset()
            return False


    def ignitFlameTask(s):
        rc = s.ignitFlame()
        if not rc:
            s.log.error("Can't iginit flame")
            s.task.sendMessage("stop")
            return

        s.telegram.send('Нагрев запущен')
        s.setState("HEATING")
        with s.store.lock:
            s.store.tree['ignition_counter'] += 1
            s.store.save()
        with s.lock:
            s._ignitTask.remove()
            s._ignitTask = None


    def stopIgnitFlameTask(s):
        with s.lock:
            if not s._ignitTask:
                return
            s._ignitTask.stop()
            s._ignitTask.remove()
            Task.sleep(2000)
            s._ignitTask = None

        s.io.fuelPumpDisable()
        s.io.ignitionRelayDisable()
        s.log.debug('stop ignit_flame task')


    def startIgnitFlameTask(s):
        s.setState("IGNITING")
        with s.lock:
            s._ignitTask = Task("ignit_flame")
            s._ignitTask.setCb(s.ignitFlameTask)
            s._ignitTask.start()


    def startHeating(s):
        s.stopIgnitFlameTask()
        s.startIgnitFlameTask()


    def stopHeating(s):
        s.stopIgnitFlameTask()
        s.io.fuelPumpDisable()
        s.tcBurning.stop()
        s.saveHeatingTime()
        s.io.airFunEnable(30000)
        s.log.info("stop heating")


    def doWaiting(s):
        if s.boiler_t <= s.targetBoilerMin_t() and s.room_t < s.targetRoomMin_t():
            s.startHeating()
            return

        s._checkFlameSensor()


    def doHeating(s):
        if s.tcBurning.time() > 10 * 60 and s.boiler_t < 30:
            s.stop()
            s.log.error("Boiler stopped by timeout. boiler t: %.1f, "
                        "heating time: %d" % (s.boiler_t, s.tcBurning.time()))
            s.telegram.send("Котёл работает более %d секунд а температура в котле "
                            "так и не превысила 30 градусов. "
                            "Котёл остановлен." % s.tcBurning.time())
            return


        if s.boiler_t >= s.targetBoilerMax_t() or s.room_t >= s.targetRoomMax_t():
            if s.room_t < s.targetRoomMin_t() and s.tcBurning.time() < 20:
                s.log.error("The boiler has reached the temperature %.1f "
                            "is very too quickly" % s.targetBoilerMax_t())
                s.telegram.send("Котёл набрал температуру до %.1f градусов "
                                "слишком быстро (за %d секунд), "
                                "Котёл остановлен." % (s.targetBoilerMax_t(),
                                                       s.tcBurning.time()))
                s.stop()
                return

            if s.room_t >= s.targetRoomMax_t():
                if s.io.isFunHeaterEnabled():
                    s.io.funHeaterEnable(10000)

            if s.boiler_t >= s.targetBoilerMax_t():
                msg = 'Нагрев прерван из за превышения температуры котла'
            else:
                msg = 'Нагрев завершен'
            s.telegram.send("%s, время нагрева: %s\n"
                            "Температура в мастерской: %.1f градусов" %
                                (msg, timeStr(s.tcBurning.time()), s.room_t))

            s.stopHeating()
            s.setState("WAITING")
            return

        if s.returnWater_t >= 45 and not s.io.isFunHeaterEnabled():
            s.io.funHeaterEnable()

        if not s.io.isFlameBurning():
            s.setState("WAITING")
            s.stopHeating()
            s.log.error("the flame went out!")
            s.telegram.send("Пламя в котле самопроизвольно погасло!")
            Task.sleep(3000)
            return False


    def setState(s, state):
        with s.lock:
            s._state = state
        s.log.info("set state %s" % state)


    def state(s):
        with s.lock:
            return s._state


    def resetStatistics(s):
        s.tcBurning.reset()
        with s.store.lock:
            s.store.tree['burning_time'] = 0
            s.store.tree['ignition_counter'] = 0
            s.store.tree['overage_room_t'] = {}
            s.store.tree['overage_return_water_t'] = {}
            s.store.save()


    def httpReqStat(s, args, body):
        data = {}
        data['state'] = s.state()
        data['target_boiler_t_max'] = s.targetBoilerMax_t()
        data['target_boiler_t_min'] = s.targetBoilerMin_t()
        data['total_burning_time'] = s.burningTimeTotal()
        data['total_burning_time_text'] = timeStr(s.burningTimeTotal())
        data['total_fuel_consumption'] = s.fuelConsumption()
        data['total_energy_consumption'] = s.energyConsumption()
        data['ignition_counter'] = s.ignitionCounter()
        data['overage_room_t'] = s.room_tOverage()
        data['overage_return_water_t'] = s.returnWater_tOverage()


        if s.state() != "STOPPED":
            data['current_boiler_t'] = s.boiler_t
            data['current_return_water_t'] = s.returnWater_t
            data['target_room_t'] = s.targetRoom_t()
            data['current_room_t'] = s.room_t
            data['current_burning_time'] = s.tcBurning.time()
            data['fun_heater_is_enabled'] = s.io.isFunHeaterEnabled()

        return json.dumps(data)


    def httpReqSbioStat(s, args, body):
        f = os.popen('uptime')
        c = f.read()
        f.close()
        uptime = re.search(r'up (.+?),', c).group(1)

        termoSensors = []
        tList = [s.io._boilerTermo, s.io._retTermo, s.io._roomTermo, s.io._boilerInside]
        for sensor in tList:
            termoSensors.append({'name': sensor.devName(),
                                 'temperature': sensor.val()})

        data = {}
        data['status'] = 'ok'
        data['error_msg'] = ''
        data['uptime'] = uptime
        data['status'] = 'ok'
        data['termo_sensors'] = termoSensors
        return json.dumps(data)


    def httpReqResetStat(s, args, body):
        s.resetStatistics()
        s.log.debug('reset statistics by http request')
        return json.dumps({"status": "ok"})


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
        rc = s.start()
        if not rc:
            return json.dumps({"status": "error"})
        s.telegram.send('Котёл запущен по REST запросу')
        return json.dumps({"status": "ok"})


    def httpReqStop(s, args, body):
        s.stop()
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
        str = "Boiler state: %s\n" % s.state()
        if s.state() != "STOPPED":
            str += "target boiler t max: %.1f\n" % s.targetBoilerMax_t()
            str += "target boiler t min: %.1f\n" % s.targetBoilerMin_t()
            str += "current boiler t: %.1f\n" % s.boiler_t
            str += "current return water t: %.1f\n" % s.returnWater_t
            str += "target room t: %.1f - %.1f\n" % (s.targetRoomMin_t(), s.targetRoomMax_t())
            str += "current room t: %.1f\n" % s.room_t
            str += "current burning time: %s\n" % timeStr(s.tcBurning.time())
            str += "total burning time: %s\n" % timeStr(s.burningTimeTotal())
            str += "total fuel consumption: %.1f liters\n" % s.fuelConsumption()
            str += "total energy consumption: %.1f kW*h\n" % s.energyConsumption()
            str += "ignition counter: %d\n" % s.ignitionCounter()
            str += "fun heater: %s\n" % s.io.isFunHeaterEnabled()
            str += "overage room t: %.1f\n" % s.room_tOverage()
            str += "overage return water t: %.1f\n" % s.returnWater_tOverage()

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

