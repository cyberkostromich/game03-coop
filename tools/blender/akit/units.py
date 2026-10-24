"""Unit roster of the Animal Kingdoms set (GDD 'Звериные королевства').

Each builder returns a UnitSpec: body plan, all mesh parts, and how it
animates. Team-coloured parts use the 'team' material with a light
vertex-colour pattern; engines tint them with the player colour.
"""
from dataclasses import dataclass, field

import numpy as np

from . import beast, gear, geo, palette
from .beast import body_for

TW = "#f4f4f4"     # team white (tinted at runtime)
TL = "#d2d2d2"     # team light shade
TD = "#8c8c8c"     # team dark shade


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
    spec = fn()
    spec.id, spec.faction, spec.name, spec.role = uid, faction, name, role
    return spec


def F(faction):
    return palette.FACTIONS[faction]


SPECIAL = {"cat": "groom", "dog": "sniff", "hamster": "stuff", "hare": "thump", "rat": "scheme"}
WALK = {"cat": "prowl", "dog": "march", "hamster": "waddle", "hare": "hop", "rat": "skitter"}


def spec(b, parts, **kw):
    kw.setdefault("special", SPECIAL[b.species])
    kw.setdefault("walk", WALK[b.species])
    return UnitSpec("", "", "", "", b, parts, **kw)


def tunic(b, color, z_bot=None, flare=0.3, mat="cloth", trim=None, trim_mat="team"):
    z_bot = b.hip_h - 0.09 if z_bot is None else z_bot
    out = [gear.garment(b, z_bot, b.neck_z - 0.01, color, mat, inflate=1.06, flare=flare)]
    if trim:
        out.append(gear.band(b, z_bot + 0.008, trim, trim_mat, 0.012, 1.08 * (1 + flare * 0.95),
                             bone="hips"))
    return out


# ===========================================================================
# CATS — Котовое Герцогство Когтеград
# ===========================================================================

@unit("cat_worker", "cats", "Котёнок-подмастерье", "worker")
def cat_worker():
    f = F("cats")
    b = body_for("cat", fur="grey_tabby", scale=0.84, head_r=(0.23, 0.205, 0.21), eye_size=1.18,
                 extras={"iris": "#9fd36a", "brow_angle": 6})
    p = beast.fur_body(b, sleeve="#d8cfbf")
    p += tunic(b, "#d8cfbf", flare=0.25)
    p.append(gear.front_panel(b, b.neck_z - 0.05, b.hip_h - 0.11, 0.1, "#7a5232", "body",
                              tip="round", inflate=1.12))
    p += gear.belt(b, palette.LEATHER, pouch="#6b4a33")
    p += gear.cap(b, TW, mat="team", tilt=-14)
    p += gear.in_hand(b, gear.hammer(), "R")
    return spec(b, p, style="tool", worker=True)


@unit("cat_swordsman", "cats", "Мечник-полосатик", "infantry")
def cat_swordsman():
    f = F("cats")
    b = body_for("cat", fur="ginger", extras={"iris": "#c9d63a", "brow_angle": -22, "lid": 0.55, "fangs": True})
    p = beast.fur_body(b, sleeve=f["cloth"], boots=palette.LEATHER)
    p += tunic(b, f["cloth"], flare=0.32)
    p += gear.cuirass(b, f["metal"])
    p.append(gear.front_panel(b, b.neck_z - 0.07, b.hip_h - 0.08, 0.1, TW, "team", tip="point",
                              inflate=1.2))
    p += gear.chest_emblem(b, "cats", f["accent"], inflate=1.2, scale=0.75)
    p += gear.faulds(b, f["metal"], 1, trim=f["accent"])
    p += gear.pauldrons(b, f["metal"], 1.3, trim=f["accent"])
    p += gear.belt(b, palette.LEATHER, buckle=f["accent"])
    p += gear.helm_sallet(b, f["metal"], trim=f["accent"], plume=TW)
    p += gear.bracers(b, palette.LEATHER)
    p += gear.in_hand(b, gear.sword(0.44, steel=palette.STEEL, guard=f["accent"]), "R")
    p += gear.on_forearm(b, gear.shield_round(TW, f["accent"], gear.emblem("cats", f["accent"], 1.25), r=0.16, boss=False))
    return spec(b, p, style="sword", shield=True)


