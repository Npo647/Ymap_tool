"""YMAP core: RNA properties, flags, and virtual link sync."""
import re

import bpy
from bpy.props import (
    StringProperty,
    IntProperty,
    BoolProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup

_gta_link_sync_fp = {}


def clear_link_sync_fingerprints():
    _gta_link_sync_fp.clear()


def gta_export_ymap_name(name):
    """Name written to XML: text before first '.', spaces and '-' become '_'."""
    if not name or not isinstance(name, str):
        return "YMAP"
    base = name.split(".", 1)[0]
    s = base.replace(" ", "_").replace("-", "_")
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        return "YMAP"
    return s


# ==================================
# ACTIVE YMAP (enum items)
# ==================================
def gta_ymap_items(self, context):
    """Build enum items for YMAPs stored on the scene."""
    items = []
    if context is None:
        return items

    for ymap in getattr(context.scene, "gta_ymaps", []):
        items.append((ymap.name, ymap.name, ""))

    if not items:
        items.append(("NONE", "<No YMAP>", ""))

    return items

# ==================================
# AUTO FULL ROTATION (update callback)
# ==================================
def update_auto_full_rot(self, context):
    """When Auto full rotation is toggled, update gta_flag_allow_full_rotation from the object rotation."""
    # If Auto full rotation is off, do not touch the flag
    if not getattr(self, "gta_auto_full_rot", False):
        return

    try:
        quat = self.matrix_world.to_quaternion()
        eul = quat.to_euler("ZYX")
        # Non-Z rotation: enable the flag
        self.gta_flag_allow_full_rotation = (
            abs(eul.x) > 1e-4 or abs(eul.y) > 1e-4
        )
    except Exception:
        # Cannot read rotation: leave unchanged
        pass

# ==================================
# FLAGS (integer from checkboxes)
# ==================================
def gta_compute_flags(entity, include_auto_full_rot=False):
    """Compute the combined flags integer from the object's checkboxes.

    include_auto_full_rot is kept for compatibility; the result uses the
    gta_flag_allow_full_rotation bool, which the depsgraph handler and
    Auto full rotation callback keep in sync.
    """
    flags_val = 0
    if getattr(entity, "gta_flag_allow_full_rotation", False):
        flags_val |= 1
    if getattr(entity, "gta_flag_stream_low_priority", False):
        flags_val |= 2
    if getattr(entity, "gta_flag_disable_embedded_collisions", False):
        flags_val |= 4
    if getattr(entity, "gta_flag_lod_in_parent_map", False):
        flags_val |= 8
    if getattr(entity, "gta_flag_lod_adopt_me", False):
        flags_val |= 16
    if getattr(entity, "gta_flag_static_entity", True):
        flags_val |= 32
    if getattr(entity, "gta_flag_interior_lod", False):
        flags_val |= 64
    if getattr(entity, "gta_flag_lod_use_alt_fade", False):
        flags_val |= 32768
    if getattr(entity, "gta_flag_underwater", False):
        flags_val |= 65536
    if getattr(entity, "gta_flag_doesnt_touch_water", False):
        flags_val |= 131072
    if getattr(entity, "gta_flag_doesnt_spawn_peds", False):
        flags_val |= 262144
    if getattr(entity, "gta_flag_cast_static_shadows", False):
        flags_val |= 524288
    if getattr(entity, "gta_flag_cast_dynamic_shadows", False):
        flags_val |= 1048576
    if getattr(entity, "gta_flag_ignore_time_settings", False):
        flags_val |= 2097152
    if getattr(entity, "gta_flag_no_render_shadows", False):
        flags_val |= 4194304
    if getattr(entity, "gta_flag_only_render_shadows", False):
        flags_val |= 8388608
    if getattr(entity, "gta_flag_no_render_reflections", False):
        flags_val |= 16777216
    if getattr(entity, "gta_flag_only_render_reflections", False):
        flags_val |= 33554432
    if getattr(entity, "gta_flag_no_render_water_reflections", False):
        flags_val |= 67108864
    if getattr(entity, "gta_flag_only_render_water_reflections", False):
        flags_val |= 134217728
    if getattr(entity, "gta_flag_no_render_mirror_reflections", False):
        flags_val |= 268435456
    if getattr(entity, "gta_flag_only_render_mirror_reflections", False):
        flags_val |= 536870912

    return flags_val


_GTA_FLAG_BITS = [
    ("gta_flag_allow_full_rotation", 1),
    ("gta_flag_stream_low_priority", 2),
    ("gta_flag_disable_embedded_collisions", 4),
    ("gta_flag_lod_in_parent_map", 8),
    ("gta_flag_lod_adopt_me", 16),
    ("gta_flag_static_entity", 32),
    ("gta_flag_interior_lod", 64),
    ("gta_flag_lod_use_alt_fade", 32768),
    ("gta_flag_underwater", 65536),
    ("gta_flag_doesnt_touch_water", 131072),
    ("gta_flag_doesnt_spawn_peds", 262144),
    ("gta_flag_cast_static_shadows", 524288),
    ("gta_flag_cast_dynamic_shadows", 1048576),
    ("gta_flag_ignore_time_settings", 2097152),
    ("gta_flag_no_render_shadows", 4194304),
    ("gta_flag_only_render_shadows", 8388608),
    ("gta_flag_no_render_reflections", 16777216),
    ("gta_flag_only_render_reflections", 33554432),
    ("gta_flag_no_render_water_reflections", 67108864),
    ("gta_flag_only_render_water_reflections", 134217728),
    ("gta_flag_no_render_mirror_reflections", 268435456),
    ("gta_flag_only_render_mirror_reflections", 536870912),
]


def gta_get_flags_value(self):
    # Copy-friendly field derived from bools
    try:
        return int(gta_compute_flags(self, include_auto_full_rot=True))
    except Exception:
        return 0


def gta_set_flags_value(self, value):
    # Paste an integer to set all flag bools from bits.
    try:
        v = int(value)
    except Exception:
        return
    for attr, bit in _GTA_FLAG_BITS:
        if hasattr(self, attr):
            try:
                setattr(self, attr, bool(v & bit))
            except Exception:
                pass


# ==================================
# UI LIST / VIRTUAL YMAP LINKS
# ==================================
class GTA_YmapLinkItem(PropertyGroup):
    target: PointerProperty(
        name="Object",
        type=bpy.types.Object,
        description="Object (mesh / empty / armature) linked to this YMAP",
    )

    # True: manually added virtual link
    is_virtual: BoolProperty(
        name="Virtual link",
        default=True,
    )

    # Multi-select rows in the list
    selected: BoolProperty(
        name="Selected",
        default=False,
    )
    last_known_name: StringProperty(
        name="Last known name",
        default="",
        options={"HIDDEN"},
    )


def gta_unique_ymap_name(base, scene, exclude_ptr=None):
    """First free name among gta_ymaps.
    exclude_ptr: as_pointer() of the entry to skip (rename or newly added)."""
    existing = set()
    for item in getattr(scene, "gta_ymaps", []):
        if exclude_ptr is not None and item.as_pointer() == exclude_ptr:
            continue
        existing.add(item.name)
    if base not in existing:
        return base
    i = 1
    while True:
        cand = f"{base}.{i:03d}"
        if cand not in existing:
            return cand
        i += 1


def gta_ymap_name_taken_in_active(scene, wanted_name, exclude_ptr):
    """True if wanted_name is already used by another active YMAP."""
    for item in getattr(scene, "gta_ymaps", []):
        if exclude_ptr is not None and item.as_pointer() == exclude_ptr:
            continue
        if item.name == wanted_name:
            return True
    return False


def gta_has_forbidden_numeric_suffix(name):
    """Detect Blender auto suffixes like .001, .002, etc."""
    if "." not in name:
        return False
    base, suffix = name.rsplit(".", 1)
    return bool(base) and suffix.isdigit()


def gta_ymap_data_name_update(self, context):
    """Prevent two YMAPs in the active list from sharing the same name."""
    if not context:
        return
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    ptr = self.as_pointer()
    wanted = self.name
    unique = gta_unique_ymap_name(wanted, scene, exclude_ptr=ptr)
    if unique != wanted:
        self.name = unique
        try:
            if gta_ymap_name_taken_in_active(scene, wanted, ptr):
                reason = "another active YMAP already uses this name"
            else:
                reason = "another YMAP already uses this name"
            msg = (
                f"Warning: {reason}. "
                f"Blender auto-added suffix '{unique}' until you rename."
            )
            scene.gta_name_conflict_message = msg
        except Exception:
            pass
        return

    # Keep the message while the name still has an auto suffix (.001, .002, ...).
    if gta_has_forbidden_numeric_suffix(self.name):
        scene.gta_name_conflict_message = (
            f"Warning: '.{self.name.split('.')[-1]}' is a Blender auto suffix. "
            "This YMAP name collides with another. "
            "Rename to remove the suffix."
        )
    else:
        scene.gta_name_conflict_message = ""


class GTA_YmapDataItem(PropertyGroup):
    name: StringProperty(name="YMAP name", default="YMAP", update=gta_ymap_data_name_update)
    is_hidden: BoolProperty(name="Hidden", default=False)
    gta_ymap_links: CollectionProperty(type=GTA_YmapLinkItem)
    gta_ymap_links_index: IntProperty(default=0)
    gta_ymap_last_index: IntProperty(default=0, options={"HIDDEN"})
    trashed_at: StringProperty(
        name="Moved to trash",
        default="",
        options={"HIDDEN"},
    )


def gta_get_active_ymap(scene):
    ymap_name = getattr(scene, "gta_active_ymap", "NONE")
    if not ymap_name or ymap_name == "NONE":
        return None
    for ymap in getattr(scene, "gta_ymaps", []):
        if ymap.name == ymap_name:
            return ymap
    return None


def gta_copy_ymap_data(src, dst):
    """Copy name, visibility, and virtual links from one GTA_YmapDataItem to another."""
    dst.name = src.name
    dst.is_hidden = src.is_hidden
    links = dst.gta_ymap_links
    while len(links):
        links.remove(0)
    for link in src.gta_ymap_links:
        new_link = links.add()
        new_link.target = link.target
        new_link.is_virtual = link.is_virtual
        new_link.selected = False
        new_link.last_known_name = link.last_known_name
    n = len(links)
    if n:
        idx = min(max(getattr(src, "gta_ymap_links_index", 0), 0), n - 1)
        dst.gta_ymap_links_index = idx
    else:
        dst.gta_ymap_links_index = -1
    dst.gta_ymap_last_index = getattr(src, "gta_ymap_last_index", 0)


def gta_snapshot_ymap_item(src):
    """Snapshot dict of a YMAP (avoids RNA name clashes between trash and active list)."""
    return {
        "name": src.name,
        "is_hidden": src.is_hidden,
        "links": [
            {
                "target": l.target,
                "is_virtual": l.is_virtual,
                "last_known_name": l.last_known_name,
            }
            for l in src.gta_ymap_links
        ],
        "gta_ymap_links_index": getattr(src, "gta_ymap_links_index", 0),
        "gta_ymap_last_index": getattr(src, "gta_ymap_last_index", 0),
    }


def gta_apply_ymap_snapshot(dst, snap):
    """Apply a snapshot onto a GTA_YmapDataItem (links, name, etc.)."""
    dst.name = snap["name"]
    dst.is_hidden = snap["is_hidden"]
    links = dst.gta_ymap_links
    while len(links):
        links.remove(0)
    for ld in snap["links"]:
        nl = links.add()
        nl.target = ld["target"]
        nl.is_virtual = ld["is_virtual"]
        nl.selected = False
        nl.last_known_name = ld["last_known_name"]
    n = len(links)
    if n:
        idx = min(max(snap["gta_ymap_links_index"], 0), n - 1)
        dst.gta_ymap_links_index = idx
    else:
        dst.gta_ymap_links_index = -1
    dst.gta_ymap_last_index = snap["gta_ymap_last_index"]


def gta_sync_ymap_links(ymap_coll, force=False):
    """Clean and normalize the virtual link list for one YMAP."""
    if not hasattr(ymap_coll, "gta_ymap_links"):
        return

    links = ymap_coll.gta_ymap_links
    scene = getattr(bpy.context, "scene", None)
    seen_valid_objs = set()
    rows = []

    for link in links:
        obj = getattr(link, "target", None)
        selected = bool(getattr(link, "selected", False))
        last_name = getattr(link, "last_known_name", "") or ""

        is_obj_alive = False
        obj_type = None
        if obj is not None:
            try:
                obj_name = obj.name
                if scene is not None:
                    is_obj_alive = obj_name in scene.objects
                else:
                    is_obj_alive = obj_name in bpy.data.objects
                if is_obj_alive:
                    last_name = obj_name
                    obj_type = obj.type
            except Exception:
                is_obj_alive = False

        if is_obj_alive and obj_type in {"MESH", "EMPTY", "ARMATURE"}:
            if obj in seen_valid_objs:
                continue
            seen_valid_objs.add(obj)

        is_deleted = not (is_obj_alive and obj_type in {"MESH", "EMPTY", "ARMATURE"})
        sort_name = (last_name or "zzz").lower()
        rows.append({
            "target": obj,
            "selected": selected,
            "last_name": last_name,
            "is_deleted": is_deleted,
            "sort_name": sort_name,
        })

    rows.sort(key=lambda r: (0 if r["is_deleted"] else 1, r["sort_name"]))

    new_fp = tuple(
        (
            r["target"].as_pointer() if r["target"] is not None else 0,
            r["selected"],
            r["last_name"],
            r["is_deleted"],
        )
        for r in rows
    )
    key = ymap_coll.as_pointer()
    if not force and _gta_link_sync_fp.get(key) == new_fp:
        return
    _gta_link_sync_fp[key] = new_fp

    old_index = getattr(ymap_coll, "gta_ymap_links_index", 0)
    while len(links):
        links.remove(0)

    for r in rows:
        item = links.add()
        item.target = r["target"]
        item.is_virtual = True
        item.selected = r["selected"]
        item.last_known_name = r["last_name"]

    if links:
        ymap_coll.gta_ymap_links_index = min(max(old_index, 0), len(links) - 1)
    else:
        ymap_coll.gta_ymap_links_index = -1


def gta_iter_descendant_meshes(root):
    """Yield every MESH object under ``root`` (recursive children)."""
    if root is None:
        return
    stack = list(root.children)
    while stack:
        child = stack.pop()
        stack.extend(child.children)
        if getattr(child, "type", None) == "MESH":
            yield child


def gta_ymap_link_row_matches_3d_selection(link_target, selected_set) -> bool:
    """True if this YMAP list row should appear selected for the current 3D selection."""
    if link_target is None:
        return False
    if link_target in selected_set:
        return True
    if getattr(link_target, "type", None) in {"EMPTY", "ARMATURE"}:
        for mesh in gta_iter_descendant_meshes(link_target):
            if mesh in selected_set:
                return True
    return False


def gta_expand_prop_root_selection_for_3d(objs):
    """For EMPTY/ARMATURE link targets, include all descendant meshes in 3D selection."""
    seen = set()
    out = []
    for obj in objs:
        if obj is None or obj in seen:
            continue
        seen.add(obj)
        out.append(obj)
        if getattr(obj, "type", None) in {"EMPTY", "ARMATURE"}:
            for mesh in gta_iter_descendant_meshes(obj):
                if mesh not in seen:
                    seen.add(mesh)
                    out.append(mesh)
    return out


def gta_on_ymap_link_index_update(self, context):
    """When the UI list selection changes, select the linked object in the 3D View.
    Handles multi-select (Shift/Ctrl) via gta_ymap_last_index.
    """
    try:
        scene = context.scene if context is not None else bpy.context.scene
    except Exception:
        scene = None

    if scene is None:
        return

    if not hasattr(self, "gta_ymap_links"):
        return

    links = self.gta_ymap_links
    index = getattr(self, "gta_ymap_links_index", -1)

    if not links or index < 0 or index >= len(links):
        return

    # Modifiers stored by the list-click operator
    shift = getattr(scene, "gta_multisel_shift", False)
    ctrl  = getattr(scene, "gta_multisel_ctrl",  False)
    from_ui = getattr(scene, "gta_ymap_index_from_ui", False)
    last  = getattr(self,  "gta_ymap_last_index", index)

    # Only change multi-select checkboxes on a real UI click.
    # Internal index changes (auto sync) must not overwrite selection.
    if from_ui:
        if shift and last >= 0:
            # Range select: check every row between last and index
            lo, hi = sorted((last, index))
            for i, lnk in enumerate(links):
                if lo <= i <= hi:
                    lnk.selected = True
        elif ctrl:
            # Toggle only the clicked row
            links[index].selected = not links[index].selected
        else:
            # Simple click: single selection
            for lnk in links:
                lnk.selected = False
            links[index].selected = True

        # Remember index for next Shift+click
        self.gta_ymap_last_index = index

    # Sync 3D selection when enabled
    scene_flag = getattr(scene, "gta_sync_ymap_selection", True)
    ctx_flag   = getattr(bpy.context.scene, "gta_sync_ymap_selection", scene_flag)
    skip_view_sync_once = getattr(scene, "gta_skip_view_sync_once", False)
    if skip_view_sync_once:
        scene.gta_skip_view_sync_once = False
    elif scene_flag and ctx_flag:
        view_layer = bpy.context.view_layer

        # In sync mode, align 3D selection to ALL checked rows.
        # EMPTY/ARMATURE rows also select every descendant MESH (prop hierarchy).
        roots = [
            getattr(lnk, "target", None)
            for lnk in links
            if getattr(lnk, "selected", False) and getattr(lnk, "target", None) is not None
        ]
        selected_objs = gta_expand_prop_root_selection_for_3d(roots)

        if selected_objs:
            for o in view_layer.objects:
                o.select_set(False)
            for obj in selected_objs:
                try:
                    obj.select_set(True)
                except Exception:
                    pass
            # Active list row becomes Blender active object
            active_obj = getattr(links[index], "target", None)
            if active_obj is not None:
                try:
                    view_layer.objects.active = active_obj
                except Exception:
                    pass

    # Reset keyboard modifier flags
    scene.gta_multisel_shift = False
    scene.gta_multisel_ctrl  = False
    scene.gta_ymap_index_from_ui = False



# ==================================
# MULTI-SELECTION PROPAGATION
# ==================================
_GTA_PROP_ATTRS = [
    "gta_lod_dist",
    "gta_lod_level",
    "gta_priority_level",
    "gta_flag_allow_full_rotation",
    "gta_flag_stream_low_priority",
    "gta_flag_disable_embedded_collisions",
    "gta_flag_lod_in_parent_map",
    "gta_flag_lod_adopt_me",
    "gta_flag_static_entity",
    "gta_flag_interior_lod",
    "gta_flag_lod_use_alt_fade",
    "gta_flag_underwater",
    "gta_flag_doesnt_touch_water",
    "gta_flag_doesnt_spawn_peds",
    "gta_flag_cast_static_shadows",
    "gta_flag_cast_dynamic_shadows",
    "gta_flag_ignore_time_settings",
    "gta_flag_no_render_shadows",
    "gta_flag_only_render_shadows",
    "gta_flag_no_render_reflections",
    "gta_flag_only_render_reflections",
    "gta_flag_no_render_water_reflections",
    "gta_flag_only_render_water_reflections",
    "gta_flag_no_render_mirror_reflections",
    "gta_flag_only_render_mirror_reflections",
]

# Guard against infinite recursion in RNA update callbacks
_gta_propagating = False

def gta_propagate_to_selected(src_obj, attr):
    """Copy src_obj.attr to every other checked row's object in any YMAP."""
    global _gta_propagating
    if _gta_propagating:
        return
    _gta_propagating = True
    try:
        val = getattr(src_obj, attr)
        scene = bpy.context.scene
        for ymap_data in scene.gta_ymaps:
            for lnk in ymap_data.gta_ymap_links:
                if not getattr(lnk, "selected", False):
                    continue
                dst = getattr(lnk, "target", None)
                if dst is None or dst is src_obj:
                    continue
                if hasattr(dst, attr):
                    setattr(dst, attr, val)
    finally:
        _gta_propagating = False


def _make_gta_update(attr):
    """Build an RNA update callback for a given property name."""
    def _update(self, context):
        gta_propagate_to_selected(self, attr)
    return _update


def gta_on_sync_selection_toggle(self, context):
    """When sync is enabled, realign the list with the current 3D selection."""
    if context is None:
        return
    from . import handlers
    if not getattr(self, "gta_sync_ymap_selection", False):
        handlers.invalidate_selection_sync_cache()
        return


    # Clear stale checkboxes so the UI does not look half-selected.
    for ymap_data in getattr(self, "gta_ymaps", []):
        for lnk in ymap_data.gta_ymap_links:
            lnk.selected = False
        ymap_data.gta_ymap_links_index = -1

    active_obj = getattr(context.view_layer.objects, "active", None)
    if active_obj is None:
        handlers.set_selection_sync_cache(handlers.compute_selection_key_from_context(context))
        return

    try:
        selected_objs = [
            o for o in context.view_layer.objects if o.select_get()
        ]
    except Exception:
        selected_objs = []
    selected_set = frozenset(selected_objs)

    lineage = []
    cur = active_obj
    while cur is not None:
        lineage.append(cur)
        cur = getattr(cur, "parent", None)

    for ymap_data in getattr(self, "gta_ymaps", []):
        links = ymap_data.gta_ymap_links
        for i, link in enumerate(links):
            target = getattr(link, "target", None)
            if target in lineage:
                ymap_data.gta_ymap_links_index = i
                handlers.apply_ymap_list_selection_from_3d(links, selected_set)
                handlers.set_selection_sync_cache(handlers.compute_selection_key_from_context(context))
                return

    handlers.set_selection_sync_cache(handlers.compute_selection_key_from_context(context))


def gta_object_in_other_ymap_lists(scene, obj, skip_ymap_data):
    """True if obj is linked from any other active YMAP than skip_ymap_data."""
    if obj is None or skip_ymap_data is None:
        return False
    skip_ptr = skip_ymap_data.as_pointer()
    for y in getattr(scene, "gta_ymaps", []):
        if y.as_pointer() == skip_ptr:
            continue
        for lnk in y.gta_ymap_links:
            if getattr(lnk, "target", None) is obj:
                return True
    return False


def gta_reset_object_gta_props_to_defaults(obj):
    """Reset GTA / YMAP-related Object RNA props to register defaults (no multi-select propagation)."""
    global _gta_propagating
    if obj is None or getattr(obj, "type", None) not in {"MESH", "EMPTY", "ARMATURE"}:
        return
    if not hasattr(obj, "gta_lod_dist"):
        return
    _gta_propagating = True
    try:
        obj.gta_lod_dist = 200
        obj.gta_lod_level = "LODTYPES_DEPTH_ORPHANHD"
        obj.gta_priority_level = "PRI_REQUIRED"
        obj.gta_flag_allow_full_rotation = False
        obj.gta_flag_stream_low_priority = False
        obj.gta_flag_disable_embedded_collisions = False
        obj.gta_flag_lod_in_parent_map = False
        obj.gta_flag_lod_adopt_me = False
        obj.gta_flag_static_entity = True
        obj.gta_flag_interior_lod = False
        obj.gta_flag_lod_use_alt_fade = False
        obj.gta_flag_underwater = False
        obj.gta_flag_doesnt_touch_water = False
        obj.gta_flag_doesnt_spawn_peds = False
        obj.gta_flag_cast_static_shadows = False
        obj.gta_flag_cast_dynamic_shadows = False
        obj.gta_flag_ignore_time_settings = False
        obj.gta_flag_no_render_shadows = False
        obj.gta_flag_only_render_shadows = False
        obj.gta_flag_no_render_reflections = False
        obj.gta_flag_only_render_reflections = False
        obj.gta_flag_no_render_water_reflections = False
        obj.gta_flag_only_render_water_reflections = False
        obj.gta_flag_no_render_mirror_reflections = False
        obj.gta_flag_only_render_mirror_reflections = False
        obj.gta_auto_full_rot = True
    finally:
        _gta_propagating = False
