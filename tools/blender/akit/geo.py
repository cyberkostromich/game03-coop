"""Procedural mesh primitives (pure numpy, no bpy).

Every primitive returns a Part: vertices, faces, per-vertex colors, plus the
bone it is skinned to and the material slot it renders with. Parts are built
in local space, painted, then transformed into place; build.py merges them
into one skinned mesh per asset.

Axes follow Blender: +Z up, characters face -Y, character's left is +X.
"""
import math
import numpy as np

from . import palette


def _rot_matrix(rx, ry, rz):
    """Euler XYZ in degrees -> 3x3 matrix (applied X, then Y, then Z)."""
    rx, ry, rz = (math.radians(a) for a in (rx, ry, rz))
    cx, sx, cy, sy, cz, sz = (math.cos(rx), math.sin(rx), math.cos(ry),
                              math.sin(ry), math.cos(rz), math.sin(rz))
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ my @ mx


class Part:
    def __init__(self, V, F, color=(1, 1, 1), bone=None, mat="body", smooth=True):
        self.V = np.asarray(V, dtype=float).reshape(-1, 3)
        self.F = [tuple(int(i) for i in f) for f in F]
        self.C = np.tile(palette.rgb(color), (len(self.V), 1))
        self.bone = bone
        self.weights = None  # optional {bone: per-vertex weight array}
        self.mat = mat
        self.smooth = smooth
        self.ao = True  # receives baked AO

    # -- construction helpers -------------------------------------------
    def copy(self):
        p = Part(self.V.copy(), list(self.F), bone=self.bone, mat=self.mat, smooth=self.smooth)
        p.C = self.C.copy()
        p.weights = None if self.weights is None else {k: v.copy() for k, v in self.weights.items()}
        p.ao = self.ao
        return p

    def tf(self, loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0):
        s = np.broadcast_to(np.asarray(scale, dtype=float), (3,))
        V = self.V * s
        if any(rot):
            V = V @ _rot_matrix(*rot).T
        self.V = V + np.asarray(loc, dtype=float)
        if np.prod(s) < 0:
            self.F = [tuple(reversed(f)) for f in self.F]
        return self

    def deform(self, fn):
        """fn(V) -> V, vectorised over an (n,3) array."""
        self.V = np.asarray(fn(self.V.copy()), dtype=float)
        return self

    def paint(self, fn):
        """fn(V, C) -> C. Colors are linear RGB floats."""
        self.C = np.asarray(fn(self.V, self.C.copy()), dtype=float)
        return self

    def color(self, c):
        self.C[:] = palette.rgb(c)
        return self

    def on(self, bone, mat=None):
        self.bone = bone
        if mat:
            self.mat = mat
        return self

    def flat(self):
        self.smooth = False
        return self

    def mirrored(self, bone_map=None):
        """Copy mirrored across X (left <-> right)."""
        p = self.copy()
        p.V[:, 0] *= -1
        p.F = [tuple(reversed(f)) for f in p.F]
        if self.bone and bone_map is not False:
            p.bone = mirror_name(self.bone)
        if p.weights:
            p.weights = {mirror_name(k): v for k, v in p.weights.items()}
        return p

    @property
    def bounds(self):
        return self.V.min(0), self.V.max(0)


def mirror_name(name):
    if name.endswith(".L"):
        return name[:-2] + ".R"
    if name.endswith(".R"):
        return name[:-2] + ".L"
    return name


def merge(parts, bone=None, mat=None):
    """Concatenate several parts into one (keeps per-part colors)."""
    V, F, C = [], [], []
    off = 0
    for p in parts:
        V.append(p.V)
        C.append(p.C)
        F.extend(tuple(i + off for i in f) for f in p.F)
        off += len(p.V)
    out = Part(np.vstack(V), F, bone=bone or parts[0].bone, mat=mat or parts[0].mat,
               smooth=parts[0].smooth)
    out.C = np.vstack(C)
    return out


# ---------------------------------------------------------------------------
# Box-grid based primitives (quad sphere, rounded box)
# ---------------------------------------------------------------------------

