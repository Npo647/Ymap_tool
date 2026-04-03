"""Registers RNA classes and custom properties."""

import bpy
from bpy.props import (
    StringProperty,
    EnumProperty,
    IntProperty,
    BoolProperty,
    CollectionProperty,
)

from . import handlers
from . import perf
from . import ymap_core as yc
from .operators_ui import (
    GTA_UL_ymap_links,
    GTA_OT_ymap_list_click,
    GTA_OT_ymap_focus_object,
    GTA_OT_ymap_link_add,
    GTA_OT_ymap_link_remove,
    GTA_OT_ymap_links_sync,
    GTA_OT_ymap_toggle_visibility,
    GTA_OT_export_ymap_xml,
    GTA_OT_create_ymap_structure,
    GTA_OT_ymap_delete,
    GTA_OT_ymap_delete_final,
    GTA_PT_ymap_panel,
)

classes = (
    yc.GTA_YmapLinkItem,
    yc.GTA_YmapDataItem,
    GTA_UL_ymap_links,
    GTA_OT_ymap_list_click,
    GTA_OT_ymap_focus_object,
    GTA_OT_ymap_link_add,
    GTA_OT_ymap_link_remove,
    GTA_OT_ymap_links_sync,
    GTA_OT_ymap_toggle_visibility,
    GTA_OT_export_ymap_xml,
    GTA_OT_create_ymap_structure,
    GTA_OT_ymap_delete,
    GTA_OT_ymap_delete_final,
    perf.GTA_OT_perf_report,
    perf.GTA_OT_perf_reset,
    GTA_PT_ymap_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.gta_active_ymap = EnumProperty(
        name="Select another YMAP",
        description="Choose which YMAP is active (current name is edited in the Name field)",
        items=yc.gta_ymap_items,
    )
    bpy.types.Scene.gta_ymaps = CollectionProperty(
        type=yc.GTA_YmapDataItem,
        name="YMAP entries",
    )
    bpy.types.Scene.gta_name_conflict_message = StringProperty(
        name="YMAP name warning",
        default="",
        options={"HIDDEN"},
    )
    bpy.types.Scene.gta_sync_ymap_selection = BoolProperty(
        name="Sync selection",
        description="Keep 3D View selection in sync with the active YMAP list row",
        default=False,
        update=yc.gta_on_sync_selection_toggle,
    )

    bpy.types.Scene.gta_multisel_shift = BoolProperty(default=False, options={"HIDDEN"})
    bpy.types.Scene.gta_multisel_ctrl = BoolProperty(default=False, options={"HIDDEN"})
    bpy.types.Scene.gta_ymap_index_from_ui = BoolProperty(default=False, options={"HIDDEN"})
    bpy.types.Scene.gta_skip_view_sync_once = BoolProperty(default=False, options={"HIDDEN"})

    bpy.types.Object.gta_lod_dist = IntProperty(
        name="LOD Dist",
        description="Prop cull distance",
        default=200,
        min=0,
        update=yc._make_gta_update("gta_lod_dist"),
    )

    bpy.types.Object.gta_lod_level = EnumProperty(
        name="LOD Level",
        description="Entity LOD type in the YMAP",
        items=[
            ("LODTYPES_DEPTH_ORPHANHD", "ORPHANHD", "Orphan HD (default)"),
            ("LODTYPES_DEPTH_HD", "HD", "High detail (close)"),
            ("LODTYPES_DEPTH_LOD", "LOD", "Standard LOD"),
            ("LODTYPES_DEPTH_SLOD1", "SLOD1", "Super LOD 1 (far)"),
            ("LODTYPES_DEPTH_SLOD2", "SLOD2", "Super LOD 2"),
            ("LODTYPES_DEPTH_SLOD3", "SLOD3", "Super LOD 3"),
            ("LODTYPES_DEPTH_SLOD4", "SLOD4", "Super LOD 4 (very far)"),
        ],
        default="LODTYPES_DEPTH_ORPHANHD",
        update=yc._make_gta_update("gta_lod_level"),
    )

    bpy.types.Object.gta_priority_level = EnumProperty(
        name="Priority",
        description="Entity streaming priority",
        items=[
            ("PRI_REQUIRED", "Required", "Always required"),
            ("PRI_OPTIONAL_HIGH", "Optional High", "Optional, high priority"),
            ("PRI_OPTIONAL_MEDIUM", "Optional Medium", "Optional, medium priority"),
            ("PRI_OPTIONAL_LOW", "Optional Low", "Optional, low priority"),
        ],
        default="PRI_REQUIRED",
        update=yc._make_gta_update("gta_priority_level"),
    )

    bpy.types.Object.gta_auto_full_rot = BoolProperty(
        name="Auto full rotation",
        description="Automatically set Allow Full Rotation when rotation is not Z-only",
        default=True,
        update=yc.update_auto_full_rot,
    )

    bpy.types.Object.gta_flag_allow_full_rotation = BoolProperty(
        name="Allow Full Rotation",
        default=False,
        update=yc._make_gta_update("gta_flag_allow_full_rotation"),
    )
    bpy.types.Object.gta_flag_stream_low_priority = BoolProperty(
        name="Stream Low Priority",
        default=False,
        update=yc._make_gta_update("gta_flag_stream_low_priority"),
    )
    bpy.types.Object.gta_flag_disable_embedded_collisions = BoolProperty(
        name="Disable embedded Collisions",
        default=False,
        update=yc._make_gta_update("gta_flag_disable_embedded_collisions"),
    )
    bpy.types.Object.gta_flag_lod_in_parent_map = BoolProperty(
        name="LOD in parent map",
        default=False,
        update=yc._make_gta_update("gta_flag_lod_in_parent_map"),
    )
    bpy.types.Object.gta_flag_lod_adopt_me = BoolProperty(
        name="LOD Adopt me",
        default=False,
        update=yc._make_gta_update("gta_flag_lod_adopt_me"),
    )
    bpy.types.Object.gta_flag_static_entity = BoolProperty(
        name="Static Entity",
        default=True,
        update=yc._make_gta_update("gta_flag_static_entity"),
    )
    bpy.types.Object.gta_flag_interior_lod = BoolProperty(
        name="Interior LOD",
        default=False,
        update=yc._make_gta_update("gta_flag_interior_lod"),
    )
    bpy.types.Object.gta_flag_lod_use_alt_fade = BoolProperty(
        name="LOD Use Alt Fade",
        default=False,
        update=yc._make_gta_update("gta_flag_lod_use_alt_fade"),
    )
    bpy.types.Object.gta_flag_underwater = BoolProperty(
        name="Underwater",
        default=False,
        update=yc._make_gta_update("gta_flag_underwater"),
    )
    bpy.types.Object.gta_flag_doesnt_touch_water = BoolProperty(
        name="Doesn't touch water",
        default=False,
        update=yc._make_gta_update("gta_flag_doesnt_touch_water"),
    )
    bpy.types.Object.gta_flag_doesnt_spawn_peds = BoolProperty(
        name="Doesn't spawn peds",
        default=False,
        update=yc._make_gta_update("gta_flag_doesnt_spawn_peds"),
    )
    bpy.types.Object.gta_flag_cast_static_shadows = BoolProperty(
        name="Cast Static Shadows",
        default=False,
        update=yc._make_gta_update("gta_flag_cast_static_shadows"),
    )
    bpy.types.Object.gta_flag_cast_dynamic_shadows = BoolProperty(
        name="Cast Dynamic Shadows",
        default=False,
        update=yc._make_gta_update("gta_flag_cast_dynamic_shadows"),
    )
    bpy.types.Object.gta_flag_ignore_time_settings = BoolProperty(
        name="Ignore Time Settings",
        default=False,
        update=yc._make_gta_update("gta_flag_ignore_time_settings"),
    )
    bpy.types.Object.gta_flag_no_render_shadows = BoolProperty(
        name="Don't render shadows",
        default=False,
        update=yc._make_gta_update("gta_flag_no_render_shadows"),
    )
    bpy.types.Object.gta_flag_only_render_shadows = BoolProperty(
        name="Only render shadows",
        default=False,
        update=yc._make_gta_update("gta_flag_only_render_shadows"),
    )
    bpy.types.Object.gta_flag_no_render_reflections = BoolProperty(
        name="Dont render reflections",
        default=False,
        update=yc._make_gta_update("gta_flag_no_render_reflections"),
    )
    bpy.types.Object.gta_flag_only_render_reflections = BoolProperty(
        name="Only render reflections",
        default=False,
        update=yc._make_gta_update("gta_flag_only_render_reflections"),
    )
    bpy.types.Object.gta_flag_no_render_water_reflections = BoolProperty(
        name="Don't render water reflections",
        default=False,
        update=yc._make_gta_update("gta_flag_no_render_water_reflections"),
    )
    bpy.types.Object.gta_flag_only_render_water_reflections = BoolProperty(
        name="Only render water reflections",
        default=False,
        update=yc._make_gta_update("gta_flag_only_render_water_reflections"),
    )
    bpy.types.Object.gta_flag_no_render_mirror_reflections = BoolProperty(
        name="Don't render mirror reflections",
        default=False,
        update=yc._make_gta_update("gta_flag_no_render_mirror_reflections"),
    )
    bpy.types.Object.gta_flag_only_render_mirror_reflections = BoolProperty(
        name="Only render mirror reflections",
        default=False,
        update=yc._make_gta_update("gta_flag_only_render_mirror_reflections"),
    )

    bpy.types.Object.gta_flags_value = IntProperty(
        name="Flags value",
        description="Combined flags as an integer (copy/paste). Pasting updates the checkboxes.",
        get=yc.gta_get_flags_value,
        set=yc.gta_set_flags_value,
    )

    if handlers.gta_on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(handlers.gta_on_depsgraph_update)
    if handlers.gta_on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(handlers.gta_on_load_post)


def unregister():
    if handlers.gta_on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(handlers.gta_on_depsgraph_update)
    if handlers.gta_on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(handlers.gta_on_load_post)

    for attr in (
        "gta_active_ymap",
        "gta_ymaps",
        "gta_name_conflict_message",
        "gta_sync_ymap_selection",
        "gta_multisel_shift",
        "gta_multisel_ctrl",
        "gta_ymap_index_from_ui",
        "gta_skip_view_sync_once",
    ):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)

    for attr in (
        "gta_lod_dist",
        "gta_auto_full_rot",
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
        "gta_flags_value",
        "gta_lod_level",
        "gta_priority_level",
    ):
        if hasattr(bpy.types.Object, attr):
            delattr(bpy.types.Object, attr)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