@unit("cat_crossbow", "cats", "Арбалетчик-сиамец", "ranged")
def cat_crossbow():
    f = F("cats")
    b = body_for("cat", fur="siamese", extras={"iris": "#6fc0f0", "brow_angle": -14, "lid": 0.4})
    p = beast.fur_body(b, sleeve="#4a5470", boots=palette.LEATHER)
    p += tunic(b, TW, mat="team", flare=0.3, trim=f["accent"], trim_mat="metal")
    p.append(gear.front_panel(b, b.neck_z - 0.03, b.hip_h + 0.0, 0.11, "#4a5470", "cloth",
                              tip="straight", inflate=1.13))
    p += gear.belt(b, palette.LEATHER, buckle=f["metal"], pouch=palette.LEATHER)
    p += gear.cap(b, "#2c3352", feather=f["accent"], mat="cloth", tilt=16)
    p += gear.in_hand(b, gear.crossbow(steel=f["metal"]), "R", scale=1.3)
    p += gear.on_hip(b, [geo.cyl(0.04, 0.16, 8, color=palette.LEATHER).tf((0, 0, -0.1))], "L",
                     rot=(0, 15, 0))
    return spec(b, p, style="crossbow")


@unit("cat_assassin", "cats", "Чёрный кот-ассасин", "elite")
def cat_assassin():
    f = F("cats")
    b = body_for("cat", fur="black", extras={"iris": "#f0c419", "brow_angle": -26, "lid": 0.65, "fangs": True})
    dark = "#262838"
    p = beast.fur_body(b, sleeve=dark, boots="#1c1c26")
    p += tunic(b, dark, flare=0.4, z_bot=b.hip_h - 0.12)
    p += gear.hood(b, "#2d3150", mat="cloth", open_face=0.72)
    p += gear.scarf(b, TW)
    p += gear.belt(b, "#3b2a24", buckle=f["metal"], pouch="#3b2a24")
    p += gear.bracers(b, "#3b2a24")
    p += gear.in_hand(b, gear.dagger(0.26), "R", scale=1.3)
    p += gear.in_hand(b, gear.dagger(0.26), "L", scale=1.3)
    return spec(b, p, style="dagger2", special="groom")


@unit("cat_hero_murena", "cats", "Герцогиня Мурена Когтистая", "hero")
def cat_hero_murena():
    f = F("cats")
    b = body_for("cat", fur="white_cat", scale=1.22, extras={"iris": "#5fd0f0", "brow_angle": -14, "lid": 0.35})
    p = beast.fur_body(b, sleeve=f["metal"], boots="#2c3352")
    p += tunic(b, "#2c3352", flare=0.45, z_bot=b.hip_h - 0.15)
    p += gear.cuirass(b, f["metal"])
    p.append(gear.front_panel(b, b.neck_z - 0.04, b.hip_h - 0.14, 0.09, TW, "team", tip="point",
                              inflate=1.2))
    p += gear.pauldrons(b, f["metal"], 1.45, trim=palette.GOLD, spikes=True)
    p += gear.cape(b, TW, collar="#f6f2ea")
    p += gear.belt(b, "#2c3352", buckle=palette.GOLD)
    p += gear.crown(b, gold="#dfe6ee", gem="#3aa0e0", points=5, h=0.06, r_scale=0.62)
    p += gear.in_hand(b, gear.sabre(0.52, guard=palette.GOLD), "R")
    return spec(b, p, style="sabre", special="proud", hero=True)


# ===========================================================================
# DOGS — Пёсья Марка
# ===========================================================================

@unit("dog_worker", "dogs", "Щенок-оруженосец", "worker")
def dog_worker():
    f = F("dogs")
    b = body_for("dog", fur="beagle", scale=0.84, head_r=(0.215, 0.2, 0.21), eye_size=1.12,
                 extras={"dog": "beagle", "ears": "floppy", "brow_angle": 8, "tongue": True})
    p = beast.fur_body(b, sleeve=f["cloth"])
    p += tunic(b, f["cloth"], flare=0.25)
    p.append(gear.front_panel(b, b.neck_z - 0.04, b.hip_h - 0.1, 0.1, palette.LEATHER, "body",
                              tip="round", inflate=1.12))
    p += gear.belt(b, "#5a3a22", pouch="#7a4b2a")
    p += gear.collar(b, "#a33a2a", tag=palette.GOLD)
    p += gear.in_hand(b, gear.hammer(), "R")
    return spec(b, p, style="tool", worker=True)