def _box_surface(xs, ys, zs):
    """Quad surface of an axis-aligned box sampled on the given 1D coords."""
    axes = [np.asarray(xs, float), np.asarray(ys, float), np.asarray(zs, float)]
    index = {}
    verts = []
    faces = []

    def vid(p):
        key = (round(p[0], 6), round(p[1], 6), round(p[2], 6))
        i = index.get(key)
        if i is None:
            i = len(verts)
            index[key] = i
            verts.append(p)
        return i

    for a in range(3):
        b, c = (a + 1) % 3, (a + 2) % 3
        for side in (0, -1):
            fixed = axes[a][side]
            ub, uc = axes[b], axes[c]
            grid = [[None] * len(uc) for _ in ub]
            for i, vb in enumerate(ub):
                for j, vc in enumerate(uc):
                    p = [0.0, 0.0, 0.0]
                    p[a], p[b], p[c] = fixed, vb, vc
                    grid[i][j] = vid(p)
            for i in range(len(ub) - 1):
                for j in range(len(uc) - 1):
                    f = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
                    # cyclic (a,b,c): e_b x e_c = e_a, so this order faces +a
                    faces.append(f if side == -1 else tuple(reversed(f)))
    return np.array(verts, float), faces


def qsphere(r=1.0, n=6, color=(1, 1, 1)):
    """Quad sphere (cube projected to sphere) - even, low-poly friendly."""
    t = np.tan(np.linspace(-1, 1, n + 1) * math.pi / 4)
    V, F = _box_surface(t, t, t)
    V = V / np.linalg.norm(V, axis=1, keepdims=True) * r
    return Part(V, F, color)


def ellipsoid(rx, ry, rz, n=6, color=(1, 1, 1)):
    return qsphere(1.0, n, color).tf(scale=(rx, ry, rz))


def _ramp(h, r, k, mid):
    """1D coords for one axis of a rounded box: k segments per round corner."""
    r = min(r, h * 0.999)
    a = [-h + r - r * math.cos(i / k * math.pi / 2) for i in range(k)]
    inner = np.linspace(-h + r, h - r, mid + 1).tolist()
    b = [-x for x in reversed(a)]
    return np.array(a + inner + b)


def rbox(sx, sy, sz, r=0.05, k=2, mid=1, color=(1, 1, 1)):
    """Rounded box with size (sx, sy, sz) and corner radius r."""
    h = np.array([sx, sy, sz]) / 2
    r = float(min(r, h.min() * 0.999))
    xs, ys, zs = (_ramp(h[i], r, k, mid) for i in range(3))
    V, F = _box_surface(xs, ys, zs)
    if r > 0:
        inner = np.clip(V, -(h - r), h - r)
        d = V - inner
        ln = np.linalg.norm(d, axis=1, keepdims=True)
        ln[ln == 0] = 1
        V = inner + d / ln * r
    return Part(V, F, color)


def box(sx, sy, sz, color=(1, 1, 1)):
    V, F = _box_surface([-sx / 2, sx / 2], [-sy / 2, sy / 2], [-sz / 2, sz / 2])
    return Part(V, F, color, smooth=False)


# ---------------------------------------------------------------------------
# Lathe / loft / tube
# ---------------------------------------------------------------------------

def lathe(profile, segs=12, cap_bottom=True, cap_top=True, phase=0.0, color=(1, 1, 1)):
    """Revolve [(radius, z), ...] (bottom to top) around Z.

    radius 0 at an end collapses to a pole vertex.
    """
    V, F, rings = [], [], []
    for r, z in profile:
        if r <= 1e-9:
            rings.append([len(V)])
            V.append((0.0, 0.0, z))
        else:
            ring = []
            for j in range(segs):
                a = 2 * math.pi * j / segs + phase
                ring.append(len(V))
                V.append((r * math.cos(a), r * math.sin(a), z))
            rings.append(ring)
    for lo, hi in zip(rings[:-1], rings[1:]):
        if len(lo) == 1 and len(hi) == 1:
            continue
        if len(lo) == 1:
            for j in range(segs):
                F.append((lo[0], hi[j], hi[(j + 1) % segs]))
        elif len(hi) == 1:
            for j in range(segs):
                F.append((lo[j], lo[(j + 1) % segs], hi[0]))
        else:
            for j in range(segs):
                k = (j + 1) % segs
                F.append((lo[j], lo[k], hi[k], hi[j]))
    if cap_bottom and len(rings[0]) > 1:
        F.append(tuple(reversed(rings[0])))
    if cap_top and len(rings[-1]) > 1:
        F.append(tuple(rings[-1]))
    return Part(V, F, color)


def cyl(r, h, segs=12, r_top=None, color=(1, 1, 1), z0=0.0, caps=True):
    rt = r if r_top is None else r_top
    return lathe([(r, z0), (rt, z0 + h)], segs, caps, caps, color=color)


