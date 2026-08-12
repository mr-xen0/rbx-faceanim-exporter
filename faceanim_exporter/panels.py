"""3D View sidebar."""
from __future__ import annotations

try:
    from bpy.types import Panel, UIList
except ModuleNotFoundError:
    Panel = object
    UIList = object

from .exporter import get_export_range


class FACEANIM_UL_channels(UIList):
    def draw_item(self, _context, layout, _data, item, _icon, _active_data, _active_propname, _index):
        if self.layout_type == "GRID":
            layout.label(text="")
            return
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.channel_id)
        row.label(text=item.object_name)
        row.label(text="Ready" if item.status == "READY" else item.status, icon="NONE" if item.status == "READY" else "ERROR")


class FACEANIM_PT_export(Panel):
    bl_idname = "FACEANIM_PT_export"
    bl_label = "RBX Face Animation Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RBX Face Animation"

    def draw(self, context: object) -> None:
        layout = self.layout
        scene = context.scene
        settings = scene.faceanim_export

        layout.prop(settings, "target_rig")
        layout.prop(settings, "rig_id")
        layout.prop(settings, "animation_id")
        layout.operator("faceanim.auto_fix", icon="TOOL_SETTINGS")
        layout.template_list("FACEANIM_UL_channels", "", settings, "channels", settings, "active_channel_index")
        layout.operator("faceanim.refresh_channels", text="Refresh")

        start, end, _ = get_export_range(scene)
        ready = sum(item.status == "READY" for item in settings.channels)
        layout.label(text=f"{ready} ready · {start}–{end} · {scene.render.fps}/{scene.render.fps_base:g} FPS")

        row = layout.row(align=True)
        row.operator("faceanim.export_json", text="Export to File")
        row.operator("faceanim.copy_json", text="Copy JSON")

        invalid = sum(item.enabled and item.status != "READY" for item in settings.channels)
        layout.label(text=f"Cannot export: {invalid} selected channel(s) have errors" if invalid else "Status: Ready", icon="ERROR" if invalid else "NONE")


CLASSES = (FACEANIM_UL_channels, FACEANIM_PT_export)
