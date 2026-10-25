"""Unit roster of the Animal Kingdoms set (GDD 'Звериные королевства').

Each faction has an armour *kit* following the Blizzard formula: one plate
material, one bright trim metal, the team colour framed inside. Units differ
by role silhouette: workers in cloth and leather, infantry in plate, ranged
in leather with hoods, elites heavier and spikier, heroes larger with capes
and crowns.

Team-coloured parts use the 'team' material with a light vertex colour;
engines tint them with the player colour.
"""
from dataclasses import dataclass, field

import numpy as np

from . import armor, beast, gear, geo, palette
from .beast import body_for

TW = "#f4f4f4"     # team white (tinted at runtime)

KITS = {
    #            plate       trim       rivet      mail       leather    cloth
    "cats":     ("#6e7789", "#e3a227", "#f2c25a", "#6c7382", "#4a2e1e", "#2c3352"),
    "dogs":     ("#a2753c", "#ecc35e", "#f5d98a", "#7c7466", "#5a3a22", "#2f4a2c"),
    "hamsters": ("#b06a38", "#e9c46a", "#f2d88e", "#8a7a66", "#6b4226", "#d9b26f"),
    "hares":    ("#c3c7cf", "#e7b53c", "#f3d27a", "#9aa0aa", "#6e4228", "#efe9dc"),
    "rats":     ("#6a5a4c", "#9c5a2c", "#b07a4a", "#5c5248", "#3e3024", "#4e4a3c"),
}


class Kit:
    def __init__(self, faction):
        (self.plate, self.trim, self.rivet, self.mail, self.leather, self.cloth) = KITS[faction]
        self.faction = faction


@dataclass
class UnitSpec:
    id: str
    faction: str
    name: str
    role: str
    body: beast.Body
    parts: list
    style: str = "sword"
    shield: bool = False
    walk: str = "walk"
    special: str = "groom"
    posture: float = 0.0
    worker: bool = False
    hero: bool = False
    meta: dict = field(default_factory=dict)


REGISTRY = {}


def unit(uid, faction, name, role):
    def deco(fn):
        REGISTRY[uid] = (fn, faction, name, role)
        return fn
    return deco


def build(uid):
    fn, faction, name, role = REGISTRY[uid]
    s = fn()
    s.id, s.faction, s.name, s.role = uid, faction, name, role
    return s


SPECIAL = {"cat": "groom", "dog": "sniff", "hamster": "stuff", "hare": "thump", "rat": "scheme"}
ARMOURED_SPECIAL = "flourish"   # plate units: no paws to the face through gauntlets
WALK = {"cat": "prowl", "dog": "march", "hamster": "waddle", "hare": "hop", "rat": "skitter"}


def spec(b, parts, **kw):
    if not kw.get("worker") and any(getattr(p, "group", "") and p.group.startswith(("gauntlet", "vambrace"))
                                    for p in parts):
        kw.setdefault("special", ARMOURED_SPECIAL)
    kw.setdefault("special", SPECIAL[b.species])
    kw.setdefault("walk", WALK[b.species])
    return UnitSpec("", "", "", "", b, parts, **kw)


def mail_sleeves(parts, b):
    for part in parts:
        if part.bone is None and part.weights and any(k.startswith("upper_arm") for k in part.weights):
            part.mat = "mail"
    return parts


def plate_set(b, k, *, pauldron=1.2, tiers=2, team_pauldron=True, spikes=0, arms=True, legs=True,
              breast=True, back=True, gorget=True, fauld_rows=1, tassets=False, cuisses=True,
              mat="metal", plate=None, trim=None):
    """Full or partial plate harness in the faction kit."""
    pc, tc = plate or k.plate, trim or k.trim
    out = []
    if breast:
        out += armor.breastplate(b, pc, tc, z0=b.hip_h + b.torso_h * 0.42, width=0.8, mat=mat)
    if back:
        out += armor.backplate(b, pc, tc, mat=mat)
    if gorget:
        out += armor.gorget(b, pc, tc, mat=mat)
    if fauld_rows:
        out += armor.fauld(b, pc, tc, rows=fauld_rows)
    for s in ("L", "R"):
        if pauldron:
            out += armor.pauldron(b, s, pc, tc, size=pauldron, tiers=tiers,
                                  team=TW if team_pauldron else None, spikes=spikes, mat=mat)
        if arms:
            out += armor.couter(b, s, pc, tc, mat=mat)
            out += armor.vambrace(b, s, pc, tc, mat=mat)
            out += armor.gauntlet(b, s, pc, tc, mat=mat)
        if legs:
            out += armor.greave(b, s, pc, tc, mat=mat)
            out += armor.poleyn(b, s, pc, tc, mat=mat)
            out += armor.sabaton(b, s, pc, tc, mat=mat)
            if cuisses:
                out += armor.cuisse(b, s, pc, tc, mat=mat)
        if tassets:
            out += armor.tasset(b, s, pc, tc, team=TW, length=0.1)
    return out


