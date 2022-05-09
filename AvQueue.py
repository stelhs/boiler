
class AvQueue():
    def __init__(s, size):
        s.size = size
        s.clear()

    def push(s, val):
        s._q.append(val)
        if len(s._q) > s.size:
            s._q = s._q[1:]


    def round(s):
        s._q.sort()
        return s._q[int((len(s._q) / 2) - 1)]


    def clear(s):
        s._q = []