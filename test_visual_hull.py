import json
import struct
import unittest

from visual_hull import VisualHullError, build_visual_hull


def box_view(resolution=8):
    width, height = resolution, resolution * 2
    return [
        "".join("1" if 1 <= x < width - 1 and 2 <= y < height - 2 else "0" for x in range(width))
        for y in range(height)
    ]


class VisualHullTests(unittest.TestCase):
    def test_consistent_four_views_project_at_100_percent(self):
        silhouette = box_view()
        result = build_visual_hull({name: silhouette for name in ("front", "back", "left", "right")}, 8)
        self.assertEqual(result["scores"], {name: 1.0 for name in ("front", "back", "left", "right")})
        self.assertGreater(result["occupied_voxels"], 0)
        self.assertEqual(struct.unpack_from("<I", result["glb"])[0], 0x46546C67)
        self.assertEqual(struct.unpack_from("<I", result["glb"], 8)[0], len(result["glb"]))
        json_size, json_type = struct.unpack_from("<II", result["glb"], 12)
        self.assertEqual(json_type, 0x4E4F534A)
        doc = json.loads(result["glb"][20:20 + json_size])
        self.assertEqual(doc["asset"]["version"], "2.0")
        self.assertEqual(doc["meshes"][0]["primitives"][0]["mode"], 4)
        position_accessor = doc["accessors"][0]
        self.assertAlmostEqual(position_accessor["max"][1] - position_accessor["min"][1], 1.5)

    def test_inconsistent_views_report_less_than_100_percent(self):
        front = box_view()
        narrow = ["0" * 8 for _ in range(16)]
        for y in range(5, 11):
            narrow[y] = "00111100"
        result = build_visual_hull({"front": front, "back": front, "left": narrow, "right": narrow}, 8)
        self.assertLess(result["scores"]["front"], 1.0)

    def test_missing_or_empty_view_is_rejected(self):
        with self.assertRaises(VisualHullError):
            build_visual_hull({"front": box_view()}, 8)
        views = {name: box_view() for name in ("front", "back", "left", "right")}
        views["left"] = ["0" * 8 for _ in range(16)]
        with self.assertRaises(VisualHullError):
            build_visual_hull(views, 8)

    def test_resolution_limit_is_enforced(self):
        with self.assertRaises(VisualHullError):
            build_visual_hull({}, 64)


if __name__ == "__main__":
    unittest.main()