def skirt(b, color=TW, mat="team", drop=0.05, flare=0.25, top=0.03):
    drop = min(drop, 0.07)      # plate units: the skirt ends above the cuisses
    """Short skirt that tucks under the fauld (cloth layer)."""
    return [gear.garment(b, b.hip_h - drop, b.hip_h + top, color, mat, inflate=1.03, flare=flare)]


def tunic(b, color, z_bot=None, flare=0.3, mat="cloth", trim=None, trim_mat="team"):
    z_bot = b.hip_h - 0.11 if z_bot is None else z_bot
    out = [gear.garment(b, z_bot, b.neck_z - 0.01, color, mat, flare=flare)]
    if trim:
        out += hem_trim(b, z_bot, flare, trim, trim_mat)
    return out


def hem_trim(b, z_bot, flare, color, mat):
    """Trim ring sitting just outside a garment hem (follows the thighs like the hem)."""
    zt = z_bot + 0.012
    rx, ry = gear.garment_r(b, zt, z_bot, flare)
    t = gear.band(b, zt, color, mat, 0.012, radius=(rx + 0.01, ry + 0.01))
    t.group = "garment"
    armor.thigh_follow([t], b, 0.65)
    return [t]


def short_cape(b):
    """Tailed species wear a mantle-length cape so the tail leaves below it."""
    return b.hip_h + 0.08 if b.species in ("cat", "dog", "rat") else None


def leather_set(b, k, pauldron=0.85, side="both"):
    """Light ranger harness: leather plates with brass trim."""
    out = []
    lc, tc = k.leather, k.trim
    out += armor.breastplate(b, lc, tc, z0=b.hip_h + b.torso_h * 0.45, width=0.75, mat="body")
    sides = ("L", "R") if side == "both" else (side,)
    for s in sides:
        out += armor.pauldron(b, s, lc, tc, size=pauldron, tiers=2, team=None, mat="body")
    for s in ("L", "R"):
        out += armor.vambrace(b, s, lc, tc, mat="body")
    return out


def belt(b, k, medal=True, z=None, fit=None):
    out = gear.belt(b, k.leather, buckle=k.trim, z=z, fit=fit)
    if medal:
        ry = max(out[0].fit[1], armor.layer_r(b, z or b.hip_h + 0.065, "plate")[1]) if fit is not None else None
        out += armor.on_belt(b, armor.medallion(k.faction, k.trim, r=0.055), z=z, ry=ry)
    return out


def mount_shield(b, parts, offset=0.12):
    return gear.on_forearm(b, parts, out_offset=offset)


# ===========================================================================
# CATS — Котовое Герцогство Когтеград
# ===========================================================================

@unit("cat_worker", "cats", "Котёнок-подмастерье", "worker")
def cat_worker():
    b = body_for("cat", fur="grey_tabby", scale=0.86, head_r=(0.156, 0.14, 0.145), eye_size=1.12,
                 extras={"iris": "#9fd36a", "brow_angle": 4})
    p = beast.fur_body(b, sleeve="#d8cfbf")
    p += tunic(b, "#d8cfbf", flare=0.25)
    p.append(gear.front_panel(b, b.neck_z - 0.06, b.hip_h - 0.12, 0.1, "#7a5232", "body",
                              tip="round", inflate=1.12))
    p += gear.belt(b, palette.LEATHER, pouch="#6b4a33", fit=p)
    p += gear.cap(b, TW, mat="team", tilt=-14)
    p += gear.in_hand(b, gear.hammer(size=1.2), "R")
    return spec(b, p, style="tool", worker=True)


