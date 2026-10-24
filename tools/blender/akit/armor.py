"""Hard-surface armour in the Blizzard idiom.

A plate is a parametric surface patch P(u, v) given thickness, with a thick
rounded *trim* (gold/bronze/silver) running along its edges and optional
rivets just inside the trim. Tiered pauldrons, breastplates, vambraces,
greaves, tassets and helmets are all built from that one primitive, which
is what gives Reforged armour its look: dark plate, bright trimmed edges,
team colour framed inside.
"""
import math

import numpy as np

from .geo import tagged
from . import geo, palette
from .beast import torso_r
from .rig import blend_weights, chain_weights


def _normals(P, ref):
    """Finite-difference normals of a (nu, nv, 3) grid, oriented away from ref."""
    du = np.gradient(P, axis=0)
    dv = np.gradient(P, axis=1)
    N = np.cross(du, dv)
    ln = np.linalg.norm(N, axis=2, keepdims=True)
    ln[ln < 1e-12] = 1
    N /= ln
    ref = np.asarray(ref, float)
    if ref.ndim == 1:
        out = P - ref
    else:
        out = P - ref
    if np.sum(N * out) < 0:
        N = -N
    return N


def plate(P, thick, color, mat="metal", ref=(0, 0, 0), trim=None, trim_r=None,
          edges=("u0", "u1", "v0", "v1"), trim_mat="gold", rivets=None, rivet_step=0.045,
          wrap_u=False, N=None, smooth=True):
    """Thick plate from a grid of surface points P[(nu, nv, 3)].

    Returns a list of Parts (plate + trims + rivets), not yet skinned.
    """
    P = np.asarray(P, float)
    nu, nv = P.shape[:2]
    if N is None:
        N = _normals(P, ref)
    top = P + N * thick
    V = np.vstack([top.reshape(-1, 3), P.reshape(-1, 3)])
    off = nu * nv

    def idx(i, j, layer=0):
        return layer * off + i * nv + j

    F = []
    iu = range(nu if wrap_u else nu - 1)
    for i in iu:
        i2 = (i + 1) % nu
        for j in range(nv - 1):
            F.append((idx(i, j), idx(i2, j), idx(i2, j + 1), idx(i, j + 1)))
            F.append((idx(i, j, 1), idx(i, j + 1, 1), idx(i2, j + 1, 1), idx(i2, j, 1)))
    # rim strips
    def strip(path):
        for a, b in zip(path[:-1], path[1:]):
            F.append((idx(*a), idx(*b), idx(*b, 1), idx(*a, 1)))
    strip([(i, 0) for i in range(nu)] + ([(0, 0)] if wrap_u else []))
    strip([(i, nv - 1) for i in range(nu)][::-1] + ([(nu - 1, nv - 1)][:0]))
    if not wrap_u:
        strip([(0, j) for j in range(nv)][::-1])
        strip([(nu - 1, j) for j in range(nv)])
    body = geo.Part(V, F, color, mat=mat, smooth=smooth)
    # fix rim winding: orient strip normals outward from patch centre
    out = [body]
    mid = P + N * thick * 0.5
    trim_r = trim_r or thick * 0.95
    if trim:
        lines, nrms = [], []
        if "v0" in edges:
            lines.append(mid[:, 0])
            nrms.append(N[:, 0])
        if "v1" in edges:
            lines.append(mid[:, -1])
            nrms.append(N[:, -1])
        if not wrap_u:
            if "u0" in edges:
                lines.append(mid[0, :])
                nrms.append(N[0, :])
            if "u1" in edges:
                lines.append(mid[-1, :])
                nrms.append(N[-1, :])
        for ln, nn in zip(lines, nrms):
            if wrap_u:
                ln = np.vstack([ln, ln[:1]])
                nn = np.vstack([nn, nn[:1]])
            t = band_trim(ln, nn, trim_r * 2.7, trim_r * 1.5, trim, closed=wrap_u)
            t.mat = trim_mat
            out.append(t)
        if rivets:
            for ln_i, ln in enumerate(lines):
                inset = _inset_line(P, N, thick, ln_i, edges, wrap_u, trim_r)
                if inset is None:
                    continue
                n = max(2, int(_length(inset) / rivet_step))
                for p, nn in zip(*_sample_with_normals(inset, P, N, n)):
                    out.append(stud(p + nn * thick, nn, trim_r * 0.8, rivets))
    return out


def band_trim(pts, nrms, width, height, color, closed=False, step=0.034):
    """Flat chamfered band following a surface edge (Blizzard-style trim)."""
    pts = np.asarray(pts, float)
    nrms = np.asarray(nrms, float)
    n = max(4, int(_length(pts) / step))
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    t = np.linspace(0, d[-1], n)
    P = np.column_stack([np.interp(t, d, pts[:, k]) for k in range(3)])
    Nn = np.column_stack([np.interp(t, d, nrms[:, k]) for k in range(3)])
    T = np.gradient(P, axis=0)
    if closed:
        T[0] = T[-1] = P[1] - P[-2]
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    Nn = Nn - (Nn * T).sum(1, keepdims=True) * T
    Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
    W = np.cross(T, Nn)
    w, h = width / 2, height / 2
    c = min(w, h) * 0.45
    prof = [(w, -h * 0.1), (w * 0.55, h), (-w * 0.55, h), (-w, -h * 0.1), (0.0, -h)]
    secs = []
    for i in range(n):
        base = P[i] + Nn[i] * h * 0.35
        secs.append([base + W[i] * a + Nn[i] * b for a, b in prof])
    part = geo.loft(secs, cap_start=not closed, cap_end=not closed, color=color)
    part.smooth = False
    return part


def _length(pts):
    return float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))


def _resample(pts, n):
    pts = np.asarray(pts, float)
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    if d[-1] < 1e-9:
        return pts
    t = np.linspace(0, d[-1], n)
    return np.column_stack([np.interp(t, d, pts[:, k]) for k in range(3)])


