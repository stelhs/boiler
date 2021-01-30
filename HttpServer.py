import socket
import select
from Task import *


class HttpServer():
    subscribers = []
    def __init__(s, host, port):
        s._host = host
        s._port = port

        s._task = Task('http_server_%s:%d' % (host, port))
        s._task.setCb(s.taskDo)
        s._task.start()


    def taskDo(s):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((s._host, s._port))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(1.0)
            sock.listen(5)
            while 1:
                while 1:
                    try:
                        conn, addr = sock.accept()
                    except socket.error:
                        Task.sleep(0)
                        continue
                    break
                httpConn = HttpConnection(conn, addr)


    def setReqCb(s, method, page, cb):
        HttpServer.subscribers.append((method, page, cb))



class HttpConnection():
    def __init__(s, conn, remoteAddr):
        s._conn = conn
        s.log = Syslog("http_connection_%s:%d" % (remoteAddr[0], remoteAddr[1]))
        s._task = Task("http_connection_%s:%d" % (remoteAddr[0], remoteAddr[1]))
        s._task.setCb(s.taskDo)
        s._task.start()


    def taskDo(s):
        with s._conn:
            poll = select.poll()
            poll.register(s._conn.fileno(), select.POLLIN)
            while 1:
                Task.sleep()
                poll_list = poll.poll(100)
                if not len(poll_list):
                    continue

                data = s._conn.recv(65535)
                if (not data) or (not len(data)):
                    s._task.remove()
                    return

                try:
                    req = data.decode()
                except:
                    s._task.remove()
                    return

                parts = s.parseHttpReq(req)
                if not parts:
                    s._task.remove()
                    return

                method, url, version, attrs, body = parts
                s.log.info("%s %s" % (method, url))

                page, args = s.parseUrl(url)
                found = False
                for (sMethod, sPage, sCb) in HttpServer.subscribers:
                    if sMethod == method and sPage == page:
                        found = True
                        content = sCb(args, body)
                        break

                if found:
                    s.log.info('response 200 OK')
                    s.respOk(content)
                else:
                    s.log.info('response 404 ERROR')
                    s.resp404()

                s._conn.close()
                s._task.remove()
                return


    def parseHttpReq(s, req):
        parts = req.split("\r\n\r\n")
        if not len(parts):
            return

        header = parts[0]
        body = None
        if len(parts) > 1:
            body = parts[1]

        lines = header.split("\n")
        if not len(lines):
            return None

        if not len(lines):
            return None

        parts = lines[0].split()
        if len(parts) < 2:
            return None

        method, url, version = parts

        attrs = {}
        for line in lines[1:]:
            if not line.strip():
                continue

            row = line.split(":")
            name = row[0].strip()
            val = row[1].strip()
            attrs[name] = val

        return (method, url, version, attrs, body)


    def parseUrl(s, url):
        parts = url.split("?")
        if not parts:
            return None

        if len(parts) == 1:
            return (url, None)

        page = parts[0]
        argsText = parts[1].split("&")
        args = {}
        for keyVal in argsText:
            row = keyVal.split("=")
            if len(row) < 2:
                continue
            key, val = keyVal.split("=")
            args[key] = val

        return (page, args)


    def respOk(s, data = ""):
        str = "HTTP/1.1 200 OK\n"
        str += "Content-Type: text/plain\n"
        str += "Content-Length: %d\n" % len(data)
        str += "\n"
        str += data
        s._conn.sendall(str.encode())


    def respBadRequest(s, data = ""):
        str = "HTTP/1.1 400 Bad Request\n"
        str += "Content-Type: text/plain\n"
        str += "Content-Length: %d\n" % len(data)
        str += "\n"
        str += data
        s._conn.sendall(str.encode())


    def resp404(s):
        content = "404 Page not found"
        str = "HTTP/1.1 404 Page Not Found\n"
        str += "Content-Type: text/plain\n"
        str += "Content-Length: %d\n" % len(content)
        str += "\n"
        str += content
        s._conn.sendall(str.encode())