@unit("cat_swordsman", "cats", "Мечник-полосатик", "infantry")
def cat_swordsman():
    k = Kit("cats")
    b = body_for("cat", fur="ginger", extras={"iris": "#d4e04a", "brow_angle": -24, "lid": 0.55,
                                               "fangs": True})
    p = mail_sleeves(beast.fur_body(b, sleeve=k.mail, boots=k.leather, paw="#5a3826"), b)
    p += skirt(b)
    p += armor.brigandine(b, TW, k.rivet, breast_z=b.hip_h + b.torso_h * 0.42, rows=3)
    p += plate_set(b, k, pauldron=1.05, legs=True)
    p += belt(b, k, fit=p)
    p += armor.tabard_strip(b, TW, k.trim)
    p += armor.sallet(b, k.plate, k.trim, team=TW)
    p += armor.ear_rings(b, k.trim)
    p += gear.in_hand(b, gear.sword(0.62, 0.1, guard=k.trim), "R")
    p += mount_shield(b, armor.shield_heater(TW, k.trim, gear.emblem("cats", k.trim, 1.3), rivet=k.rivet,
                                             w=0.32, h=0.38))
    return spec(b, p, style="sword", shield=True)


@unit("cat_crossbow", "cats", "Арбалетчик-сиамец", "ranged")
def cat_crossbow():
    k = Kit("cats")
    b = body_for("cat", fur="siamese", extras={"iris": "#6fc0f0", "brow_angle": -16, "lid": 0.4})
    p = beast.fur_body(b, sleeve=k.cloth, boots=k.leather, paw="#5a3826")
    p += tunic(b, TW, mat="team", flare=0.3, trim=k.trim, trim_mat="gold")
    p += leather_set(b, k, pauldron=0.8, side="L")
    p += belt(b, k, medal=False, fit=p)
    p += gear.cap(b, "#2c3352", feather=k.trim, mat="cloth", tilt=16)
    p += gear.in_hand(b, gear.crossbow(steel=k.plate), "R", scale=1.35)
    p += gear.on_hip(b, [geo.cyl(0.045, 0.2, 8, color=k.leather).tf((0, 0, -0.12))], "L", rot=(0, 15, 0))
    return spec(b, p, style="crossbow")


@unit("cat_assassin", "cats", "Чёрный кот-ассасин", "elite")
def cat_assassin():
    b = body_for("cat", fur="black", extras={"iris": "#f0c419", "brow_angle": -28, "lid": 0.65,
                                              "fangs": True})
    dark, plate, silver = "#2a2b3a", "#33354a", "#b9c2cf"
    p = beast.fur_body(b, sleeve=dark, boots="#1c1c26", paw="#1c1c26")
    p += tunic(b, dark, flare=0.45, z_bot=b.hip_h - 0.16)
    p += armor.breastplate(b, plate, silver, z0=b.hip_h + b.torso_h * 0.4, width=0.9, mat="body")
    p += armor.pauldron(b, "R", plate, silver, size=0.95, tiers=3, team=TW, spikes=2, mat="body")
    for s in ("L", "R"):
        p += armor.vambrace(b, s, plate, silver, mat="body")
    p += gear.hood(b, "#2d3150", mat="cloth", open_face=0.72)
    p += gear.scarf(b, TW)
    p += gear.belt(b, "#3b2a24", buckle=silver, pouch="#3b2a24", fit=p)
    p += gear.in_hand(b, gear.dagger(0.3, steel=silver), "R", scale=1.35)
    p += gear.in_hand(b, gear.dagger(0.3, steel=silver), "L", scale=1.35)
    return spec(b, p, style="dagger2", special="groom")


@unit("cat_hero_murena", "cats", "Герцогиня Мурена Когтистая", "hero")
def cat_hero_murena():
    k = Kit("cats")
    silver = "#c9d1dc"
    b = body_for("cat", fur="white_cat", scale=1.2, extras={"iris": "#5fd0f0", "brow_angle": -16,
                                                             "lid": 0.35, "fangs": True})
    p = mail_sleeves(beast.fur_body(b, sleeve=k.mail, boots=k.leather, paw="#3a3a50"), b)
    p += skirt(b, drop=0.16, flare=0.25)
    p += plate_set(b, k, pauldron=1.5, tiers=3, spikes=3, plate=silver, gorget=False)
    p += gear.cape(b, TW, collar="#f6f2ea", length=(b.shoulder_z + 0.02 - short_cape(b)) if short_cape(b) else None)
    p += gear.belt(b, "#2c3352", buckle=k.trim, fit=p)
    p += armor.tabard_strip(b, TW, k.trim, length=0.36, width=0.085)
    p += armor.on_belt(b, armor.medallion("cats", k.trim, r=0.065))
    p += gear.crown(b, gold=k.trim, gem="#3aa0e0", points=5, h=0.07, r_scale=0.66)
    p += gear.in_hand(b, gear.sabre(0.66, guard=k.trim), "R")
    return spec(b, p, style="sabre", special="proud", hero=True)