def _inset_line(P, N, thick, which, edges, wrap_u, trim_r):
    nu, nv = P.shape[:2]
    order = []
    if "v0" in edges:
        order.append(("v", 1 if nv > 2 else 0))
    if "v1" in edges:
        order.append(("v", nv - 2 if nv > 2 else nv - 1))
    if not wrap_u:
        if "u0" in edges:
            order.append(("u", 1))
        if "u1" in edges:
            order.append(("u", nu - 2))
    if which >= len(order):
        return None
    kind, k = order[which]
    return P[:, k] if kind == "v" else P[k, :]


def _sample_with_normals(line, P, N, n):
    line = _resample(line, n + 2)[1:-1]
    flatP = P.reshape(-1, 3)
    flatN = N.reshape(-1, 3)
    out_n = []
    for p in line:
        i = np.argmin(np.linalg.norm(flatP - p, axis=1))
        out_n.append(flatN[i])
    return line, out_n


def stud(p, n, r, color):
    """Low-poly dome rivet sitting on a surface."""
    d = geo.lathe([(r, 0), (r * 0.85, r * 0.45), (r * 0.45, r * 0.8), (0, r * 0.9)], 6,
                  cap_bottom=False, color=color)
    n = np.asarray(n, float) / max(np.linalg.norm(n), 1e-9)
    z = np.array([0, 0, 1.0])
    v = np.cross(z, n)
    s = np.linalg.norm(v)
    c = float(np.dot(z, n))
    if s < 1e-9:
        R = np.eye(3) if c > 0 else np.diag([1, -1, -1])
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        R = np.eye(3) + vx + vx @ vx * ((1 - c) / s ** 2)
    d.V = d.V @ R.T + p
    d.mat = "metal"
    d.ao = True
    return d

# Torso layering: (inflate, add) per layer, innermost first. Every garment or
# plate that wraps the torso uses one of these so shells nest without crossing.
LAYERS = {"cloth": (1.02, 0.004), "brig": (1.04, 0.01), "plate": (1.06, 0.028),
          "belt": (1.1, 0.046), "over": (1.14, 0.075)}


def layer_r(b, z, layer):
    """(rx, ry) of a torso layer at height z. Around the hips every layer also
    clears the thighs, so skirts/faulds/belts nest and legs leave through the hem."""
    rx, ry = torso_r(b, max(z, b.hip_h + 0.01))
    k, a = LAYERS[layer]
    rx, ry = rx * k + a, ry * k + a
    if z < b.hip_h + 0.06:
        cx = b.hip_w + b.leg_r * 1.3 + 0.012
        cy = b.leg_r * 1.35 + 0.035
        rx, ry = max(rx, cx + a), max(ry, cy + a)
    return rx, ry


def gorget_r(b, z):
    """Outer radius of the gorget at height z (None outside its span)."""
    zb, zt = b.neck_z - 0.035, b.neck_z + 0.04
    if not (zb - 0.03 <= z <= zt + 0.07):
        return None
    rxb, ryb = layer_r(b, zb, "plate")
    neck_r = b.torso_w * 0.2 + 0.03
    rxb, ryb = max(neck_r + 0.03, rxb * 0.72) + 0.035, max(neck_r + 0.03, ryb * 0.95) + 0.035
    t = min(max((z - zb) / (zt - zb), 0.0), 1.0)
    rx = rxb + (max(neck_r, rxb * 0.62) - rxb) * t ** 0.8
    ry = ryb + (max(neck_r, ryb * 0.62) - ryb) * t ** 0.8
    return rx, ry


def push_outside(parts, b, layer="over", margin=0.012, z_range=None, gorget=True):
    """Resolve collisions: push vertices that sink into a torso layer (and the gorget) back out."""
    z0, z1 = z_range or (b.hip_h - 0.1, b.neck_z + 0.12)
    for p in parts:
        V = p.V
        for i in range(len(V)):
            x, y, z = V[i]
            if not (z0 <= z <= z1):
                continue
            rx, ry = layer_r(b, min(z, b.neck_z), layer)
            if gorget:
                g = gorget_r(b, z)
                if g is not None:
                    rx, ry = max(rx, g[0]), max(ry, g[1])
            e = math.sqrt((x / (rx + margin)) ** 2 + (y / (ry + margin)) ** 2)
            if 1e-6 < e < 1.0:
                V[i, 0] /= e
                V[i, 1] /= e
    return parts


def thigh_follow(parts, b, amount=0.5):
    """Cloth/lames below the hips: each side follows its thigh a little, more toward the hem."""
    for p in parts:
        V = p.V
        side = np.clip(V[:, 0] / (b.hip_w * 1.5), -1, 1)
        low = np.clip((b.hip_h + 0.02 - V[:, 2]) / 0.12, 0, 1)
        wl = amount * low * np.clip(side, 0, 1)
        wr = amount * low * np.clip(-side, 0, 1)
        p.bone = None
        p.weights = {"hips": 1 - wl - wr, "thigh.L": wl, "thigh.R": wr}
    return parts


def skin(parts, bone=None, blend=None, chain=None):
    for p in parts:
        if chain:
            chain_weights(p, chain[0], chain[1])
        elif blend:
            blend_weights(p, *blend)
        else:
            p.bone = bone
            p.weights = None
    return parts


# ---------------------------------------------------------------------------
# Surfaces
# ---------------------------------------------------------------------------

def torso_surface(b, u0, u1, z0, z1, nu=12, nv=8, inflate=1.12, add=0.012, flare=0.0,
                  front_push=0.0, layer=None):
    """Grid on the torso: u = angle (0 = front, + toward the left side)."""
    us = np.linspace(u0, u1, nu)
    zs = np.linspace(z0, z1, nv)
    P = np.zeros((nu, nv, 3))
    for j, z in enumerate(zs):
        zz = max(z, b.hip_h + 0.01)
        if layer:
            lrx, lry = layer_r(b, z, layer)
        else:
            rx, ry = torso_r(b, zz)
            lrx, lry = rx * inflate + add, ry * inflate + add
        k = 1 + flare * max(0.0, (b.hip_h + 0.01 - z)) / 0.1
        for i, u in enumerate(us):
            x = math.sin(u) * lrx * k
            y = -math.cos(u) * lry * k
            if y < 0:
                y -= front_push * math.cos(u) ** 2
            P[i, j] = (x, y, z)
    return P


