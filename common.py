import os

def filePutContent(filename, data):
    f = open(filename, "w")
    f.write(data)
    f.close()


def fileGetContent(filename):
    f = open(filename, "r")
    data = f.read()
    f.close()
    return data


def printToTelegram(msg):
    fd = open(".telegram_chat_id", "r")
    content = fd.read()
    fd.close()
    chatId = int(content)
    os.system("./telegram.php msg_send %s '%s'" % (chatId, msg))