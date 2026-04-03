"""
Depsgraph handler: avoids recomputing everything on every click / redraw.

Blender fires depsgraph_update_post often (selection, transforms, etc.).
The old version walked the whole scene and rebuilt link lists each time,
which felt like "everything updates" when clicking a mesh.
"""

import time
from typing import Optional, Tuple

import bpy
from bpy.app.handlers import persistent

from . import constants

# Last 3D View selection state for YMAP list sync (avoids rewriting the UI in a loop).
_gta_last_sel_key = None


def compute_selection_key_from_context(context) -> Optional[Tuple[int, Tuple[int, ...]]]:
    try:
        vl = context.view_layer
        active = vl.objects.active
        ap = active.as_pointer() if active else 0
        sels = tuple(sorted(o.as_pointer() for o in vl.objects if o.select_get()))
        return (ap, sels)
    except Exception:
        return None


def set_selection_sync_cache(key) -> None:
    global _gta_last_sel_key
    _gta_last_sel_key = key


def invalidate_selection_sync_cache() -> None:
    set_selection_sync_cache(None)


def apply_ymap_list_selection_from_3d(links, selected_set) -> None:
    """Set each link's UI `selected` flag from the 3D selection (incl. mesh children of EMPTY/ARMATURE)."""
    from . import ymap_core as yc

    for lnk in links:
        t = getattr(lnk, "target", None)
        lnk.selected = yc.gta_ymap_link_row_matches_3d_selection(t, selected_set)


def _collect_object_updates(depsgraph):
    """Returns (touch_objects, transform_objs)."""
    touch_objects = False
    transform_objs = []
    for u in depsgraph.updates:
        bid = u.id
        if isinstance(bid, bpy.types.Object):
            touch_objects = True
            if getattr(u, "is_updated_transform", False):
                transform_objs.append(bid)
    return touch_objects, transform_objs


@persistent
def gta_on_load_post(_dummy):
    """Clear caches after loading a .blend (stale pointers)."""
    from . import ymap_core

    invalidate_selection_sync_cache()
    ymap_core.clear_link_sync_fingerprints()


