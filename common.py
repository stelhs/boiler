import os

def filePutContent(filename, data):
    f = open(filename, "w")
    f.write(data)
    f.flush()
    f.close()


def fileGetContent(filename):
    f = open(filename, "r")
    data = f.read()
    f.close()
    return data


def fileGetBinary(filename):
    f = open(filename, "rb")
    data = f.read()
    f.close()
    return data


def timeStr(time):
    if time < 60:
        return "%d sec" % time

    if time < 3600:
        return "%d min, %d sec" % (time / 60,
                 time - (int(time / 60) * 60))

    if time < 60 * 60 * 24:
        return "%d hour, %d min" % (time / 3600, (time - (int(time / 3600) * 3600)) / 60)

