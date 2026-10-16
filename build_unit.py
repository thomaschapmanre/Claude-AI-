"""Unit Type F (2 bed / 2 bath) - procedural Blender build.

Run:  blender --background --python build_unit.py      (or: python3 build_unit.py with `pip install bpy`)
      add `-- --render` after the script to also make preview renders.
Plan coords in feet: x = east, z = south (north = balcony), y = up. Floor at y=0, ceiling 9 ft.
Outputs: out/unit.blend, docs/unit.glb, docs/collision.json, out/render_*.png
"""
import bpy, math, json, os, sys, random
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT, WEB = os.path.join(HERE, "out"), os.path.join(HERE, "docs")
FT = 0.3048
T = 0.35          # wall thickness
H = 9.0           # ceiling
DH = 6.8          # door head
random.seed(7)

# ---------------------------------------------------------------- textures
def tex_lvp(n=512):    # 8 planks (0.6 ft) across 4.8 ft, grain along v
    img = np.zeros((n, n, 3)); pw = n // 8
    for i in range(8):
        off = random.randint(0, n)
        for seg in range(3):
            s0 = (off + seg * n // 2) % n
            tone = np.array([0.42, 0.33, 0.26]) * random.uniform(0.93, 1.07)
            rows = (np.arange(n // 2) + s0) % n
            u = np.arange(pw)
            grain = 0.06 * np.sin(u[None, :] * random.uniform(0.3, 0.9) + rows[:, None] * 0.02 + random.random() * 6)
            img[rows, i * pw:(i + 1) * pw] = tone * (1 + grain[..., None] + np.random.normal(0, 0.015, (n // 2, pw, 1)))
            img[s0, i * pw:(i + 1) * pw] *= 0.8
        img[:, i * pw] *= 0.8
    return img

def tex_noise(base, amp, n=256):
    return np.array(base) * (1 + np.random.normal(0, amp, (n, n, 1)))

def tex_granite(n=512):
    img = np.ones((n, n, 3)) * 0.87 + np.random.normal(0, 0.02, (n, n, 1))
    for col, cnt, r in [((0.45, 0.45, 0.46), 5000, 4), ((0.12, 0.12, 0.13), 3000, 3), ((0.62, 0.55, 0.48), 1500, 3)]:
        ys, xs = np.random.randint(0, n, cnt), np.random.randint(0, n, cnt)
        for d in range(r):
            img[(ys + d) % n, xs] = col; img[ys, (xs + d) % n] = col
    return img

def tex_subway(n=384):  # 3" x 6" tiles, 1.5 ft repeat
    img = np.ones((n, n, 3)) * 0.95
    th, tw = n // 6, n // 3
    for r in range(6):
        img[r * th:r * th + 3] = 0.78
        o = (tw // 2) if r % 2 else 0
        for c in range(4):
            x = (c * tw + o) % n
            img[r * th:(r + 1) * th, x:x + 3] = 0.78
    return img

def tex_deck(n=512):   # 8 boards across 3.6 ft
    img = np.zeros((n, n, 3)); pw = n // 8
    for i in range(8):
        tone = np.array([0.80, 0.66, 0.48]) * random.uniform(0.9, 1.08)
        img[:, i * pw:(i + 1) * pw] = tone * (1 + np.random.normal(0, 0.03, (n, 1, 1)))
        img[:, i * pw:i * pw + 4] = (0.25, 0.2, 0.15)
    return img

def tex_siding(n=512):  # shingle courses 0.6 ft on a 3 ft repeat
    img = np.ones((n, n, 3)) * np.array([0.83, 0.81, 0.75]); ch = n // 5
    for r in range(5):
        img[r * ch:(r + 1) * ch] *= np.linspace(0.85, 1.0, ch)[:, None, None]
        x = 0
        while x < n:
            img[r * ch:(r + 1) * ch, x:x + 2] *= 0.8
            x += random.randint(25, 70)
    return img + np.random.normal(0, 0.01, (n, n, 1))

# ---------------------------------------------------------------- materials
# name: (rgb, roughness, metallic, texture fn, tile ft, alpha, emission)
MATS = {
    "wall":      ((0.89, 0.86, 0.80), 0.9, 0, None, 0, 1, 0),
    "accent":    ((0.29, 0.27, 0.25), 0.9, 0, None, 0, 1, 0),
    "ceiling":   ((0.93, 0.92, 0.89), 0.95, 0, None, 0, 1, 0),
    "trim":      ((0.62, 0.58, 0.52), 0.5, 0, None, 0, 1, 0),   # greige/taupe trim + doors
    "lvp":       ((1, 1, 1), 0.45, 0, tex_lvp, 4.8, 1, 0),
    "carpet":    ((1, 1, 1), 1.0, 0, lambda: tex_noise((0.70, 0.67, 0.62), 0.05), 2, 1, 0),
    "granite":   ((1, 1, 1), 0.25, 0, tex_granite, 2.0, 1, 0),
    "subway":    ((1, 1, 1), 0.15, 0, tex_subway, 1.5, 1, 0),
    "cabinet":   ((0.93, 0.93, 0.91), 0.4, 0, None, 0, 1, 0),
    "steel":     ((0.78, 0.78, 0.79), 0.3, 0.6, None, 0, 1, 0),
    "nickel":    ((0.70, 0.69, 0.67), 0.35, 0.6, None, 0, 1, 0),
    "black":     ((0.03, 0.03, 0.03), 0.2, 0, None, 0, 1, 0),
    "porcelain": ((0.95, 0.95, 0.95), 0.1, 0, None, 0, 1, 0),
    "white":     ((0.95, 0.95, 0.94), 0.5, 0, None, 0, 1, 0),
    "glass":     ((0.85, 0.92, 0.95), 0.05, 0, None, 0, 0.18, 0),
    "mirror":    ((0.72, 0.78, 0.80), 0.05, 0.4, None, 0, 1, 0),
    "bulb":      ((1.0, 0.95, 0.85), 0.5, 0, None, 0, 1, 3.0),
    "deck":      ((1, 1, 1), 0.7, 0, tex_deck, 3.6, 1, 0),
    "siding":    ((1, 1, 1), 0.8, 0, tex_siding, 3.0, 1, 0),
    "grass":     ((0.30, 0.42, 0.20), 1.0, 0, None, 0, 1, 0),
}

# ---------------------------------------------------------------- geometry accumulator (feet, plan coords)
GEO = {m: ([], [], []) for m in MATS}     # verts, faces, uvs-per-loop
COLL = []                                  # [x0,x1,z0,z1] in feet
LIGHTS = []                                # (x,y,z, kind)

def add(mat, verts, faces):
    V, F, U = GEO[mat]; base = len(V); tile = MATS[mat][4] or 4.0
    V.extend(verts)
    for f in faces:
        p = [np.array(verts[i]) for i in f]
        nrm = np.abs(np.cross(p[1] - p[0], p[2] - p[0]))
        ax = int(np.argmax(nrm))
        a, b = {0: (2, 1), 1: (0, 2), 2: (0, 1)}[ax]
        U.append([(q[a] / tile, q[b] / tile) for q in p])
        F.append([base + i for i in f])

QUADS = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]

def box(mat, x0, x1, y0, y1, z0, z1, collide=False):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]
    add(mat, v, QUADS)
    if collide and y0 < 4 and y1 > 0.5:
        COLL.append([x0, x1, z0, z1])

def rbox(mat, hx, hz, ang, l0, l1, w0, w1, y0, y1):
    """Box in a frame rotated `ang` deg about y at (hx,hz): local u along ang, w perpendicular."""
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    pt = lambda u, w, y: (hx + u * c - w * s, y, hz + u * s + w * c)
    v = [pt(l0, w0, y0), pt(l1, w0, y0), pt(l1, w1, y0), pt(l0, w1, y0),
         pt(l0, w0, y1), pt(l1, w0, y1), pt(l1, w1, y1), pt(l0, w1, y1)]
    add(mat, v, QUADS)

def cyl(mat, x, z, y0, y1, r, seg=16, ry=None):
    """Vertical cylinder (or ellipsoid cap when ry given: dome of radius r, height ry from y0 downward)."""
    v, f = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        v += [(x + r * math.cos(a), y0, z + r * math.sin(a)), (x + r * math.cos(a), y1, z + r * math.sin(a))]
    for i in range(seg):
        j = (i + 1) % seg
        f.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
    v += [(x, y0, z), (x, y1, z)]
    for i in range(seg):
        j = (i + 1) % seg
        f += [(2 * i, len(v) - 2, 2 * j), (2 * i + 1, 2 * j + 1, len(v) - 1)]
    add(mat, v, f)

def sphere(mat, x, y, z, r, sy=1.0, seg=12, rings=8):
    v, f = [], []
    for j in range(rings + 1):
        t = math.pi * j / rings
        for i in range(seg):
            a = 2 * math.pi * i / seg
            v.append((x + r * math.sin(t) * math.cos(a), y + r * sy * math.cos(t), z + r * math.sin(t) * math.sin(a)))
    for j in range(rings):
        for i in range(seg):
            a, b = j * seg + i, j * seg + (i + 1) % seg
            f.append((a, b, b + seg, a + seg))
    add(mat, v, f)

# ---------------------------------------------------------------- walls
def wall(x0, z0, x1, z1, openings=(), mat="wall", base=True):
    """Axis-aligned wall on a centerline. openings: (a, b, sill, head) along the wall axis."""
    alongx = z0 == z1
    a0, a1 = sorted((x0, x1) if alongx else (z0, z1))
    c = z0 if alongx else x0
    a0 -= T / 2; a1 += T / 2

    def piece(p0, p1, y0, y1, collide=True):
        if p1 - p0 < 1e-3 or y1 - y0 < 1e-3:
            return
        if alongx:
            box(mat, p0, p1, y0, y1, c - T / 2, c + T / 2, collide)
        else:
            box(mat, c - T / 2, c + T / 2, y0, y1, p0, p1, collide)

    def base_piece(p0, p1):
        if not base or p1 - p0 < 0.05:
            return
        for side in (-1, 1):
            o = c + side * (T / 2 + 0.03)
            if alongx: box("trim", p0, p1, 0, 0.4, o - 0.03, o + 0.03)
            else:      box("trim", o - 0.03, o + 0.03, 0, 0.4, p0, p1)

    cur = a0
    for (a, b, sill, head) in sorted(openings):
        piece(cur, a, 0, H); base_piece(cur, a)
        piece(a, b, 0, sill); piece(a, b, head, H, collide=False)
        if sill > 0:
            base_piece(a, b)
        else:   # door casing on both faces
            for side in (-1, 1):
                o0, o1 = sorted((c + side * T / 2, c + side * (T / 2 + 0.05)))
                for (p0, p1, y0, y1) in [(a - 0.3, a, 0, head + 0.3), (b, b + 0.3, 0, head + 0.3), (a - 0.3, b + 0.3, head, head + 0.3)]:
                    if alongx: box("trim", p0, p1, y0, y1, o0, o1)
                    else:      box("trim", o0, o1, y0, y1, p0, p1)
        cur = b
    piece(cur, a1, 0, H); base_piece(cur, a1)

def window(x0, z0, x1, z1, sill, head):
    """Double-hung vinyl window filling an opening (pass the same span as the wall opening)."""
    alongx = z0 == z1
    c = z0 if alongx else x0
    a, b = (x0, x1) if alongx else (z0, z1)
    def B(m, p0, p1, y0, y1, d0, d1):
        if alongx: box(m, p0, p1, y0, y1, c + d0, c + d1)
        else:      box(m, c + d0, c + d1, y0, y1, p0, p1)
    f = 0.15
    B("white", a, b, sill, sill + f, -0.08, 0.08); B("white", a, b, head - f, head, -0.08, 0.08)
    B("white", a, a + f, sill, head, -0.08, 0.08); B("white", b - f, b, sill, head, -0.08, 0.08)
    mid = (sill + head) / 2
    B("white", a, b, mid - 0.06, mid + 0.06, -0.08, 0.08)
    B("glass", a + f, b - f, sill + f, head - f, -0.01, 0.01)
    B("trim", a - 0.1, b + 0.1, sill - 0.08, sill, -T / 2 - 0.25, T / 2 + 0.25)   # stool / sill

def door(hx, hz, ang, width, collide=True):
    """2-panel door slab, hinge at (hx,hz), swung open toward angle `ang` deg (0=+x east, 90=+z south)."""
    rbox("trim", hx, hz, ang, 0.05, width - 0.05, -0.08, 0.08, 0.02, DH - 0.05)
    for w in (-0.1, 0.1):
        for (y0, y1) in [(0.6, 3.4), (3.9, 6.3)]:
            rbox("trim", hx, hz, ang, 0.35, width - 0.35, w - 0.03, w + 0.03, y0, y1)
        rbox("nickel", hx, hz, ang, width - 0.4, width - 0.25, w * 1.5 - 0.04, w * 1.5 + 0.04, 3.0, 3.1)
    if collide:
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        xe, ze = hx + width * c, hz + width * s
        COLL.append([min(hx, xe) - 0.08, max(hx, xe) + 0.08, min(hz, ze) - 0.08, max(hz, ze) + 0.08])

def floor(mat, x0, x1, z0, z1, top=0.0):
    box(mat, x0, x1, top - 0.1, top, z0, z1)

# ---------------------------------------------------------------- fixtures
def dome(x, z):
    cyl("white", x, z, H - 0.05, H, 0.6)
    sphere("bulb", x, H - 0.05, z, 0.55, sy=0.3)
    LIGHTS.append((x, H - 0.6, z))

def can(x, z):
    cyl("bulb", x, z, H - 0.02, H, 0.3)
    LIGHTS.append((x, H - 0.6, z))

def fan(x, z):
    cyl("nickel", x, z, H - 1.0, H, 0.06)
    cyl("nickel", x, z, H - 1.3, H - 1.0, 0.35)
    sphere("bulb", x, H - 1.3, z, 0.3, sy=0.5)
    for k in range(3):
        rbox("nickel", x, z, k * 120 + 15, 0.3, 2.4, -0.25, 0.25, H - 1.15, H - 1.1)
    LIGHTS.append((x, H - 1.6, z))

def pendant(x, z):
    cyl("black", x, z, 6.4, H, 0.02, seg=6)
    cyl("bulb", x, z, 5.9, 6.4, 0.22)
    LIGHTS.append((x, 5.7, z))

def wire_shelf(x0, x1, z0, z1, y=5.6, rod=True):
    box("white", x0, x1, y - 0.03, y, z0, z1)
    if rod:
        if x1 - x0 > z1 - z0: box("white", x0, x1, y - 0.35, y - 0.3, (z0 + z1) / 2 - 0.03, (z0 + z1) / 2 + 0.03)
        else:                 box("white", (x0 + x1) / 2 - 0.03, (x0 + x1) / 2 + 0.03, y - 0.35, y - 0.3, z0, z1)

def shaker(x0, x1, y0, y1, z0, z1, face, doors=1):
    """White shaker cabinet box; `face` = direction its fronts point: 'n','s','e','w'."""
    box("cabinet", x0, x1, y0, y1, z0, z1, collide=True)
    along = face in "ns"
    a0, a1 = (x0, x1) if along else (z0, z1)
    d = {"n": z0, "s": z1, "w": x0, "e": x1}[face]; sg = -1 if face in "nw" else 1
    w = (a1 - a0) / doors
    for i in range(doors):
        p0, p1 = a0 + i * w + 0.05, a0 + (i + 1) * w - 0.05
        for (q0, q1, r0, r1) in [(p0, p1, y0 + 0.1, y0 + 0.25), (p0, p1, y1 - 0.25, y1 - 0.1), (p0, p0 + 0.2, y0 + 0.1, y1 - 0.1), (p1 - 0.2, p1, y0 + 0.1, y1 - 0.1)]:
            if along: box("cabinet", q0, q1, r0, r1, d, d + sg * 0.05)
            else:     box("cabinet", d, d + sg * 0.05, r0, r1, q0, q1)
        hx = p1 - 0.3 if i % 2 == 0 else p0 + 0.3
        hy = (y1 - 0.6, y1 - 0.15) if y0 < 1 else (y0 + 0.15, y0 + 0.6)
        if along: box("nickel", hx - 0.02, hx + 0.02, hy[0], hy[1], d + sg * 0.05, d + sg * 0.12)
        else:     box("nickel", d + sg * 0.05, d + sg * 0.12, hy[0], hy[1], hx - 0.02, hx + 0.02)

def toilet(x, z, face):
    """face: direction the bowl points ('s','w')."""
    dx, dz = {"s": (0, 1), "w": (-1, 0), "e": (1, 0), "n": (0, -1)}[face]
    tx, tz = x - dx * 0.0, z - dz * 0.0
    if dx: box("porcelain", tx, tx - dx * 0.75, 1.3, 2.7, z - 0.9, z + 0.9, collide=True)
    else:  box("porcelain", x - 0.9, x + 0.9, 1.3, 2.7, tz, tz - dz * 0.75, collide=True)
    bx, bz = x + dx * 1.2, z + dz * 1.2
    cyl("porcelain", bx, bz, 0, 1.25, 0.6)
    COLL.append([bx - 0.6, bx + 0.6, bz - 0.6, bz + 0.6])
    cyl("white", bx, bz, 1.25, 1.33, 0.62)

def vanity_east(xw, z0, z1, ylight=7.0):
    """Vanity against an east wall whose inner face is at xw."""
    shaker(xw - 1.8, xw, 0.3, 2.8, z0, z1, "w", doors=2)
    box("trim", xw - 1.75, xw, 0, 0.3, z0 + 0.05, z1 - 0.05)
    box("granite", xw - 1.9, xw, 2.8, 2.95, z0 - 0.05, z1 + 0.05)
    box("granite", xw - 0.05, xw, 2.95, 3.3, z0, z1)
    box("porcelain", xw - 1.4, xw - 0.6, 2.951, 2.96, (z0 + z1) / 2 - 0.6, (z0 + z1) / 2 + 0.6)
    cyl("nickel", xw - 0.3, (z0 + z1) / 2, 2.95, 3.6, 0.05)
    box("white", xw - 0.1, xw, 3.5, 6.4, z0 + 0.1, z1 - 0.1)       # mirror frame
    box("mirror", xw - 0.12, xw - 0.1, 3.7, 6.2, z0 + 0.3, z1 - 0.3)
    box("nickel", xw - 0.2, xw, ylight - 0.05, ylight + 0.05, (z0 + z1) / 2 - 1.2, (z0 + z1) / 2 + 1.2)
    for k in (-1, 0, 1):
        sphere("bulb", xw - 0.45, ylight - 0.1, (z0 + z1) / 2 + k * 0.95, 0.25)
    LIGHTS.append((xw - 1.2, ylight, (z0 + z1) / 2))

# ---------------------------------------------------------------- build plan
def build():
    S = T / 2
    # floors (LVP in living/kitchen/baths/hall/laundry, carpet in bedrooms+closets)
    for r in [(0, 12.6, 0, 25.8), (0, 13.2, 25.8, 39.5), (0, 4, 39.5, 44), (4, 8, 39.5, 44), (12.6, 19.3, 21.4, 25.8),
              (12.6, 15.1, 0, 6.6), (10.4, 15.1, -4.4, 0), (21.4, 28.4, 6.6, 10.9), (17.9, 28.4, 10.9, 15.3),
              (19.3, 28.4, 15.3, 25.8), (12.6, 19.3, 17.4, 21.4)]:
        floor("lvp", *r)
    for r in [(15.1, 28.4, -4.4, 6.6), (12.6, 21.4, 6.6, 10.9), (12.6, 17.9, 10.9, 15.3), (12.6, 19.3, 15.3, 17.4),
              (13.2, 28.4, 25.8, 35.8), (13.2, 22, 35.8, 41)]:
        floor("carpet", *r, top=0.03)
    floor("deck", 0, 10.4, -5.4, 0)
    box("grass", -200, 200, -11, -10.9, -200, 200)                 # ground, one storey down
    # ceilings
    box("ceiling", 0, 28.4, H, H + 0.2, 0, 44); box("ceiling", 10.4, 28.4, H, H + 0.2, -4.4, 0)
    box("deck", 0, 10.4, H, H + 0.2, -5.4, 0)
    for x in range(1, 11, 2):
        box("deck", x, x + 0.15, H - 0.7, H, -5.4, 0)                # exposed joists

    # exterior walls
    wall(0, 0, 15.1, 0, [(4.0, 10.1, 0, DH + 0.2)])                  # balcony wall + slider
    wall(10.4, -4.4, 10.4, 0, [(-3.6, -1.0, 0, DH)])                 # mech closet (door from balcony)
    wall(10.4, -4.4, 15.1, -4.4)
    wall(15.1, -4.4, 15.1, 6.6, [(2.2, 5.0, 0, DH)])                 # primary bedroom door (from nook)
    wall(15.1, -4.4, 28.4, -4.4, [(17.0, 20.5, 2.5, 7.0), (23.0, 26.5, 2.5, 7.0)])
    wall(28.4, -4.4, 28.4, 41, [(7.8, 9.8, 3.5, 6.8), (15.8, 17.6, 3.5, 6.8), (29.0, 32.0, 2.5, 7.0)])
    wall(0, 0, 0, 44)
    wall(0, 44, 8, 44, [(0.6, 3.6, 0, DH)])                          # front door
    wall(8, 39.5, 8, 44); wall(4, 39.5, 4, 44, [(40.2, 43.2, 0, DH)])   # laundry
    wall(4, 39.5, 13.2, 39.5)                                         # kitchen back
    wall(13.2, 25.8, 13.2, 41)                                        # kitchen | bedroom 2
    wall(13.2, 41, 22, 41); wall(22, 35.8, 22, 41)                   # bedroom 2 closet
    wall(13.2, 35.8, 28.4, 35.8, [(14.0, 16.5, 0, DH)])
    wall(22, 41, 28.4, 41, base=False)
    # interior
    wall(12.6, 6.6, 28.4, 6.6, [(15.5, 17.5, 0, DH), (21.7, 24.4, 0, DH)])
    wall(12.6, 6.6, 12.6, 21.4, [(18.0, 21.0, 0, DH)])               # accent wall w/ double linen doors
    wall(21.4, 6.6, 21.4, 10.9); wall(17.9, 10.9, 21.4, 10.9); wall(17.9, 10.9, 17.9, 15.3)
    wall(17.9, 15.3, 28.4, 15.3); wall(12.6, 17.4, 19.3, 17.4); wall(12.6, 21.4, 19.3, 21.4)
    wall(19.3, 15.3, 19.3, 25.8)
    wall(12.6, 25.8, 28.4, 25.8, [(13.8, 16.6, 0, DH), (22.0, 24.6, 0, DH)])

    # accent paint on living side of x=12.6 wall
    ax = 12.6 - S - 0.01
    for (z0, z1, y0, y1) in [(6.6 + S, 18.0, 0.4, H), (21.0, 21.4 + S, 0.4, H), (18.0, 21.0, DH + 0.3, H)]:
        box("accent", ax - 0.01, ax, y0, y1, z0, z1)
    # siding on balcony faces
    for (x0, x1, y0) in [(0, 4.0, 0), (4.0, 10.1, DH + 0.2), (10.1, 10.4 - S, 0)]:   # skip the slider opening
        box("siding", x0, x1, y0, H, -S - 0.04, -S - 0.01)
    box("siding", 10.4 - S - 0.04, 10.4 - S - 0.01, 0, H, -4.4, -S)
    box("siding", -0.4, -0.1, 0, H, -5.4, 0, collide=True)            # privacy wall (west)

    # windows / slider
    window(17.0, -4.4, 20.5, -4.4, 2.5, 7.0); window(23.0, -4.4, 26.5, -4.4, 2.5, 7.0)
    window(28.4, 7.8, 28.4, 9.8, 3.5, 6.8); window(28.4, 15.8, 28.4, 17.6, 3.5, 6.8); window(28.4, 29.0, 28.4, 32.0, 2.5, 7.0)
    for (a, b) in [(4.0, 4.15), (9.95, 10.1), (6.95, 7.15)]:
        box("white", a, b, 0, DH + 0.2, -0.1, 0.1)
    box("white", 4.0, 10.1, DH + 0.05, DH + 0.2, -0.1, 0.1); box("white", 4.0, 10.1, 0, 0.1, -0.1, 0.1)
    box("glass", 4.15, 6.95, 0.1, DH + 0.05, -0.06, -0.04, collide=True)   # fixed panel
    box("glass", 7.15, 9.95, 0.1, DH + 0.05, 0.04, 0.06)                   # sliding panel (open path shown closed-able)

    # doors (open)
    door(15.1, 5.0, 180, 2.8)                      # primary bed (swings into nook)
    door(15.5, 6.6, 270, 2.0)                      # walk-in closet
    door(24.4, 6.6, 270, 2.7)                      # primary bath
    door(12.6, 18.0, 180, 1.5); door(12.6, 21.0, 180, 1.5)   # linen double doors
    door(13.8, 25.8, 90, 2.8)                      # bedroom 2
    door(24.6, 25.8, 90, 2.6)                      # bath 2 (from bedroom 2)
    door(16.5, 35.8, 270, 2.5)                     # bedroom 2 closet
    door(4.0, 43.2, 180, 3.0)                      # laundry
    door(0.6, 44.0, 270, 3.0)                      # front door
    door(10.4, -1.0, 180, 2.6)                     # mech (out to balcony)

    # balcony railing + posts
    for (px, pz) in [(0.2, -5.2), (10.2, -5.2)]:
        box("white", px - 0.2, px + 0.2, 0, H, pz - 0.2, pz + 0.2, collide=True)
    box("white", 0, 10.4, H - 1.0, H, -5.45, -5.05)                   # header beam
    box("white", 0.4, 10.0, 3.3, 3.5, -5.35, -5.1, collide=True); box("white", 0.4, 10.0, 0.3, 0.45, -5.35, -5.1)
    x = 0.6
    while x < 10.0:
        box("white", x, x + 0.13, 0.45, 3.3, -5.28, -5.15); x += 0.4

    # kitchen: south run, peninsula, appliances (fronts face north/south into the galley)
    box("steel", 4.3, 7.2, 0, 5.8, 36.7, 39.3, collide=True)          # fridge
    for (y0, y1) in [(0.1, 3.4), (3.5, 5.7)]:
        box("steel", 4.4, 7.1, y0, y1, 36.6, 36.7); box("nickel", 6.8, 6.9, y0 + 0.3, y1 - 0.3, 36.45, 36.6)
    shaker(7.2, 9.5, 0.3, 2.95, 37.3, 39.3, "n", doors=2); shaker(12.0, 13.0, 0.3, 2.95, 37.3, 39.3, "n")
    box("trim", 7.25, 9.45, 0, 0.3, 37.4, 39.3); box("trim", 12.05, 13.0, 0, 0.3, 37.4, 39.3)
    for (a, b) in [(7.2, 9.5), (12.0, 13.0)]:
        box("granite", a, b, 2.95, 3.1, 37.2, 39.33)
    box("steel", 9.5, 12.0, 0, 3.05, 37.3, 39.3, collide=True); box("black", 9.55, 11.95, 3.05, 3.1, 37.4, 39.3)
    box("black", 9.8, 11.7, 0.8, 2.2, 37.25, 37.3); box("steel", 9.6, 11.9, 3.05, 3.7, 39.0, 39.3)
    box("steel", 9.5, 12.0, 5.0, 6.4, 37.9, 39.3); box("black", 9.7, 11.3, 5.2, 6.2, 37.85, 37.9)   # OTR microwave
    box("subway", 7.2, 13.0, 3.1, 5.0, 39.3, 39.33)
    shaker(4.3, 7.2, 6.0, 8.0, 37.3, 39.3, "n", doors=2)
    shaker(7.2, 9.5, 5.0, 8.0, 38.1, 39.3, "n", doors=2); shaker(9.5, 12.0, 6.4, 8.0, 38.1, 39.3, "n", doors=2)
    shaker(12.0, 13.0, 5.0, 8.0, 38.1, 39.3, "n")
    # peninsula: cabinets face south (galley side), counter overhangs north toward living for stools
    shaker(11.5, 13.0, 0.3, 7.6, 28.6, 30.6, "s", doors=1)          # tall pantry at wall
    box("trim", 11.55, 13.0, 0, 0.3, 28.6, 30.5)
    shaker(6.0, 9.6, 0.3, 2.95, 28.6, 30.6, "s", doors=2)
    box("trim", 6.05, 11.5, 0, 0.3, 28.6, 30.5)
    box("steel", 9.6, 11.5, 0.3, 2.95, 28.6, 30.65, collide=True)    # dishwasher
    box("granite", 5.9, 11.5, 2.95, 3.1, 27.6, 30.7)
    box("steel", 7.0, 9.0, 3.1, 3.105, 29.0, 30.2)                   # undermount sink
    cyl("nickel", 8.0, 30.45, 3.1, 4.2, 0.06)
    box("subway", 10.0, 11.5, 3.1, 5.0, 28.6, 28.63)
    shaker(10.0, 11.5, 5.0, 7.6, 28.6, 29.8, "s")
    pendant(7.3, 29.3); pendant(9.9, 29.3)

    # primary bath: glass walk-in shower (west), vanity + toilet (east, by window)
    box("white", 17.9 + S, 21.0, 0, 0.4, 10.9 + S, 15.3 - S, collide=True)
    box("white", 17.9 + S, 17.9 + S + 0.05, 0.4, 6.8, 10.9 + S, 15.3 - S)
    box("white", 17.9 + S, 21.0, 0.4, 6.8, 10.9 + S, 10.9 + S + 0.05); box("white", 17.9 + S, 21.0, 0.4, 6.8, 15.3 - S - 0.05, 15.3 - S)
    box("glass", 20.95, 21.0, 0.4, 6.6, 11.1, 15.1, collide=True)
    for zz in (11.1, 13.0, 15.1):
        box("nickel", 20.93, 21.02, 0.4, 6.6, zz - 0.04, zz + 0.04)
    vanity_east(28.4 - S, 11.2, 15.0)
    toilet(28.4 - S, 8.8, "w")
    box("nickel", 26.3, 26.35, 3.0, 3.05, 6.6 + S, 6.6 + S + 0.15)

    # bath 2: tub/shower combo with curved rod (west), toilet, vanity (east)
    tx0, tx1, tz0, tz1 = 19.3 + S, 21.9, 15.3 + S, 20.6
    box("white", tx0, tx1, 0, 1.8, tz0, tz1, collide=True)
    box("porcelain", tx0 + 0.25, tx1 - 0.25, 1.75, 1.81, tz0 + 0.25, tz1 - 0.25)
    for (a, b, c0, c1) in [(tx0, tx0 + 0.05, tz0, tz1), (tx0, tx1, tz0, tz0 + 0.05), (tx0, tx1, tz1 - 0.05, tz1)]:
        box("white", a, b, 1.8, 6.8, c0, c1)
    for i in range(12):
        a0, a1 = math.pi * i / 12, math.pi * (i + 1) / 12
        p = lambda a: (tx1 + 0.5 * math.sin(a), tz0 + (tz1 - tz0) * (1 - math.cos(a)) / 2)
        (x0, z0), (x1, z1) = p(a0), p(a1)
        box("nickel", min(x0, x1) - 0.03, max(x0, x1) + 0.03, 6.5, 6.56, min(z0, z1) - 0.03, max(z0, z1) + 0.03)
    toilet(24.6, 15.3 + S, "s")
    vanity_east(28.4 - S, 19.0, 24.0)

    # closets: wire shelving
    wire_shelf(12.6 + S, 21.4 - S, 6.6 + S, 7.8)                      # walk-in, north leg
    wire_shelf(12.6 + S, 13.8, 7.8, 17.4 - S)                          # west run
    wire_shelf(16.7, 17.9 - S, 10.9 + S, 15.3)                         # east run
    wire_shelf(13.2 + S, 22 - S, 39.8, 41 - S)                          # bedroom 2 closet, back wall
    wire_shelf(13.2 + S, 14.4, 35.8 + S, 39.8)
    for y in (1.5, 3.0, 4.5, 6.0):
        wire_shelf(17.8, 19.3 - S, 17.4 + S, 21.4 - S, y, rod=False)   # linen
    # laundry: stacked washer/dryer + shelf
    box("white", 5.0, 7.5, 0, 6.2, 41.6, 44 - S, collide=True)
    for y in (1.6, 4.7):
        sphere("black", 6.25, y, 41.6, 0.7, sy=1.0)
    wire_shelf(4 + S, 8 - S, 42.9, 44 - S, 6.8, rod=False)
    # mech closet: water heater + air handler
    cyl("white", 11.4, -3.4, 0, 5.0, 0.9); COLL.append([10.5, 12.3, -4.3, -2.5])
    box("steel", 13.0, 15.1 - S, 0, 6.5, -4.4 + S, -2.0, collide=True)

    # lighting
    fan(6.3, 11.0); fan(20.8, 30.8)
    for p in [(21.75, 1.1), (13.85, 3.3), (16.0, 8.8), (15.0, 13.0), (24.9, 8.8), (24.0, 13.0), (23.8, 20.5),
              (16.0, 23.6), (2.0, 41.5), (6.0, 41.5), (17.6, 38.4), (15.9, 19.4), (12.7, -2.2), (5.2, -2.7)]:
        dome(*p)
    for p in [(6.3, 3.5), (6.3, 19.0), (2.0, 33.0), (8.5, 34.0), (11.5, 34.0)]:
        can(*p)

# ---------------------------------------------------------------- blender scene
def to_bl(p):           # plan feet -> blender meters (blender: x east, -y south, z up)
    return (p[0] * FT, -p[2] * FT, p[1] * FT)

def make_material(name):
    rgb, rough, metal, texfn, tile, alpha, emit = MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if texfn:
        data = np.clip(texfn(), 0, 1); n = data.shape[0]
        img = bpy.data.images.new(name + "_tex", n, n)
        rgba = np.concatenate([data, np.ones((n, n, 1))], axis=2).astype(np.float32)
        img.pixels.foreach_set(rgba.ravel()); img.pack()
        node = m.node_tree.nodes.new("ShaderNodeTexImage"); node.image = img
        m.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha < 1:
        bsdf.inputs["Alpha"].default_value = alpha
        m.surface_render_method = "BLENDED"
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1)
        bsdf.inputs["Emission Strength"].default_value = emit
    return m

def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for name, (V, F, U) in GEO.items():
        if not F:
            continue
        me = bpy.data.meshes.new(name)
        me.from_pydata([to_bl(v) for v in V], [], F)   # (x,y,z)->(x,-z,y) is a proper rotation: winding kept
        uv = me.uv_layers.new(name="UVMap")
        for poly, uvs in zip(me.polygons, U):
            for li, (u, v) in zip(poly.loop_indices, uvs):
                uv.data[li].uv = (u, v)
        me.materials.append(make_material(name)); me.validate(); me.update()
        ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    w = bpy.data.worlds.new("sky"); w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.6, 0.75, 0.95, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    bpy.context.scene.world = w
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3; sun.rotation_euler = (math.radians(50), 0, math.radians(200))
    bpy.context.scene.collection.objects.link(sun)
    for i, p in enumerate(LIGHTS):
        L = bpy.data.lights.new(f"lamp{i}", "POINT"); L.energy = 120; L.shadow_soft_size = 0.2
        o = bpy.data.objects.new(f"lamp{i}", L); o.location = to_bl(p)
        bpy.context.scene.collection.objects.link(o)

def render(name, eye, target, ortho=False, hide_ceiling=False):
    sc = bpy.context.scene
    cam = bpy.data.objects.get("cam") or bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.data.type = "ORTHO" if ortho else "PERSP"; cam.data.ortho_scale = 15.5; cam.data.lens = 16
    cam.location = to_bl(eye)
    d = np.array(to_bl(target)) - np.array(to_bl(eye))
    cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
    sc.camera = cam
    for n in ("ceiling", "deck"):
        if n in bpy.data.objects:
            bpy.data.objects[n].hide_render = hide_ceiling
    sc.render.engine = "CYCLES"; sc.cycles.samples = 48; sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.view_settings.view_transform = "AgX"
    sc.render.filepath = os.path.join(OUT, f"render_{name}.png")
    bpy.ops.render.render(write_still=True)

def self_check():
    area = sum((r[1] - r[0]) * (r[3] - r[2]) for r in [(0, 12.6, 0, 25.8), (0, 13.2, 25.8, 39.5), (0, 8, 39.5, 44), (12.6, 19.3, 17.4, 25.8),
           (12.6, 15.1, 0, 6.6), (10.4, 15.1, -4.4, 0), (21.4, 28.4, 6.6, 10.9), (17.9, 28.4, 10.9, 15.3), (19.3, 28.4, 15.3, 25.8),
           (15.1, 28.4, -4.4, 6.6), (12.6, 21.4, 6.6, 10.9), (12.6, 17.9, 10.9, 15.3), (12.6, 19.3, 15.3, 17.4), (13.2, 28.4, 25.8, 35.8), (13.2, 22, 35.8, 41)])
    print(f"gross floor area (centerlines): {area:.0f} sq ft")
    assert 1000 < area < 1350, area
    assert all(c[0] < c[1] and c[2] < c[3] for c in COLL)
    # spawn point and every doorway centre must be walkable (no collider within player radius 0.6 ft)
    free = lambda x, z: not any(c[0] - 0.6 < x < c[1] + 0.6 and c[2] - 0.6 < z < c[3] + 0.6 for c in COLL)
    for p in [(6.3, 22), (16.5, 6.6), (12.6, 3.3), (15.1, 3.6), (23.1, 6.6), (15.2, 25.8), (23.3, 25.8), (15.2, 35.8), (2.1, 44), (4, 41.7), (7.0, -2)]:
        assert free(*p), f"blocked doorway at {p}"

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True); os.makedirs(WEB, exist_ok=True)
    build(); self_check(); scene()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "unit.blend"))
    bpy.ops.export_scene.gltf(filepath=os.path.join(WEB, "unit.glb"), export_format="GLB", export_lights=False, export_cameras=False)
    with open(os.path.join(WEB, "collision.json"), "w") as f:
        json.dump({"boxes": [[round(v * FT, 3) for v in c] for c in COLL],
                   "lights": [[round(v * FT, 3) for v in p] for p in LIGHTS],
                   "spawn": [6.3 * FT, 22 * FT], "eye": 5.5 * FT}, f)
    if "--render" in sys.argv:
        render("living", (6.3, 5.5, 33.5), (6.3, 4.5, 0))
        render("kitchen", (3.0, 5.5, 22.0), (11.0, 3.5, 36.0))
        render("primary_bath", (22.2, 5.5, 7.6), (28.0, 3.5, 13.5))
        render("bedroom2", (17.0, 5.5, 34.5), (28.0, 4.0, 27.0))
        render("plan", (14.2, 60, 19.3), (14.2, 0, 19.31), ortho=False, hide_ceiling=True)
    print("done")
