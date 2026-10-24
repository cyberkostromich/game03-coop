"""Aggregate build/clip/*.txt into the most common gear intersection pairs."""
import collections
import glob
import re

pairs, weight, ex = collections.Counter(), collections.Counter(), {}
total = 0
for f in glob.glob("build/clip/*.txt"):
    uid = f.split("/")[-1][:-4]
    for line in open(f):
        m = re.match(r"CLIP\s+(\d+)\s+(\S+)\s+x\s+(\S+)\s+worst in (\S+)", line)
        if m:
            n, a, b, w = int(m.group(1)), m.group(2), m.group(3), m.group(4)
            key = tuple(sorted((re.sub(r"\.[LR]$", ".*", a), re.sub(r"\.[LR]$", ".*", b))))
            pairs[key] += 1
            weight[key] += n
            total += n
            ex.setdefault(key, []).append((n, uid, w))
print("TOTAL intersecting triangles (worst frames):", total)
for key, c in sorted(pairs.items(), key=lambda x: -weight[x[0]])[:30]:
    top = sorted(ex[key], reverse=True)[:3]
    print(f"{weight[key]:6d} {c:3d}  {key[0]:14s} x {key[1]:14s}  {top}")
