"""Encoder mapping helpers for FIZ lens data."""

from __future__ import annotations

from dataclasses import dataclass, field


MAX_ENCODER_VALUE = 65535


def create_mapping_from_samples(
    samples: list[tuple[int, float]],
) -> list[tuple[int, float]]:
    """Normalize, deduplicate, and sort measured encoder samples."""

    ordered: dict[int, float] = {}
    for raw, value in samples:
        raw_clamped = max(0, min(int(raw), MAX_ENCODER_VALUE))
        ordered[raw_clamped] = float(value)
    return sorted(ordered.items(), key=lambda item: item[0])


def _interpolate(mapping: list[tuple[int, float]], raw: int) -> float:
    ordered = create_mapping_from_samples(mapping)
    if not ordered:
        return 0.0

    raw_clamped = max(0, min(int(raw), MAX_ENCODER_VALUE))
    if raw_clamped <= ordered[0][0]:
        return ordered[0][1]
    if raw_clamped >= ordered[-1][0]:
        return ordered[-1][1]

    for left, right in zip(ordered, ordered[1:]):
        if left[0] <= raw_clamped <= right[0]:
            span = max(right[0] - left[0], 1)
            alpha = (raw_clamped - left[0]) / span
            return left[1] + alpha * (right[1] - left[1])
    return ordered[-1][1]


@dataclass
class EncoderMapping:
    """Maps raw encoder values to physical lens parameters."""

    lens_name: str
    focus_map: list[tuple[int, float]] = field(default_factory=list)
    zoom_map: list[tuple[int, float]] = field(default_factory=list)
    iris_map: list[tuple[int, float]] = field(default_factory=list)

    def encoder_to_focus(self, raw: int) -> float:
        return _interpolate(self.focus_map, raw)

    def encoder_to_zoom(self, raw: int) -> float:
        return _interpolate(self.zoom_map, raw)

    def encoder_to_iris(self, raw: int) -> float:
        return _interpolate(self.iris_map, raw)
