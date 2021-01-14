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

