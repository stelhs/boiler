import threading
import time
from Syslog import *
from Telegram import *
from common import *
import traceback


class TaskStopException(Exception):
    pass


class Task():
    listTasks = []
    _state = "stopped"
    _removing = False
    _tid = None
    cb = None
    log = Syslog("task")
    lastId = 0
    tasksLock = threading.Lock()

    def __init__(s, name):
        s._name = name
        s._msgQueue = []

        if Task.taskByName(name):
            raise Exception("Task with name '%s' is existed" % name)

        with Task.tasksLock:
            s.listTasks.append(s)

        s.log = Syslog("task_%s" % name)
        s.telegram = Telegram("task_%s" % name)
        s.log.debug("created")
        s._lock = threading.Lock()
        with s._lock:
            Task.lastId += 1
            s._id = Task.lastId
            s._alive = False


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


    def message(s):
        with s._lock:
            if not len(s._msgQueue):
                return None

            msg = s._msgQueue[0]
            s._msgQueue.remove(s._msgQueue[0])
            return msg


    def start(s):
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
            if s.cb:
                if s.cbArgs:
                    s.cb((s.cbArgs))
                else:
                    s.cb()
            else:
                s.do()
        except TaskStopException:
            s.log.info("stopped")
        except Exception as e:
            trace = traceback.format_exc()
            s.log.error("Exception: %s" % trace)
            print("Task '%s' Exception:\n%s" % (s._name, trace))
            s.telegram.send("stopped by exception: %s" % trace)

        s.setState("stopped")

        if s._removing:
            s.setState("removed")
            s.log.info("removed by flag")
            with Task.tasksLock:
                Task.listTasks.remove(s)


    def stop(s):
        if s.state() != "running":
            return
        s.log.info("stopping")
        s.setState("stopping")


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
            with Task.tasksLock:
                Task.listTasks.remove(s)
            s.setState("removed")
            s.log.info("removed")
            return

        s.log.info("removing")
        with s._lock:
            s._removing = True


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


    def waitForRemoved(s): #TODO !!
        while 1:
            if s.state() == "removed":
                return
            s.sleep(100)


    @staticmethod
    def doObserveTasks():
        ot = Task.observeTask
        while 1:
            with Task.tasksLock:
                for t in Task.listTasks:
                    if t.state() == "running":
                        t.checkForAlive()

            Task.sleep(4000)
            with Task.tasksLock:
                for t in Task.listTasks:
                    if t.state() != "running":
                        continue
                    if not t.isAlived():
                        t.setFreezed()
                        ot.log.info("task %d:%s is freezed" % (t.id(), t.name()))
                        ot.telegram.send("task %d:%s is freezed. Task stopped." % (t.id(), t.name()))


    @staticmethod
    def runObserveTasks():
        Task.observeTask = Task("observe")
        Task.observeTask.setCb(Task.doObserveTasks)
        Task.observeTask.start()


    @staticmethod
    def taskById(id):
        with Task.tasksLock:
            for t in Task.listTasks:
                if t.id() == id:
                    return t
        return None


    @staticmethod
    def taskByTid(tid):
        with Task.tasksLock:
            for t in Task.listTasks:
                if t.tid() == tid:
                    return t
        return None


    @staticmethod
    def taskByName(name):
        with Task.tasksLock:
            for t in Task.listTasks:
                if t.name() == name:
                    return t
        return None


    @staticmethod
    def sleep(interval = 0):
        tid = threading.get_ident()
        task = Task.taskByTid(tid)
        if not task:
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
    def printList():
        with Task.tasksLock:
            for tsk in Task.listTasks:
                print("%s" % tsk)