def torso_line(b, uz, inflate=1.1, add=0.02, front_push=0.0, n=16):
    """Points + outward normals on the torso surface along a (u, z) polyline."""
    uz = np.asarray(uz, float)
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(uz, axis=0), axis=1))])
    t = np.linspace(0, d[-1], n)
    us = np.interp(t, d, uz[:, 0])
    zs = np.interp(t, d, uz[:, 1])
    pts, nrms = [], []
    for u, z in zip(us, zs):
        rx, ry = torso_r(b, max(z, b.hip_h + 0.01))
        x = math.sin(u) * (rx * inflate + add)
        y = -math.cos(u) * (ry * inflate + add)
        if y < 0:
            y -= front_push * math.cos(u) ** 2
        pts.append((x, y, z))
        nn = np.array([math.sin(u) * ry, -math.cos(u) * rx, 0.0])
        nrms.append(nn / np.linalg.norm(nn))
    return np.array(pts), np.array(nrms)


def ellipsoid_surface(c, r, u0, u1, v0, v1, nu=16, nv=8, rim=None):
    """Grid on an ellipsoid: u azimuth (0 = front, -Y), v polar from top (0) down."""
    c = np.asarray(c, float)
    us = np.linspace(u0, u1, nu)
    P = np.zeros((nu, nv, 3))
    for i, u in enumerate(us):
        vmax = v1 if rim is None else rim(u)
        for j, t in enumerate(np.linspace(0, 1, nv)):
            v = v0 + (vmax - v0) * t
            x = math.sin(v) * math.sin(u) * r[0]
            y = -math.sin(v) * math.cos(u) * r[1]
            z = math.cos(v) * r[2]
            P[i, j] = c + (x, y, z)
    return P


def limb_surface(a, b_, r0, r1, nu=12, nv=5, bulge=0.0, u0=-math.pi, u1=math.pi):
    a, b_ = np.asarray(a, float), np.asarray(b_, float)
    d = b_ - a
    L = np.linalg.norm(d)
    d /= L
    ref = np.array([0, -1.0, 0]) if abs(d[1]) < 0.9 else np.array([1.0, 0, 0])
    x = np.cross(ref, d)
    x /= np.linalg.norm(x)
    y = np.cross(d, x)
    P = np.zeros((nu, nv, 3))
    for i, u in enumerate(np.linspace(u0, u1, nu)):
        for j, t in enumerate(np.linspace(0, 1, nv)):
            r = r0 + (r1 - r0) * t + bulge * math.sin(math.pi * t)
            P[i, j] = a + d * L * t + (x * math.cos(u) + y * math.sin(u)) * r
    return P


def cap_surface(c, axis, R, polar, nu=16, nv=6, squash=(1, 1), flare=0.0, phase=0.0, square=2.0):
    """Spherical cap around 'axis' (pauldron lames). Rim flares outward."""
    c = np.asarray(c, float)
    ax = np.asarray(axis, float)
    ax /= np.linalg.norm(ax)
    ref = np.array([0, -1.0, 0]) if abs(ax[1]) < 0.9 else np.array([1.0, 0, 0])
    e1 = np.cross(ref, ax)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(ax, e1)
    P = np.zeros((nu, nv, 3))
    for i, u in enumerate(np.linspace(-math.pi, math.pi, nu)):
        sq = 1.0 / (abs(math.cos(u + phase)) ** square + abs(math.sin(u + phase)) ** square) ** (1 / square)
        for j, t in enumerate(np.linspace(0, 1, nv)):
            v = polar * t
            rr = R * (1 + flare * max(0.0, t - 0.6) / 0.4) * (1 + (sq - 1) * t)
            P[i, j] = c + ax * math.cos(v) * R + (e1 * math.cos(u + phase) * squash[0]
                                                  + e2 * math.sin(u + phase) * squash[1]) * math.sin(v) * rr
    return P


# ---------------------------------------------------------------------------
# Armour pieces
# ---------------------------------------------------------------------------

