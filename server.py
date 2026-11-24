"""Local HTTP bridge for the standalone 3DDesigner outline-to-mesh tool."""
import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from mesh_core import GeometryError, export_glb, export_obj
from visual_hull import build_visual_hull
ROOT = Path(__file__).resolve().parent
MAX_BODY = 512 * 1024
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
    def do_POST(self):
        route = urlsplit(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        if route.path == "/api/visual-hull":
            self.handle_visual_hull(length)
            return
        if route.path != "/api/mesh":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            self.send_error(413, "Invalid mesh request size")
            return
        try:
            data = json.loads(self.rfile.read(length))
            points, depth = data.get("points"), data.get("depth")
            if not isinstance(points, list):
                raise ValueError("points must be an array")
            if not isinstance(depth, (int, float)) or isinstance(depth, bool):
                raise ValueError("depth must be a positive number")
            fmt = parse_qs(route.query).get("format", ["glb"])[0].lower()
            if fmt == "glb":
                payload, mime, filename = export_glb(points, float(depth)), "model/gltf-binary", "outline-mesh.glb"
            elif fmt == "obj":
                payload, mime, filename = export_obj(points, float(depth)).encode(), "model/obj", "outline-mesh.obj"
            else:
                raise ValueError("format must be glb or obj")
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(payload)
        except (GeometryError, ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            payload = json.dumps({"error": str(e)}).encode()
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def handle_visual_hull(self, length):
        if length <= 0 or length > MAX_BODY:
            self.send_error(413, "Invalid visual hull request size")
            return
        try:
            data = json.loads(self.rfile.read(length))
            result = build_visual_hull(data.get("views"), data.get("resolution", 32))
            payload = result["glb"]
            self.send_response(200)
            self.send_header("Content-Type", "model/gltf-binary")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Content-Disposition", 'attachment; filename="four-view-visual-hull.glb"')
            self.send_header("X-Silhouette-Scores", json.dumps(result["scores"], separators=(",", ":")))
            self.end_headers()
            self.wfile.write(payload)
        except (GeometryError, ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            payload = json.dumps({"error": str(e)}).encode()
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

if __name__ == "__main__":
    print("3DDesigner: http://127.0.0.1:8766/")
    ThreadingHTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
