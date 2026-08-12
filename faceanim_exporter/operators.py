"""Blender UI operators."""
from __future__ import annotations

from pathlib import Path

try:
    import bpy  # type: ignore
    from bpy.app.handlers import persistent
    from bpy.props import StringProperty
    from bpy.types import Operator
    from bpy_extras.io_utils import ExportHelper
except ModuleNotFoundError:
    bpy = None
    persistent = lambda fn: fn
    StringProperty = lambda **kwargs: None

    class Operator:  # type: ignore[no-redef]
        pass

    class ExportHelper:  # type: ignore[no-redef]
        pass

from .discovery import auto_fix_rig_materials_and_drivers, discover_rig_objects, discover_scene_channels, ensure_unique_rig_ids
from .exporter import FaceChannelConfig, canonical_json, export_face_animation, output_path, write_export


def _configs(settings: object) -> list[FaceChannelConfig]:
    return [
        FaceChannelConfig(
            item.channel_id.strip(),
            item.object_name.strip(),
            item.material_name.strip(),
            item.image_node_name.strip(),
            item.enabled,
        )
        for item in settings.channels
    ]


def _refresh(context: object) -> None:
    settings = context.scene.faceanim_export
    ensure_unique_rig_ids(context.scene)

    if settings.target_rig is None:
        rigs = discover_rig_objects(context.scene)
        if len(rigs) == 1:
            settings.target_rig = rigs[0]
        elif context.active_object in rigs:
            settings.target_rig = context.active_object

    if settings.target_rig is not None:
        if "rig_id" in settings.target_rig:
            settings["rig_id"] = str(settings.target_rig["rig_id"])
        else:
            settings.target_rig["rig_id"] = settings.rig_id

    existing = {item.discovery_key: item.enabled for item in settings.channels}
    discovered = discover_scene_channels(context.scene, settings.target_rig)
    settings.channels.clear()

    for source in discovered:
        item = settings.channels.add()
        item.channel_id = source.channel_id
        item.object_name = source.object_name
        item.material_name = source.material_name
        item.image_node_name = source.image_node_name
        item.status = source.status
        item.discovery_key = f"{source.object_name}|{source.channel_id}"
        item.enabled = existing.get(item.discovery_key, source.status == "READY")

    enabled_counts: dict[str, int] = {}
    for item in settings.channels:
        if item.enabled:
            enabled_counts[item.channel_id] = enabled_counts.get(item.channel_id, 0) + 1
    for item in settings.channels:
        if item.status == "DUPLICATE_CHANNEL_ID" and item.enabled and enabled_counts.get(item.channel_id) == 1:
            item.status = "READY"


def _build_document(context: object) -> dict:
    _refresh(context)
    invalid = [item for item in context.scene.faceanim_export.channels if item.enabled and item.status != "READY"]
    if invalid:
        raise ValueError("Cannot export: selected channels have errors")
    return export_face_animation(context.scene, _configs(context.scene.faceanim_export))


def _default_filename(context: object) -> str:
    animation_id = context.scene.faceanim_export.animation_id or "face_animation"
    filename = f"{animation_id}.faceanim.json"
    if bpy and getattr(bpy.data, "is_saved", False):
        return str(Path(bpy.path.abspath("//")) / filename)
    return filename


class FACEANIM_OT_refresh_channels(Operator):
    bl_idname = "faceanim.refresh_channels"
    bl_label = "Refresh Channels"

    def execute(self, context: object):
        _refresh(context)
        return {"FINISHED"}


class FACEANIM_OT_auto_fix(Operator):
    bl_idname = "faceanim.auto_fix"
    bl_label = "Auto Fix Duplicated Rig"
    bl_description = "Make face materials/images single-user and retarget frame_offset drivers to the selected rig"

    def execute(self, context: object):
        target = context.scene.faceanim_export.target_rig
        if target is None:
            self.report({"ERROR"}, "Select a Target Rig first")
            return {"CANCELLED"}
        materials, images, drivers = auto_fix_rig_materials_and_drivers(context.scene, target)
        if hasattr(target, "update_tag"):
            target.update_tag()
        context.view_layer.update()
        _refresh(context)
        self.report({"INFO"}, f"Auto Fix: {materials} material(s), {images} image(s), {drivers} driver target(s)")
        return {"FINISHED"}


class FACEANIM_OT_export_json(Operator, ExportHelper):
    bl_idname = "faceanim.export_json"
    bl_label = "Export to File"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})
    filepath: StringProperty(subtype="FILE_PATH")

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = _default_filename(context)
        return ExportHelper.invoke(self, context, event) if bpy is not None else self.execute(context)

    def execute(self, context: object):
        try:
            document = _build_document(context)
            path = output_path(self.filepath or _default_filename(context), context.scene.faceanim_export.animation_id)
            write_export(document, path)
        except (OSError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Exported {Path(path).name}")
        return {"FINISHED"}


class FACEANIM_OT_copy_json(Operator):
    bl_idname = "faceanim.copy_json"
    bl_label = "Copy JSON"

    def execute(self, context: object):
        try:
            context.window_manager.clipboard = canonical_json(_build_document(context))
        except ValueError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, "Copied JSON to clipboard")
        return {"FINISHED"}


@persistent
def auto_refresh_handler(_scene) -> None:
    if bpy is not None:
        bpy.ops.faceanim.refresh_channels()


CLASSES = (FACEANIM_OT_auto_fix, FACEANIM_OT_refresh_channels, FACEANIM_OT_export_json, FACEANIM_OT_copy_json)
