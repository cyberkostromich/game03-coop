"""Pack the map PNGs into raw little-endian binaries the web client reads
without colour-management surprises: heights as uint16, pathing as uint8.
Rows stay north-up like the PNGs."""
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
name = sys.argv[1] if len(sys.argv) > 1 else "mill_pond"
d = os.path.join(ROOT, "assets", "animal_kingdoms", "maps")
h = np.array(Image.open(os.path.join(d, f"{name}_height.png"))).astype("<u2")
p = (np.array(Image.open(os.path.join(d, f"{name}_path.png"))) > 127).astype(np.uint8)
h.tofile(os.path.join(d, f"{name}_height.bin"))
p.tofile(os.path.join(d, f"{name}_path.bin"))
print(name, h.shape, h.dtype, h.min(), h.max(), "walkable", p.mean())