# ===========================================================================
# DOGS — Пёсья Марка
# ===========================================================================

@unit("dog_worker", "dogs", "Щенок-оруженосец", "worker")
def dog_worker():
    k = Kit("dogs")
    b = body_for("dog", fur="beagle", scale=0.86, head_r=(0.16, 0.15, 0.158), eye_size=1.1,
                 extras={"dog": "beagle", "ears": "floppy", "brow_angle": 8, "tongue": True})
    p = beast.fur_body(b, sleeve=k.cloth)
    p += tunic(b, k.cloth, flare=0.25)
    p.append(gear.front_panel(b, b.neck_z - 0.04, b.hip_h - 0.12, 0.1, k.leather, "body",
                              tip="round", inflate=1.12))
    p += gear.belt(b, "#5a3a22", pouch="#7a4b2a", fit=p)
    p += gear.collar(b, "#a33a2a", tag=palette.GOLD)
    p += gear.in_hand(b, gear.hammer(size=1.2), "R")
    return spec(b, p, style="tool", worker=True)


@unit("dog_halberdier", "dogs", "Овчарка-алебардщик", "infantry")
def dog_halberdier():
    k = Kit("dogs")
    b = body_for("dog", fur="shepherd", extras={"dog": "shepherd", "brow_angle": -24, "lid": 0.55,
                                                 "fangs": True})
    p = mail_sleeves(beast.fur_body(b, sleeve=k.mail, boots=k.leather, paw=k.leather), b)
    p += tunic(b, k.mail, mat="mail", flare=0.3, z_bot=b.hip_h - 0.06)
    p.append(gear.front_panel(b, b.neck_z - 0.03, b.hip_h - 0.16, 0.12, TW, "team", tip="point",
                              inflate=1.17))
    p += gear.chest_emblem(b, "dogs", k.trim, inflate=1.17)
    p += plate_set(b, k, pauldron=1.15, tiers=2, breast=False, back=False, fauld_rows=0, tassets=False,
                   gorget=False)
    p += belt(b, k, fit=p)
    p += armor.bascinet(b, k.plate, k.trim, aventail=k.mail)
    p += gear.in_hand(b, gear.halberd(), "R", scale=1.35)
    return spec(b, p, style="thrust")


@unit("dog_archer", "dogs", "Лучник-гончая", "ranged")
def dog_archer():
    k = Kit("dogs")
    b = body_for("dog", fur="beagle", extras={"dog": "hound", "ears": "floppy", "brow_angle": -18,
                                               "lid": 0.45})
    p = beast.fur_body(b, sleeve=k.cloth, boots=k.leather, paw=k.leather)
    p += tunic(b, k.cloth, flare=0.3)
    p += leather_set(b, k, pauldron=0.85, side="L")
    p += gear.hood(b, TW, mat="team", open_face=0.85, mantle=True)
    p += belt(b, k, medal=False, fit=p)
    p += gear.backpack(b, k.leather, kind="quiver")
    p += gear.in_hand(b, gear.longbow(), "L", scale=1.3)
    return spec(b, p, style="bow")


@unit("dog_bulldog_guard", "dogs", "Бульдог-гвардеец", "elite")
def dog_bulldog_guard():
    k = Kit("dogs")
    b = body_for("dog", fur="bulldog", scale=1.08, chest=1.2, torso_w=0.42, belly=1.08, waist=0.85,
                 head_r=(0.16, 0.15, 0.15),
                 extras={"dog": "bulldog", "ears": "rose", "brow_angle": -30, "lid": 0.7, "fangs": True})
    p = mail_sleeves(beast.fur_body(b, sleeve=k.mail, boots=k.leather, paw=k.leather), b)
    p += skirt(b, drop=0.13)
    p += plate_set(b, k, pauldron=1.55, tiers=3, spikes=3, fauld_rows=2)
    p += gear.collar(b, "#3a2a20", spikes=palette.STEEL)
    p += belt(b, k, fit=p)
    p += armor.tabard_strip(b, TW, k.trim, length=0.3, width=0.09)
    p += armor.bascinet(b, k.plate, k.trim, nasal=False, plume=TW)
    p += gear.in_hand(b, gear.mace(k.plate, size=1.7), "R", scale=1.35)
    p += mount_shield(b, armor.shield_heater(TW, k.trim, gear.emblem("dogs", k.trim, 1.4), rivet=k.rivet,
                                             w=0.38, h=0.48), 0.13)
    return spec(b, p, style="mace", shield=True)


