import os, sys, datetime, threading, FreeCAD

# --- Log file path ---
LOG_DIR = os.path.join(FreeCAD.getUserAppDataDir(), "OpenSCAD_Ext")
LOG_FILE = os.path.join(LOG_DIR, "workbench.log")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

_lock = threading.Lock()

def _timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def write_log(level, msg):
    """Write message to the log file only.

    Nothing goes to the FreeCAD Report View panel here.  Callers that want a
    visible panel message for genuine failures should call
    FreeCAD.Console.PrintError() / PrintWarning() explicitly alongside
    write_log(), so the distinction between normal fallback activity (silent)
    and real geometry loss (visible) is clear at the call site.
    """
    with _lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{_timestamp()} [{level}] {msg}\n")

# --- Redirect Python print ---
#class PrintLogger:
#    def write(self, msg):
#        msg = msg.rstrip()
#        if msg:
#            write_log("PRINT", msg)
#    def flush(self):
#        pass

# --- Redirect Python errors ---
#class ErrorLogger(PrintLogger):
#    def write(self, msg):
#        msg = msg.rstrip()
#        if msg:
#            write_log("ERROR", msg)

# --- Initialize logger ---
def init():
    """Install logging handlers and write confirmation."""
    #ys.stdout = PrintLogger()
    #sys.stderr = ErrorLogger()
    write_log("INIT", "Logging started for OpenSCAD_Ext")

    # Also print a clear confirmation to Report View / console
    msg = "OpenSCAD_Ext logger successfully registered — output active"
    write_log("INIT", msg)
    print(msg)  # ensures print() also goes to log
if FreeCAD.GuiUp:
    FreeCAD.Console.PrintError(f"OpenSCAD_Ext logger active, log file: {LOG_FILE}\n")
