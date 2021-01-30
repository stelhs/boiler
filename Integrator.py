
class Integrator():
    def __init__(s):
        s.reset()


    def add(s, val):
        s.queue.append(val)


    def addQueue(s, queue):
        if not len(queue):
            return

        for val in queue:
            s.queue.append(val)


    def overage(s):
        sum = 0.0
        size = len(s.queue)
        if not size:
            return 0

        for val in s.queue:
            sum += val
        return sum / size


    def reset(s):
        s.queue = []
