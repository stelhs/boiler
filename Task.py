import threading
import time
from Syslog import *


class TaskStopException(Exception):
    pass


class Task():
    listTasks = []
    _state = "stopped"
    _id = None

    def __init__(s, name):
        s._name = name

        if Task.taskByName(name):
            raise Exception("Task with name '%s' is existed" % name)
        s.listTasks.append(s)
        s.log = Syslog("task")


    def start(s):
        s.log.info("staring task %s" % s._name)
        t = threading.Thread(target=s.thread, daemon=True, args=(s._name, ))
        t.start()
        s._state = "running"


    def setCb(s, cb):
        s.do = cb


    def thread(s, name):
        s._id = threading.get_ident()
        try:
            if s.do:
                s.do()
        except TaskStopException:
            s.log.info("task %s is stopped" % s._name)
        s._state = "stopped"


    def stop(s):
        if s._state != "running":
            return
        s.log.info("task %s is stoping" % s._name)
        s._state = "stopping"


    def pause(s):
        s.log.info("task %s paused" % s._name)
        s._state = "paused"


    def resume(s):
        if s._state != "paused":
            return
        s.log.info("task %s resumed" % s._name)
        s._state = "running"


    def name(s):
        return s._name


    def id(s):
        return s._id


    def taskById(id):
        for t in Task.listTasks:
            if t.id() == id:
                return t
        return None


    def taskByName(name):
        for t in Task.listTasks:
            if t.name() == name:
                return t
        return None


    def sleep(interval = 0):
        id = threading.get_ident()
        task = Task.taskById(id)
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
        return "Task %s, state: %s" % s._state


    def printListTasks():
        for tsk in s.listTasks:
            print("%s\n" % tsk)

