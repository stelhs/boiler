from common import *
import threading
import json
import os


class Store():
    tree = {"target_room_t": "18",
            "target_boiler_min_t": "60",
            "target_boiler_max_t": "80",
            "burning_time": 0,
            "ignition_counter": 0,
            "overage_room_t": {},
            "overage_return_water_t": {},
            "enabled" : "0",
            }
    storeFile = "store.js"

    def __init__(s):
        s.lock = threading.Lock()

        if not os.path.exists(s.storeFile):
            with s.lock:
                s.save()
            return
        s.load()


    def load(s):
        with s.lock:
            c = fileGetContent(s.storeFile)
            tree = json.loads(c)
            s.tree.update(tree)


    def save(s):
        d = json.dumps(s.tree)
        filePutContent(s.storeFile, d)


    def val(s, name):
        with s.lock:
            return s.tree[name]


    def valInt(s, name):
        with s.lock:
            return int(s.tree[name])


    def valFloat(s, name):
        with s.lock:
            return float(s.tree[name])


    def setVal(s, name, val):
        with s.lock:
            s.tree[name] = str(val);
            s.save()


    def incrementVal(s, name):
        with s.lock:
            s.tree[name] = str(int(s.tree[name]) + 1);


    def increaseVal(s, name, upVal):
        with s.lock:
            s.tree[name] = str(int(s.tree[name]) + upVal);





