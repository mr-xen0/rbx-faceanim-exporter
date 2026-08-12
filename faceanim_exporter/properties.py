"""Persistent Blender settings."""
from __future__ import annotations

import bpy  # type: ignore
from bpy.props import BoolProperty, CollectionProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Object, PropertyGroup


class FACEANIM_PG_channel(PropertyGroup):
    enabled: BoolProperty(name="Enabled", default=True)
    channel_id: StringProperty(name="Channel ID")
    object_name: StringProperty(name="Object")
    material_name: StringProperty(name="Material")
    image_node_name: StringProperty(name="Image Node")
    status: StringProperty(name="Status")
    discovery_key: StringProperty(name="Discovery Key")


def _target_rig_changed(self, _context) -> None:
    rig = self.target_rig
    if rig is None:
        return
    if "rig_id" in rig:
        self["rig_id"] = str(rig["rig_id"])
    else:
        rig["rig_id"] = self.rig_id


def _rig_id_changed(self, _context) -> None:
    if self.target_rig is not None and self.rig_id:
        self.target_rig["rig_id"] = self.rig_id


class FACEANIM_PG_settings(PropertyGroup):
    animation_id: StringProperty(name="Animation ID", default="face_animation")
    target_rig: PointerProperty(type=Object, name="Target Rig", update=_target_rig_changed)
    rig_id: StringProperty(name="Rig ID", default="faceset_rig", update=_rig_id_changed)
    channels: CollectionProperty(type=FACEANIM_PG_channel)
    active_channel_index: IntProperty(default=0)


CLASSES = (FACEANIM_PG_channel, FACEANIM_PG_settings)
