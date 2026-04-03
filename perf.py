"""Performance counters (optional when constants.GTA_DEBUG_PERF is True)."""

import collections
import time

import bpy
from bpy.types import Operator

from . import constants

gta_perf_state = {
    "calls": 0,
    "total_ms": 0.0,
    "last_ms": 0.0,
    "max_ms": 0.0,
    "spikes": 0,
    "history": collections.deque(maxlen=constants.GTA_DEBUG_HISTORY),
    "section_max": {},
    "section_total": {},
    "section_calls": {},
}


def gta_perf_section(name, t0):
    elapsed = (time.perf_counter() - t0) * 1000.0
    p = gta_perf_state
    p["section_total"][name] = p["section_total"].get(name, 0.0) + elapsed
    p["section_calls"][name] = p["section_calls"].get(name, 0) + 1
    if elapsed > p["section_max"].get(name, 0.0):
        p["section_max"][name] = elapsed
    return elapsed


def gta_perf_report():
    p = gta_perf_state
    if p["calls"] == 0:
        print("[GTA PERF] No data yet.")
        return
    avg = p["total_ms"] / p["calls"]
    print("\n" + "=" * 55)
    print("  GTA YMAP - Handler performance report")
    print("=" * 55)
    print(f"  Total calls      : {p['calls']}")
    print(f"  Average time     : {avg:.3f} ms")
    print(f"  Max spike        : {p['max_ms']:.3f} ms")
    print(f"  Spikes > {constants.GTA_DEBUG_SPIKE_MS:.1f} ms   : {p['spikes']}")
    print(f"  Cumulative time  : {p['total_ms']:.1f} ms  ({p['total_ms'] / 1000:.2f} s)")
    print("-" * 55)
    print("  Per section:")
    for sec, total in sorted(p["section_total"].items()):
        calls = p["section_calls"].get(sec, 1)
        mx = p["section_max"].get(sec, 0.0)
        print(f"    {sec:<22} avg={total / calls:.3f}ms  max={mx:.3f}ms  calls={calls}")
    print("-" * 55)
    if p["history"]:
        hist = list(p["history"])
        print(f"  Last {len(hist)} calls: avg={sum(hist) / len(hist):.3f}ms  max={max(hist):.3f}ms")
    print("=" * 55 + "\n")


def gta_perf_reset():
    p = gta_perf_state
    p["calls"] = 0
    p["total_ms"] = 0.0
    p["last_ms"] = 0.0
    p["max_ms"] = 0.0
    p["spikes"] = 0
    p["history"].clear()
    p["section_max"].clear()
    p["section_total"].clear()
    p["section_calls"].clear()
    print("[GTA PERF] Counters reset.")


class GTA_OT_perf_report(Operator):
    bl_idname = "gta.perf_report"
    bl_label = "Performance report (console)"

    def execute(self, context):
        gta_perf_report()
        self.report({"INFO"}, "Report printed to system console")
        return {"FINISHED"}


class GTA_OT_perf_reset(Operator):
    bl_idname = "gta.perf_reset"
    bl_label = "Reset performance counters"

    def execute(self, context):
        gta_perf_reset()
        self.report({"INFO"}, "Counters reset")
        return {"FINISHED"}