@tagged("pauldron", 1)
def pauldron(b, side, metal, trim, size=1.0, tiers=3, team=None, spikes=0, rivet=None, mat="metal"):
    """Tiered Blizzard pauldron: big upturned dome + lames below."""
    j = b.joints()
    sign = 1 if side == "L" else -1
    sh = j[f"shoulder.{side}"]
    bone = f"upper_arm.{side}"
    out = []
    L_up = np.linalg.norm(j[f"elbow.{side}"] - sh)
    # big pauldrons grow wider front-to-back, never down onto the elbow
    size_v = min(size, (0.42 * L_up) / (0.1 * (1 + 0.2 * (tiers - 1))))
    widen = max(1.0, size / max(size_v, 1e-6)) ** 0.5
    size = size_v
    tiers = min(tiers, 3)
    R = 0.1 * size
    axis = np.array([sign * 0.75, 0.0, 1.0])
    c = sh + np.array([sign * 0.02 * size, 0.0, -0.025 * size])
    for k in range(tiers):
        rk = R * (1 - 0.16 * k)
        ck = c + np.array([sign * 0.024 * k * size, 0, -0.03 * k * size])
        ax = axis + np.array([sign * 0.35 * k, 0, -0.3 * k])
        P = cap_surface(ck, ax, rk, math.radians(80 if k == 0 else 62), 16, 5,
                        squash=(1.0, 1.2 * widen), flare=0.28 if k == 0 else 0.14, square=3.2, phase=math.pi / 4)
        col = metal
        ps = plate(P, 0.012 * size, col, mat=mat, ref=ck, trim=trim, trim_r=0.011 * size,
                   edges=("v1",), wrap_u=True, rivets=rivet if k == 0 else None,
                   rivet_step=0.04 * size)
        out += ps
    # raised ridge over the top dome, front to back
    axn = axis / np.linalg.norm(axis)
    e_front = np.array([0, -1.0, 0])
    e_front -= axn * np.dot(e_front, axn)
    e_front /= np.linalg.norm(e_front)
    ridge_pts, ridge_n = [], []
    for a in np.linspace(-1.15, 1.15, 14):
        nrm = axn * math.cos(a) + e_front * math.sin(a)
        ridge_pts.append(c + nrm * (R * 1.0 + 0.012 * size))
        ridge_n.append(nrm)
    rd = band_trim(np.array(ridge_pts), np.array(ridge_n), 0.022 * size, 0.018 * size, trim)
    rd.mat = "gold"
    out.append(rd)
    if team is not None:   # enamel inset on the top dome
        P = cap_surface(c + axis / np.linalg.norm(axis) * 0.004, axis, R * 1.012, math.radians(46),
                        16, 3, squash=(1.0, 1.2 * widen), square=3.2, phase=math.pi / 4)
        ps = plate(P, 0.008 * size, team, mat="team", ref=c, trim=trim, trim_r=0.008 * size,
                   edges=("v1",), wrap_u=True)
        out += ps
    for s_i in range(spikes):
        ang = (s_i - (spikes - 1) / 2) * 0.55
        d = axis / np.linalg.norm(axis)
        base = c + d * R * 0.9 + np.array([0, math.sin(ang) * R * 0.8, 0])
        sp = geo.cone(0.022 * size, 0.09 * size, 6, palette.mul(metal, 1.2))
        sp.tf(rot=(0, sign * 35, 0)).tf(base)
        sp.mat = "metal"
        out.append(sp)
    # sit on the shoulder without cutting into the torso layers or the gorget
    push_outside(out, b, "over", margin=0.04)
    # rigid blend between chest and arm: the pauldron rides the shoulder and does not
    # swing fully with the arm (keeps it out of the helmet when the arm is raised)
    for p in out:
        p.bone = None
        p.weights = {"chest": np.full(len(p.V), 0.9), bone: np.full(len(p.V), 0.1)}
    return out


@tagged("breastplate")
def breastplate(b, metal, trim, rivet=None, z0=None, z1=None, width=1.05, team_panel=None, mat="metal"):
    z0 = b.hip_h + 0.05 if z0 is None else z0
    z1 = b.neck_z - 0.075 if z1 is None else min(z1, b.neck_z - 0.075)
    k, a = LAYERS["plate"]
    P = torso_surface(b, -width, width, z0, z1, 14, 8, inflate=k, add=a, front_push=0.012)
    out = plate(P, 0.014, metal, mat=mat, ref=(0, 0, (z0 + z1) / 2), trim=trim, trim_r=0.012, rivets=rivet,
                rivet_step=0.05)
    zc = z0 + (z1 - z0) * 0.62
    for line in ([(-0.8, z1 - 0.045), (0.0, zc - 0.02), (0.8, z1 - 0.045)],
                 [(-0.85, z0 + (z1 - z0) * 0.3), (0.0, z0 + (z1 - z0) * 0.22), (0.85, z0 + (z1 - z0) * 0.3)]):
        pts, nrms = torso_line(b, line, inflate=k, add=a + 0.014, front_push=0.012)
        bt = band_trim(pts, nrms, 0.02, 0.012, trim)
        bt.mat = "gold"
        out.append(bt)
    if team_panel:
        Q = torso_surface(b, -0.42, 0.42, z0 + 0.03, z1 - 0.05, 8, 6, inflate=k, add=a + 0.016,
                          front_push=0.014)
        out += plate(Q, 0.006, team_panel, mat="team", ref=(0, 0, (z0 + z1) / 2), trim=trim,
                     trim_r=0.008)
    blend = ("hips", "chest", b.hip_h + 0.02, b.hip_h + b.torso_h * 0.6)
    return skin(out, blend=blend)


@tagged("backplate")
def backplate(b, metal, trim, mat="metal"):
    z0, z1 = b.hip_h + 0.12, b.neck_z - 0.075
    k, a = LAYERS["plate"]
    P = torso_surface(b, math.pi - 0.95, math.pi + 0.95, z0, z1, 12, 7, inflate=k, add=a)
    out = plate(P, 0.012, metal, mat=mat, ref=(0, 0, (z0 + z1) / 2), trim=trim, trim_r=0.011)
    return skin(out, blend=("hips", "chest", b.hip_h + 0.02, b.hip_h + b.torso_h * 0.6))


@tagged("gorget")
def gorget(b, metal, trim, mat="metal"):
    """Collar that caps the top edges of breast- and backplate (sits outside them)."""
    zb, zt = b.neck_z - 0.035, b.neck_z + 0.04
    rxb, ryb = layer_r(b, zb, "plate")
    neck_r = b.torso_w * 0.2 + 0.03
    rxb, ryb = max(neck_r + 0.03, rxb * 0.72), max(neck_r + 0.03, ryb * 0.95)
    nu, nv = 22, 4
    P = np.zeros((nu, nv, 3))
    for i, u in enumerate(np.linspace(-math.pi, math.pi, nu)):
        for j, t in enumerate(np.linspace(0, 1, nv)):
            rx = rxb + (max(neck_r, rxb * 0.62) - rxb) * t ** 0.8
            ry = ryb + (max(neck_r, ryb * 0.62) - ryb) * t ** 0.8
            P[i, j] = (math.sin(u) * rx, -math.cos(u) * ry, zb + (zt - zb) * t)
    out = plate(P, 0.012, metal, mat=mat, ref=(0, 0, zb - 0.05), trim=trim, trim_r=0.011, edges=("v0", "v1"),
                wrap_u=True)
    return skin(out, "chest")


