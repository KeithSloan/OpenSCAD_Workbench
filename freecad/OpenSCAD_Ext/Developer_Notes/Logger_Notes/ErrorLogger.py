class ErrorLogger(PrintLogger):
    def write(self, msg):
        if msg.strip():
            FreeCAD.Console.PrintError(f"[ERR] {msg}")

sys.stdout = PrintLogger()
sys.stderr = ErrorLogger()

