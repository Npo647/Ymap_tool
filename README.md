# Npo GTA YMAP Tool

A **Blender** add-on to author and export **YMAP** maps (XML) for *Grand Theft Auto V* / *FiveM*, with entity, flag, and LOD handling directly from the 3D View.

- **Author:** Npo  
- **Version:** 1.0.2  
- **Minimum Blender:** 3.0.0  

---

## Requirements

- [Blender](https://www.blender.org/) 3.0 or newer  
- No external Python dependencies (standard library + Blender’s API only)

---

## Installation

1. Download or copy the **`npo_ymap_tool`** folder (the one with `__init__.py` at its root).
2. In Blender: **Edit → Preferences → Add-ons → Install…** and pick a **ZIP** of that folder, **or** drop the folder into Blender’s `addons` directory and enable **“Npo GTA YMAP Tool”** in the list.

---

## Where to find the UI

**3D View → Sidebar (N)** → **“Npo YMAP Tools”** tab.

The panel title is **“YMAP Tools By Npo”**.

---

## Quick start

1. **Create a YMAP** with the **+** button next to the YMAP selector.  
2. **Rename** the YMAP if needed (**Rename YMAP**). You can manage **several** per scene via **Select another YMAP**.  
3. Select **Mesh**, **Empty**, or **Armature** objects in the scene, then **add them** to **Props in this YMAP** (the list’s **+** button).  
4. Set per prop (or multi-row selection): **LOD Dist**, **LOD Level**, **Priority**, and **flags** (checkboxes or **Flags value** for integer bitmasks).  
5. **Export** with **Export YMAP** → **`.ymap.xml`** file.

Objects are not duplicated: the list is a **virtual link** to existing Blender objects.

---

## Main features

| Feature | Description |
|--------|-------------|
| **Multiple YMAPs per scene** | Switch, create, delete (double confirmation). |
| **Prop list** | Add/remove, refresh, ghost rows if the object was deleted. |
| **Selection** | Single click, **Shift** (range), **Ctrl** (toggle); **Sync selection** aligns the list with 3D selection. |
| **Focus** | Magnifier on a row: selects the object and frames it (**View Selected**). |
| **Visibility** | One-click hide/show for everything linked to the active YMAP (hierarchy included). |
| **Multi-edit** | Changing a property can **propagate** to other checked rows; **Apply to selected** copies LOD / priority / flags from the active row. |
| **Auto full rotation** | Optionally drives **Allow Full Rotation** from the object’s real orientation. |
| **XML export** | **CMapData** with **CEntityDef** entities: position, rotation (see below), scale (**scaleXY** / **scaleZ**), **lodDist**, **lodLevel**, **priorityLevel**, **flags**. |

---

## Export & compatibility

- The **map name** in the file is **derived from the YMAP name**: text before the first `.`, spaces and hyphens normalized to `_`.  
- The exported **archetype name** uses the Blender object name with numeric suffixes like `.001`, `.002` stripped.  
- Exported **rotation** is the **inverse** of Blender’s world quaternion, matching CodeWalker / in-game behavior for non-MLO entities.  
- **Extents** (streaming / entities) are computed from exported entity positions.  
- Empty or generic sections (occluders, car generators, etc.) follow a CodeWalker-like layout.

**CodeWalker** (and similar tools) are commonly used to inspect or refine the file on the GTA side.

---

## Naming tips

- Blender may append **`.001`**, **`.002`** when names collide: the add-on **warns** if that hurts the **YMAP** name—rename manually to avoid clashes between active YMAPs.  
- Two YMAPs **cannot** share the same name in the list: the add-on auto-renames when needed.

---

## Performance debugging (developers)

In `constants.py`, set **`GTA_DEBUG_PERF`** to `True` to enable timing and a **Performance debug** section in the panel (console report via the dedicated operators). **Off** by default.

---

## Module files

| File | Role |
|------|------|
| `__init__.py` | Add-on metadata and entry point |
| `register_addon.py` | Class and RNA property registration |
| `ymap_core.py` | YMAP data, flags, link sync |
| `operators_ui.py` | Operators, XML export, UI |
| `handlers.py` | Depsgraph updates (perf, selection sync) |
| `perf.py` | Performance counters (debug mode) |
| `constants.py` | Debug constants |

---

## License

To be defined by the author (Npo), unless a separate `LICENSE` file is provided.