@tagged("fauld")
def fauld(b, metal, trim, rows=1, team=None, mat="metal"):
    """Hip lames over the mail skirt, under the belt."""
    out = []
    k, a = LAYERS["plate"]
    for r in range(rows):
        z1 = b.hip_h + 0.02 - r * 0.05
        z0 = z1 - 0.075
        P = torso_surface(b, -1.35, 1.35, z0, z1, 14, 3, layer="plate", flare=0.18 + 0.08 * r)
        out += plate(P, 0.011, metal if (team is None or r % 2 == 0) else team,
                     mat="metal" if (team is None or r % 2 == 0) else "team",
                     ref=(0, 0, z1), trim=trim, trim_r=0.01, edges=("v0",))
    return thigh_follow(out, b, 0.65)


@tagged("tasset", 1)
def tasset(b, side, metal, trim, team=None, length=0.13, mat="metal"):
    """Thigh plate hanging from the belt, swings with the thigh."""
    j = b.joints()
    sign = 1 if side == "L" else -1
    hp, kn = j[f"hip.{side}"], j[f"knee.{side}"]
    a = hp + np.array([sign * 0.035, -0.02, 0.05])
    bb = a + (kn - hp) / np.linalg.norm(kn - hp) * length + np.array([sign * 0.03, -0.01, 0])
    P = limb_surface(a, bb, b.leg_r * 1.55, b.leg_r * 1.75, 9, 4, u0=-2.2 * sign - 0.0,
                     u1=0.5 * sign)
    if sign < 0:
        P = P[::-1]
    out = plate(P, 0.011, team or metal, mat="team" if team else "metal", ref=(hp + kn) / 2,
                trim=trim, trim_r=0.01)
    return skin(out, f"thigh.{side}")


@tagged("vambrace", 1)
def vambrace(b, side, metal, trim, rivet=None, mat="metal"):
    j = b.joints()
    el, wr = j[f"elbow.{side}"], j[f"wrist.{side}"]
    a = el + (wr - el) * 0.32
    c = el + (wr - el) * 0.74
    P = limb_surface(a, c, b.arm_r * 1.3, b.arm_r * 1.4, 14, 4)
    out = plate(P, 0.011, metal, mat=mat, ref=(a + c) / 2, trim=trim, trim_r=0.011, edges=("v0", "v1"),
                wrap_u=True, rivets=rivet, rivet_step=0.035)
    return skin(out, f"forearm.{side}")


@tagged("couter", 1)
def couter(b, side, metal, trim, mat="metal"):
    j = b.joints()
    el, sh = j[f"elbow.{side}"], j[f"shoulder.{side}"]
    sign = 1 if side == "L" else -1
    P = cap_surface(el + np.array([sign * 0.008, 0.03, 0.012]), (sign * 0.3, 1.0, 0.15), b.arm_r * 1.0,
                    math.radians(55), 12, 4, flare=0.2)
    out = plate(P, 0.01, metal, mat=mat, ref=el, trim=trim, trim_r=0.009, edges=("v1",), wrap_u=True)
    return skin(out, f"upper_arm.{side}")


@tagged("greave", 1)
def greave(b, side, metal, trim, rivet=None, mat="metal"):
    j = b.joints()
    kn, an = j[f"knee.{side}"], j[f"ankle.{side}"]
    a = kn + (an - kn) * 0.36
    c = kn + (an - kn) * 0.6
    P = limb_surface(a, c, b.leg_r * 1.25, b.leg_r * 1.2, 14, 4, bulge=0.008)
    out = plate(P, 0.011, metal, mat=mat, ref=(a + c) / 2, trim=trim, trim_r=0.011, edges=("v0", "v1"),
                wrap_u=True, rivets=rivet)
    return skin(out, f"shin.{side}")


@tagged("poleyn", 1)
def poleyn(b, side, metal, trim, mat="metal"):
    j = b.joints()
    kn = j[f"knee.{side}"]
    sign = 1 if side == "L" else -1
    P = cap_surface(kn + np.array([0, -b.leg_r * 0.55, 0.0]), (sign * 0.15, -1.0, 0.1), b.leg_r * 0.92,
                    math.radians(76), 14, 4, flare=0.3, square=2.6, phase=math.pi / 4)
    out = plate(P, 0.01, metal, mat=mat, ref=kn, trim=trim, trim_r=0.01, edges=("v1",), wrap_u=True)
    # half thigh / half shin so it stays on the knee as the leg bends
    for p in out:
        p.bone = None
        p.weights = {f"thigh.{side}": np.full(len(p.V), 0.5), f"shin.{side}": np.full(len(p.V), 0.5)}
    return out


@tagged("sabaton", 1)
def sabaton(b, side, metal, trim, mat="metal"):
    j = b.joints()
    an, toe = j[f"ankle.{side}"], j[f"toe.{side}"]
    out = []
    for k, (t, rr) in enumerate(((0.6, 1.05), (0.88, 0.92))):
        cc = an + (toe - an) * t
        cc[2] = b.foot_r * 0.42
        P = cap_surface(cc, (0, -0.45, 1.0), b.foot_r * rr, math.radians(72), 12, 4, squash=(1.0, 1.25))
        out += plate(P, 0.009, metal, mat=mat, ref=cc - np.array([0, 0, 0.03]), trim=trim, trim_r=0.008,
                     edges=("v1",), wrap_u=True)
    return skin(out, f"foot.{side}")


@tagged("gauntlet", 1)
def gauntlet(b, side, metal, trim, mat="metal"):
    """Flared cuff at the wrist (sits below the vambrace end)."""
    j = b.joints()
    wr, el = j[f"wrist.{side}"], j[f"elbow.{side}"]
    d = (wr - el) / np.linalg.norm(wr - el)
    a = wr + d * 0.004
    c = wr + d * 0.03
    P = limb_surface(a, c, b.arm_r * 1.3, b.arm_r * 1.6, 14, 3)
    out = plate(P, 0.01, metal, mat=mat, ref=wr, trim=trim, trim_r=0.011, edges=("v0", "v1"), wrap_u=True)
    return skin(out, f"hand.{side}")


