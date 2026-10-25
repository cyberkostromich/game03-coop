"""GLB -> glTF JSON with geometry as a base64 data URI and textures as
separate .webp files. Used for hosts that only serve text/image types."""
import base64
import json
import os
import struct
import sys


def convert(src, dst_json, img_prefix):
    b = open(src, "rb").read()
    assert b[:4] == b"glTF"
    n = struct.unpack("<I", b[12:16])[0]
    g = json.loads(b[20:20 + n])
    off = 20 + n
    blen = struct.unpack("<I", b[off:off + 4])[0]
    binc = b[off + 8: off + 8 + blen]
    views = g["bufferViews"]
    img_views = set()
    out_dir = os.path.dirname(dst_json)
    for i, im in enumerate(g.get("images", [])):
        if "bufferView" not in im:
            continue
        v = views[im["bufferView"]]
        data = binc[v.get("byteOffset", 0): v.get("byteOffset", 0) + v["byteLength"]]
        ext = {"image/webp": "webp", "image/png": "png", "image/jpeg": "jpg"}[im["mimeType"]]
        name = f"{img_prefix}_{i}.{ext}"
        open(os.path.join(out_dir, name), "wb").write(data)
        img_views.add(im["bufferView"])
        del im["bufferView"]
        im.pop("mimeType", None)
        im["uri"] = name
    # repack the remaining views into a fresh buffer
    remap, new_views, chunks, pos = {}, [], [], 0
    for i, v in enumerate(views):
        if i in img_views:
            continue
        data = binc[v.get("byteOffset", 0): v.get("byteOffset", 0) + v["byteLength"]]
        pad = (-pos) % 4
        chunks.append(b"\0" * pad); pos += pad
        nv = dict(v); nv["byteOffset"] = pos; nv["buffer"] = 0
        chunks.append(data); pos += len(data)
        remap[i] = len(new_views); new_views.append(nv)
    g["bufferViews"] = new_views
    for a in g.get("accessors", []):
        if "bufferView" in a:
            a["bufferView"] = remap[a["bufferView"]]
        sp = a.get("sparse")
        if sp:
            sp["indices"]["bufferView"] = remap[sp["indices"]["bufferView"]]
            sp["values"]["bufferView"] = remap[sp["values"]["bufferView"]]
    buf = b"".join(chunks)
    g["buffers"] = [{"byteLength": len(buf), "uri": "data:application/octet-stream;base64," + base64.b64encode(buf).decode()}]
    json.dump(g, open(dst_json, "w"), separators=(",", ":"))


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
