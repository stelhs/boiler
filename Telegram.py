import os
from common import *

class Telegram():
    def __init__(s, name):
        s._name = name
        s._chatId = int(fileGetContent(".telegram_chat_id"))
        s.lastMessage = None
        s._sameMsgCnt = 0


    def send(s, msg):
        return
        def sendMsg(msg):
            os.system("./telegram.php msg_send %d '%s: %s'" % (
                            s._chatId, s._name, msg))

        if not msg:
            return

        if s.lastMessage == msg:
            s._sameMsgCnt += 1
            return

        if s._sameMsgCnt:
            sendMsg('message repeated %d times: [ %s ]' % (
                        s._sameMsgCnt, s.lastMessage))
            s._sameMsgCnt = 0

        s.lastMessage = msg
        sendMsg(msg)