@unit("dog_hero_rex", "dogs", "Король Рекс Верный", "hero")
def dog_hero_rex():
    k = Kit("dogs")
    b = body_for("dog", fur="golden", scale=1.22, chest=1.12,
                 extras={"dog": "hound", "ears": "floppy", "brow_angle": -14, "lid": 0.4, "fangs": True})
    p = mail_sleeves(beast.fur_body(b, sleeve=k.mail, boots=k.leather, paw=k.leather), b)
    p += skirt(b, drop=0.15, flare=0.25)
    p += plate_set(b, k, pauldron=1.6, tiers=3, spikes=0, gorget=False)
    p += gear.cape(b, TW, collar="#f2e6cc", length=(b.shoulder_z + 0.02 - short_cape(b)) if short_cape(b) else None)
    p += belt(b, k, fit=p)
    p += armor.tabard_strip(b, TW, k.trim, length=0.36, width=0.09)
    p += gear.crown(b, gold=k.trim, points=5, h=0.085, r_scale=0.7)
    p += gear.in_hand(b, gear.sword(0.7, 0.11, guard=k.trim), "R")
    p += mount_shield(b, armor.shield_heater(TW, k.trim, gear.emblem("dogs", k.trim, 1.4), rivet=k.rivet,
                                             w=0.38, h=0.48), 0.13)
    return spec(b, p, style="sword", shield=True, special="proud", hero=True)


# ===========================================================================
# HAMSTERS — Защёчная Республика
# ===========================================================================

@unit("ham_worker", "hamsters", "Хомяк-носильщик", "worker")
def ham_worker():
    b = body_for("hamster", fur="golden_ham", scale=0.92, extras={"brow_angle": 6})
    p = beast.fur_body(b)
    p += tunic(b, "#d9b26f", flare=0.2, z_bot=b.hip_h - 0.06)
    p += gear.bandana(b, TW)
    p += gear.backpack(b, "#d8c08a", kind="sack", size=1.3)
    p += gear.belt(b, palette.LEATHER, fit=p)
    p += gear.in_hand(b, gear.pickaxe(), "R", scale=1.2)
    return spec(b, p, style="tool", worker=True)


@unit("ham_militia", "hamsters", "Ополченец с вилкой", "infantry")
def ham_militia():
    k = Kit("hamsters")
    b = body_for("hamster", fur="white_ham", extras={"brow_angle": -22, "lid": 0.45})
    p = beast.fur_body(b, sleeve="#d9b26f", paw=k.leather)
    gam = tunic(b, "#d9b26f", flare=0.25)
    gam[0].paint(geo.stripes(palette.mul("#d9b26f", 0.8), axis=2, freq=110, width=0.2))
    p += gam
    p.append(gear.front_panel(b, b.neck_z - 0.05, b.hip_h - 0.08, 0.12, TW, "team", tip="straight",
                              inflate=1.12))
    p += gear.chest_emblem(b, "hamsters", k.trim, inflate=1.14)
    for s in ("L", "R"):
        p += armor.pauldron(b, s, k.leather, k.trim, size=1.0, tiers=2, team=None, mat="body")
    p += belt(b, k, medal=False, fit=p)
    p += armor.chapel(b, k.plate, k.trim, brim=1.35)
    p += gear.in_hand(b, gear.pitchfork(), "R", scale=1.3)
    p += mount_shield(b, gear.pot_lid(), 0.08)
    return spec(b, p, style="thrust")


@unit("ham_slinger", "hamsters", "Пращник с семечками", "ranged")
def ham_slinger():
    k = Kit("hamsters")
    b = body_for("hamster", fur="golden_ham", extras={"brow_angle": -16, "lid": 0.35})
    p = beast.fur_body(b, paw=k.leather)
    p += tunic(b, TW, mat="team", flare=0.2, z_bot=b.hip_h - 0.06, trim=k.trim, trim_mat="gold")
    p += leather_set(b, k, pauldron=0.8, side="R")
    p += gear.bandana(b, "#efe6cf", mat="cloth")
    p += gear.belt(b, k.leather, buckle=k.trim, pouch="#e9d6a0", fit=p)
    p += gear.in_hand(b, gear.sling(), "R", scale=1.3)
    return spec(b, p, style="sling")