@unit("dog_halberdier", "dogs", "Овчарка-алебардщик", "infantry")
def dog_halberdier():
    f = F("dogs")
    b = body_for("dog", fur="shepherd", extras={"dog": "shepherd", "brow_angle": -22, "lid": 0.55, "fangs": True})
    mail = "#8d929a"
    p = beast.fur_body(b, sleeve=mail, boots=palette.LEATHER)
    p += tunic(b, mail, mat="metal", flare=0.3)
    p.append(gear.front_panel(b, b.neck_z - 0.02, b.hip_h - 0.1, 0.12, TW, "team", tip="straight",
                              inflate=1.17))
    p.append(gear.front_panel(b, b.neck_z - 0.02, b.hip_h - 0.1, 0.12, TW, "team", tip="straight",
                              inflate=1.17, side=1))
    p += gear.chest_emblem(b, "dogs", palette.GOLD, inflate=1.17)
    p += gear.belt(b, palette.LEATHER, buckle=f["metal"])
    p += gear.helm_nasal(b, f["metal"], trim=palette.mul(f["metal"], 0.75), aventail=mail)
    p += gear.pauldrons(b, f["metal"], 1.3, trim=palette.mul(f["metal"], 0.7))
    p += gear.in_hand(b, gear.halberd(), "R", scale=1.2)
    return spec(b, p, style="thrust")


@unit("dog_archer", "dogs", "Лучник-гончая", "ranged")
def dog_archer():
    f = F("dogs")
    b = body_for("dog", fur="beagle", extras={"dog": "hound", "ears": "floppy", "brow_angle": -16, "lid": 0.45})
    p = beast.fur_body(b, sleeve=f["cloth"], boots=palette.LEATHER)
    p += tunic(b, f["cloth"], flare=0.3)
    p.append(gear.front_panel(b, b.neck_z - 0.04, b.hip_h + 0.0, 0.12, palette.LEATHER, "body",
                              tip="straight", inflate=1.13))
    p += gear.hood(b, TW, mat="team", open_face=0.85, mantle=True)
    p += gear.belt(b, "#5a3a22", buckle=f["metal"])
    p += gear.backpack(b, palette.LEATHER, kind="quiver")
    p += gear.bracers(b, palette.LEATHER)
    p += gear.in_hand(b, gear.longbow(), "L", scale=1.15)
    return spec(b, p, style="bow")


@unit("dog_bulldog_guard", "dogs", "Бульдог-гвардеец", "elite")
def dog_bulldog_guard():
    f = F("dogs")
    b = body_for("dog", fur="bulldog", scale=1.06, chest=1.18, torso_w=0.34, belly=1.1,
                 head_r=(0.22, 0.2, 0.2), extras={"dog": "bulldog", "ears": "rose", "brow_angle": -28, "lid": 0.7, "fangs": True})
    p = beast.fur_body(b, sleeve=f["metal"], boots=palette.mul(f["metal"], 0.8))
    p += tunic(b, f["cloth"], flare=0.3)
    p += gear.cuirass(b, f["metal"], inflate=1.13)
    p += gear.faulds(b, f["metal"], 2, trim=palette.GOLD)
    p += gear.pauldrons(b, f["metal"], 1.6, trim=palette.GOLD, spikes=True)
    p += gear.collar(b, "#3a2a20", spikes=palette.STEEL)
    p += gear.helm_great(b, f["metal"], crest=TW)
    p += gear.in_hand(b, gear.mace(f["metal"], size=1.6), "R", scale=1.3)
    p += gear.on_forearm(b, gear.shield_heater(TW, palette.GOLD, gear.emblem("dogs", palette.GOLD, 1.1),
                                               w=0.32, h=0.4), out_offset=0.06)
    return spec(b, p, style="mace", shield=True)


