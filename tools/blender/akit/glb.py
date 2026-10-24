"""Small GLB post-processing helpers (pure python, no bpy)."""
import json
import struct


def read(path):
    with open(path, "rb") as fh:
        data = fh.read()
    magic, version, length = struct.unpack_from("<III", data, 0)
    assert magic == 0x46546C67, "not a GLB"
    off = 12
    chunks = []
    while off < length:
        clen, ctype = struct.unpack_from("<II", data, off)
        chunks.append([ctype, data[off + 8: off + 8 + clen]])
        off += 8 + clen
    doc = json.loads(chunks[0][1].decode("utf8"))
    return doc, chunks


def write(path, doc, chunks):
    js = json.dumps(doc, separators=(",", ":")).encode("utf8")
    js += b" " * ((4 - len(js) % 4) % 4)
    chunks[0][1] = js
    body = b""
    for ctype, cdata in chunks:
        pad = (4 - len(cdata) % 4) % 4
        cdata = cdata + (b"\0" * pad if ctype != 0x4E4F534A else b" " * pad)
        body += struct.pack("<II", len(cdata), ctype) + cdata
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)


def patch_materials(path, factors):
    """factors: {material_name: [r, g, b] linear} -> baseColorFactor."""
    doc, chunks = read(path)
    for m in doc.get("materials", []):
        if m.get("name") in factors:
            r, g, b = factors[m["name"]][:3]
            m.setdefault("pbrMetallicRoughness", {})["baseColorFactor"] = [r, g, b, 1.0]
            m.setdefault("extras", {})["teamColor"] = True
    write(path, doc, chunks)