@tagged("helm")
def sallet(b, metal, trim, team=None, rivet=None, ear_holes=True, mat="metal"):
    """Open sallet: covers crown and back, flared neck guard, brow band."""
    hc = b.head_c
    rx, ry, rz = b.head_r
    r = (rx * 1.07, ry * 1.1, rz * 1.08)

    def rim(u):
        back = (1 - math.cos(u)) / 2           # 0 front .. 1 back
        return math.radians(66 + 36 * back ** 1.3)
    P = ellipsoid_surface(hc + np.array([0, 0.0, 0.0]), r, -math.pi, math.pi, 0.05, 1.0, 20, 7, rim)
    # flare the neck guard outward
    for i in range(P.shape[0]):
        for jj in range(P.shape[1]):
            t = jj / (P.shape[1] - 1)
            p = P[i, jj] - hc
            back = max(0.0, p[1] / r[1])
            k = 1 + 0.22 * back * max(0, t - 0.55) / 0.45
            P[i, jj] = hc + np.array([p[0] * k, p[1] * k, p[2] - 0.03 * back * max(0, t - 0.6)])
    out = plate(P, 0.013, metal, mat=mat, ref=hc, trim=trim, trim_r=0.013, edges=("v1",), wrap_u=True,
                rivets=rivet, rivet_step=0.04)
    # comb / crest ridge front to back
    crest = [hc + np.array([0, -r[1] * math.cos(a) * 0.98, r[2] * math.sin(a) * 1.02 + 0.012])
             for a in np.linspace(math.radians(35), math.radians(150), 10)]
    cr = geo.tube(crest, np.linspace(0.008, 0.014, 10), 6, color=trim, squash=2.2)
    cr.mat = "gold"
    out.append(cr)
    if team is not None:
        out += horsehair_crest(crest, team)
    return skin(out, "head")


def horsehair_crest(line, color, n=16, length=0.1):
    """Galea-style crest: a fan of flattened hair spikes along the helmet comb."""
    from .beast import tuft
    out = []
    line = np.asarray(line, float)
    for i, t in enumerate(np.linspace(0.05, 0.95, n)):
        k = t * (len(line) - 1)
        i0 = int(k)
        p0 = line[min(i0, len(line) - 1)] * (1 - (k - i0)) + line[min(i0 + 1, len(line) - 1)] * (k - i0)
        lean = np.array([0, 0.55 + 1.1 * t, 1.0 - 0.45 * t])
        L = length * (0.7 + 0.55 * math.sin(math.pi * min(t * 1.15, 1)))
        for q in tuft(p0, lean, L, 0.028, color, n=3, spread=7, curl=0.55, seed=i):
            q.mat = "team"
            out.append(q)
    return out


@tagged("helm")
def ear_rings(b, trim):
    """Trimmed collars where ears poke through a helmet."""
    from .beast import ear_chain
    out = []
    for s, sign in (("L", 1), ("R", -1)):
        e0, e1, _ = ear_chain(b, sign)
        d = (e1 - e0) / np.linalg.norm(e1 - e0)
        c = e0 + d * 0.02
        P = limb_surface(c - d * 0.012, c + d * 0.012, 0.05, 0.045, 12, 2)
        P[:, :, 1] = (P[:, :, 1] - c[1]) * 0.6 + c[1]
        ring = plate(P, 0.008, trim, ref=c, trim=None, wrap_u=True)
        out += skin(ring, f"ear.{s}")
    return out


@tagged("brigandine")
def brigandine(b, cloth, rivet, z0=None, z1=None, rows=4, breast_z=None):
    """Team-coloured padded torso studded with rivets (above the hips only)."""
    z0 = b.hip_h + 0.06 if z0 is None else z0
    z1 = b.neck_z - 0.05 if z1 is None else z1
    P = torso_surface(b, -math.pi, math.pi, z0, z1, 22, 8, layer="brig")
    out = list(plate(P, 0.01, cloth, mat="team", ref=(0, 0, (z0 + z1) / 2), wrap_u=True))
    top = (breast_z - 0.03) if breast_z else z1 - 0.05
    for r in range(rows):
        z = z0 + 0.07 + (top - z0 - 0.07) * r / max(rows - 1, 1)
        rx, ry = layer_r(b, z, "brig")
        for u in np.linspace(-1.2, 1.2, 7):
            p = np.array([math.sin(u) * (rx + 0.01), -math.cos(u) * (ry + 0.01), z])
            n = np.array([math.sin(u) * ry, -math.cos(u) * rx, 0.0])
            out.append(stud(p, n, 0.009, rivet))
    return skin(out, blend=("hips", "chest", b.hip_h + 0.02, b.hip_h + b.torso_h * 0.6))


def shield_heater(face, trim, emblem=None, w=0.4, h=0.5, rivet=None, curve=0.03):
    """Heater shield facing -Y: team field, thick trim outline, rivets, emblem."""
    n = 14
    pts = []
    top = h * 0.5
    for i in range(n + 1):
        t = i / n
        x = w / 2 * math.cos(t * math.pi / 2) ** 0.6
        pts.append((x, top - t * h))
    outline = pts[:-1] + [(0.0, -h * 0.5)] + [(-x, z) for x, z in reversed(pts[:-1])]
    # top edge: add a slight dip in the middle
    outline = outline + [(0.0, top - 0.01)]
    out = []
    f = geo.extrude(outline, 0.03, face, bevel=0.05)
    f.mat = "team"
    out.append(f)
    ring = np.array([(x, -0.016, z) for x, z in outline] + [(outline[0][0], -0.016, outline[0][1])])
    tr = geo.tube(_resample(ring, 60), 0.016, 7, color=trim, squash=0.6)
    tr.mat = "gold"
    out.append(tr)
    if rivet:
        inner = _resample(np.array([(x * 0.86, -0.02, z * 0.88 + 0.01) for x, z in outline]), 18)
        for p_ in inner[:-1]:
            out.append(stud(p_, (0, -1, 0), 0.009, rivet))
    # vertical and horizontal bands (heraldic cross)
    if emblem:
        out += [e.tf((0, -0.024, 0.03)) for e in emblem]

    def bend(V):
        V[:, 1] += curve * (V[:, 0] / (w / 2)) ** 2
        return V
    for p_ in out:
        p_.deform(bend)
    return out



