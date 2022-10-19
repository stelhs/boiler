from Task import *
from HwIo import *
from Syslog import *
from Telegram import *
from HttpServer import *
from TimerCounter import *
from AveragerQueue import *
from ConfBoiler import *
from SkynetNotifier import *
from TelegramClient import *
from Storage import *
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

    def __init__(s):
        s.lock = threading.Lock()
#        Task.runObserveTasks()
        s.fake = False
        if os.path.isdir("FAKE"):
            s.fake = True

        s.conf = ConfBoiler()
        s.storage = Storage('boiler.json', s.conf.boiler['storageDir'])
        s._targetRoom_t = s.storage.key('/target_room_t', 18.0)
        s._targetBoilerMin_t = s.storage.key('/target_boiler_min_t', 60)
        s._targetBoilerMax_t = s.storage.key('/target_boiler_max_t', 80)
        s._burningTime = s.storage.key('/burning_time', 0)
        s._ignitionCounter = s.storage.key('/ignition_counter', 0)
        s._boilerEnabled = s.storage.key('/enabled', False)
        s.overageRoom_t = s.storage.key('/overage_room_t', {})
        s.overageReturnWater_t = s.storage.key('/overage_return_water_t', {})


        s.io = HwIo()
        s.log = Syslog("Boiler")

        s.task = Task('boiler', s.doTask, s.stopHw)

        s.tc = TelegramClient(s.conf.telegram)
        Task.setErrorCb(s.taskExceptionHandler)

        s.sn = SkynetNotifier('boiler',
                              s.conf.boiler['skynetServer']['host'],
                              s.conf.boiler['skynetServer']['port'],
                              s.conf.boiler['host'])


        s.httpServer = HttpServer(s.conf.boiler['host'],
                                  s.conf.boiler['port'])
        s.httpHandlers = Boiler.HttpHandlers(s, s.httpServer)

        s.io.setHwEnableCb(s.hwEnableCb)
        s.io.setHwEventsCb(s.skynetSendUpdate)
        s.io.setFlameBurningCb(lambda gpio, st, pst: s.skynetSendUpdate())

        s._ignitTask = None
        s.boiler_t = 0
        s.room_t = 0
        s.returnWater_t = 0

        s.tcBurning = TimerCounter('burning_time')
        s._checkOverHeating = Observ(lambda: s.io.isOverHearting(), s.evOverHeating)
        s._checkWaterIsCold = Observ(lambda: s.returnWater_t, s.evWaterIsCold)
        s._checkWaterPressure = Observ(lambda: s.io.isPressureNormal(), s.evWaterPressure)
        s._checkDiffWater_t = Observ(lambda: s.boiler_t and s.returnWater_t and (s.boiler_t - s.returnWater_t) > 3,
                                     s.evDiffWater_t, ignoreFirst=False)
        s._hour = Observ(lambda: datetime.datetime.now().hour, s.evHourTick)
        s._minute = Observ(lambda: datetime.datetime.now().minute, s.evMinuteTick)

        s._room_tIntegrator = AveragerQueue()
        s._retWater_tIntegrator = AveragerQueue()

        s.task.start()

        if s._boilerEnabled.val:
            s.enableMainPower()
            s.start()

        s.skynetSendUpdate()
        s.log.info("Initialization finished")

        msg = 'Котёл перезапущен'
        s.tc.sendToChat('stelhs', msg)
        s.sn.notify('info', msg)


    def taskExceptionHandler(s, task, errMsg):
        s.tc.sendToChat('stelhs',
                "Boiler: task '%s' error:\n%s" % (task.name(), errMsg))


    def stopHw(s):
        s.io.fuelPumpDisable()
        s.io.airFunDisable()
        s.io.ignitionRelayDisable()
        s.io.funHeaterDisable()


    def hwEnableCb(s, gpio, state, prevState):
        if state == 0 and prevState == 1:
            s.log.info('HW power is enabled')
            if s.io.isOverHearting():
                msg = 'Boiler is overHeating'
                s.log(msg)
                s.sn.notify('error', msg)
                s.stop()
                return

            s.start()
            return

        if state == 1 and prevState == 0:
            s.log.info('HW power is disabled')
            if s.state() == "STOPPED":
                return

            s.stop()
            msg = 'Отсуствует питание горелки. Котёл остановлен'
            s.sn.notify('error', msg)
            s.tgSendAdmin(msg)


    def doTask(s):
        errCnt = 0
        while(1):
            msg = s.task.message()
            if msg:
                if msg == "stop":
                    s.stop()
                    s.tgSendAdmin("Котёл остановлен")

            s.room_t = s.io.room_t()
            s.boiler_t = s.io.boiler_t()
            s.returnWater_t = s.io.retWater_t()
            s.skynetSendUpdate()

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

            Task.sleep(2000)


    def evOverHeating(s, isOverHearting):
        if not isOverHearting:
            return

        s.log.err("Over Heating!")
        msg = "Пропало питание, возможно перегрев котла!"
        if s.state() != "STOPPED":
            s.stop()
            s.io.funHeaterEnable(5 * 60 * 1000)
            msg += " Котёл остановлен."

        s.sn.notify('error', msg)
        s.tgSendAdmin(msg)


    def evWaterIsCold(s, returnWater_t):
        if returnWater_t <= 3:
            msg = "Температура теплоносителя упала " \
                  "до %.1f градусов!" % returnWater_t
            s.sn.notify('error', msg)
            s.tgSendAdmin(msg)
            s.log.err("returnWater_t failing down to %.1f degree" % returnWater_t)


    def evWaterPressure(s, isWaterPressureNormal):
        s.skynetSendUpdate()
        if isWaterPressureNormal:
            msg = "Давление в системе отопления восстановлено"
            s.sn.notify('info', msg)
            s.tgSendAdmin(msg)
            s.log.info("Water pressure go to normal")
            return

        s.log.err("Falling water pressure")
        msg = "Упало давление в системе отопления!"
        if s.state() != "STOPPED":
            s.stop()
            msg += " Котёл остановлен."
        s.sn.notify('error', msg)
        s.tgSendAdmin(msg)
        return


    def evDiffWater_t(s, result):
        if result:
            s.io.waterPumpEnable()
        else:
            s.io.waterPumpEnable(60000 * 2)


    def evHourTick(s, hour):
        overageRoom_t = s._room_tIntegrator.round()
        overageRetWater_t = s._retWater_tIntegrator.round()

        s._room_tIntegrator.clear()
        s._retWater_tIntegrator.clear()

        l = s.overageRoom_t.val
        l[hour] = overageRoom_t
        s.overageRoom_t.set(l)

        l = s.overageReturnWater_t.val
        l[hour] = overageRetWater_t
        s.overageReturnWater_t.set(l)


    def evMinuteTick(s, minute):
        s._room_tIntegrator.push(s.room_t)
        s._retWater_tIntegrator.push(s.returnWater_t)


    def room_tOverage(s):
        queue = list(s.overageRoom_t.val.values())
        aq = AveragerQueue(queue=queue)
        aq.push(s._room_tIntegrator.round())
        return aq.round()


    def returnWater_tOverage(s):
        queue = list(s.overageReturnWater_t.val.values())
        aq = AveragerQueue(queue=queue)
        aq.push(s._retWater_tIntegrator.round())
        return aq.round()


    def checkTermoSensors(s):
        if s.state() == "STOPPED":
            return

        if s.room_t < -10 or s.room_t > 40:
            s.log.err("termosensor room_t is not correct, %.1f degree." % s.room_t)
            msg = "Ошибка термодатчика room_t, " \
                  "он показывает температуру: %.1f градусов. " \
                  "Котёл остановлен." % s.room_t
            s.sn.notify('error', msg)
            s.tgSendAdmin(msg)
            s.stop()
            return

        if s.boiler_t < -1 or s.boiler_t > 120:
            s.log.err("termosensor boiler_t is not correct, %.1f degree." % s.room_t)
            msg = "Ошибка термодатчика boiler_t, " \
                  "он показывает температуру: %.1f градусов. " \
                  "Котёл остановлен." % s.boiler_t
            s.sn.notify('error', msg)
            s.tgSendAdmin(msg)
            s.stop()
            return

        if s.returnWater_t < -1 or s.returnWater_t > 120:
            s.log.err("termosensor returnWater_t is not correct, %.1f degree." % s.room_t)
            msg = "Ошибка термодатчика returnWater_t, " \
                  "он показывает температуру: %.1f градусов. " \
                  "Котёл остановлен." % s.boiler_t
            s.sn.notify('error', msg)
            s.tgSendAdmin(msg)
            s.stop()
            return


    def targetRoom_t(s):
        return float(s._targetRoom_t.val)


    def targetRoomMax_t(s):
        return float(s._targetRoom_t.val)


    def targetRoomMin_t(s):
        return float(s._targetRoom_t.val) - 0.5


    def setTargetRoom_t(s, t):
        s._targetRoom_t.set(float(t))
        s.skynetSendUpdate()


    def targetBoilerMin_t(s):
        return float(s._targetBoilerMin_t.val)


    def setTargetBoilerMin_t(s, t):
        s._targetBoilerMin_t.set(float(t))


    def targetBoilerMax_t(s):
        return float(s._targetBoilerMax_t.val)


    def setTargetBoilerMax_t(s, t):
        s._targetBoilerMax_t.set(float(t))


    def enableMainPower(s):
        s.io.mainPowerRelayEnable()
        Task.sleep(500)
        s.io.mainPowerRelayDisable()
        s.skynetSendUpdate()


    def burningTimeTotal(s):
        return int(s._burningTime.val)


    def fuelConsumption(s):
        heatingTime = s.burningTimeTotal()
        return heatingTime * 4.925 / 3600


    def energyConsumption(s):
        heatingTime = s.burningTimeTotal()
        return heatingTime * 40 / 3600


    def ignitionCounter(s):
        return int(s._ignitionCounter.val)


    def saveHeatingTime(s):
        burningTime = s.tcBurning.duration()
        s.tcBurning.reset()
        if burningTime:
            s._burningTime.set(s.burningTimeTotal() + burningTime)
        s.skynetSendUpdate()


    def start(s):
        if s.state() != "STOPPED":
            raise BoilerError(s.log, "Can't start boiler, boiler already was started")

        if not s.io.isHwEnabled():
            raise BoilerError(s.log, "Can't start boiler, HW power is not present")

        if not s.io.isPressureNormal():
            raise BoilerError(s.log, "Can't start boiler, No water pressure")

        if s.io.isOverHearting():
            raise BoilerError(s.log, "Can't start boiler, Boiler is overheating")

        s._boilerEnabled.set(True)
        s.setState("WAITING")
        s.log.info("boiler started")
        s.sn.notify('info', "Котёл включен")
        s.tgSendAdmin("Котёл включен")
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

        s._boilerEnabled.set(False)

        if s.io.isFunHeaterEnabled():
            s.io.funHeaterDisable()

        s.setState("STOPPED")
        s.log.info("boiler stopped")
        s.sn.notify('info', "Котёл остановлен")


    def ignitFlame(s):
        s.log.info("start ignit flame procedure")

        s.setState("IGNITING")
        if s.fake:
            s.io.airFunEnable()
            s.io.fuelPumpEnable()
            Task.sleep(2000)
            s.log.info("the flame was stabilizated")
            s.sn.notify('info', 'Нагрев запущен')
            s.tgSendAdmin('Нагрев запущен')
            s._ignitionCounter.set(int(s._ignitionCounter.val) + 1)
            s.setState("HEATING")


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
                msg = "can't first burn, attemptCnt: %d" % attemptCnt
                s.log.err(msg)
                s.sn.notify('error', msg)
                Task.sleep(15000)
                continue

            s.tcBurning.start()
            s.log.info("Waiting flame stabilization")
            s.sn.notify('info', "Ожидание стабилизации пламени")
            success = False
            for attempt in range(30):
                if s.io.isFlameBurning():
                    Task.sleep(500)
                    continue

                s.io.fuelPumpDisable()
                msg = "Can't stabilization: the flame went out, attemptCnt: %d" % attemptCnt
                s.log.err(msg)
                s.sn.notify('error', msg)
                Task.sleep(15000)
                break
            else:
                s.log.info("The flame was stabilizated")
                s.sn.notify('info', 'Нагрев запущен')
                s.tgSendAdmin('Нагрев запущен')
                s.setState("HEATING")
                s._ignitionCounter.set(int(s._ignitionCounter.val) + 1)
                return True

        else:
            s.io.fuelPumpDisable()
            Task.sleep(15000)
            s.io.airFunDisable()
            s.tcBurning.reset()
            msg = "Не удалось зажечь пламя, все попытки исчерпаны."
            s.tgSendAdmin(msg)
            s.sn.notify('error', msg)
            s.task.sendMessage("stop")
            raise BoilerError(s.log, "Can't start heating. All attempts were exhausted.")


    def startHeating(s):
        def abort():
            s._ignitTask = None
        s._ignitTask = Task.asyncRunSingle('ignition_flame',
                                           s.ignitFlame, abort)


    def stopHeating(s):
        if s._ignitTask:
            s._ignitTask.remove()
        s.io.fuelPumpDisable()
        s.io.ignitionRelayDisable()
        s.tcBurning.stop()
        s.saveHeatingTime()
        s.io.airFunEnable(30000)
        Task.sleep(1000) # TODO
        s.log.info("stop heating")
        s.sn.notify('info', "stop heating")


    def doWaiting(s):
        if s.boiler_t <= s.targetBoilerMin_t() and s.room_t < s.targetRoomMin_t():
            s.startHeating()
            return


    def doHeating(s):
        if s.tcBurning.duration() > 10 * 60 and s.boiler_t < 30:
            s.stop()
            s.log.err("Boiler stopped by timeout. boiler t: %.1f, "
                        "heating time: %d" % (s.boiler_t, s.tcBurning.duration()))
            msg = "Котёл работает более %d секунд а температура в котле " \
                  "так и не превысила 30 градусов. " \
                  "Котёл остановлен." % s.tcBurning.duration()
            s.sn.notify('error', msg)
            s.tgSendAdmin(msg)
            return


        if s.boiler_t >= s.targetBoilerMax_t() or s.room_t >= s.targetRoomMax_t():
            if s.room_t < s.targetRoomMin_t() and s.tcBurning.duration() < 20:
                s.log.err("The boiler has reached the temperature %.1f "
                            "is very too quickly" % s.targetBoilerMax_t())
                msg = "Котёл набрал температуру до %.1f градусов " \
                      "слишком быстро (за %d секунд), " \
                      "Котёл остановлен." % (s.targetBoilerMax_t(),
                                             s.tcBurning.duration())
                s.sn.notify('error', msg)
                s.tgSendAdmin(msg)
                s.stop()
                return

            if s.room_t >= s.targetRoomMax_t():
                if s.io.isFunHeaterEnabled():
                    s.io.funHeaterEnable(20000)

            if s.boiler_t >= s.targetBoilerMax_t():
                msg = 'Нагрев прерван из за превышения температуры котла'
            else:
                msg = 'Нагрев завершен'
            s.tgSendAdmin("%s, время нагрева: %s\n"
                            "Температура в мастерской: %.1f градусов" %
                                (msg, timeDurationStr(s.tcBurning.duration()), s.room_t))

            s.stopHeating()
            s.setState("WAITING")
            return

        if (s.returnWater_t >= 50 and s.boiler_t >= 80
                and not s.io.isFunHeaterEnabled()):
            s.io.funHeaterEnable()

        if not s.io.isFlameBurning():
            s.sn.notify('error', "Пламя в котле самопроизвольно погасло!")
            s.setState("WAITING")
            s.stopHeating()
            s.log.err("the flame went out!")
            s.tgSendAdmin("Пламя в котле самопроизвольно погасло!")
            Task.sleep(3000)
            return False


    def setState(s, state):
        with s.lock:
            s._state = state
        s.log.info("set state %s" % state)
        s.skynetSendUpdate()


    def state(s):
        with s.lock:
            return s._state


    def destroy(s):
        s.stopHw()
        s.httpServer.destroy()
        s.storage.destroy()
        s.sn.notify('info', "boiler.py process was killed")


    def tgSendAdmin(s, msg):
        s.tc.sendToChat('stelhs', "Boiler: %s" % msg)


    def skynetSendUpdate(s):
        stat = {'state': str(s._state),
                'power': str(s.io.isHwEnabled()),
                'air_fun': str(s.io.isAirFunEnabled()),
                'fuel_pump': str(s.io.isFuelPumpEnabled()),
                'ignition': str(s.io.isIgnitionRelayEnabled()),
                'water_pump': str(s.io.isWaterPumpEnabled()),
                'flame': str(s.io.isFlameBurning()),
                'heater': str(s.io.isFunHeaterEnabled()),
                'no_pressure': str(not s.io.isPressureNormal()),
                'overheat': str(s.io.isOverHearting()),

                'target_t': str(s.targetRoom_t()),
                'room_t': str(s.room_t),
                'boiler_box_t': str(s.io.boilerInside_t()),
                'boiler_t': str(s.boiler_t),
                'return_t': str(s.returnWater_t),
                'ignition_counter': str(s.ignitionCounter()),
                'fuel_consumption': str(s.fuelConsumption()),
                };
        s.sn.notify('boilerStatus', stat)



    def resetStatistics(s):
        s.tcBurning.reset()
        s._burningTime.set(0)
        s._ignitionCounter.set(0)
        s.overageRoom_t.set({})
        s.overageReturnWater_t.set({})


    def __str__(s):
        str = "Boiler state: %s\n" % s.state()
        if s.state() != "STOPPED":
            str += "target boiler t max: %.1f\n" % s.targetBoilerMax_t()
            str += "target boiler t min: %.1f\n" % s.targetBoilerMin_t()
            str += "current boiler t: %.1f\n" % s.boiler_t
            str += "current return water t: %.1f\n" % s.returnWater_t
            str += "target room t: %.1f - %.1f\n" % (s.targetRoomMin_t(), s.targetRoomMax_t())
            str += "current room t: %.1f\n" % s.room_t
            str += "current burning time: %s\n" % timeDurationStr(s.tcBurning.duration())
            str += "total burning time: %s\n" % timeDurationStr(s.burningTimeTotal())
            str += "total fuel consumption: %.1f liters\n" % s.fuelConsumption()
            str += "total energy consumption: %.1f kW*h\n" % s.energyConsumption()
            str += "ignition counter: %d\n" % s.ignitionCounter()
            str += "fun heater: %s\n" % s.io.isFunHeaterEnabled()
            try:
                str += "overage room t: %.1f\n" % s.room_tOverage()
                str += "overage return water t: %.1f\n" % s.returnWater_tOverage()
            except AveragerQueueEmptyError:
                pass
        return str


    def __repr__(s):
        return s.__str__()


    def print(s):
        print(s.__str__())


    class HttpHandlers():
        def __init__(s, boiler, httpServer):
            s.boiler = boiler
            s.httpServer = httpServer
            s.httpServer.setReqHandler("GET", "/boiler/reset_stat", s.resetStatHandler)
            s.httpServer.setReqHandler("GET", "/boiler/set_target_t", s.setTargetTemperatureHandler, ['t'])
            s.httpServer.setReqHandler("GET", "/boiler/start", s.startHandler)
            s.httpServer.setReqHandler("GET", "/boiler/fun_heater_enable", s.enableFunHeaterHandler)
            s.httpServer.setReqHandler("GET", "/boiler/fun_heater_disable", s.disableFunHeaterHandler)


        def resetStatHandler(s, args, conn):
            s.boiler.log.debug('reset statistics by http request')
            s.boiler.resetStatistics()


        def setTargetTemperatureHandler(s, args, conn):
            try:
                t = float(args['t'])
                if t < 2.0 or t > 35.0:
                    raise HttpHandlerError("Incorrect temperature %.1f" % t)
                s.boiler.setTargetRoom_t(args['t'])
            except ValueError as e:
                raise HttpHandlerError("Incorrect temperature %s" % args['t'])


        def startHandler(s, args, conn):
            if s.boiler.state() != "STOPPED":
                raise HttpHandlerError("Boiler already started")
            if s.boiler.io.isHwEnabled():
                try:
                    s.boiler.start()
                except BoilerError as e:
                    raise HttpHandlerError("Can't start boiler: %s" % e)

            def doEnPower():
                s.boiler.enableMainPower()
            Task.asyncRunSingle("enabling", doEnPower)


        def enableFunHeaterHandler(s, args, conn):
            s.boiler.io.funHeaterEnable()
            s.boiler.tgSendAdmin('Тепло-вентилятор включен по REST запросу')


        def disableFunHeaterHandler(s, args, conn):
            s.boiler.io.funHeaterDisable()
            s.boiler.tgSendAdmin('Тепло-вентилятор отключен по REST запросу')



class Observ():
    def __init__(s, condCb, eventCb, ignoreFirst=True):
        s.condCb = condCb
        s.eventCb = eventCb
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
        s.eventCb(val)