@unit("dog_hero_rex", "dogs", "Король Рекс Верный", "hero")
def dog_hero_rex():
    f = F("dogs")
    b = body_for("dog", fur="golden", scale=1.22, chest=1.12,
                 extras={"dog": "hound", "ears": "floppy", "brow_angle": -16, "lid": 0.4, "fangs": True})
    p = beast.fur_body(b, sleeve=f["metal"], boots=palette.mul(f["metal"], 0.8))
    p += tunic(b, f["cloth"], flare=0.4, z_bot=b.hip_h - 0.14)
    p += gear.cuirass(b, f["metal"])
    p.append(gear.front_panel(b, b.neck_z - 0.05, b.hip_h - 0.14, 0.1, TW, "team", tip="point",
                              inflate=1.2))
    p += gear.pauldrons(b, f["metal"], 1.6, trim=palette.GOLD)
    p += gear.cape(b, TW, collar="#f2e6cc")
    p += gear.belt(b, palette.LEATHER, buckle=palette.GOLD)
    p += gear.crown(b, points=5, h=0.075, r_scale=0.66)
    p += gear.in_hand(b, gear.sword(0.55, 0.07, guard=palette.GOLD), "R")
    p += gear.on_forearm(b, gear.shield_heater(TW, palette.GOLD, gear.emblem("dogs", palette.GOLD, 1.0)))
    return spec(b, p, style="sword", shield=True, special="proud", hero=True)


# ===========================================================================
# HAMSTERS — Защёчная Республика
# ===========================================================================

@unit("ham_worker", "hamsters", "Хомяк-носильщик", "worker")
def ham_worker():
    f = F("hamsters")
    b = body_for("hamster", fur="golden_ham", scale=0.95, extras={"brow_angle": 6})
    p = beast.fur_body(b)
    p += tunic(b, "#d9b26f", flare=0.2, z_bot=b.hip_h - 0.05)
    p += gear.bandana(b, TW)
    p += gear.backpack(b, "#d8c08a", kind="sack", size=1.15)
    p += gear.belt(b, palette.LEATHER)
    p += gear.in_hand(b, gear.pickaxe(), "R")
    return spec(b, p, style="tool", worker=True)


@unit("ham_militia", "hamsters", "Ополченец с вилкой", "infantry")
def ham_militia():
    f = F("hamsters")
    b = body_for("hamster", fur="white_ham", extras={"brow_angle": -20, "lid": 0.45})
    p = beast.fur_body(b, sleeve="#d9b26f")
    gam = tunic(b, "#d9b26f", flare=0.25)
    gam[0].paint(geo.stripes(palette.mul("#d9b26f", 0.82), axis=2, freq=110, width=0.2))
    p += gam
    p.append(gear.front_panel(b, b.neck_z - 0.05, b.hip_h - 0.06, 0.1, TW, "team", tip="straight",
                              inflate=1.12))
    p += gear.belt(b, palette.LEATHER)
    p += gear.helm_kettle(b, f["metal"], brim=1.12)
    p += gear.in_hand(b, gear.pitchfork(), "R", scale=1.15)
    p += gear.on_forearm(b, gear.pot_lid(), out_offset=0.07)
    p += gear.pauldrons(b, palette.LEATHER, 1.1, trim="#5a3a22", layers=1, rivets=True)
    return spec(b, p, style="thrust", shield=False)


@unit("ham_slinger", "hamsters", "Пращник с семечками", "ranged")
def ham_slinger():
    f = F("hamsters")
    b = body_for("hamster", fur="golden_ham", extras={"brow_angle": -14, "lid": 0.35})
    p = beast.fur_body(b)
    p += tunic(b, TW, mat="team", flare=0.2, z_bot=b.hip_h - 0.05)
    p += gear.bandana(b, "#efe6cf", mat="cloth")
    p += gear.belt(b, palette.LEATHER, pouch="#e9d6a0")
    p += gear.in_hand(b, gear.sling(), "R")
    return spec(b, p, style="sling")


