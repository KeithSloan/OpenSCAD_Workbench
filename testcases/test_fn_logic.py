"""
test_fn_logic.py — unit tests for the $fn threshold logic in processAST.py.

Run standalone (no FreeCAD required) to verify the _use_brep rule.
The shape-building helpers (_make_prism etc.) require FreeCAD/Part so are
tested only at the integration level via fn_threshold_test.csg.
"""

import sys

# ── Replicate the _use_brep logic locally for standalone testing ──────────────
_fnmax = 16   # default preference value

def _use_brep(fn_val):
    n = int(round(float(fn_val))) if fn_val else 0
    return n < 3 or _fnmax == 0 or n > _fnmax


# ── Test cases ────────────────────────────────────────────────────────────────
failures = 0

def check(desc, got, want):
    global failures
    status = "PASS" if got == want else "FAIL"
    if got != want:
        failures += 1
    print(f"  [{status}] {desc}: got={got}, want={want}")

print(f"\n_fnmax = {_fnmax}\n")

print("$fn == 0 (unspecified) → BRep")
check("fn=0",  _use_brep(0),  True)

print("\n$fn < 3 (degenerate) → BRep")
check("fn=1",  _use_brep(1),  True)
check("fn=2",  _use_brep(2),  True)

print("\n$fn <= fnmax → polygon/prism")
check("fn=3",   _use_brep(3),   False)
check("fn=8",   _use_brep(8),   False)
check("fn=16",  _use_brep(16),  False)   # AT threshold → prism

print("\n$fn > fnmax → BRep")
check("fn=17",  _use_brep(17),  True)    # just above → BRep
check("fn=32",  _use_brep(32),  True)
check("fn=50",  _use_brep(50),  True)

print("\n_fnmax=0 (threshold disabled) → always BRep")
_fnmax_saved = _fnmax
_fnmax = 0
check("fn=8  fnmax=0",  _use_brep(8),  True)
check("fn=32 fnmax=0",  _use_brep(32), True)
_fnmax = _fnmax_saved

print(f"\n{'All tests passed.' if failures == 0 else f'{failures} test(s) FAILED.'}\n")
sys.exit(0 if failures == 0 else 1)
