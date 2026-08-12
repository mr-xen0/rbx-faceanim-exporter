"""Pure ImageUser sequence-frame math used by the Blender sampler."""
from __future__ import annotations


def calculate_sequence_frame(
    scene_frame: int,
    frame_start: int,
    frame_duration: int,
    frame_offset: int,
    cyclic: bool,
) -> int:
    """Return the 1-based Image Sequence position for an evaluated ImageUser."""
    if frame_duration <= 0:
        raise ValueError("frame_duration must be positive")
    relative = scene_frame - frame_start + 1
    if cyclic:
        playback = ((relative - 1) % frame_duration) + 1
    else:
        playback = max(1, min(relative, frame_duration))
    return playback + frame_offset


def require_integral_offset(value: object) -> int:
    """Reject non-integral values rather than silently rounding a driver result."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("ImageUser.frame_offset is not numeric")
    as_int = int(value)
    if as_int != value:
        raise ValueError("ImageUser.frame_offset is not an integer")
    return as_int