@unit("ham_barrel", "hamsters", "Хомяк-тяжеловес в бочке-доспехе", "elite")
def ham_barrel():
    from .rig import blend_weights
    k = Kit("hamsters")
    b = body_for("hamster", fur="golden_ham", scale=1.1, belly=1.3, extras={"brow_angle": -28, "lid": 0.65})
    p = beast.fur_body(b, paw=k.leather)
    z0, z1 = b.hip_h - 0.1, b.neck_z - 0.02
    prof = []
    for i in range(11):
        t = i / 10
        r = 0.215 * (1 + 0.14 * np.sin(np.pi * t))
        prof.append((r, z0 + (z1 - z0) * t))
    bar = geo.lathe(prof, 18, color=palette.WOOD)
    bar.paint(geo.stripes(palette.WOOD_DARK, axis=0, freq=55, width=0.12))
    bar.V[:, 1] *= 0.92
    blend_weights(bar, "hips", "chest", b.hip_h, b.hip_h + b.torso_h * 0.6)
    bar.group = "barrel"
    p.append(bar)
    for t, kk in ((0.08, 1.0), (0.5, 1.16), (0.92, 1.0)):
        z = z0 + (z1 - z0) * t
        hp = geo.lathe([(0.215 * kk * 1.03, z - 0.02), (0.215 * kk * 1.07, z), (0.215 * kk * 1.03, z + 0.02)],
                       18, cap_bottom=False, cap_top=False, color=k.plate)
        hp.V[:, 1] *= 0.92
        blend_weights(hp, "hips", "chest", b.hip_h, b.hip_h + b.torso_h * 0.6)
        hp.mat = "metal"
        hp.group = "barrel"
        p.append(hp)
    p.append(gear.front_panel(b, b.neck_z - 0.08, b.hip_h + 0.02, 0.08, TW, "team", tip="point",
                              inflate=1.4))
    p += armor.on_belt(b, armor.medallion("hamsters", k.trim, r=0.07), z=b.hip_h + b.torso_h * 0.45)
    for s in ("L", "R"):
        p += armor.pauldron(b, s, k.plate, k.trim, size=1.4, tiers=3, team=TW, spikes=2)
        p += armor.vambrace(b, s, k.plate, k.trim)
        p += armor.gauntlet(b, s, k.plate, k.trim)
    p += armor.chapel(b, k.plate, k.trim, brim=1.2, plume=TW)
    p += gear.in_hand(b, gear.hammer(size=2.1, mallet=True), "R")
    return spec(b, p, style="mace")


@unit("ham_hero_puhloshek", "hamsters", "Магистр Пухлощёк", "hero")
def ham_hero_puhloshek():
    k = Kit("hamsters")
    b = body_for("hamster", fur="golden_ham", scale=1.2, belly=1.35, extras={"brow_angle": -8, "lid": 0.2})
    p = beast.fur_body(b, sleeve=TW, paw=k.leather, skip=("tail",))
    p.append(gear.garment(b, 0.03, b.neck_z - 0.01, TW, "team", inflate=1.07, flare=0.35))
    p += hem_trim(b, 0.03, 0.35, k.trim, "gold")
    p.append(gear.front_panel(b, b.neck_z - 0.03, 0.04, 0.04, k.trim, "gold", tip="straight",
                              inflate=1.1, depth=0.008))
    for s in ("L", "R"):
        p += armor.pauldron(b, s, k.plate, k.trim, size=1.2, tiers=2, team=TW)
    p += gear.belt(b, "#6b3a1e", buckle=k.trim, pouch=k.trim, fit=p)
    z = b.neck_z - 0.04
    rx, ry = beast.torso_r(b, z)
    ch = geo.tube(geo.bezier((-rx * 0.8, -ry * 0.4, z + 0.02), (0, -ry * 1.5, z - 0.14),
                             (rx * 0.8, -ry * 0.4, z + 0.02), n=12), 0.012, 6, color=k.trim)
    ch.mat = "gold"
    ch.bone = "chest"
    p.append(ch)
    p += armor.skin([q.tf((0, -ry * 1.3, z - 0.11)) for q in armor.medallion("hamsters", k.trim, r=0.05)],
                    "chest")
    p += gear.cape(b, TW, collar=k.trim, length=(b.shoulder_z + 0.02 - short_cape(b)) if short_cape(b) else None)
    p += gear.merchant_hat(b, TW)
    p += gear.in_hand(b, gear.staff(top=gear.wheel_topper(k.trim), length=1.3), "R")
    return spec(b, p, style="staff", special="stuff", hero=True)


