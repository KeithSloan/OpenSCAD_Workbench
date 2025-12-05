import sys

class PrintLogger:
    def write(self, msg):
        if msg.strip():   # ignore empty lines
            FreeCAD.Console.PrintMessage(f"[PRINT] {msg}")

    def flush(self):
        pass  # required for Python file-like interface

# Install logger
sys.stdout = PrintLogger()

