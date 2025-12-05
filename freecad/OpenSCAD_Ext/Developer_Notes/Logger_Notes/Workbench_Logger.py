import os, sys, datetime, threading, FreeCAD

LOG_DIR = os.path.join(FreeCAD.getUserAppDataDir(), "gbXMLWorkbench")
LOG_FILE = os.path.join(LOG_DIR, "workbench.log")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

_lock = threading.Lock()

def _timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def write_log(level, msg):
    with _lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{_timestamp()} [{level}] {msg}\n")

# --- Redirect Python print ---
class PrintLogger:
    def write(self, msg):
        msg = msg.rstrip()
        if msg:
            write_log("PRINT", msg)
    def flush(self):
        pass

# --- Redirect Python errors ---
class ErrorLogger(PrintLogger):
    def write(self, msg):
        msg = msg.rstrip()
        if msg:
            write_log("ERROR", msg)

# --- Capture FreeCAD internal console messages (optional) ---
class FCHandler:
    def log(self, msg, level):
        # level: 0=Msg, 1=Warn, 2=Err
        lvl = {0:"FC", 1:"FC-WARN", 2:"FC-ERR"}.get(level, "FC")
        write_log(lvl, msg.rstrip())

def init():
    # install handlers
    sys.stdout = PrintLogger()
    sys.stderr = ErrorLogger()
    FreeCAD.Console.AddLogHandler(FCHandler())
    write_log("INIT", "Logging started")