@persistent
def gta_on_depsgraph_update(scene, depsgraph):
    # Lazy import: avoids circular imports when the module loads.
    from . import ymap_core as yc

    _t_handler = time.perf_counter() if constants.GTA_DEBUG_PERF else None
    _t_sec = time.perf_counter() if constants.GTA_DEBUG_PERF else None

    touch_objects, transform_objs = _collect_object_updates(depsgraph)

    # --- 1) Auto full rotation: only if an object's transform changed ---
    for obj in transform_objs:
        if obj.type not in {"MESH", "EMPTY", "ARMATURE"}:
            continue
        if not getattr(obj, "gta_auto_full_rot", False):
            continue
        try:
            quat = obj.matrix_world.to_quaternion()
            eul = quat.to_euler("ZYX")
            should_allow = abs(eul.x) > 1e-4 or abs(eul.y) > 1e-4
            if getattr(obj, "gta_flag_allow_full_rotation", None) != should_allow:
                obj.gta_flag_allow_full_rotation = should_allow
        except Exception:
            pass

    if constants.GTA_DEBUG_PERF:
        from . import perf

        perf.gta_perf_section("1_auto_rotation", _t_sec)
        _t_sec = time.perf_counter()

    # --- 2) Link list sync: only if an Object appears in the depsgraph ---
    if touch_objects:
        for ymap_data in scene.gta_ymaps:
            try:
                yc.gta_sync_ymap_links(ymap_data)
            except Exception:
                pass

    if constants.GTA_DEBUG_PERF:
        from . import perf

        perf.gta_perf_section("2_links_sync", _t_sec)
        _t_sec = time.perf_counter()

    # --- 3) 3D selection <-> list: only when selection actually changed ---
    global _gta_last_sel_key
    try:
        view_layer = bpy.context.view_layer
        active_obj = view_layer.objects.active
    except Exception:
        active_obj = None

    scene_flag = getattr(scene, "gta_sync_ymap_selection", True)
    try:
        ctx_flag = getattr(bpy.context.scene, "gta_sync_ymap_selection", scene_flag)
    except Exception:
        ctx_flag = scene_flag

    if not (scene_flag and ctx_flag):
        if constants.GTA_DEBUG_PERF:
            from . import perf

            perf.gta_perf_section("3_sel_sync", _t_sec)
            _record_total_perf(_t_handler)
        return

    sk = compute_selection_key_from_context(bpy.context)
    if sk == _gta_last_sel_key:
        if constants.GTA_DEBUG_PERF:
            from . import perf

            perf.gta_perf_section("3_sel_sync", _t_sec)
            _record_total_perf(_t_handler)
        return

    _gta_last_sel_key = sk

    try:
        selected_objs = [o for o in bpy.context.view_layer.objects if o.select_get()]
    except Exception:
        try:
            selected_objs = list(getattr(bpy.context, "selected_objects", []) or [])
        except Exception:
            selected_objs = []

    if len(selected_objs) == 0:
        try:
            bpy.context.view_layer.objects.active = None
        except Exception:
            pass
        for ymap_data in scene.gta_ymaps:
            ymap_data.gta_ymap_links_index = -1
            for lnk in ymap_data.gta_ymap_links:
                lnk.selected = False
        if constants.GTA_DEBUG_PERF:
            from . import perf

            perf.gta_perf_section("3_sel_sync", _t_sec)
            _record_total_perf(_t_handler)
        return

    selected_set = frozenset(selected_objs)

    if active_obj is not None:
        lineage = []
        cur = active_obj
        while cur is not None:
            lineage.append(cur)
            cur = getattr(cur, "parent", None)

        for ymap_data in scene.gta_ymaps:
            links = ymap_data.gta_ymap_links
            for i, link in enumerate(links):
                target = getattr(link, "target", None)
                if target is active_obj:
                    apply_ymap_list_selection_from_3d(links, selected_set)
                    ymap_data.gta_ymap_last_index = i
                    if getattr(ymap_data, "gta_ymap_links_index", -1) != i:
                        ymap_data.gta_ymap_links_index = i
                    scene.gta_skip_view_sync_once = True
                    yc.gta_on_ymap_link_index_update(ymap_data, bpy.context)
                    if constants.GTA_DEBUG_PERF:
                        from . import perf

                        perf.gta_perf_section("3_sel_sync", _t_sec)
                        _record_total_perf(_t_handler)
                    return

            for i, link in enumerate(links):
                target = getattr(link, "target", None)
                if target in lineage:
                    apply_ymap_list_selection_from_3d(links, selected_set)
                    ymap_data.gta_ymap_last_index = i
                    if getattr(ymap_data, "gta_ymap_links_index", -1) != i:
                        ymap_data.gta_ymap_links_index = i
                    scene.gta_skip_view_sync_once = True
                    yc.gta_on_ymap_link_index_update(ymap_data, bpy.context)
                    if constants.GTA_DEBUG_PERF:
                        from . import perf

                        perf.gta_perf_section("3_sel_sync", _t_sec)
                        _record_total_perf(_t_handler)
                    return

        for ymap_data in scene.gta_ymaps:
            ymap_data.gta_ymap_links_index = -1
            for lnk in ymap_data.gta_ymap_links:
                lnk.selected = False

    if constants.GTA_DEBUG_PERF:
        from . import perf

        perf.gta_perf_section("3_sel_sync", _t_sec)
        _record_total_perf(_t_handler)


def _record_total_perf(_t_handler):
    if _t_handler is None:
        return
    from . import constants as C
    from . import perf

    total_ms = (time.perf_counter() - _t_handler) * 1000.0
    p = perf.gta_perf_state
    p["calls"] += 1
    p["total_ms"] += total_ms
    p["last_ms"] = total_ms
    p["history"].append(total_ms)
    if total_ms > p["max_ms"]:
        p["max_ms"] = total_ms
    if total_ms > C.GTA_DEBUG_SPIKE_MS:
        p["spikes"] += 1
        s = p["section_total"]
        c = p["section_calls"]
        print(
            f"[GTA PERF] SPIKE {total_ms:.2f}ms "
            f"| auto_rot={s.get('1_auto_rotation', 0) / max(c.get('1_auto_rotation', 1), 1):.2f}ms "
            f"| links_sync={s.get('2_links_sync', 0) / max(c.get('2_links_sync', 1), 1):.2f}ms "
            f"| sel_sync={s.get('3_sel_sync', 0) / max(c.get('3_sel_sync', 1), 1):.2f}ms"
        )


def redraw_gta_ui():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
