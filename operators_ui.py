"""Blender operators and UI panel."""
import xml.etree.ElementTree as ET
from xml.dom import minidom

import bpy
import mathutils
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, IntProperty, EnumProperty
from bpy.types import Operator, Panel, UIList

from . import constants
from . import perf
from . import ymap_core as yc

# Readable aliases (logic migrated from legacy __init__.py)
gta_get_active_ymap = yc.gta_get_active_ymap
gta_sync_ymap_links = yc.gta_sync_ymap_links
gta_on_ymap_link_index_update = yc.gta_on_ymap_link_index_update
gta_unique_ymap_name = yc.gta_unique_ymap_name
gta_has_forbidden_numeric_suffix = yc.gta_has_forbidden_numeric_suffix
gta_export_ymap_name = yc.gta_export_ymap_name
gta_compute_flags = yc.gta_compute_flags

# Float noise when a value is meant to be exactly 1 or 0 (any source).
_YMAP_SCALE_UNIT_EPS = 1e-5


def _ymap_sanitize_scale_component(v):
    """Export only: snap |v| very close to 1 or 0; leave real scales (e.g. 3.26) unchanged."""
    a = abs(float(v))
    if abs(a - 1.0) < _YMAP_SCALE_UNIT_EPS:
        return 1.0
    if a < _YMAP_SCALE_UNIT_EPS:
        return 0.0
    return a


def _ymap_rotation_for_file(world_quat):
    """CEntityDef.rotation in YMAP is stored inverted vs world orientation in CodeWalker
    (see CodeWalker YmapEntityDef: Invert on load / Invert on save for non-MLO entities).
    Export the inverse of Blender world rotation so CodeWalker / in-game match the viewport."""
    q = world_quat.copy()
    if q.magnitude < 1e-10:
        return mathutils.Quaternion((1.0, 0.0, 0.0, 0.0))
    q.normalize()
    return q.inverted()


class GTA_OT_ymap_list_click(Operator):
    """Handle list clicks for Shift/Ctrl multi-select."""
    bl_idname  = "gta.ymap_list_click"
    bl_label   = "YMAP list click"
    bl_options = set()

    index: bpy.props.IntProperty()

    def invoke(self, context, event):
        scene = context.scene
        # Store modifiers before changing the active index
        scene.gta_multisel_shift = event.shift
        scene.gta_multisel_ctrl  = event.ctrl
        scene.gta_ymap_index_from_ui = True

        ymap_data = gta_get_active_ymap(scene)
        if ymap_data is not None:
            ymap_data.gta_ymap_links_index = self.index
            gta_on_ymap_link_index_update(ymap_data, context)
        return {"FINISHED"}


class GTA_OT_ymap_focus_object(Operator):
    """Select the object and run View Selected (numpad .)."""
    bl_idname = "gta.ymap_focus_object"
    bl_label  = "Focus object"
    bl_options = set()

    index: bpy.props.IntProperty()

    def execute(self, context):
        scene = context.scene
        ymap_data = gta_get_active_ymap(scene)
        if ymap_data is None:
            return {"CANCELLED"}

        links = ymap_data.gta_ymap_links
        if not links or self.index < 0 or self.index >= len(links):
            return {"CANCELLED"}

        obj = getattr(links[self.index], "target", None)
        if obj is None:
            return {"CANCELLED"}

        # Select the target object.
        # For EMPTY/ARMATURE, include descendants for View Selected bounds.
        view_layer = context.view_layer
        for o in view_layer.objects:
            o.select_set(False)

        to_select = {obj}
        if obj.type in {"EMPTY", "ARMATURE"}:
            stack = list(obj.children)
            while stack:
                child = stack.pop()
                if child in to_select:
                    continue
                to_select.add(child)
                stack.extend(child.children)

        for sel_obj in to_select:
            try:
                sel_obj.select_set(True)
            except Exception:
                pass
        view_layer.objects.active = obj

        # View Selected in every 3D View
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    for region in area.regions:
                        if region.type == "WINDOW":
                            with context.temp_override(window=window, area=area, region=region):
                                bpy.ops.view3d.view_selected()
                            break

        return {"FINISHED"}


