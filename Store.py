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
        with s.lock:
            s.load()


    def load(s):
        c = fileGetContent(s.storeFile)
        s.tree = json.loads(c)


    def save(s):
        d = json.dumps(s.tree)
        filePutContent(s.storeFile, d)

