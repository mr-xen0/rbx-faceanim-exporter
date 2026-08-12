"""Deterministic numbered Image Sequence discovery."""
from __future__ import annotations

from pathlib import Path
import re

_SUFFIX = re.compile(r"(.+?)(\d+)(\.[^.]+)")


def parse_filename_suffix(filename: str) -> tuple[str, int, str]:
    match = _SUFFIX.fullmatch(filename)
    if not match:
        raise ValueError(f"Image filename needs a numeric suffix: {filename}")
    prefix, digits, extension = match.groups()
    return prefix, int(digits), extension


def build_sequence_manifest(image_path: str) -> tuple[int, ...]:
    """Return file numbers in ImageUser sequence order; reject holes/ambiguity."""
    source = Path(image_path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Base image file does not exist: {source}")

    prefix, _, extension = parse_filename_suffix(source.name)
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+){re.escape(extension)}$", re.IGNORECASE)
    discovered: dict[int, str] = {}

    for entry in source.parent.iterdir():
        if not entry.is_file():
            continue
        match = pattern.fullmatch(entry.name)
        if not match:
            continue
        number = int(match.group(1))
        if number in discovered:
            raise ValueError(f"Duplicate sequence number {number}: {discovered[number]}, {entry.name}")
        discovered[number] = entry.name

    if not discovered:
        raise ValueError(f"No sequence files match {source.name}")

    numbers = sorted(discovered)
    if numbers != list(range(numbers[0], numbers[-1] + 1)):
        present = set(numbers)
        missing = [str(number) for number in range(numbers[0], numbers[-1] + 1) if number not in present]
        raise ValueError(f"Sequence has missing file number(s): {', '.join(missing)}")
    if numbers[0] < 1 or numbers[-1] > 9999:
        raise ValueError("Importer-compatible sequence file numbers must be in 1..9999")
    return tuple(numbers)


def resolve_sequence_file(manifest: tuple[int, ...], sequence_frame: int) -> int:
    if sequence_frame < 1 or sequence_frame > len(manifest):
        raise ValueError(f"No source image exists for sequence frame {sequence_frame}")
    return manifest[sequence_frame - 1]