def shield_round(face, trim, emblem=None, r=0.21, rivet=None, boss=True):
    out = []
    f = geo.disc(r, 0.03, 24, face, bevel=0.06)
    f.mat = "team"
    out.append(f)
    ring = np.array([(math.cos(a) * r, -0.016, math.sin(a) * r) for a in np.linspace(0, 2 * math.pi, 49)])
    tr = geo.tube(ring, 0.018, 7, color=trim, squash=0.6)
    tr.mat = "gold"
    out.append(tr)
    if rivet:
        for a in np.linspace(0, 2 * math.pi, 12, endpoint=False):
            out.append(stud((math.cos(a) * r * 0.85, -0.02, math.sin(a) * r * 0.85), (0, -1, 0), 0.01, rivet))
    if boss:
        bs = geo.lathe([(r * 0.3, 0), (r * 0.27, 0.02), (r * 0.15, 0.045), (0, 0.05)], 14, color=trim)
        bs.tf(rot=(90, 0, 0)).tf((0, -0.012, 0))
        bs.mat = "metal"
        out.append(bs)
    if emblem:
        out += [e.tf((0, -0.03 if not boss else -0.024, 0)) for e in emblem]
    for p_ in out:
        p_.deform(lambda V: V + np.column_stack([np.zeros(len(V)),
                                                 0.06 * (V[:, 0] ** 2 + V[:, 2] ** 2) / r ** 2,
                                                 np.zeros(len(V))]))
    return out


def medallion(faction, metal, r=0.055, emblem_color=None):
    """Big round centrepiece (belt buckle / chest badge), facing -Y."""
    from . import gear
    out = []
    d = geo.disc(r, 0.018, 20, metal, bevel=0.15)
    d.mat = "gold"
    out.append(d)
    ring = np.array([(math.cos(a) * r, -0.01, math.sin(a) * r) for a in np.linspace(0, 2 * math.pi, 33)])
    t = geo.tube(ring, r * 0.13, 6, color=palette.mul(metal, 1.15))
    t.mat = "gold"
    out.append(t)
    for e in gear.emblem(faction, emblem_color or palette.mul(metal, 1.25), r / 0.07):
        e.tf((0, -0.014, 0))
        out.append(e)
    return out


@tagged("medal")
def on_belt(b, parts, z=None):
    z = b.hip_h + 0.065 if z is None else z
    ry = layer_r(b, z, "over")[1] + 0.03     # in front of tabards and panels
    out = []
    for p in parts:
        q = p.copy()
        q.tf((0, -ry, z))
        q.bone = "hips"
        q.weights = None
        out.append(q)
    return out


@tagged("cuisse", 1)
def cuisse(b, side, metal, trim, mat="metal"):
    """Front thigh plate between fauld and knee."""
    j = b.joints()
    hp, kn = j[f"hip.{side}"], j[f"knee.{side}"]
    a = hp + (kn - hp) * 0.5
    c = hp + (kn - hp) * 0.6
    P = limb_surface(a, c, b.leg_r * 1.3, b.leg_r * 1.22, 11, 4, u0=-1.25, u1=1.25)
    out = plate(P, 0.01, metal, mat=mat, ref=(a + c) / 2, trim=trim, trim_r=0.009)
    return skin(out, f"thigh.{side}")


@tagged("tabard")
def tabard_strip(b, color, trim, width=0.05, length=None, emblem=None):
    """Team strip hanging in front of the fauld, ending above the knees."""
    z_top = b.hip_h - 0.015
    kn = b.joints()["knee.L"][2]
    max_len = z_top - kn - 0.06
    length = max_len if length is None else min(length, max_len)
    rx, ry = layer_r(b, b.hip_h - 0.03, "belt")
    y0 = -(ry * 1.22 + 0.03)
    n = 8
    secs = []
    for i in range(n + 1):
        t = i / n
        z = z_top - length * t
        y = y0 - 0.025 * t
        w = width * (1 - 0.15 * t)
        if t > 0.82:
            w *= max(0.05, 1 - (t - 0.82) / 0.18 * 0.95)
        secs.append([(-w, y, z), (-w * 0.6, y - 0.008, z), (w * 0.6, y - 0.008, z), (w, y, z),
                     (w, y + 0.008, z), (-w, y + 0.008, z)])
    p = geo.loft(secs, color=color)
    p.mat = "team"
    out = [p]
    for e in (np.array([s_[0] for s_ in secs]), np.array([s_[3] for s_ in secs])):
        t = geo.tube(e, 0.006, 5, color=trim)
        t.mat = "gold"
        out.append(t)
    pts = [(0, y0, z_top + 0.01), (0, y0 - 0.01, z_top - length * 0.45), (0, y0 - 0.02, z_top - length - 0.01)]
    for q in out:
        chain_weights(q, ["tabard", "tabard_tip"], pts)
    return out


# ---------------------------------------------------------------------------
# Faction helmets
# ---------------------------------------------------------------------------

def _helm_shell(b, metal, trim, rim, mat, peak=0.0, inflate=(1.08, 1.1, 1.08), rivet=None, nv=8):
    hc = b.head_c
    rx, ry, rz = b.head_r
    r = (rx * inflate[0], ry * inflate[1], rz * inflate[2])
    P = ellipsoid_surface(hc, r, -math.pi, math.pi, 0.05, 1.0, 20, nv, rim)
    if peak:
        for i in range(P.shape[0]):
            for j in range(P.shape[1]):
                p = P[i, j] - hc
                top = max(0.0, p[2] / r[2])
                P[i, j] = hc + np.array([p[0] * (1 - 0.25 * top ** 3 * peak), p[1] * (1 - 0.25 * top ** 3 * peak),
                                         p[2] + peak * r[2] * top ** 4])
    out = plate(P, 0.013, metal, mat=mat, ref=hc, trim=trim, trim_r=0.012, edges=("v1",), wrap_u=True,
                rivets=rivet, rivet_step=0.04)
    return out, r


