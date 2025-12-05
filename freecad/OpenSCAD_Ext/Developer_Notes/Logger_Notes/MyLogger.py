import FreeCAD

class MyLogger:
    def __init__(self):
        FreeCAD.Console.AddLogHandler(self)

    def log(self, msg, level):
        # level: 0=message, 1=warning, 2=error
        print(f"[FC-{level}] {msg}")

logger = MyLogger()

