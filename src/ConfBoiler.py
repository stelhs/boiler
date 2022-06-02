from ConfParser import *


class ConfBoiler(ConfParser):
    def __init__(s):
        super().__init__()
        s.addConfig('boiler', 'boiler.conf')
        s.addConfig('telegram', 'telegram.conf')