@tagged("helm")
def bascinet(b, metal, trim, mat="metal", nasal=True, spike=True, aventail=None, plume=None):
    """Dog helm: deep bowl, nasal bar, finial spike, optional mail aventail."""
    hc = b.head_c

    def rim(u):
        back = (1 - math.cos(u)) / 2
        return math.radians(70 + 45 * back ** 0.8)
    out, r = _helm_shell(b, metal, trim, rim, mat, peak=0.35 if spike else 0.0)
    if nasal:
        top = hc + np.array([0, -r[1] * 0.93, r[2] * 0.42])
        bot = hc + np.array([0, -r[1] * 1.02, -r[2] * 0.12])
        P = limb_surface(top, bot, 0.016, 0.02, 6, 3, u0=-1.2 - math.pi / 2, u1=1.2 - math.pi / 2)
        out += plate(P, 0.008, metal, mat=mat, ref=(top + bot) / 2 + np.array([0, 0.03, 0]), trim=trim,
                     trim_r=0.006)
    if spike:
        sp = geo.lathe([(0.02, 0), (0.012, 0.03), (0.004, 0.07), (0, 0.08)], 8, color=trim).tf(
            hc + np.array([0, 0, r[2] * 1.3]))
        sp.mat = "gold"
        out.append(sp)
    if aventail:
        av = geo.lathe([(1.0, -0.2), (1.08, 0.0)], 20, cap_bottom=False, cap_top=False, color=aventail)
        av.V[:, 0] *= r[0]
        av.V[:, 1] *= r[1]
        av.V[:, 2] = av.V[:, 2] * r[2] * 1.3
        av.V += hc + np.array([0, 0, -r[2] * 0.15])
        av.F = [f for f in av.F if np.mean(av.V[list(f), 1] - hc[1]) > -r[1] * 0.45]
        av.mat = "mail"
        out.append(av)
    if plume:
        out += horsehair_crest([hc + np.array([0, r[1] * 0.2 * k, r[2] * (1.25 - 0.2 * k)]) for k in range(6)],
                               plume, n=8, length=0.08)
    return skin(out, "head")


@tagged("helm")
def chapel(b, metal, trim, mat="metal", brim=1.45, plume=None):
    """Hamster kettle hat (chapel de fer): round bowl with a broad trimmed brim."""
    hc = b.head_c
    rx, ry, rz = b.head_r

    def rim(u):
        return math.radians(72)
    out, r = _helm_shell(b, metal, trim, rim, mat, inflate=(1.06, 1.08, 1.12))
    zc = hc[2] + math.cos(math.radians(72)) * r[2]
    nu, nv = 28, 3
    P = np.zeros((nu, nv, 3))
    for i, u in enumerate(np.linspace(-math.pi, math.pi, nu)):
        for jj, t in enumerate(np.linspace(0, 1, nv)):
            k = 0.92 + (brim - 0.92) * t
            P[i, jj] = (hc[0] + math.sin(u) * r[0] * k, hc[1] - math.cos(u) * r[1] * k,
                        zc - 0.035 * t ** 1.5)
    out += plate(P, 0.01, metal, mat=mat, ref=hc + np.array([0, 0, -0.2]), trim=trim, trim_r=0.012,
                 edges=("v1",), wrap_u=True)
    if plume:
        out += horsehair_crest([hc + np.array([0, r[1] * (0.6 * k - 0.3), r[2] * 1.12]) for k in range(5)],
                               plume, n=7, length=0.07)
    return skin(out, "head")


@tagged("helm")
def shishak(b, metal, trim, mat="metal", ear_guards=True, plume=None):
    """Hare helm: tall pointed bowl, gilded band, ear sleeves for long ears."""
    hc = b.head_c

    def rim(u):
        back = (1 - math.cos(u)) / 2
        return math.radians(72 + 30 * back)
    out, r = _helm_shell(b, metal, trim, rim, mat, peak=0.9)
    fin = geo.lathe([(0.014, 0), (0.01, 0.03), (0.022, 0.045), (0, 0.075)], 8, color=trim).tf(
        hc + np.array([0, 0, r[2] * 1.85]))
    fin.mat = "gold"
    out.append(fin)
    out = skin(out, "head")
    if ear_guards and b.species == "hare":
        from .beast import ear_chain
        for s, sign in (("L", 1), ("R", -1)):
            e0, e1, e2 = ear_chain(b, sign)
            d = (e1 - e0) / np.linalg.norm(e1 - e0)
            a = e0 + d * 0.02
            c = e0 + (e1 - e0) * 0.92
            P = limb_surface(a, c, 0.042, 0.036, 12, 4)
            ctr = (a + c) / 2
            P = ctr + (P - ctr) * np.array([1.0, 0.62, 1.0])
            sl = plate(P, 0.008, metal, mat=mat, ref=ctr, trim=trim, trim_r=0.008, edges=("v0", "v1"),
                       wrap_u=True)
            out += skin(sl, f"ear.{s}")
    if plume:
        out += skin(horsehair_crest([hc + np.array([0, r[1] * 0.25 * k, r[2] * (1.3 - 0.15 * k)])
                                     for k in range(6)], plume, n=8, length=0.08), "head")
    return out


@tagged("helm")
def pot_helm(b, metal, trim, mat="metal"):
    """Rat scrap helm: a battered pot with a rusty rim and a dent."""
    hc = b.head_c

    def rim(u):
        return math.radians(78 + 8 * math.sin(u * 3))
    out, r = _helm_shell(b, metal, trim, rim, mat, inflate=(1.1, 1.12, 1.1))
    dent = hc + np.array([r[0] * 0.5, -r[1] * 0.3, r[2] * 0.8])
    for p in out:
        d = np.linalg.norm(p.V - dent, axis=1)
        p.V -= (p.V - hc) * (0.12 * np.clip(1 - d / 0.06, 0, 1))[:, None]
    return skin(out, "head")
