import socket
import threading
import json
from Task import *
from Settings import *
from HttpServer import *


class UiNotifier():
    def __init__(s, conf):
        s.conf = conf
        s.lock = threading.Lock()

        s.conn = None
        s.notifyQueue = []
        s.task = Task('ui_notifyer', s.close)
        s.task.setCb(s.doTask)
        s.task.start()
        s.log = Syslog('ui_notifyer')


    def doTask(s):
        while 1:
            if not s.isConnected():
                rc = s.connect()
                if not rc:
                    Task.sleep(3000)
                    continue

            with s.lock:
                n = len(s.notifyQueue)

            if not n:
                s.task.waitMessage(60)
                with s.lock:
                    n = len(s.notifyQueue)

            if not n:
                s.close()
                continue

            with s.lock:
                queue = s.notifyQueue
            for item in queue:
                (type, data) = item
                rc = s.send(type, data)
                if not rc:
                    s.close()
                    continue

                with s.lock:
                    s.notifyQueue.remove(item)


    def notify(s, type, data):
        with s.lock:
            s.notifyQueue.append((type, data))
            s.task.sendMessage('event')


    def send(s, type, data):
        if not s.conn:
            return False

        d = {'sender': 'boiler',
             'type': type,
             'data': data}
        payload = json.dumps(d)

        header = "POST /send_event http/1.1\r\n"
        header += "Host: %s\r\n" % s.conf.boilerHost
        header += "Connection: keep-alive\r\n"
        header += "Content-Type: text/json\r\n"
        header += "Content-Length: %s\r\n" % len(payload.encode('utf-8'))
        header += "\r\n"
        try:
            s.conn.send((header + payload).encode('utf-8'))
        except:
            s.log.err('can`t sending data to UI server: "%s"' % payload)
            return False

#        s.log.info('sended to UI: %s' % payload)

        try:
            resp = s.conn.recv(16535).decode()
        except Exception as e:
            s.log.err("Can't receive from socket: %s" % e)
            return False

        parts = HttpServer.parseHttpResponce(resp)
        if not parts:
            s.log.err('No valid responce from UI server: %s' % resp)
            return False

        version, respCode, respCodeText, attrs, body = parts
        if version != 'HTTP/1.1':
            s.log.err('Incorrect version of HTTP protocol: %s' % version)
            return False

        if respCode != '200':
            s.log.err('Incorrect responce code: %s' % respCode)
            return False

        try:
            jsonResp = json.loads(body)
        except Exception as e:
            s.log.err("Can't decode responce as JSON: %s" % body)
            return False

        if not 'status' in jsonResp:
            s.log.err("field 'status' is absent in responce: %s" % body)
            return False

        if jsonResp['status'] != 'ok':
            s.log.err("status is not OK: %s" % body)
            return False

        return True


    def connect(s):
        if s.conn:
            return
        try:
            s.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.conn.connect((s.conf.uiServerHost, s.conf.uiServerPort))
        except:
            s.conn = None
            s.log.err('can`t connect to UI server')
            return False

        return True


    def isConnected(s):
        return s.conn != None


    def close(s):
        if not s.conn:
            return
        try:
            s.connectnn.shutdown(socket.SHUT_RDWR)
            s.conn.close()
        except:
            pass
        s.conn = None