# ===========================================================================
# HARES — Длинноухое Княжество
# ===========================================================================

@unit("hare_worker", "hares", "Крольчонок-огородник", "worker")
def hare_worker():
    b = body_for("hare", fur="brown_hare", scale=0.84, head_r=(0.15, 0.15, 0.158), eye_size=1.1,
                 extras={"brow_angle": 6})
    p = beast.fur_body(b, sleeve="#efe9dc")
    p += tunic(b, "#efe9dc", flare=0.2)
    p.append(gear.front_panel(b, b.neck_z - 0.06, b.hip_h - 0.12, 0.11, "#5a7fa8", "cloth",
                              tip="straight", inflate=1.12))
    p += gear.belt(b, palette.LEATHER, fit=p)
    p += gear.straw_hat(b, band_c=palette.FACTIONS["hares"]["team"])
    p += gear.in_hand(b, gear.hoe(), "R", scale=1.2)
    return spec(b, p, style="tool", worker=True)


@unit("hare_spearman", "hares", "Копейщик-русак", "infantry")
def hare_spearman():
    k = Kit("hares")
    b = body_for("hare", fur="brown_hare", extras={"brow_angle": -22, "lid": 0.5})
    p = mail_sleeves(beast.fur_body(b, sleeve=k.mail, boots="#7a2a1e", paw=k.leather), b)
    p.append(gear.garment(b, b.hip_h - 0.2, b.neck_z - 0.01, TW, "team", inflate=1.06, flare=0.35))
    p += plate_set(b, k, pauldron=1.05, tiers=2, team_pauldron=False, legs=False, fauld_rows=0,
                   tassets=False, gorget=False)
    p += belt(b, k, medal=False, fit=p)
    p += armor.shishak(b, k.plate, k.trim)
    p += gear.in_hand(b, gear.spear(tassel=TW), "R", scale=1.35)
    p += mount_shield(b, gear.shield_kite(TW, k.trim, gear.emblem("hares", k.trim, 1.3)), 0.12)
    return spec(b, p, style="thrust", shield=True)


@unit("hare_archer", "hares", "Лучник-беляк", "ranged")
def hare_archer():
    k = Kit("hares")
    b = body_for("hare", fur="white_hare", extras={"brow_angle": -16, "lid": 0.4})
    p = beast.fur_body(b, sleeve=TW, boots="#7a2a1e", paw=k.leather)
    p += tunic(b, TW, mat="team", flare=0.3, trim=k.trim, trim_mat="gold")
    p += leather_set(b, k, pauldron=0.8, side="L")
    p += belt(b, k, medal=False, fit=p)
    p += gear.fur_hat(b, TW)
    p += gear.backpack(b, "#7a2a1e", kind="quiver")
    p += gear.in_hand(b, gear.longbow(wood="#c9a26a", recurve=True, length=0.85), "L", scale=1.3)
    return spec(b, p, style="bow")


@unit("hare_vityaz", "hares", "Князь-витязь", "elite")
def hare_vityaz():
    k = Kit("hares")
    b = body_for("hare", fur="brown_hare", scale=1.08, chest=1.08, extras={"brow_angle": -24, "lid": 0.6})
    p = mail_sleeves(beast.fur_body(b, sleeve=k.mail, boots="#7a2a1e", paw=k.leather, skip=("tail",)), b)
    p += skirt(b, drop=0.14, flare=0.25)
    p += plate_set(b, k, pauldron=1.4, tiers=3, gorget=False)
    p += gear.cape(b, TW, collar=k.trim, length=(b.shoulder_z + 0.02 - short_cape(b)) if short_cape(b) else None)
    p += belt(b, k, fit=p)
    p += armor.tabard_strip(b, TW, k.trim, length=0.32)
    p += armor.shishak(b, k.trim, k.plate, plume=TW)
    p += gear.in_hand(b, gear.sword(0.62, 0.1, guard=k.trim), "R")
    p += mount_shield(b, armor.shield_round(TW, k.trim, gear.emblem("hares", k.trim, 1.3), rivet=k.rivet))
    return spec(b, p, style="sword", shield=True)


