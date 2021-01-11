import threading
import time


class TaskStopException(Exception):
    pass


class Task():
    listTasks = []
    _stop = 0
    _pause = 0
    _id = None

    def __init__(s, name):
        s._name = name

        if Task.taskByName(name):
            raise Exception("Task with name '%s' is existed" % name)
        s.listTasks.append(s)


    def start(s):
        t = threading.Thread(target=s.thread, daemon=True, args=(s._name, ))
        t.start()


    def setCb(s, cb):
        s.do = cb


    def thread(s, name):
        s._id = threading.get_ident()
        try:
            if s.do:
                s.do()
        except TaskStopException:
            print("task %s is stopped" % s.name())
        s._stop = 0


    def stop(s):
        s._stop = 1


    def pause(s):
        s._pause = 1


    def resume(s):
        s._pause = 0


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
            if task._stop:
                print("rise stop")
                raise TaskStopException

            while(task._pause):
                time.sleep(1/10)

            if t >= 100:
                time.sleep(1/10)
                t -= 100

            if t <= 0:
                break