@unit("ham_barrel", "hamsters", "Хомяк-тяжеловес в бочке-доспехе", "elite")
def ham_barrel():
    f = F("hamsters")
    b = body_for("hamster", fur="golden_ham", scale=1.1, belly=1.3, extras={"brow_angle": -26, "lid": 0.65})
    p = beast.fur_body(b)
    # barrel armour: staves + copper hoops
    z0, z1 = b.hip_h - 0.08, b.neck_z - 0.02
    prof = []
    for i in range(9):
        t = i / 8
        r = 0.21 * (1 + 0.16 * np.sin(np.pi * t))
        prof.append((r, z0 + (z1 - z0) * t))
    bar = geo.lathe(prof, 16, color=palette.WOOD)
    bar.paint(geo.stripes(palette.WOOD_DARK, axis=0, freq=70, width=0.12))
    bar.V[:, 1] *= 0.92
    from .rig import blend_weights
    blend_weights(bar, "hips", "chest", b.hip_h, b.hip_h + b.torso_h * 0.6)
    p.append(bar)
    for t, k in ((0.1, 1.0), (0.5, 1.16), (0.9, 1.0)):
        z = z0 + (z1 - z0) * t
        hp = geo.lathe([(0.21 * k * 1.03, z - 0.016), (0.21 * k * 1.06, z), (0.21 * k * 1.03, z + 0.016)],
                       16, cap_bottom=False, cap_top=False, color=f["metal"])
        hp.V[:, 1] *= 0.92
        blend_weights(hp, "hips", "chest", b.hip_h, b.hip_h + b.torso_h * 0.6)
        hp.mat = "metal"
        p.append(hp)
    p.append(gear.front_panel(b, b.neck_z - 0.08, b.hip_h + 0.02, 0.07, TW, "team", tip="point",
                              inflate=1.45))
    p += gear.helm_kettle(b, f["metal"], brim=1.12, plume=TW)
    p += gear.pauldrons(b, f["metal"], 1.3, trim=palette.GOLD, layers=1)
    p += gear.in_hand(b, gear.hammer(size=1.9, mallet=True), "R")
    return spec(b, p, style="mace")


@unit("ham_hero_puhloshek", "hamsters", "Магистр Пухлощёк", "hero")
def ham_hero_puhloshek():
    f = F("hamsters")
    b = body_for("hamster", fur="golden_ham", scale=1.22, belly=1.4, extras={"brow_angle": -4})
    p = beast.fur_body(b, sleeve=TW)
    robe = gear.garment(b, 0.03, b.neck_z - 0.01, TW, "team", inflate=1.07, flare=0.35)
    p.append(robe)
    p.append(gear.band(b, 0.045, palette.GOLD, "metal", 0.014, 1.07 * 1.36, bone="hips"))
    p.append(gear.front_panel(b, b.neck_z - 0.03, 0.04, 0.035, palette.GOLD, "metal", tip="straight",
                              inflate=1.1, depth=0.008))
    p += gear.belt(b, "#6b3a1e", buckle=palette.GOLD, pouch=palette.GOLD)
    # chain of office
    z = b.neck_z - 0.04
    rx, ry = beast.torso_r(b, z)
    ch = geo.tube(geo.bezier((-rx * 0.8, -ry * 0.4, z + 0.02), (0, -ry * 1.4, z - 0.12),
                             (rx * 0.8, -ry * 0.4, z + 0.02), n=10), 0.01, 6, color=palette.GOLD)
    ch.mat = "metal"
    ch.bone = "chest"
    p.append(ch)
    p.append(geo.disc(0.035, 0.012, 12, palette.GOLD).tf((0, -ry * 1.25, z - 0.09)).on("chest", "metal"))
    p += gear.merchant_hat(b, TW)
    p += gear.in_hand(b, gear.staff(top=gear.wheel_topper()), "R")
    return spec(b, p, style="staff", special="stuff", hero=True)


# ===========================================================================
# HARES — Длинноухое Княжество
# ===========================================================================

