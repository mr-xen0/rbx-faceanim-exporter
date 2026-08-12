"""Blender sampler for the exact faceanim/1 fields consumed by the Roblox importer."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from .manifest import build_sequence_manifest, resolve_sequence_file

_CHANNEL_ID = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class FaceChannelConfig:
    channel_id: str
    object_name: str
    material_name: str
    image_node_name: str
    enabled: bool = True


@dataclass
class ResolvedChannel:
    config: FaceChannelConfig
    node: Any
    manifest: tuple[int, ...]


def get_export_range(scene: Any) -> tuple[int, int, str]:
    if scene.use_preview_range:
        return scene.frame_preview_start, scene.frame_preview_end, "preview"
    return scene.frame_start, scene.frame_end, "scene"


def validate_integer_fps(scene: Any) -> int:
    fps = int(scene.render.fps)
    fps_base = Fraction(str(scene.render.fps_base)).limit_denominator()
    if not 1 <= fps <= 999 or fps_base != 1:
        raise ValueError(f"Moon 34000 v1 needs integer FPS in 1..999; got {fps}/{fps_base}")
    return fps


def calculate_sequence_frame(scene_frame: int, frame_start: int, frame_duration: int, frame_offset: object, cyclic: bool) -> int:
    if frame_duration <= 0:
        raise ValueError("frame_duration must be positive")
    if isinstance(frame_offset, bool) or not isinstance(frame_offset, (int, float)) or int(frame_offset) != frame_offset:
        raise ValueError("ImageUser.frame_offset must be an integer")

    relative = scene_frame - frame_start + 1
    playback = ((relative - 1) % frame_duration) + 1 if cyclic else max(1, min(relative, frame_duration))
    return playback + int(frame_offset)


def texture_key(channel_id: str, file_number: int) -> str:
    """Canonical AssetRegistry key form: <channel>/<4-digit frame>."""
    if not _CHANNEL_ID.fullmatch(channel_id):
        raise ValueError(f"Invalid channel_id for AssetRegistry key: {channel_id!r}")
    if not 1 <= file_number <= 9999:
        raise ValueError(f"Texture frame must be in 1..9999; got {file_number}")
    return f"{channel_id}/{file_number:04d}"


def _absolute_blender_path(path: str) -> str:
    import bpy  # type: ignore

    return bpy.path.abspath(path)


def _resolve_channel(scene: Any, config: FaceChannelConfig) -> ResolvedChannel:
    obj = scene.objects.get(config.object_name)
    if obj is None:
        raise ValueError(f"Object not found: {config.object_name}")

    material = next(
        (slot.material for slot in obj.material_slots if slot.material and slot.material.name == config.material_name),
        None,
    )
    if material is None:
        raise ValueError(f"Material {config.material_name!r} is not assigned to {config.object_name!r}")
    if not material.use_nodes or material.node_tree is None:
        raise ValueError(f"Material {config.material_name!r} does not use nodes")

    node = material.node_tree.nodes.get(config.image_node_name)
    if node is None or getattr(node, "bl_idname", "") != "ShaderNodeTexImage":
        raise ValueError(f"Image Texture node not found: {config.image_node_name}")
    image = node.image
    if image is None or image.source != "SEQUENCE":
        raise ValueError(f"Image Texture node {config.image_node_name!r} must use an Image Sequence")

    return ResolvedChannel(config, node, build_sequence_manifest(_absolute_blender_path(image.filepath)))


def validate_export(scene: Any, configs: list[FaceChannelConfig]) -> list[ResolvedChannel]:
    start, end, _ = get_export_range(scene)
    if not isinstance(start, int) or not isinstance(end, int) or end < start:
        raise ValueError("Export range is invalid")
    validate_integer_fps(scene)

    enabled = [config for config in configs if config.enabled]
    if not enabled:
        raise ValueError("At least one enabled channel is required")

    seen: set[str] = set()
    resolved: list[ResolvedChannel] = []
    for config in enabled:
        channel_id = config.channel_id
        if not _CHANNEL_ID.fullmatch(channel_id):
            raise ValueError(f"Invalid channel_id: {channel_id!r}")
        if channel_id in seen:
            raise ValueError(f"Duplicate channel_id: {channel_id}")
        seen.add(channel_id)
        resolved.append(_resolve_channel(scene, config))
    return sorted(resolved, key=lambda item: item.config.channel_id)


def validate_document(document: dict[str, Any]) -> None:
    """Mirror the fields/constraints used by Core/FaceAnim.luau."""
    if document.get("schema") != "faceanim/1":
        raise ValueError("schema must be faceanim/1")
    if not isinstance(document.get("animation_id"), str) or not document["animation_id"]:
        raise ValueError("animation_id must be non-empty")
    if not isinstance(document.get("rig_id"), str) or not document["rig_id"]:
        raise ValueError("rig_id must be non-empty")

    timeline = document.get("timeline")
    if not isinstance(timeline, dict):
        raise ValueError("timeline is required")
    duration = timeline.get("duration_ticks")
    fps = timeline.get("fps_num")
    if not isinstance(duration, int) or isinstance(duration, bool) or duration < 0:
        raise ValueError("duration_ticks must be a non-negative integer")
    if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0 or timeline.get("fps_den") != 1:
        raise ValueError("Importer requires positive integer fps_num and fps_den = 1")

    tracks = document.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("At least one animation track is required")
    seen: set[str] = set()
    for track in tracks:
        if not isinstance(track, dict) or not isinstance(track.get("channel_id"), str) or not track["channel_id"]:
            raise ValueError("Every track needs a channel_id")
        channel_id = track["channel_id"]
        if channel_id in seen:
            raise ValueError(f"Duplicate channel_id: {channel_id}")
        seen.add(channel_id)
        if track.get("property_adapter") != "decal_image":
            raise ValueError(f"Track {channel_id} has unsupported property_adapter")

        keys = track.get("keys")
        if not isinstance(keys, list) or not keys:
            raise ValueError(f"Track {channel_id} contains no keys")
        previous = -1
        for key in keys:
            tick = key.get("tick") if isinstance(key, dict) else None
            value = key.get("texture_key") if isinstance(key, dict) else None
            if not isinstance(tick, int) or isinstance(tick, bool) or tick < 0 or tick > duration or tick <= previous:
                raise ValueError(f"Track {channel_id} contains an invalid/out-of-order tick")
            if not isinstance(value, str) or not value:
                raise ValueError(f"Track {channel_id} contains an empty texture_key")
            previous = tick
        if keys[0]["tick"] != 0:
            raise ValueError(f"Track {channel_id} must start at tick 0")


def _sample_texture_key(resolved: ResolvedChannel, source_frame: int) -> str:
    user = resolved.node.image_user
    sequence_frame = calculate_sequence_frame(
        source_frame,
        user.frame_start,
        user.frame_duration,
        user.frame_offset,
        user.use_cyclic,
    )
    file_number = resolve_sequence_file(resolved.manifest, sequence_frame)
    return texture_key(resolved.config.channel_id, file_number)


def export_face_animation(scene: Any, configs: list[FaceChannelConfig]) -> dict[str, Any]:
    """Evaluate each timeline frame; restore the original frame on all paths."""
    resolved = validate_export(scene, configs)
    start, end, _ = get_export_range(scene)
    fps = validate_integer_fps(scene)
    animation_id = scene.faceanim_export.animation_id
    rig_id = scene.faceanim_export.rig_id
    if not animation_id or not rig_id:
        raise ValueError("Animation ID and Rig ID are required")

    keys_by_channel = {item.config.channel_id: [] for item in resolved}
    previous: dict[str, str] = {}
    original_frame = scene.frame_current

    try:
        import bpy  # type: ignore

        for frame in range(start, end + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            tick = frame - start
            for item in resolved:
                channel_id = item.config.channel_id
                key = _sample_texture_key(item, frame)
                if key != previous.get(channel_id):
                    keys_by_channel[channel_id].append({"tick": tick, "texture_key": key})
                    previous[channel_id] = key
    finally:
        scene.frame_set(original_frame)

    document = {
        "schema": "faceanim/1",
        "animation_id": animation_id,
        "rig_id": rig_id,
        "timeline": {"duration_ticks": end - start, "fps_num": fps, "fps_den": 1},
        "tracks": [
            {
                "channel_id": item.config.channel_id,
                "property_adapter": "decal_image",
                "keys": keys_by_channel[item.config.channel_id],
            }
            for item in resolved
        ],
    }
    validate_document(document)
    return document


def canonical_json(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def output_path(path: str, animation_id: str) -> str:
    destination = Path(path).expanduser()
    if destination.suffix.lower() != ".json":
        destination /= f"{animation_id}.faceanim.json"
    elif not destination.name.endswith(".faceanim.json"):
        destination = destination.with_name(f"{destination.stem}.faceanim.json")
    return str(destination)


def write_export(document: dict[str, Any], path: str) -> None:
    validate_document(document)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=destination.parent, delete=False) as temporary:
        temporary.write(canonical_json(document))
        temporary_path = temporary.name
    os.replace(temporary_path, destination)