class GTA_UL_ymap_links(UIList):
    """Objects linked to the active YMAP (virtual list)."""

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        obj = item.target

        # Only the linked object itself (not its hierarchy).
        obj_deleted = True
        if obj is not None:
            try:
                # Not in scene = treat as deleted in the list.
                obj_deleted = obj.name not in context.scene.objects
            except Exception:
                obj_deleted = True

        if obj_deleted:
            # Deleted object: red row
            row = layout.row(align=True)
            row.alert = True
            ghost_name = getattr(item, "last_known_name", "") or "Deleted object"
            op = row.operator(
                "gta.ymap_list_click",
                text=f"DELETED: {ghost_name}",
                icon="ERROR",
                emboss=False,
            )
            op.index = index
        else:
            row = layout.row(align=True)

            # Object type icon
            if obj.type == "MESH":
                icon_id = "MESH_CUBE"
            elif obj.type == "ARMATURE":
                icon_id = "ARMATURE_DATA"
            else:
                icon_id = "EMPTY_AXIS"

            # Game name only (strip Blender .001, .002, etc.)
            clean_name = obj.name
            if "." in obj.name:
                base, suffix = obj.name.rsplit(".", 1)
                if suffix.isdigit():
                    clean_name = base

            name_row = row.row(align=True)
            is_selected = getattr(item, "selected", False)
            selected_count = sum(
                1 for lnk in getattr(data, "gta_ymap_links", [])
                if getattr(lnk, "selected", False)
            )
            op = name_row.operator(
                "gta.ymap_list_click",
                text=clean_name,
                icon=icon_id,
                # Avoid double-highlight on single click; show state when multi-selected.
                emboss=(selected_count > 1 and is_selected),
            )
            op.index = index

            # Zoom: select and View Selected
            op_focus = row.operator(
                "gta.ymap_focus_object",
                text="",
                icon="VIEWZOOM",
                emboss=False,
            )
            op_focus.index = index


class GTA_OT_ymap_link_add(Operator):
    bl_idname = "gta.ymap_link_add"
    bl_label = "Add link"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        ymap_data = gta_get_active_ymap(scene)
        if ymap_data is None:
            self.report({"ERROR"}, "Select a valid YMAP from the list")
            return {"CANCELLED"}

        links = ymap_data.gta_ymap_links

        # Objects already in the list (no duplicates)
        existing_targets = {
            link.target for link in links if link.target is not None
        }

        # Valid selected objects (MESH, EMPTY, ARMATURE)
        valid_objs = [
            obj for obj in context.selected_objects
            if obj.type in {"MESH", "EMPTY", "ARMATURE"}
            and obj not in existing_targets
        ]

        if not valid_objs:
            self.report({"WARNING"}, "No valid objects selected (or already in the list)")
            return {"CANCELLED"}

        for obj in valid_objs:
            item = links.add()
            item.target = obj
            item.is_virtual = True
            item.last_known_name = obj.name

        # Active row becomes the last added
        ymap_data.gta_ymap_links_index = len(links) - 1

        self.report({"INFO"}, f"{len(valid_objs)} object(s) added to YMAP")
        return {"FINISHED"}


class GTA_OT_ymap_link_remove(Operator):
    bl_idname = "gta.ymap_link_remove"
    bl_label = "Remove link"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        ymap_data = gta_get_active_ymap(scene)
        if ymap_data is None:
            self.report({"ERROR"}, "Select a valid YMAP from the list")
            return {"CANCELLED"}

        links = ymap_data.gta_ymap_links
        index = ymap_data.gta_ymap_links_index

        if not links:
            return {"CANCELLED"}

        # Remove all selected rows (virtual links)
        selected_virtual_indices = [
            i for i, lnk in enumerate(links)
            if getattr(lnk, "selected", False)
        ]

        if selected_virtual_indices:
            # Remove checked rows from the end
            for i in reversed(selected_virtual_indices):
                links.remove(i)
            removed = len(selected_virtual_indices)
            self.report({"INFO"}, f"{removed} virtual link(s) removed")
        else:
            # Nothing checked: remove active row
            if index < 0 or index >= len(links):
                return {"CANCELLED"}
            links.remove(index)

        if links:
            ymap_data.gta_ymap_links_index = min(index, len(links) - 1)
        else:
            ymap_data.gta_ymap_links_index = -1

        return {"FINISHED"}


