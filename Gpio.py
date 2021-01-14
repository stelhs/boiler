import os, select
from Task import *
from common import *
from Syslog import *



class Gpio():
    gpioMode = 'real'

    _usedGpio = []
    def __init__(s, name, num, mode):
        if Gpio.gpioByNum(num):
            raise Exception("GPIO %d already in used" % num)

        s._num = num
        s._mode = mode
        s._name = name
        s._num = num
        s._fake = False
        s._timeoutTask = None
        s._lock = threading.Lock()

        s.log = Syslog("gpio%d_%s" % (s._num, s._name))

        s._usedGpio.append(s)
        if Gpio.gpioMode == 'real':
            s.initReal()
        elif Gpio.gpioMode == 'fake':
            s.initFake()
            s._fake = True


    def name(s):
        return s._name;


    def num(s):
        return s._num;


    def fd(s):
        if s._of:
            return s._of.fileno();
        return None


    def initReal(s):
        if not os.path.exists("/sys/class/gpio/gpio%d" % s._num):
            filePutContent("/sys/class/gpio/export", "%d" % s._num)

        filePutContent("/sys/class/gpio/gpio%d/direction" % s._num, s._mode)
        filePutContent("/sys/class/gpio/gpio%d/edge" % s._num, "both")

        s._of = open("/sys/class/gpio/gpio%d/value" % s._num, "r")


    def initFake(s):
        s._fileName = "FAKE/GPIO%d_%s_%s" % (s._num, s._mode, s._name)

        if not os.path.exists(s._fileName):
            if s._mode == 'in':
                filePutContent(s._fileName, "1")
            else:
                filePutContent(s._fileName, "0")

        s._of = None


    def setValueReal(s, val):
        s._of.write("%d" % val)


    def setValueFake(s, val):
        filePutContent(s._fileName, "%d" % val)


    def setValue(s, val):
        with s._lock:
            if s._timeoutTask:
                s.log.debug('cancel setValueTimeout')
                s._timeoutTask.stop()
                s._timeoutTask.remove()
                s._timeoutTask = None

        if s._fake:
            return s.setValueFake(val)
        return s.setValueReal(val)


    def valueFake(s):
        val = fileGetContent(s._fileName)
        if val.strip() == '1':
            return 1
        return 0


    def valueReal(s):
        val = s._of.read()
        if val.strip() == '1':
            return 1
        return 0


    def value(s):
        if s._fake:
            return s.valueFake()
        return s.valueReal()


    def setValueTimeout(s, val, interval):
        def timeout():
            s.setValue(val)
            s.log.info("set to value '%d' by timeout: %d mS" % (val, interval))
            with s._lock:
                s._timeoutTask = None

        task = Task.setTimeout('gpio_%s_%dmS' % (s._name, interval), interval, timeout)
        with s._lock:
            s._timeoutTask = task


    def __str__(s):
        return "GPIO%d_%s %s, val = %d" % (s._num, s._mode, s._name, s.value())


    @staticmethod
    def gpioByNum(num):
        for gpio in Gpio._usedGpio:
            if gpio.num() == num:
                return gpio
        return None


    @staticmethod
    def gpioByFd(fd):
        for gpio in Gpio._usedGpio:
            if gpio.fd() == fd:
                return gpio

        return None


    @staticmethod
    def gpioByName(name):
        for gpio in Gpio._usedGpio:
            if gpio.name() == name:
                return gpio
        return None


    @staticmethod
    def printList():
        for gpio in Gpio._usedGpio:
            print(gpio)



class GpioEventsTask(Task):
    def __init__(s, gpios, cb):
        Task.__init__(s, "gpio_events")
        fake = False
        s._poll = select.poll()
        for gpio in gpios:
            if not gpio.fd():
                fake = True
                break

            s._poll.register(gpio.fd(), select.POLLPRI)

        s._cb = cb
        if not fake:
            s.start()


    def do(s):
        while (1):
            Task.sleep()
            poll_list = s._poll.poll(100)
            if not len(poll_list):
                continue

            for poll_ret in poll_list:
                fd = poll_ret[0]
                gpio = Gpio.gpioByFd(fd)
                val = gpio.value()
                s._cb(gpio, val)


    def generateAction(s, gpioNum, val):
        gpio = Gpio.gpioByNum(gpioNum)
        if not gpio:
            return
        s._cb(gpio, val)


