import sys

def trace(frame, event, arg):
    if event == "call":
        print("CALL:", frame.f_code.co_name, "in", frame.f_code.co_filename)
    return trace

sys.settrace(trace)

