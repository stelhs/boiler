from common import *
import json
import os


class Store():
    tree = {"target_room_t": "18",
            "target_boiler_min_t": "60",
            "target_boiler_max_t": "80",
            }
    storeFile = "store.js"

    def __init__(s):
        if not os.path.exists(s.storeFile):
            s.save()
            return
        s.load()


    def load(s):
        c = fileGetContent(s.storeFile)
        s.tree = json.loads(c)



    def save(s):
        d = json.dumps(s.tree)
        filePutContent(s.storeFile, d)

