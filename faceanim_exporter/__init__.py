"""Blender face animation exporter for the faceanim/1 importer contract."""

bl_info = {
    "name": "Face Animation Exporter",
    "author": "BlenderToMoonWorkflow",
    "version": (0, 1, 0),
    "blender": (4, 4, 0),
    "location": "View3D > Sidebar > Face Animation",
    "description": "Exports Image Sequence channels as faceanim/1 JSON",
    "category": "Import-Export",
}

if "bpy" in locals():
    import importlib
    from . import discovery, exporter, manifest, operators, panels, properties, sequence_eval, validation
    importlib.reload(discovery)
    importlib.reload(exporter)
    importlib.reload(manifest)
    importlib.reload(operators)
    importlib.reload(panels)
    importlib.reload(properties)
    importlib.reload(sequence_eval)
    importlib.reload(validation)

try:
    import bpy  # type: ignore
except ModuleNotFoundError:  # allows pure tests outside Blender
    bpy = None

if bpy is not None:
    from .operators import CLASSES as OPERATOR_CLASSES, auto_refresh_handler
    from .panels import CLASSES as PANEL_CLASSES
    from .properties import CLASSES as PROPERTY_CLASSES

    CLASSES = (*PROPERTY_CLASSES, *OPERATOR_CLASSES, *PANEL_CLASSES)

    def register() -> None:
        for cls in CLASSES:
            bpy.utils.register_class(cls)
        bpy.types.Scene.faceanim_export = bpy.props.PointerProperty(type=PROPERTY_CLASSES[1])
        if auto_refresh_handler not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(auto_refresh_handler)

        def initial_refresh():
            if bpy.context.scene:
                bpy.ops.faceanim.refresh_channels()
            return None

        bpy.app.timers.register(initial_refresh, first_interval=0.1)

    def unregister() -> None:
        if auto_refresh_handler in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(auto_refresh_handler)
        del bpy.types.Scene.faceanim_export
        for cls in reversed(CLASSES):
            bpy.utils.unregister_class(cls)
