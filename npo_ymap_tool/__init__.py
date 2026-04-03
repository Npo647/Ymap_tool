bl_info = {
    "name": "Npo GTA YMAP Tool",
    "author": "Npo",
    "version": (1, 0, 2),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > GTA",
    "category": "3D View",
}

from .register_addon import register, unregister

if __name__ == "__main__":
    register()
