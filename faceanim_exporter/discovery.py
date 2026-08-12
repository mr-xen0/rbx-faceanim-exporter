"""Discover marked face channels and isolate duplicated rig data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

_CHANNEL_ID = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class DiscoveredChannel:
    channel_id: str
    object_name: str
    material_name: str = ""
    image_node_name: str = ""
    status: str = "READY"


def is_descendant_of(obj: Any, target_rig: Any) -> bool:
    if target_rig is None or obj == target_rig:
        return True
    visited = {id(obj)}
    cursor = getattr(obj, "parent", None)
    while cursor is not None:
        if cursor == target_rig:
            return True
        if id(cursor) in visited:
            if isinstance(target_rig, str):
                return True
            break
        visited.add(id(cursor))
        cursor = getattr(cursor, "parent", None)
    return False


def discover_rig_objects(scene: Any) -> list[Any]:
    rigs: dict[str, Any] = {}
    objects = getattr(scene, "objects", [])
    for obj in objects:
        if getattr(obj, "type", "") == "ARMATURE" or "rig_id" in obj:
            rigs.setdefault(getattr(obj, "name", ""), obj)
    for obj in objects:
        if "face_channel_id" not in obj or getattr(obj, "parent", None) is None:
            continue
        root = obj
        visited = {id(root)}
        while getattr(root, "parent", None) is not None:
            parent = root.parent
            if id(parent) in visited:
                break
            visited.add(id(parent))
            root = parent
        rigs.setdefault(getattr(root, "name", ""), root)
    return [rigs[name] for name in sorted(rigs)]


def ensure_unique_rig_ids(scene: Any) -> None:
    used: set[str] = set()
    for obj in getattr(scene, "objects", []):
        if "rig_id" not in obj:
            continue
        base = str(obj["rig_id"]).strip() or "faceset_rig"
        value = base
        suffix = 1
        while value in used:
            value = f"{base}_{suffix}"
            suffix += 1
        obj["rig_id"] = value
        used.add(value)


def auto_fix_rig_materials_and_drivers(scene: Any, target_rig: Any) -> tuple[int, int, int]:
    if target_rig is None:
        raise ValueError("Target rig is required")

    materials = images = drivers = 0
    for obj in getattr(scene, "objects", []):
        if "face_channel_id" not in obj or not is_descendant_of(obj, target_rig):
            continue
        for slot in getattr(obj, "material_slots", []):
            material = slot.material
            if material is None or not getattr(material, "use_nodes", False) or material.node_tree is None:
                continue
            if getattr(material, "users", 1) > 1:
                material = material.copy()
                slot.material = material
                materials += 1

            for node in material.node_tree.nodes:
                if getattr(node, "bl_idname", "") != "ShaderNodeTexImage":
                    continue
                image = getattr(node, "image", None)
                if image and image.source == "SEQUENCE" and getattr(image, "users", 1) > 1:
                    node.image = image.copy()
                    images += 1

            animation = getattr(material.node_tree, "animation_data", None)
            for curve in getattr(animation, "drivers", []) if animation else []:
                # Only ImageUser drivers participate in face-frame selection.
                if "image_user.frame_offset" not in str(getattr(curve, "data_path", "")):
                    continue
                driver = getattr(curve, "driver", None)
                for variable in getattr(driver, "variables", []) if driver else []:
                    for target in getattr(variable, "targets", []):
                        current = getattr(target, "id", None)
                        if current is not None and current != target_rig:
                            target.id = target_rig
                            drivers += 1
    return materials, images, drivers


def discover_scene_channels(scene: Any, target_rig: Any = None, target_rig_object: Any = None) -> list[DiscoveredChannel]:
    if target_rig_object is not None:
        target_rig = target_rig_object
    results: list[DiscoveredChannel] = []
    for obj in getattr(scene, "objects", []):
        if "face_channel_id" not in obj or not is_descendant_of(obj, target_rig):
            continue

        channel_id = str(obj["face_channel_id"]).strip()
        name = getattr(obj, "name", "")
        if not _CHANNEL_ID.fullmatch(channel_id):
            results.append(DiscoveredChannel(channel_id, name, status="INVALID_CHANNEL_ID"))
            continue

        candidates: list[tuple[str, Any]] = []
        has_material = False
        for slot in getattr(obj, "material_slots", []):
            material = slot.material
            if material is None or not material.use_nodes or material.node_tree is None:
                continue
            has_material = True
            for node in material.node_tree.nodes:
                image = getattr(node, "image", None)
                if getattr(node, "bl_idname", "") == "ShaderNodeTexImage" and image and image.source == "SEQUENCE":
                    candidates.append((material.name, node))

        if not has_material:
            results.append(DiscoveredChannel(channel_id, name, status="NO_MATERIAL"))
            continue
        if not candidates:
            results.append(DiscoveredChannel(channel_id, name, status="NO_SEQUENCE_NODE"))
            continue

        marked = [candidate for candidate in candidates if candidate[1].get("face_export") is True]
        if len(marked) == 1:
            material_name, node = marked[0]
        elif not marked and len(candidates) == 1:
            material_name, node = candidates[0]
        else:
            results.append(DiscoveredChannel(channel_id, name, status="AMBIGUOUS_NODE"))
            continue

        if not node.image.filepath:
            results.append(DiscoveredChannel(channel_id, name, material_name, node.name, "IMAGE_MISSING"))
            continue
        results.append(DiscoveredChannel(channel_id, name, material_name, node.name))

    counts: dict[str, int] = {}
    for item in results:
        counts[item.channel_id] = counts.get(item.channel_id, 0) + 1
    for item in results:
        if counts[item.channel_id] > 1 and item.status != "INVALID_CHANNEL_ID":
            item.status = "DUPLICATE_CHANNEL_ID"
    return sorted(results, key=lambda item: (item.channel_id, item.object_name))