def cone(r, h, segs=12, color=(1, 1, 1)):
    return lathe([(r, 0), (0, h)], segs, color=color)


def capsule(r, h, segs=12, rings=3, color=(1, 1, 1)):
    """Capsule along Z from 0 to h (h >= 2r)."""
    prof = []
    for i in range(rings + 1):
        a = -math.pi / 2 + math.pi / 2 * i / rings
        prof.append((r * math.cos(a), r + r * math.sin(a)))
    for i in range(rings + 1):
        a = math.pi / 2 * i / rings
        prof.append((r * math.cos(a), h - r + r * math.sin(a)))
    prof[0] = (0, 0)
    prof[-1] = (0, h)
    return lathe(prof, segs, color=color)


def loft(sections, cap_start=True, cap_end=True, closed=True, color=(1, 1, 1)):
    """Skin a list of (m,3) cross-sections (same m) into a surface.

    Sections should be listed along the path; each section's points wind
    counter-clockwise when looking back along the path (from the end).
    Winding is auto-corrected so faces point away from the section centroids.
    """
    secs = [np.asarray(s, float) for s in sections]
    m = len(secs[0])
    V = np.vstack(secs)
    F = []
    n_open = m if closed else m - 1
    for i in range(len(secs) - 1):
        a, b = i * m, (i + 1) * m
        for j in range(n_open):
            k = (j + 1) % m
            F.append((a + j, a + k, b + k, b + j))
    # orientation check against section centroids
    cents = np.array([s.mean(0) for s in secs])
    score = 0.0
    for i in range(len(secs) - 1):
        a = i * m
        p0, p1, p2 = V[a], V[a + 1], V[a + m]
        nrm = np.cross(p1 - p0, p2 - p0)
        score += np.dot(nrm, (p0 + p1 + p2) / 3 - (cents[i] + cents[i + 1]) / 2)
    if score < 0:
        F = [tuple(reversed(f)) for f in F]
    if closed:
        flip = score < 0
        if cap_start:
            f = tuple(range(m))
            F.append(f if flip else tuple(reversed(f)))
        if cap_end:
            base = (len(secs) - 1) * m
            f = tuple(range(base, base + m))
            F.append(tuple(reversed(f)) if flip else f)
    return Part(V, F, color)


def _frames(path):
    """Parallel-transport frames along a polyline."""
    P = np.asarray(path, float)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    ref = np.array([0, 0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0, 0])
    N = [np.cross(ref, T[0])]
    N[0] /= np.linalg.norm(N[0])
    for i in range(1, len(P)):
        n = N[-1] - np.dot(N[-1], T[i]) * T[i]
        ln = np.linalg.norm(n)
        N.append(n / ln if ln > 1e-9 else N[-1])
    N = np.array(N)
    B = np.cross(T, N)
    return P, T, N, B


def tube(path, radii, segs=8, cap_start=True, cap_end=True, color=(1, 1, 1),
         squash=1.0, twist=0.0):
    """Tube along a 3D polyline with per-point radius (scalar or list).

    squash scales the binormal axis (oval cross sections).
    """
    P, T, N, B = _frames(path)
    radii = np.broadcast_to(np.asarray(radii, float), (len(P),))
    secs = []
    for i in range(len(P)):
        ring = []
        for j in range(segs):
            a = 2 * math.pi * j / segs + twist
            ring.append(P[i] + radii[i] * (math.cos(a) * N[i] + squash * math.sin(a) * B[i]))
        secs.append(ring)
    p = loft(secs, cap_start, cap_end, color=color)
    return p


