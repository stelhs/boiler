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

    def __init__(s, name):
        s._name = name

        if Task.taskByName(name):
            raise Exception("Task with name '%s' is existed" % name)
        s.listTasks.append(s)
        s.log = Syslog("task_%s" % name)
        s.telegram = Telegram("task_%s" % name)
        s.log.debug("created")
        s._lock = threading.Lock()
        with s._lock:
            Task.lastId += 1
            s._id = Task.lastId


    def start(s):
        s.log.info("start")
        t = threading.Thread(target=s.thread, daemon=True, args=(s._name, ))
        t.start()
        s._state = "running"


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

        with s._lock:
            s._state = "stopped"

            if s._removing:
                s.log.info("removed")
                Task.listTasks.remove(s)
                s._state == "removed"
                s.log.info("removed")


    def stop(s):
        with s._lock:
            if s._state != "running":
                return
            s.log.info("stoping")

            s._state = "stopping"


    def pause(s):
        with s._lock:
            s.log.info("paused")
            s._state = "paused"


    def resume(s):
        with s._lock:
            if s._state != "paused":
                return
            s.log.info("resumed")
            s._state = "running"


    def remove(s):
        with s._lock:
            if s._state == "stopped":
                Task.listTasks.remove(s)
                s._state == "removed"
                s.log.info("removed")
                return

            s.log.info("removing")
            s._removing = True


    def name(s):
        return s._name


    def id(s):
        return s._id


    def tid(s):
        return s._tid


    def waitForRemoved(s):
        while 1:
            if s._state == "removed":
                return
            s.sleep(100)

    @staticmethod
    def taskById(id):
        for t in Task.listTasks:
            if t.id() == id:
                return t
        return None


    @staticmethod
    def taskByTid(tid):
        for t in Task.listTasks:
            if t.tid() == tid:
                return t
        return None


    @staticmethod
    def taskByName(name):
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
            if task._state == "stopping":
                raise TaskStopException

            while(task._state == "paused"):
                time.sleep(1/10)

            if t >= 100:
                time.sleep(1/10)
                t -= 100

            if t <= 0:
                break


    def __str__(s):
        str = "task %d %s/%s" % (s._id, s._name, s._state)
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
        for tsk in Task.listTasks:
            print("%s" % tsk)

