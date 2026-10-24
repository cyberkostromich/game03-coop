"""Shared color palette for the Animal Kingdoms art set.

Colors are authored in sRGB hex (what an artist picks) and converted to
linear floats for vertex colors / glTF.
"""
import numpy as np


def srgb_to_linear(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rgb(c):
    """'#rrggbb' | (r, g, b) in sRGB 0..1 | np.ndarray(linear) -> linear rgb."""
    if isinstance(c, np.ndarray):
        return c[:3].astype(float)
    if isinstance(c, str):
        c = c.lstrip("#")
        c = tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return srgb_to_linear(c[:3])


def linear_to_hex(c):
    c = np.clip(np.asarray(c, float), 0, 1)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
    return "#" + "".join(f"{int(round(v * 255)):02x}" for v in np.clip(s, 0, 1))


def mix(a, b, t):
    """Blend two colors (linear space); returns a hex string."""
    return linear_to_hex(rgb(a) * (1 - t) + rgb(b) * t)


def mul(a, k):
    """Scale a color's linear value; returns a hex string."""
    return linear_to_hex(rgb(a) * k)


# --- Faction palettes (Design System D10) --------------------------------
FACTIONS = {
    "cats": {  # Котовое Герцогство Когтеград: night blue + silver + copper
        "team": "#2b3f8f", "team_dark": "#1a2554", "metal": "#b9c2cf",
        "accent": "#c4793a", "cloth": "#33406e", "leather": "#5b3a2a",
        "wood": "#6b4a33", "roof": "#2c3a78", "stone": "#9aa1ad",
    },
    "dogs": {  # Пёсья Марка: dark green + bronze + leather
        "team": "#2f6b3a", "team_dark": "#1c4224", "metal": "#b38a4a",
        "accent": "#d4a64a", "cloth": "#3d5a35", "leather": "#7a4b2a",
        "wood": "#73502f", "roof": "#3a6e3c", "stone": "#a39e8e",
    },
    "hamsters": {  # Защёчная Республика: wheat + terracotta + copper
        "team": "#c0592f", "team_dark": "#82361b", "metal": "#c98a52",
        "accent": "#e9c46a", "cloth": "#d9b26f", "leather": "#8a5a32",
        "wood": "#8b6239", "roof": "#c46a3a", "stone": "#b5a58a",
    },
    "hares": {  # Длинноухое Княжество: white + cranberry + birch
        "team": "#a3243b", "team_dark": "#651526", "metal": "#d6d2c4",
        "accent": "#e8d9a8", "cloth": "#efe9dc", "leather": "#7b5236",
        "wood": "#c9b99a", "roof": "#a3243b", "stone": "#e3ded1",
    },
    "rats": {  # Крысиная Чума: rotten green + rust + dirty grey
        "team": "#6f8a2a", "team_dark": "#3e4d18", "metal": "#8b5a3c",
        "accent": "#a9c23f", "cloth": "#5e5a4c", "leather": "#4a3a2a",
        "wood": "#5a4632", "roof": "#4e4b3c", "stone": "#6e6a5e",
    },
}

# Player colors (colorblind-separable set, team-colored parts are tinted)
PLAYERS = ["#2f6fd6", "#d63a2f", "#2fae5a", "#e3b22b", "#8a3fd1", "#2bbfc4",
           "#e07a2f", "#d65aa8"]

# --- Fur ----------------------------------------------------------------
FUR = {
    "ginger": ("#e08a3c", "#f6dcb5", "#b8602a"),      # base, light (belly), dark (stripes)
    "siamese": ("#efe1c8", "#fbf3e4", "#5a3f33"),
    "black": ("#2a2830", "#4a4652", "#18161c"),
    "grey_tabby": ("#8c8f99", "#e3e1dc", "#55575f"),
    "white_cat": ("#f2efe9", "#ffffff", "#c9c2b8"),
    "shepherd": ("#c78a4a", "#f0d2a2", "#2e2622"),
    "beagle": ("#c27b3e", "#f6f0e6", "#2f2622"),
    "bulldog": ("#d9b48a", "#f7eee2", "#8b6a4f"),
    "mastiff": ("#a8794e", "#d8b58c", "#3b2a20"),
    "golden": ("#d9a35a", "#f5e2b8", "#a8743a"),
    "golden_ham": ("#e7a95b", "#fbf0dc", "#b9773a"),
    "white_ham": ("#f4efe6", "#ffffff", "#d9cfc2"),
    "brown_hare": ("#a77b52", "#efe2cc", "#6e4d33"),
    "white_hare": ("#f3f1ec", "#ffffff", "#cfd3da"),
    "rat": ("#7a7068", "#b3a99c", "#4a423c"),
}

SKIN_PINK = "#e8a0a0"
NOSE_PINK = "#e07b86"
NOSE_DARK = "#2a2224"
EYE_DARK = "#17131a"
EYE_WHITE = "#fbfbf7"
GOLD = "#e8b84a"
IRON = "#9aa3ad"
STEEL = "#c4ccd6"
DARK_IRON = "#4a4f57"
WOOD = "#7a5232"
WOOD_DARK = "#4e3320"
LEATHER = "#6e4528"
ROPE = "#c9a86a"
STRAW = "#e2c36b"
CARROT = "#f07a1f"
LEAF = "#5aa13a"