@unit("hare_worker", "hares", "Крольчонок-огородник", "worker")
def hare_worker():
    f = F("hares")
    b = body_for("hare", fur="brown_hare", scale=0.82, head_r=(0.2, 0.2, 0.21), eye_size=1.12,
                 extras={"brow_angle": 6})
    p = beast.fur_body(b, sleeve="#efe9dc")
    p += tunic(b, "#efe9dc", flare=0.2)
    p.append(gear.front_panel(b, b.neck_z - 0.06, b.hip_h - 0.1, 0.11, "#5a7fa8", "cloth",
                              tip="straight", inflate=1.12))
    p += gear.belt(b, palette.LEATHER)
    p += gear.straw_hat(b, band_c=palette.FACTIONS["hares"]["team"])
    p += gear.in_hand(b, gear.hoe(), "R")
    return spec(b, p, style="tool", worker=True)


@unit("hare_spearman", "hares", "Копейщик-русак", "infantry")
def hare_spearman():
    f = F("hares")
    b = body_for("hare", fur="brown_hare", extras={"brow_angle": -22, "lid": 0.5})
    p = beast.fur_body(b, sleeve=TW, boots="#7a2a1e")
    kaftan = gear.garment(b, b.hip_h - 0.13, b.neck_z - 0.01, TW, "team", inflate=1.06, flare=0.35)
    p.append(kaftan)
    p.append(gear.band(b, b.hip_h - 0.12, f["accent"], "cloth", 0.012, 1.06 * 1.33, bone="hips"))
    p.append(gear.front_panel(b, b.neck_z - 0.02, b.hip_h - 0.12, 0.03, f["accent"], "cloth",
                              tip="straight", inflate=1.1, depth=0.008))
    p += gear.belt(b, palette.LEATHER, buckle=palette.GOLD)
    p += gear.helm_shishak(b, f["metal"], trim=palette.GOLD)
    p += gear.pauldrons(b, f["metal"], 1.15, trim=palette.GOLD, layers=2)
    p += gear.in_hand(b, gear.spear(tassel=TW), "R", scale=1.15)
    p += gear.on_forearm(b, gear.shield_kite(TW, palette.GOLD, gear.emblem("hares", f["accent"], 1.0)))
    return spec(b, p, style="thrust", shield=True)


@unit("hare_archer", "hares", "Лучник-беляк", "ranged")
def hare_archer():
    f = F("hares")
    b = body_for("hare", fur="white_hare", extras={"brow_angle": -16, "lid": 0.4})
    p = beast.fur_body(b, sleeve=TW, boots="#7a2a1e")
    p += tunic(b, TW, mat="team", flare=0.3, trim=f["accent"], trim_mat="cloth")
    p += gear.belt(b, palette.LEATHER, buckle=palette.GOLD)
    p += gear.fur_hat(b, TW)
    p += gear.backpack(b, "#7a2a1e", kind="quiver")
    p += gear.in_hand(b, gear.longbow(wood="#c9a26a", recurve=True, length=0.8), "L")
    return spec(b, p, style="bow")


@unit("hare_vityaz", "hares", "Князь-витязь", "elite")
def hare_vityaz():
    f = F("hares")
    b = body_for("hare", fur="brown_hare", scale=1.08, chest=1.08, extras={"brow_angle": -24, "lid": 0.6})
    p = beast.fur_body(b, sleeve=f["metal"], boots="#7a2a1e")
    p += tunic(b, TW, mat="team", flare=0.35, z_bot=b.hip_h - 0.13)
    sc = gear.cuirass(b, f["metal"], ridge=False)
    sc[0].paint(geo.stripes(palette.mul(f["metal"], 0.7), axis=2, freq=150, width=0.22))
    p += sc
    p += gear.pauldrons(b, f["metal"], 1.45, trim=palette.GOLD)
    p += gear.cape(b, TW, collar=palette.GOLD)
    p += gear.belt(b, palette.LEATHER, buckle=palette.GOLD)
    p += gear.helm_shishak(b, palette.GOLD, trim=f["metal"], plume=TW)
    p += gear.in_hand(b, gear.sword(0.48, guard=palette.GOLD), "R")
    p += gear.on_forearm(b, gear.shield_round(TW, palette.GOLD, gear.emblem("hares", palette.GOLD, 1.0)))
    return spec(b, p, style="sword", shield=True)


