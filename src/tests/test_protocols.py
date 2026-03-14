from __future__ import annotations

import json
import unittest

from protocols.freed import parse_freed_d1
from protocols.opentrackio import parse_opentrackio


def _signed_int24_bytes(value: int) -> bytes:
    if value < 0:
        value += 1 << 24
    return value.to_bytes(3, byteorder="big", signed=False)


def _unsigned_int24_bytes(value: int) -> bytes:
    return value.to_bytes(3, byteorder="big", signed=False)


class ProtocolTests(unittest.TestCase):
    def test_freed_packet_parsing(self):
        payload = bytearray()
        payload.append(0xD1)
        payload.append(3)
        payload.extend(_signed_int24_bytes(int(12.5 * 32768)))
        payload.extend(_signed_int24_bytes(int(-4.25 * 32768)))
        payload.extend(_signed_int24_bytes(int(1.5 * 32768)))
        payload.extend(_signed_int24_bytes(100))
        payload.extend(_signed_int24_bytes(-200))
        payload.extend(_signed_int24_bytes(300))
        payload.extend(_unsigned_int24_bytes(123456))
        payload.extend(_unsigned_int24_bytes(654321))
        payload.extend(b"\x00\x00")
        payload.append(sum(payload) & 0xFF)

        packet = parse_freed_d1(bytes(payload))
        self.assertEqual(packet.camera_id, 3)
        self.assertEqual(packet.zoom, 123456)
        self.assertEqual(packet.focus, 654321)
        self.assertAlmostEqual(packet.pan, 12.5, places=3)
        self.assertAlmostEqual(packet.tilt, -4.25, places=3)
        self.assertEqual(packet.pos_y, -200.0)

    def test_opentrackio_parsing(self):
        data = {
            "protocol": "OpenTrackIO",
            "version": "0.9",
            "sample": {
                "timestamp": 1234.5,
                "transforms": {"translation": [1.0, 2.0, 3.0], "rotation": [10.0, 20.0, 30.0]},
                "lens": {"focalLength": 50.0, "focusDistance": 2.4, "iris": 2.8},
                "distortion": {"coefficients": [-0.01, 0.001]},
            },
        }
        sample = parse_opentrackio(json.dumps(data).encode("utf-8"))
        self.assertEqual(sample.timestamp, 1234.5)
        self.assertEqual(sample.translation, (1.0, 2.0, 3.0))
        self.assertEqual(sample.rotation, (10.0, 20.0, 30.0))
        self.assertEqual(sample.focal_length_mm, 50.0)
        self.assertEqual(sample.distortion_coefficients, [-0.01, 0.001])


if __name__ == "__main__":
    unittest.main()

