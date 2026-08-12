"""Structured diagnostics and strict faceanim/1 validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def add(
        self,
        severity: Severity,
        code: str,
        message: str,
        **context: Any,
    ) -> None:
        self.diagnostics.append(Diagnostic(severity, code, message, context))

    @property
    def ok(self) -> bool:
        return not any(item.severity == "error" for item in self.diagnostics)

    def extend(self, other: "ValidationReport") -> None:
        self.diagnostics.extend(other.diagnostics)

    def text(self) -> str:
        if not self.diagnostics:
            return "Validation passed."
        return "\n".join(
            f"[{item.severity.upper()}] {item.code}: {item.message}"
            + (f" ({item.context})" if item.context else "")
            for item in self.diagnostics
        )


def validate_faceanim_document(document: dict[str, Any]) -> ValidationReport:
    """Validate the exporter output before it is allowed to reach disk."""
    report = ValidationReport()
    if document.get("schema") != "faceanim/1":
        report.add("error", "SCHEMA", "schema must be faceanim/1")
    if not isinstance(document.get("animation_id"), str) or not document["animation_id"]:
        report.add("error", "ANIMATION_ID", "animation_id must be non-empty")
    if not isinstance(document.get("rig_id"), str) or not document["rig_id"]:
        report.add("error", "RIG_ID", "rig_id must be non-empty")

    timeline = document.get("timeline")
    if not isinstance(timeline, dict):
        report.add("error", "TIMELINE", "timeline object is required")
        return report
    start, end = timeline.get("source_start_frame"), timeline.get("source_end_frame")
    duration = timeline.get("duration_ticks")
    fps_num, fps_den = timeline.get("fps_num"), timeline.get("fps_den")
    if not all(isinstance(value, int) for value in (start, end, duration)) or end < start:
        report.add("error", "TIMELINE_RANGE", "source frame range must be ordered integers")
    elif duration != end - start:
        report.add("error", "TIMELINE_DURATION", "duration_ticks must equal end - start")
    if not isinstance(fps_num, int) or fps_num <= 0 or not isinstance(fps_den, int) or fps_den <= 0:
        report.add("error", "FPS", "fps_num and fps_den must be positive integers")

    tracks = document.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        report.add("error", "TRACKS", "at least one track is required")
        return report
    channel_ids: set[str] = set()
    for index, track in enumerate(tracks):
        if not isinstance(track, dict):
            report.add("error", "TRACK", "track must be an object", index=index)
            continue
        channel_id = track.get("channel_id")
        if not isinstance(channel_id, str) or not channel_id:
            report.add("error", "CHANNEL_ID", "channel_id must be non-empty", index=index)
        elif channel_id in channel_ids:
            report.add("error", "CHANNEL_DUPLICATE", "channel_id values must be unique", channel_id=channel_id)
        else:
            channel_ids.add(channel_id)
        if track.get("property_adapter") != "decal_image":
            report.add("error", "PROPERTY_ADAPTER", "only decal_image is supported", channel_id=channel_id)
        keys = track.get("keys")
        if not isinstance(keys, list) or not keys:
            report.add("error", "KEYS", "track must contain keys", channel_id=channel_id)
            continue
        previous = -1
        for key_index, key in enumerate(keys):
            tick = key.get("tick") if isinstance(key, dict) else None
            texture_key = key.get("texture_key") if isinstance(key, dict) else None
            if not isinstance(tick, int) or tick <= previous or tick < 0 or not isinstance(duration, int) or tick > duration:
                report.add("error", "KEY_TICK", "key ticks must be strictly increasing and in range", channel_id=channel_id, index=key_index)
            else:
                previous = tick
            if not isinstance(texture_key, str) or not texture_key:
                report.add("error", "TEXTURE_KEY", "texture_key must be non-empty", channel_id=channel_id, index=key_index)
        if isinstance(keys[0], dict) and keys[0].get("tick") != 0:
            report.add("error", "KEY_START", "first key must be at tick 0", channel_id=channel_id)
    return report