@unit("hare_hero_belyana", "hares", "Княгиня Беляна", "hero")
def hare_hero_belyana():
    f = F("hares")
    b = body_for("hare", fur="white_hare", scale=1.22, extras={"brow_angle": -14, "lid": 0.3})
    p = beast.fur_body(b, sleeve=TW, boots="#7a2a1e")
    dress = gear.garment(b, 0.04, b.neck_z - 0.01, TW, "team", inflate=1.06, flare=0.5)
    p.append(dress)
    p.append(gear.band(b, 0.055, palette.GOLD, "metal", 0.014, 1.06 * 1.5, bone="hips"))
    p.append(gear.front_panel(b, b.neck_z - 0.02, 0.05, 0.045, palette.GOLD, "metal", tip="straight",
                              inflate=1.1, depth=0.008))
    p += gear.cape(b, "#f6f2ea", mat="cloth", collar="#ffffff")
    p += gear.kokoshnik(b, TW)
    p += gear.in_hand(b, gear.sabre(0.5, guard=palette.GOLD, grip="#7a2a1e"), "R")
    return spec(b, p, style="sabre", special="proud", hero=True)


# ===========================================================================
# RATS — Крысиная Чума (AI only)
# ===========================================================================

@unit("rat_raider", "rats", "Крыса-оборванец", "infantry")
def rat_raider():
    f = F("rats")
    b = body_for("rat", extras={"brow_angle": -28, "lid": 0.6})
    rag = "#6a6150"
    p = beast.fur_body(b, sleeve=None)
    t = tunic(b, rag, flare=0.35)
    t[0].paint(geo.patch((0.06, -0.1, b.hip_h + 0.1), 0.06, "#4e463a", 0.3))
    t[0].paint(geo.patch((-0.08, -0.05, b.hip_h - 0.03), 0.05, "#7e7558", 0.3))
    t[0].deform(lambda V: V + np.column_stack([np.zeros(len(V)), np.zeros(len(V)),
                                               0.02 * np.sin(V[:, 0] * 60) * (V[:, 2] < b.hip_h - 0.05)]))
    p += t
    p += gear.hood(b, TW, mat="team", open_face=0.8, mantle=False)
    p += gear.belt(b, "#3a2e22", buckle=f["metal"])
    p += gear.in_hand(b, gear.cleaver(), "R", scale=1.35)
    p += gear.pauldrons(b, "#7a6a58", 1.2, trim="#8b4a2a", layers=1, spikes=True)[:4]
    return spec(b, p, style="sword", posture=16)


@unit("rat_plague_doctor", "rats", "Чумной лекарь", "support")
def rat_plague_doctor():
    f = F("rats")
    b = body_for("rat", extras={"brow_angle": -26, "lid": 0.55, "glow": "#c8ff4a"})
    coat = "#3a3530"
    p = beast.fur_body(b, sleeve=coat)
    p.append(gear.garment(b, 0.04, b.neck_z - 0.01, coat, "cloth", inflate=1.06, flare=0.45))
    p += gear.belt(b, "#2a2420", buckle=f["metal"], pouch="#5a4a32")
    p += gear.beak_mask(b)
    p += gear.wide_hat(b, "#2a2622")
    p += gear.scarf(b, TW, tails=True)
    p += gear.in_hand(b, gear.staff(wood="#3a2a1e", length=1.0), "R")
    p += gear.in_hand(b, gear.lantern(), "L", rot=(0, 0, 0))
    return spec(b, p, style="lantern", posture=12)


@unit("rat_king", "rats", "Крыса-Король", "boss")
def rat_king():
    f = F("rats")
    b = body_for("rat", scale=2.1, belly=1.3, torso_w=0.31, chest=1.1,
                 extras={"brow_angle": -30, "lid": 0.7, "glow": "#d6ff3a"})
    p = beast.fur_body(b, sleeve=None)
    p += tunic(b, "#4a4436", flare=0.35)
    p += gear.cuirass(b, f["metal"], inflate=1.1)
    p += gear.pauldrons(b, f["metal"], 1.6, trim="#5a3a28", spikes=True)
    p += gear.cape(b, TW, collar="#5a5040")
    p += gear.crown(b, gold="#9a8a3a", gem="#9adf2a", points=7, h=0.09, r_scale=0.66, tilt=-10)
    p += gear.in_hand(b, gear.cleaver(), "R", scale=1.7)
    return spec(b, p, style="sword", posture=18, special="scheme", hero=True)