class GTA_OT_ymap_links_sync(Operator):
    bl_idname = "gta.ymap_links_sync"
    bl_label = "Refresh list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        ymap_data = gta_get_active_ymap(scene)
        if ymap_data is None:
            self.report({"ERROR"}, "Select a valid YMAP from the list")
            return {"CANCELLED"}

        gta_sync_ymap_links(ymap_data, force=True)
        return {"FINISHED"}


class GTA_OT_ymap_select_all(Operator):
    """Select or deselect all rows in the list."""
    bl_idname = "gta.ymap_select_all"
    bl_label = "Select all / deselect all"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        ymap_data = gta_get_active_ymap(scene)
        if ymap_data is None:
            return {"CANCELLED"}

        links = ymap_data.gta_ymap_links
        # If all checked, clear; else check all
        all_selected = all(getattr(lnk, "selected", False) for lnk in links)
        for lnk in links:
            lnk.selected = not all_selected
        return {"FINISHED"}


class GTA_OT_ymap_bulk_apply(Operator):
    """Copy flags and LOD from the active row to every checked row."""
    bl_idname = "gta.ymap_bulk_apply"
    bl_label = "Apply to selected"
    bl_options = {"REGISTER", "UNDO"}

    # Which properties to copy
    apply_lod_dist: BoolProperty(name="LOD Dist", default=True)
    apply_lod_level: BoolProperty(name="LOD Level", default=True)
    apply_priority: BoolProperty(name="Priority", default=True)
    apply_flags: BoolProperty(name="Flags", default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=280)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Apply to all checked rows:")
        col = layout.column(align=True)
        col.prop(self, "apply_lod_dist")
        col.prop(self, "apply_lod_level")
        col.prop(self, "apply_priority")
        col.prop(self, "apply_flags")

    def execute(self, context):
        scene = context.scene
        ymap_data = gta_get_active_ymap(scene)
        if ymap_data is None:
            self.report({"ERROR"}, "Select a valid YMAP")
            return {"CANCELLED"}

        links = ymap_data.gta_ymap_links
        index = getattr(ymap_data, "gta_ymap_links_index", -1)

        if not links or index < 0 or index >= len(links):
            self.report({"ERROR"}, "No active row in the list")
            return {"CANCELLED"}

        src = getattr(links[index], "target", None)
        if src is None:
            self.report({"ERROR"}, "Active row has no target object")
            return {"CANCELLED"}

        _flag_attrs = [
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

        count = 0
        for lnk in links:
            if not getattr(lnk, "selected", False):
                continue
            dst = getattr(lnk, "target", None)
            if dst is None or dst is src:
                continue
            if self.apply_lod_dist:
                dst.gta_lod_dist = src.gta_lod_dist
            if self.apply_lod_level:
                dst.gta_lod_level = src.gta_lod_level
            if self.apply_priority:
                dst.gta_priority_level = src.gta_priority_level
            if self.apply_flags:
                for attr in _flag_attrs:
                    if hasattr(src, attr):
                        setattr(dst, attr, getattr(src, attr))
            count += 1

        self.report({"INFO"}, f"Properties applied to {count} object(s)")
        return {"FINISHED"}


class GTA_OT_ymap_toggle_visibility(Operator):
    """Hide or show all objects linked to the active YMAP."""
    bl_idname  = "gta.ymap_toggle_visibility"
    bl_label   = "Hide / Show YMAP"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        ymap_data = gta_get_active_ymap(scene)
        if ymap_data is None:
            self.report({"ERROR"}, "Select a valid YMAP")
            return {"CANCELLED"}

        new_state = not bool(getattr(ymap_data, "is_hidden", False))
        ymap_data.is_hidden = new_state

        to_toggle = set()
        for lnk in ymap_data.gta_ymap_links:
            root = getattr(lnk, "target", None)
            if root is None:
                continue
            try:
                to_toggle.add(root)
                # Include full hierarchy (children, etc.)
                stack = list(root.children)
                while stack:
                    child = stack.pop()
                    if child in to_toggle:
                        continue
                    to_toggle.add(child)
                    stack.extend(child.children)
            except Exception:
                pass

        for obj in to_toggle:
            try:
                obj.hide_viewport = new_state
                obj.hide_set(new_state)
            except Exception:
                pass

        action = "hidden" if new_state else "shown"
        self.report({"INFO"}, f"YMAP '{ymap_data.name}' {action}")
        return {"FINISHED"}


# ==================================
# OPERATOR : EXPORT YMAP.XML
# ==================================
class GTA_OT_export_ymap_xml(Operator, ExportHelper):
    bl_idname = "gta.export_ymap_xml"
    bl_label = "Export YMAP"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Blender only tracks ".xml"; we append ".ymap" ourselves so
    # the filename does not duplicate when changing folders.
    filename_ext = ".xml"
    filter_glob: StringProperty(
        default="*.ymap.xml",
        options={'HIDDEN'}
    )
    
    def invoke(self, context, event):
        scene = context.scene

        ymap_data = gta_get_active_ymap(scene)

        base_name = gta_export_ymap_name(ymap_data.name) if ymap_data is not None else "YMAP"

        # Force a single ".ymap.xml" extension
        if not base_name.lower().endswith(".ymap"):
            base_name += ".ymap"
        self.filepath = base_name + ".xml"

        return super().invoke(context, event)
    
    def execute(self, context):
        scene = context.scene

        ymap_data = gta_get_active_ymap(scene)
        if ymap_data is None:
            self.report({'ERROR'}, "Select a valid YMAP from the list")
            return {'CANCELLED'}

        export_name = gta_export_ymap_name(ymap_data.name)

        # Entities: virtual links from the YMAP list only
        entities = []
        for link in ymap_data.gta_ymap_links:
            obj = getattr(link, "target", None)
            if obj is None:
                continue
            if obj.type not in {'MESH', 'EMPTY', 'ARMATURE'}:
                continue
            if obj not in entities:
                entities.append(obj)

        if not entities:
            self.report({'ERROR'}, "No linked objects to export in this YMAP")
            return {'CANCELLED'}

        # Extents from entity world positions
        xs = []
        ys = []
        zs = []
        for ent in entities:
            loc = ent.matrix_world.translation
            xs.append(loc.x)
            ys.append(loc.y)
            zs.append(loc.z)

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        min_z, max_z = min(zs), max(zs)

        root = ET.Element("CMapData")

        # Name (export sanitization)
        name_elem = ET.SubElement(root, "name")
        name_elem.text = export_name

        # Generic header fields (CodeWalker-style defaults)
        ET.SubElement(root, "parent")
        ET.SubElement(root, "flags", {"value": "0"})
        ET.SubElement(root, "contentFlags", {"value": "1"})

        # Simple AABB from entities
        ET.SubElement(
            root,
            "streamingExtentsMin",
            {"x": str(min_x), "y": str(min_y), "z": str(min_z)},
        )
        ET.SubElement(
            root,
            "streamingExtentsMax",
            {"x": str(max_x), "y": str(max_y), "z": str(max_z)},
        )
        ET.SubElement(
            root,
            "entitiesExtentsMin",
            {"x": str(min_x), "y": str(min_y), "z": str(min_z)},
        )
        ET.SubElement(
            root,
            "entitiesExtentsMax",
            {"x": str(max_x), "y": str(max_y), "z": str(max_z)},
        )

        # Entities
        entities_elem = ET.SubElement(root, "entities")

        for entity in entities:
            # World position & rotation; scale from object.scale (Transform panel sliders).
            # matrix_world.to_scale() can disagree with the sidebar (e.g. shows ~1 while Scale is 3.26).
            loc = entity.matrix_world.translation
            quat_world = entity.matrix_world.to_quaternion()
            quat = _ymap_rotation_for_file(quat_world)
            scale = entity.scale

            # Per-object custom props
            lod_dist_val = int(getattr(entity, "gta_lod_dist", 200))

            # Flags from checkboxes + Auto full rotation
            flags_val = gta_compute_flags(entity, include_auto_full_rot=True)

            item_elem = ET.SubElement(entities_elem, "Item", {"type": "CEntityDef"})

            archetype_elem = ET.SubElement(item_elem, "archetypeName")
            # Strip Blender numeric suffixes, e.g. "tree.001" -> "tree"
            clean_name = entity.name
            if "." in entity.name:
                base, suffix = entity.name.rsplit(".", 1)
                if suffix.isdigit():
                    clean_name = base
            archetype_elem.text = clean_name

            ET.SubElement(item_elem, "flags", {"value": str(int(flags_val))})
            ET.SubElement(item_elem, "guid", {"value": "0"})

            pos_elem = ET.SubElement(
                item_elem,
                "position",
                {
                    "x": str(loc.x),
                    "y": str(loc.y),
                    "z": str(loc.z),
                },
            )

            rot_elem = ET.SubElement(
                item_elem,
                "rotation",
                {
                    "x": str(quat.x),
                    "y": str(quat.y),
                    "z": str(quat.z),
                    "w": str(quat.w),
                },
            )

            # YMAP scaleXY / scaleZ from local Scale (matches Sidebar); sanitize float noise only
            sx = _ymap_sanitize_scale_component(scale.x)
            sy = _ymap_sanitize_scale_component(scale.y)
            sz = _ymap_sanitize_scale_component(scale.z)
            scale_xy = (sx + sy) / 2.0
            scale_z = sz
            if abs(scale_xy - 1.0) < _YMAP_SCALE_UNIT_EPS:
                scale_xy = 1.0
            if abs(scale_z - 1.0) < _YMAP_SCALE_UNIT_EPS:
                scale_z = 1.0
            ET.SubElement(item_elem, "scaleXY", {"value": str(scale_xy)})
            ET.SubElement(item_elem, "scaleZ", {"value": str(scale_z)})
            ET.SubElement(item_elem, "parentIndex", {"value": "-1"})
            ET.SubElement(item_elem, "lodDist", {"value": str(lod_dist_val)})
            ET.SubElement(item_elem, "childLodDist", {"value": "0"})

            # LOD level (per object, default ORPHANHD)
            lod_level = ET.SubElement(item_elem, "lodLevel")
            lod_level_val = getattr(
                entity,
                "gta_lod_level",
                "LODTYPES_DEPTH_ORPHANHD",
            )
            lod_level.text = lod_level_val

            num_children = ET.SubElement(item_elem, "numChildren", {"value": "0"})

            # Priority (per object, default REQUIRED)
            priority = ET.SubElement(item_elem, "priorityLevel")
            priority_val = getattr(
                entity,
                "gta_priority_level",
                "PRI_REQUIRED",
            )
            priority.text = priority_val

            ET.SubElement(item_elem, "extensions")
            ET.SubElement(item_elem, "ambientOcclusionMultiplier", {"value": "255"})
            ET.SubElement(item_elem, "artificialAmbientOcclusion", {"value": "255"})
            ET.SubElement(item_elem, "tintValue", {"value": "0"})

        # Empty sections / base structure (CodeWalker-like)
        ET.SubElement(root, "containerLods", {"itemType": "rage__fwContainerLodDef"})
        ET.SubElement(root, "boxOccluders", {"itemType": "BoxOccluder"})
        ET.SubElement(root, "occludeModels", {"itemType": "OccludeModel"})
        ET.SubElement(root, "physicsDictionaries")

        instanced = ET.SubElement(root, "instancedData")
        ET.SubElement(instanced, "ImapLink")
        ET.SubElement(instanced, "PropInstanceList", {"itemType": "rage__fwPropInstanceListDef"})
        ET.SubElement(instanced, "GrassInstanceList", {"itemType": "rage__fwGrassInstanceListDef"})

        ET.SubElement(root, "timeCycleModifiers", {"itemType": "CTimeCycleModifier"})
        ET.SubElement(root, "carGenerators", {"itemType": "CCarGen"})

        lod_lights = ET.SubElement(root, "LODLightsSOA")
        ET.SubElement(lod_lights, "direction", {"itemType": "FloatXYZ"})
        ET.SubElement(lod_lights, "falloff")
        ET.SubElement(lod_lights, "falloffExponent")
        ET.SubElement(lod_lights, "timeAndStateFlags")
        ET.SubElement(lod_lights, "hash")
        ET.SubElement(lod_lights, "coneInnerAngle")
        ET.SubElement(lod_lights, "coneOuterAngleOrCapExt")
        ET.SubElement(lod_lights, "coronaIntensity")

        distant_lod = ET.SubElement(root, "DistantLODLightsSOA")
        ET.SubElement(distant_lod, "position", {"itemType": "FloatXYZ"})
        ET.SubElement(distant_lod, "RGBI")
        ET.SubElement(distant_lod, "numStreetLights", {"value": "0"})
        ET.SubElement(distant_lod, "category", {"value": "0"})

        block = ET.SubElement(root, "block")
        ET.SubElement(block, "version", {"value": "0"})
        ET.SubElement(block, "flags", {"value": "0"})
        block_name = ET.SubElement(block, "name")
        block_name.text = export_name
        exported_by = ET.SubElement(block, "exportedBy")
        exported_by.text = "BlenderYMAP"
        ET.SubElement(block, "owner")

        # Ensure output ends with ".ymap.xml"
        final_path = self.filepath
        if not final_path.lower().endswith(".ymap.xml"):
            if final_path.lower().endswith(".xml"):
                final_path = final_path[:-4] + ".ymap.xml"
            else:
                final_path = final_path + ".ymap.xml"

        xml_str = ET.tostring(root, encoding='unicode')
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ")
        
        with open(final_path, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)
        
        self.report({'INFO'}, f"Exported as '{export_name}'")
        return {'FINISHED'}

# ==================================
# OPERATOR : CREATE YMAP STRUCTURE
# ==================================
class GTA_OT_create_ymap_structure(Operator):
    bl_idname = "gta.create_ymap_structure"
    bl_label = "Create YMAP"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        ymap_data = scene.gta_ymaps.add()
        ymap_data.name = gta_unique_ymap_name(
            "YMAP",
            scene,
            exclude_ptr=ymap_data.as_pointer(),
        )
        ymap_data.is_hidden = False
        scene.gta_active_ymap = ymap_data.name

        self.report({'INFO'}, "YMAP created (virtual links only)")
        return {'FINISHED'}


# ==================================
# DELETE YMAP (double confirmation)
# ==================================
class GTA_OT_ymap_delete(Operator):
    """First confirmation before deleting the active YMAP."""
    bl_idname = "gta.ymap_delete"
    bl_label = "Delete this YMAP?"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        return bpy.ops.gta.ymap_delete_final("INVOKE_DEFAULT")


class GTA_OT_ymap_delete_final(Operator):
    """Second confirmation, then remove the active YMAP from the scene data."""
    bl_idname = "gta.ymap_delete_final"
    bl_label = "Delete permanently (cannot undo outside Blender)?"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        scene = context.scene
        ymap_data = gta_get_active_ymap(scene)
        if ymap_data is None:
            self.report({"ERROR"}, "No YMAP to delete")
            return {"CANCELLED"}

        idx_remove = None
        for i, y in enumerate(scene.gta_ymaps):
            if y == ymap_data:
                idx_remove = i
                break
        if idx_remove is None:
            self.report({"ERROR"}, "YMAP not found")
            return {"CANCELLED"}

        doomed = ymap_data
        removed_name = doomed.name

        seen = set()
        reset_count = 0
        for lnk in doomed.gta_ymap_links:
            target = getattr(lnk, "target", None)
            if target is None:
                continue
            try:
                if target.name not in bpy.data.objects:
                    continue
            except ReferenceError:
                continue
            if target in seen:
                continue
            seen.add(target)
            if yc.gta_object_in_other_ymap_lists(scene, target, doomed):
                continue
            yc.gta_reset_object_gta_props_to_defaults(target)
            reset_count += 1

        scene.gta_ymaps.remove(idx_remove)

        names = [y.name for y in scene.gta_ymaps]
        if names:
            scene.gta_active_ymap = names[0]
        else:
            scene.gta_active_ymap = "NONE"

        msg = f"YMAP '{removed_name}' deleted"
        if reset_count:
            msg += f" ({reset_count} object(s) GTA props reset to defaults)"
        self.report({"INFO"}, msg)
        return {"FINISHED"}


# ==================================
# PANEL : SIDEBAR
# ==================================
class GTA_PT_ymap_panel(Panel):
    bl_label = "YMAP Tools By Npo"
    bl_idname = "GTA_PT_ymap_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Npo YMAP Tools"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # ----------------------------------
        # Export (top)
        # ----------------------------------
        layout.operator("gta.export_ymap_xml", text="Export YMAP", icon="EXPORT")

        layout.separator()

        ymap_data = gta_get_active_ymap(scene)
        ymap_name = getattr(scene, "gta_active_ymap", "NONE")

        # 1) Name (current YMAP title) first
        if ymap_data is not None:
            layout.prop(ymap_data, "name", text="Rename YMAP")

        # 2) Fixed text label (not the active YMAP name) + enum with text="" so only the menu shows the selection
        row_sel = layout.row(align=True)
        row_sel.label(text="Select another YMAP")
        sub_enum = row_sel.row(align=True)
        if ymap_name != "NONE":
            sub_enum.alert = gta_has_forbidden_numeric_suffix(ymap_name)
        sub_enum.prop(scene, "gta_active_ymap", text="")
        sub_enum.alert = False
        row_sel.operator("gta.create_ymap_structure", text="", icon="ADD")
        row_del = row_sel.row(align=True)
        row_del.enabled = ymap_data is not None
        row_del.operator("gta.ymap_delete", text="", icon="TRASH")
        if ymap_data is not None:
            hide_icon = "HIDE_ON" if ymap_data.is_hidden else "HIDE_OFF"
            row_sel.operator("gta.ymap_toggle_visibility", text="", icon=hide_icon)

        if ymap_data is not None:
            name_warn = ""
            if gta_has_forbidden_numeric_suffix(ymap_data.name):
                name_warn = (
                    "Warning: another YMAP already uses this base name. "
                    "The auto suffix (.001/.002/...) stays until you rename."
                )
            if name_warn:
                warn_row = layout.row()
                warn_row.alert = True
                warn_row.label(text=name_warn, icon="ERROR")

        # ----------------------------------
        # Virtual links for this YMAP
        # ----------------------------------
        if ymap_data is not None:
            box_links = layout.box()
            box_links.label(text="Props in this YMAP")
            row_links = box_links.row()
            row_links.template_list(
                "GTA_UL_ymap_links",
                "",
                ymap_data,
                "gta_ymap_links",
                ymap_data,
                "gta_ymap_links_index",
                rows=5,
            )
            col_links = row_links.column(align=True)
            col_links.operator("gta.ymap_link_add", icon="ADD", text="")
            col_links.operator("gta.ymap_link_remove", icon="REMOVE", text="")
            col_links.operator("gta.ymap_links_sync", icon="FILE_REFRESH", text="")
            col_links.prop(scene, "gta_sync_ymap_selection", text="", icon="UV_SYNC_SELECT")

        layout.separator()

        # ----------------------------------
        # Selected link properties
        # ----------------------------------
        if ymap_data is not None:
            links = ymap_data.gta_ymap_links
            index = getattr(ymap_data, "gta_ymap_links_index", -1)

            if links and 0 <= index < len(links):
                link = links[index]
                obj = getattr(link, "target", None)

                # Props for mesh, empty, or armature targets
                if obj is not None:
                    box = layout.box()
                    nb_sel = sum(1 for lnk in links if getattr(lnk, "selected", False))
                    if nb_sel > 1:
                        box.label(text=f"Properties — applies to {nb_sel} selected", icon="INFO")
                    else:
                        box.label(text="Prop properties")

                    box.prop(obj, "gta_lod_dist", text="LOD Dist")
                    box.prop(obj, "gta_lod_level", text="LOD Level")
                    box.prop(obj, "gta_priority_level", text="Priority")
                    box.prop(obj, "gta_flags_value", text="Flags value")

                    col = box.column(align=True)
                    col.label(text="Flags:")
                    col.prop(obj, "gta_flag_allow_full_rotation", text="Allow Full Rotation (1)")
                    col.prop(obj, "gta_flag_stream_low_priority", text="Stream Low Priority (2)")
                    col.prop(obj, "gta_flag_disable_embedded_collisions", text="Disable embedded Collisions (4)")
                    col.prop(obj, "gta_flag_lod_in_parent_map", text="LOD in parent map (8)")
                    col.prop(obj, "gta_flag_lod_adopt_me", text="LOD Adopt me (16)")
                    col.prop(obj, "gta_flag_static_entity", text="Static Entity (32)")
                    col.prop(obj, "gta_flag_interior_lod", text="Interior LOD (64)")
                    col.prop(obj, "gta_flag_lod_use_alt_fade", text="LOD Use Alt Fade (32768)")
                    col.prop(obj, "gta_flag_underwater", text="Underwater (65536)")
                    col.prop(obj, "gta_flag_doesnt_touch_water", text="Doesn't touch water (131072)")
                    col.prop(obj, "gta_flag_doesnt_spawn_peds", text="Doesn't spawn peds (262144)")
                    col.prop(obj, "gta_flag_cast_static_shadows", text="Cast Static Shadows (524288)")
                    col.prop(obj, "gta_flag_cast_dynamic_shadows", text="Cast Dynamic Shadows (1048576)")
                    col.prop(obj, "gta_flag_ignore_time_settings", text="Ignore Time Settings (2097152)")
                    col.prop(obj, "gta_flag_no_render_shadows", text="Don't render shadows (4194304)")
                    col.prop(obj, "gta_flag_only_render_shadows", text="Only render shadows (8388608)")
                    col.prop(obj, "gta_flag_no_render_reflections", text="Dont render reflections (16777216)")
                    col.prop(obj, "gta_flag_only_render_reflections", text="Only render reflections (33554432)")
                    col.prop(obj, "gta_flag_no_render_water_reflections", text="Don't render water reflections (67108864)")
                    col.prop(obj, "gta_flag_only_render_water_reflections", text="Only render water reflections (134217728)")
                    col.prop(obj, "gta_flag_no_render_mirror_reflections", text="Don't render mirror reflections (268435456)")
                    col.prop(obj, "gta_flag_only_render_mirror_reflections", text="Only render mirror reflections (536870912)")

                    try:
                        s = obj.matrix_world.to_scale()
                        box.row().label(
                            text=f"World scale: X={s.x:.3f}  Y={s.y:.3f}  Z={s.z:.3f}",
                        )
                    except Exception:
                        pass

        # ----------------------------------
        # DEBUG PERFORMANCE
        # ----------------------------------
        if constants.GTA_DEBUG_PERF:
            box_dbg = layout.box()
            p = perf.gta_perf_state
            calls = p["calls"]
            box_dbg.label(text="Performance debug", icon="TEMP")

            if calls > 0:
                avg = p["total_ms"] / calls
                hist = list(p["history"])
                recent_avg = sum(hist) / len(hist) if hist else 0.0
                recent_max = max(hist) if hist else 0.0

                col_dbg = box_dbg.column(align=True)
                col_dbg.label(text=f"Calls: {calls}    Spikes: {p['spikes']}")
                col_dbg.label(text=f"Avg: {avg:.2f} ms    Max: {p['max_ms']:.2f} ms")
                col_dbg.label(
                    text=f"Recent ({len(hist)}) - avg: {recent_avg:.2f} ms    max: {recent_max:.2f} ms"
                )

                row_bar = box_dbg.row()
                if recent_avg > constants.GTA_DEBUG_SPIKE_MS * 2:
                    row_bar.alert = True
                    row_bar.label(text="Slow - see console", icon="ERROR")
                elif recent_avg > constants.GTA_DEBUG_SPIKE_MS:
                    row_bar.label(text="Slightly slow", icon="INFO")
                else:
                    row_bar.label(text="Performance OK", icon="CHECKMARK")
            else:
                box_dbg.label(text="Waiting for data...")

            row_dbg = box_dbg.row(align=True)
            row_dbg.operator("gta.perf_report", text="Console report", icon="TEXT")
            row_dbg.operator("gta.perf_reset", text="Reset", icon="TRASH")