@unit("hare_hero_belyana", "hares", "Княгиня Беляна", "hero")
def hare_hero_belyana():
    k = Kit("hares")
    b = body_for("hare", fur="white_hare", scale=1.2, extras={"brow_angle": -14, "lid": 0.3})
    p = beast.fur_body(b, sleeve=TW, boots="#7a2a1e", paw="#f0ece4", skip=("tail",))
    p.append(gear.garment(b, 0.04, b.neck_z - 0.01, TW, "team", inflate=1.06, flare=0.5))
    p += hem_trim(b, 0.04, 0.5, k.trim, "gold")
    p.append(gear.front_panel(b, b.neck_z - 0.02, 0.05, 0.05, k.trim, "gold", tip="straight",
                              inflate=1.1, depth=0.008))
    p += armor.breastplate(b, k.plate, k.trim, z0=b.hip_h + b.torso_h * 0.5, width=0.85)
    for s in ("L", "R"):
        p += armor.pauldron(b, s, k.plate, k.trim, size=1.2, tiers=2, team=TW)
    p += gear.cape(b, "#f6f2ea", mat="cloth", collar="#ffffff", length=(b.shoulder_z + 0.02 - short_cape(b)) if short_cape(b) else None)
    p += gear.kokoshnik(b, TW)
    p += gear.in_hand(b, gear.sabre(0.62, guard=k.trim, grip="#7a2a1e"), "R")
    return spec(b, p, style="sabre", special="proud", hero=True)


# ===========================================================================
# RATS — Крысиная Чума (AI only)
# ===========================================================================

@unit("rat_raider", "rats", "Крыса-оборванец", "infantry")
def rat_raider():
    k = Kit("rats")
    b = body_for("rat", extras={"brow_angle": -30, "lid": 0.6})
    rag = "#6a6150"
    p = beast.fur_body(b)
    t = tunic(b, rag, flare=0.35)
    t[0].paint(geo.patch((0.06, -0.1, b.hip_h + 0.1), 0.06, "#4e463a", 0.3))
    t[0].paint(geo.patch((-0.08, -0.05, b.hip_h - 0.03), 0.05, "#7e7558", 0.3))
    p += t
    p += armor.pauldron(b, "L", k.plate, k.trim, size=1.15, tiers=2, team=None, spikes=2)
    p += armor.vambrace(b, "R", k.leather, k.trim, mat="body")
    p += armor.pot_helm(b, k.plate, k.trim)
    p += gear.scarf(b, TW)
    p += gear.belt(b, k.leather, buckle=k.trim, fit=p)
    p += gear.in_hand(b, gear.cleaver(), "R", scale=1.5)
    return spec(b, p, style="sword", posture=16)


@unit("rat_plague_doctor", "rats", "Чумной лекарь", "support")
def rat_plague_doctor():
    k = Kit("rats")
    b = body_for("rat", extras={"brow_angle": -26, "lid": 0.55, "glow": "#c8ff4a"})
    coat = "#3a3530"
    p = beast.fur_body(b, sleeve=coat, paw="#2a2420")
    p.append(gear.garment(b, 0.04, b.neck_z - 0.01, coat, "cloth", inflate=1.06, flare=0.45))
    p += gear.belt(b, "#2a2420", buckle=k.trim, pouch="#5a4a32", fit=p)
    for s in ("L", "R"):
        p += armor.pauldron(b, s, k.leather, k.trim, size=0.9, tiers=2, team=None, mat="body")
    p += gear.beak_mask(b)
    p += gear.wide_hat(b, "#2a2622")
    p += gear.scarf(b, TW, tails=True)
    p += gear.in_hand(b, gear.staff(wood="#3a2a1e", length=1.15), "R")
    p += gear.in_hand(b, gear.lantern(), "L", rot=(0, 0, 0))
    return spec(b, p, style="lantern", posture=12)


@unit("rat_king", "rats", "Крыса-Король", "boss")
def rat_king():
    k = Kit("rats")
    b = body_for("rat", scale=1.9, belly=1.3, torso_w=0.36, chest=1.1,
                 extras={"brow_angle": -32, "lid": 0.7, "glow": "#d6ff3a"})
    p = beast.fur_body(b)
    p += tunic(b, "#4a4436", flare=0.35)
    p += plate_set(b, k, pauldron=1.6, tiers=3, spikes=3, legs=False, cuisses=False, gorget=False)
    p += gear.cape(b, TW, collar="#5a5040", length=(b.shoulder_z + 0.02 - short_cape(b)) if short_cape(b) else None)
    p += gear.crown(b, gold="#9a8a3a", gem="#9adf2a", points=7, h=0.1, r_scale=0.7, tilt=-10)
    p += gear.in_hand(b, gear.cleaver(), "R", scale=2.0)
    return spec(b, p, style="sword", posture=18, special="scheme", hero=True)
