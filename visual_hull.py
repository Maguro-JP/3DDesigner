"""Four-view silhouette visual hull reconstruction and projection scoring."""
from __future__ import annotations

import json
import math
import struct


class VisualHullError(ValueError):
    pass


VIEWS = ("front", "back", "left", "right")


def _validate_views(views, resolution):
    if not isinstance(resolution, int) or isinstance(resolution, bool) or not 8 <= resolution <= 40:
        raise VisualHullError("resolution must be an integer from 8 to 40")
    width, height = resolution, resolution * 2
    if not isinstance(views, dict) or set(VIEWS) - views.keys():
        raise VisualHullError("four silhouette views are required: front, back, left, right")
    result = {}
    for name in VIEWS:
        rows = views[name]
        if not isinstance(rows, list) or len(rows) != height:
            raise VisualHullError(f"{name} must contain {height} rows")
        if any(not isinstance(row, str) or len(row) != width or set(row) - {"0", "1"} for row in rows):
            raise VisualHullError(f"{name} rows must be {width} characters of 0/1")
        mask = [[c == "1" for c in row] for row in rows]
        if not any(map(any, mask)):
            raise VisualHullError(f"{name} silhouette is empty")
        result[name] = mask
    return result, width, height


def _glb(vertices, indices):
    if not vertices or not indices:
        raise VisualHullError("the four silhouettes have no shared volume")
    binary = bytearray()
    for v in vertices:
        binary.extend(struct.pack("<3f", *v))
    while len(binary) % 4:
        binary.append(0)
    index_offset = len(binary)
    for i in indices:
        binary.extend(struct.pack("<I", i))
    while len(binary) % 4:
        binary.append(0)
    mins = [min(v[i] for v in vertices) for i in range(3)]
    maxs = [max(v[i] for v in vertices) for i in range(3)]
    doc = {
        "asset": {"version": "2.0", "generator": "3DDesigner four-view visual hull"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "mode": 4}]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": index_offset, "target": 34962},
            {"buffer": 0, "byteOffset": index_offset, "byteLength": len(indices) * 4, "target": 34963},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(vertices), "type": "VEC3", "min": mins, "max": maxs},
            {"bufferView": 1, "componentType": 5125, "count": len(indices), "type": "SCALAR", "min": [0], "max": [len(vertices) - 1]},
        ],
    }
    chunk = json.dumps(doc, separators=(",", ":")).encode()
    chunk += b" " * ((4 - len(chunk) % 4) % 4)
    total = 12 + 8 + len(chunk) + 8 + len(binary)
    return struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(chunk), 0x4E4F534A) + chunk + struct.pack("<II", len(binary), 0x004E4942) + binary


def build_visual_hull(views, resolution=32):
    """Intersect four orthographic silhouette prisms on a voxel grid.

    Each mask is rows from top to bottom. Front/back rows map to X; side rows
    map to depth Z. Back/right are mirrored to match outward-looking views.
    Returns a GLB plus per-view binary silhouette IoU scores.
    """
    masks, w, h = _validate_views(views, resolution)
    occ = bytearray(resolution * h * resolution)

    def at(x, y, z):
        return (y * resolution + x) * resolution + z

    for y in range(h):
        for x in range(resolution):
            if not masks["front"][y][x] or not masks["back"][y][resolution - 1 - x]:
                continue
            for z in range(resolution):
                if masks["left"][y][z] and masks["right"][y][resolution - 1 - z]:
                    occ[at(x, y, z)] = 1
    projections = {name: [[False] * w for _ in range(h)] for name in VIEWS}
    for y in range(h):
        for x in range(resolution):
            for z in range(resolution):
                if occ[at(x, y, z)]:
                    projections["front"][y][x] = True
                    projections["back"][y][resolution - 1 - x] = True
                    projections["left"][y][z] = True
                    projections["right"][y][resolution - 1 - z] = True
    scores = {}
    for name in VIEWS:
        intersection = sum(a and b for ra, rb in zip(masks[name], projections[name]) for a, b in zip(ra, rb))
        union = sum(a or b for ra, rb in zip(masks[name], projections[name]) for a, b in zip(ra, rb))
        scores[name] = round(intersection / union if union else 1.0, 6)

    vertices, indices = [], []
    # Outward-facing quads for each exposed voxel face, triangulated.
    faces = [
        (-1, 0, 0, lambda x,y,z: [(x,y,z),(x,y,z+1),(x,y+1,z+1),(x,y+1,z)]),
        (1, 0, 0, lambda x,y,z: [(x+1,y,z),(x+1,y+1,z),(x+1,y+1,z+1),(x+1,y,z+1)]),
        (0, -1, 0, lambda x,y,z: [(x,y,z),(x+1,y,z),(x+1,y,z+1),(x,y,z+1)]),
        (0, 1, 0, lambda x,y,z: [(x,y+1,z),(x,y+1,z+1),(x+1,y+1,z+1),(x+1,y+1,z)]),
        (0, 0, -1, lambda x,y,z: [(x,y,z),(x,y+1,z),(x+1,y+1,z),(x+1,y,z)]),
        (0, 0, 1, lambda x,y,z: [(x,y,z+1),(x+1,y,z+1),(x+1,y+1,z+1),(x,y+1,z+1)]),
    ]
    for y in range(h):
        for x in range(resolution):
            for z in range(resolution):
                if not occ[at(x, y, z)]:
                    continue
                for dx, dy, dz, corners in faces:
                    nx, ny, nz = x + dx, y + dy, z + dz
                    if 0 <= nx < resolution and 0 <= ny < h and 0 <= nz < resolution and occ[at(nx, ny, nz)]:
                        continue
                    base = len(vertices)
                    # X/Z span [-0.5,0.5]; Y maps image top-down to world up.
                    for vx, vy, vz in corners(x, h - y - 1, z):
                        vertices.append((vx / resolution - 0.5, vy / h, vz / resolution - 0.5))
                    indices.extend((base, base+1, base+2, base, base+2, base+3))
    return {"glb": _glb(vertices, indices), "scores": scores, "occupied_voxels": sum(occ)}
