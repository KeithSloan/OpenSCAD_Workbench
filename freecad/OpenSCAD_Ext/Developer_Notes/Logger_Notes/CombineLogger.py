import sys, FreeCAD

# Capture FreeCAD Console messages
class FCHandler:
    def log(self, msg, level):
        print(f"[FC-{level}] {msg}")

FreeCAD.Console.AddLogHandler(FCHandler())

# Capture Python print and stderr
class PrintLogger:
    def write(self, msg):
        if msg.strip():
            FreeCAD.Console.PrintMessage(f"[PRINT] {msg}")
    def flush(self): pass

class ErrorLogger:
    def write(self, msg):
        if msg.strip():
            FreeCAD.Console.PrintError(f"[TRACEBACK] {msg}")
    def flush(self): pass

sys.stdout = PrintLogger()
sys.stderr = ErrorLogger()