def bezier(p0, p1, p2, p3=None, n=8):
    """Sample a quadratic (3 pts) or cubic (4 pts) bezier."""
    p0, p1, p2 = (np.asarray(p, float) for p in (p0, p1, p2))
    t = np.linspace(0, 1, n)[:, None]
    if p3 is None:
        return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2
    p3 = np.asarray(p3, float)
    return ((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1
            + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3)


def extrude(poly, depth, color=(1, 1, 1), bevel=0.0):
    """Extrude a 2D polygon (x, z points, CCW seen from -Y) along Y.

    The result is centred on y=0: front face at -depth/2 (towards the
    character's front), back at +depth/2. bevel>0 shrinks the caps toward
    the centroid, giving a chamfered rim.
    """
    poly = np.asarray(poly, float)
    m = len(poly)
    c = poly.mean(0)
    rings = []
    if bevel > 0:
        inner = c + (poly - c) * (1 - bevel)
        layout = [(inner, -depth / 2), (poly, -depth / 2 * 0.4), (poly, depth / 2 * 0.4),
                  (inner, depth / 2)]
    else:
        layout = [(poly, -depth / 2), (poly, depth / 2)]
    for pts, y in layout:
        rings.append(np.column_stack([pts[:, 0], np.full(m, y), pts[:, 1]]))
    return loft(rings, color=color)


def blade(length, width, thick, tip=0.25, color=(1, 1, 1), fuller=True, n=6):
    """Sword blade along +Z with a diamond cross-section and pointed tip."""
    secs = []
    for i in range(n + 1):
        t = i / n
        z = t * length
        w = width / 2 * (1 - 0.15 * t)
        if t > 1 - tip:
            w *= max(0.0, (1 - t) / tip) ** 0.8
        th = thick / 2 * (0.6 if fuller else 1.0) * (1 if t < 1 else 0.2)
        w = max(w, 0.002)
        secs.append([(w, 0, z), (0, -th, z), (-w, 0, z), (0, th, z)])
    return loft(secs, color=color).flat()


def disc(r, depth, segs=16, color=(1, 1, 1), bevel=0.15):
    """Round shield-like disc facing -Y, centred at origin."""
    poly = [(r * math.cos(2 * math.pi * i / segs), r * math.sin(2 * math.pi * i / segs))
            for i in range(segs)]
    return extrude(poly, depth, color, bevel=bevel)


def heater_shield(w, h, depth, color=(1, 1, 1), n=10):
    """Classic heater shield silhouette (flat top, pointed bottom)."""
    pts = []
    top = h * 0.5
    for i in range(n + 1):  # right side curve, top->bottom
        t = i / n
        x = w / 2 * math.cos(t * math.pi / 2) ** 0.7
        z = top - t * h
        pts.append((x, z))
    pts = pts[:-1] + [(0, -h * 0.5)] + [(-x, z) for x, z in reversed(pts[:-1])]
    return extrude(pts, depth, color, bevel=0.12)


def ngon_ring(r, segs, z=0.0, phase=0.0):
    return [(r * math.cos(2 * math.pi * i / segs + phase),
             r * math.sin(2 * math.pi * i / segs + phase), z) for i in range(segs)]


# ---------------------------------------------------------------------------
# Painting helpers (return fn(V, C) -> C)
# ---------------------------------------------------------------------------

def grad_z(c_bottom, c_top, z0, z1):
    cb, ct = palette.rgb(c_bottom), palette.rgb(c_top)

    def fn(V, C):
        t = np.clip((V[:, 2] - z0) / max(z1 - z0, 1e-6), 0, 1)[:, None]
        return cb * (1 - t) + ct * t
    return fn


def patch(center, radius, c, soft=0.3, axis_scale=(1, 1, 1)):
    """Blend color c within an ellipsoidal region (smooth falloff)."""
    col = palette.rgb(c)
    cen = np.asarray(center, float)
    sc = np.asarray(axis_scale, float)

    def fn(V, C):
        d = np.linalg.norm((V - cen) / sc, axis=1) / radius
        w = np.clip((1 - d) / max(soft, 1e-3), 0, 1)[:, None]
        w = w * w * (3 - 2 * w)
        return C * (1 - w) + col * w
    return fn


def stripes(c, axis=0, freq=20.0, width=0.35, phase=0.0, region=None):
    """Periodic stripes along an axis (tabby fur, heraldic bands)."""
    col = palette.rgb(c)

    def fn(V, C):
        s = 0.5 + 0.5 * np.sin(V[:, axis] * freq + phase)
        w = np.clip((s - (1 - width)) / 0.08, 0, 1)
        if region is not None:
            w = w * region(V)
        w = w[:, None]
        return C * (1 - w) + col * w
    return fn


def where(mask_fn, c):
    col = palette.rgb(c)

    def fn(V, C):
        m = mask_fn(V)[:, None].astype(float)
        return C * (1 - m) + col * m
    return fn


def shade(top=1.06, bottom=0.82, z0=0.0, z1=1.0):
    """Hand-painted style vertical value gradient (multiplies colors)."""
    def fn(V, C):
        t = np.clip((V[:, 2] - z0) / max(z1 - z0, 1e-6), 0, 1)[:, None]
        return C * (bottom * (1 - t) + top * t)
    return fn
