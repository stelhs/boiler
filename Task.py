import threading
import time
from Syslog import *
from common import *
import traceback


class TaskStopException(Exception):
    pass


class Task():
    listTasks = []
    listTasksLock = threading.Lock()

    log = Syslog("task")
    lastId = 0

    listAsyncFunctions = {}
    listAsyncLock = threading.Lock()

    def __init__(s, name, exitCb = None, autoremove = False):
        s._name = name
        s.cb = None
        s._state = "stopped"
        s._tid = None
        s._removing = False
        s._msgQueue = []
        s.exitCb = exitCb
        s.autoremove = autoremove

        if Task.taskByName(name):
            raise Exception("Task with name '%s' is existed" % name)

        s.log = Syslog("task_%s" % name)
        #s.log.mute('info')
        s.log.info("created")
        s._lock = threading.Lock()
        s._ev = threading.Event()
        with s._lock:
            Task.lastId += 1
            s._id = Task.lastId
            s._alive = False

        with Task.listTasksLock:
            s.listTasks.append(s)


    def iAmAlive(s):
        with s._lock:
            s._alive = True


    def checkForAlive(s):
        with s._lock:
            s._alive = False


    def isAlived(s):
        with s._lock:
            return s._alive


    def setFreezed(s):
        s.setState("freezed")


    def sendMessage(s, msg):
        with s._lock:
            s._msgQueue.append(msg)
        s._ev.set()


    def message(s):
        s._ev.clear()
        with s._lock:
            if not len(s._msgQueue):
                return None

            msg = s._msgQueue[0]
            s._msgQueue.remove(msg)
            return msg


    def waitMessage(s, timeoutSec = None):
        for sec in range(timeoutSec):
            s._ev.wait(1)
            if s.isRemoving():
                return s.message()
        return s.message()


    def start(s):
        if s.state() != "stopped":
            return

        s.log.info("start")
        t = threading.Thread(target=s.thread, daemon=True, args=(s._name, ))
        t.start()
        s.setState("running")


    def setCb(s, cb, args = None):
        s.cb = cb
        s.cbArgs = args


    def thread(s, name):
        s._tid = threading.get_ident()
        try:
            if s.cbArgs:
                s.cb(s.cbArgs)
            else:
                s.cb()
        except TaskStopException:
            s.log.info("stopped")
        except Exception as e:
            trace = traceback.format_exc()
            s.log.err("Exception: %s" % trace)
            print("Task '%s' Exception:\n%s" % (s._name, trace))
            #s.telegram.send("stopped by exception: %s" % trace) TODO!!!!

        if s.exitCb:
            try:
                s.exitCb()
            except TaskStopException:
                pass

        s.setState("stopped")
        if s.isRemoving() or s.autoremove:
            with Task.listTasksLock:
                Task.listTasks.remove(s)
            s.setState("removed")
            s.log.info("removed by flag")


    def stop(s):
        if s.state() != "running":
            return
        s.log.info("stopping")
        s.setState("stopping")


    def restart(s):
        s.stop()
        while 1:
            s.sleep(100)
            if s.state() == "stopped":
                break
        s.start()


    def pause(s):
        s.log.info("paused")
        s.setState("paused")


    def resume(s):
        if s.state() != "paused":
            return
        s.log.info("resumed")
        s.setState("running")


    def remove(s):
        if s.state() == "stopped":
            with Task.listTasksLock:
                Task.listTasks.remove(s)
            s.setState("removed")
            s.log.info("removed immediately")
            return

        s.log.info("removing..")
        s.stop()
        with s._lock:
            s._removing = True

        while 1:
            if s.state() == "removed":
                return
            s.sleep(100)


    def isRemoving(s):
        with s._lock:
            return s._removing


    def name(s):
        return s._name


    def id(s):
        return s._id


    def tid(s):
        return s._tid


    def setState(s, state):
        with s._lock:
            s._state = state
            s.log.info("set state %s" % state)


    def state(s):
        with s._lock:
            return s._state


    @staticmethod
    def doObserveTasks():
        ot = Task.observeTask
        while 1:
            with Task.listTasksLock:
                for t in Task.listTasks:
                    if t.state() == "running":
                        t.checkForAlive()

            Task.sleep(10000)
            with Task.listTasksLock:
                for t in Task.listTasks:
                    if t.state() != "running":
                        continue
                    if not t.isAlived():
                        t.setFreezed()
                        if t.exitCb:
                            t.exitCb()
                        ot.log.info("task %d:%s is freezed" % (t.id(), t.name()))
                        ot.telegram.send("task %d:%s is freezed. Task stopped." % (t.id(), t.name()))


    @staticmethod
    def runObserveTasks():
        Task.observeTask = Task("observe")
        Task.observeTask.setCb(Task.doObserveTasks)
        Task.observeTask.start()


    @staticmethod
    def taskById(id):
        with Task.listTasksLock:
            for t in Task.listTasks:
                if t.id() == id:
                    return t
        return None


    @staticmethod
    def taskByTid(tid):
        with Task.listTasksLock:
            for t in Task.listTasks:
                if t.tid() == tid:
                    return t
        return None


    @staticmethod
    def taskByName(name):
        with Task.listTasksLock:
            for t in Task.listTasks:
                if t.name() == name:
                    return t
        return None


    @staticmethod
    def sleep(interval = 0):
        tid = threading.get_ident()
        task = Task.taskByTid(tid)
        if not task:
            print("sleep in not task %d" % interval)
            time.sleep(interval / 1000)
            return

        t = interval
        while (1):
            task.iAmAlive()
            if task.state() == "stopping":
                raise TaskStopException

            while(task.state() == "paused"):
                time.sleep(1/10)

            if t >= 100:
                time.sleep(1/10)
                t -= 100

            if t <= 0:
                break


    @staticmethod
    def asyncRunSingle(name, fn, exitCb = None):
        with Task.listAsyncLock:
            list = Task.listAsyncFunctions

        if name in list:
            with Task.listAsyncLock:
                task = Task.listAsyncFunctions[name]
            task.stop()
            task.remove()
            with Task.listAsyncLock:
                Task.listAsyncFunctions.pop(name)

        task = Task("Async_%s" % name, exitCb)
        def do():
            fn()
            task.remove()
        task.setCb(do)
        task.start()
        with Task.listAsyncLock:
            Task.listAsyncFunctions[name] = task
        return task



    def __str__(s):
        str = "task %d:%s/%s" % (s._id, s._name, s.state())
        if s._removing:
            str += ":removing"
        return str


    @staticmethod
    def setTimeout(name, interval, cb):
        task = Task('timeout_task_%s' % name)

        def timeout():
            nonlocal task
            Task.sleep(interval)
            task.log.info("timeout expire")
            cb()
            task.remove()

        task.setCb(timeout)
        task.start()
        return task


    @staticmethod
    def setPeriodic(name, interval, cb):
        task = Task('periodic_task_%s' % name)

        def do():
            nonlocal task
            while 1:
                task.sleep(interval)
                cb()

        task.setCb(do)
        task.start()
        return task


    @staticmethod
    def printList():
        with Task.listTasksLock:
            for tsk in Task.listTasks:
                print("%s" % tsk)



