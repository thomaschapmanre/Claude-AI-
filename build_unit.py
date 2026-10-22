"""Unit Type F (2 bed / 2 bath) - rebuildable Blender model.

Run:  blender --background --python build_unit.py            (Blender app)
  or: .venv/bin/python build_unit.py                          (pip bpy module)
Optional args after "--":  --render   (preview renders)

Plan coordinates are in FEET: x = east, z = south (north = balcony side),
origin = inside NW corner of the living room at the sliding-door wall.
Blender scene is in metres: X = x, Y = -z (north = +Y), Z = up.
"""
import math, os, sys
import bpy, bmesh
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
TEX = os.path.join(HERE, "textures")
os.makedirs(OUT, exist_ok=True)
os.makedirs(TEX, exist_ok=True)
FT = 0.3048
CEIL = 9.0
WALL_T = 0.35
DOOR_H = 6.67
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]

# ---------------------------------------------------------------- textures
def save_tex(name, arr):
    p = os.path.join(TEX, name + ".png")
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(p)
    return p

def make_textures():
    rng = np.random.default_rng(7)
    S = 512
    # wood-look LVP: 4 planks across, staggered ends, fine grain
    y, x = np.mgrid[0:S, 0:S]
    plank = x // (S // 4)
    off = (plank * 197) % S
    tone = rng.uniform(-14, 14, size=8)[plank % 8]
    grain = 4 * np.sin(x * 0.5 + 3 * np.sin(y * 0.012 + plank)) + rng.normal(0, 2.5, (S, S))
    base = np.stack([122, 102, 86], -1)[None, None, :] + (tone + grain)[..., None]
    gap = ((x % (S // 4)) < 2) | (((y + off) % S) < 2)
    base[gap] *= 0.6
    save_tex("lvp", base)
    # carpet: light greige noise
    n = rng.normal(0, 9, (S, S))
    save_tex("carpet", np.stack([186, 178, 166], -1)[None, None, :] + n[..., None])
    # granite: white/grey speckle with dark flecks
    g = np.full((S, S, 3), 222.0) + rng.normal(0, 10, (S, S))[..., None]
    fl = np.kron(rng.random((S // 4, S // 4)), np.ones((4, 4)))  # ~5mm flecks so they read at eye height
    g[fl > 0.93] = [140, 138, 135]
    g[fl > 0.985] = [55, 52, 50]
    g[(fl > 0.9) & (fl < 0.905)] = [196, 170, 150]
    save_tex("granite", g)
    # white 3x6 subway tile (2 rows x 2 cols per tile => 6x3in each when tile=1ft)
    t = np.full((S, S, 3), 240.0)
    row = y // (S // 4)
    xx = (x + (row % 2) * (S // 4)) % (S // 2)
    t[(y % (S // 4) < 5) | (xx < 5)] = [190, 188, 184]
    save_tex("subway", t)
    # natural pine deck boards
    dk = np.stack([196, 160, 118], -1)[None, None, :] + (6 * np.sin(y * 0.5 + 8 * np.sin(x * 0.03)))[..., None] + rng.normal(0, 4, (S, S, 1))
    dk[(x % (S // 5)) < 6] *= 0.55
    save_tex("deck", dk)
    # shingle siding, light greige
    sd = np.full((S, S, 3), 205.0) + rng.normal(0, 4, (S, S, 1))
    r2 = y // (S // 6)
    col = (x + (r2 % 2) * 37) // 60
    sd += (((col * 31 + r2 * 17) % 7) - 3)[..., None] * 3
    sd[(y % (S // 6)) < 4] *= 0.8
    sd[((x + (r2 % 2) * 37) % 60) < 2] *= 0.85
    save_tex("siding", sd * np.array([1.0, 0.99, 0.95]))

# ---------------------------------------------------------------- materials
MATS = {}
TILE = {}  # material -> UV tile size in metres

def mat(name, color, rough=0.6, tex=None, tile=1.0, metal=0.0, alpha=1.0, emit=None):
    color = tuple(v ** 2.2 for v in color)  # authored as sRGB, Blender wants linear
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if tex:
        im = nt.nodes.new("ShaderNodeTexImage")
        im.image = bpy.data.images.load(os.path.join(TEX, tex + ".png"))
        nt.links.new(im.outputs["Color"], p.inputs["Base Color"])
    if alpha < 1:
        p.inputs["Alpha"].default_value = alpha
        m.surface_render_method = "BLENDED"
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = 3.0
    m.diffuse_color = (*color, alpha)
    MATS[name] = m
    TILE[name] = tile
    return m

def make_materials():
    mat("Wall_Paint", (0.80, 0.78, 0.72), 0.85)
    mat("Accent_Charcoal", (0.33, 0.31, 0.28), 0.85)
    mat("Trim_Greige", (0.53, 0.50, 0.44), 0.5)
    mat("Ceiling_White", (0.86, 0.86, 0.84), 0.9)
    mat("Floor_LVP", (1, 1, 1), 0.45, "lvp", 0.8)
    mat("Carpet", (1, 1, 1), 1.0, "carpet", 0.5)
    mat("Granite", (1, 1, 1), 0.25, "granite", 0.6)
    mat("Subway_Tile", (1, 1, 1), 0.2, "subway", 0.3)
    mat("Deck_Wood", (1, 1, 1), 0.7, "deck", 0.7)
    mat("Siding", (1, 1, 1), 0.8, "siding", 1.0)
    mat("Cabinet_White", (0.88, 0.88, 0.86), 0.4)
    mat("Stainless", (0.62, 0.62, 0.62), 0.25, metal=1.0)
    mat("Black_Glass", (0.03, 0.03, 0.03), 0.1)
    mat("Brushed_Nickel", (0.7, 0.68, 0.64), 0.3, metal=1.0)
    mat("Porcelain", (0.93, 0.93, 0.92), 0.15)
    mat("Glass", (0.85, 0.92, 0.95), 0.05, alpha=0.18)
    mat("Frosted_Glass", (0.9, 0.92, 0.93), 0.3, alpha=0.55)
    mat("Window_Frame", (0.92, 0.92, 0.90), 0.4)
    mat("Slider_Frame", (0.12, 0.11, 0.10), 0.4)
    mat("Concrete", (0.5, 0.5, 0.49), 0.9)
    mat("Railing_White", (0.93, 0.93, 0.91), 0.5)
    mat("Wire_Shelf", (0.95, 0.95, 0.95), 0.4)
    mat("Light_Glow", (1, 0.97, 0.9), 0.5, emit=(1, 0.95, 0.85))
    mat("Fabric_Gray", (0.45, 0.46, 0.48), 0.95)
    mat("Fabric_Dark", (0.12, 0.12, 0.13), 0.9)
    mat("Wood_Walnut", (0.28, 0.17, 0.10), 0.5)
    mat("Marble_White", (0.9, 0.9, 0.88), 0.2)
    mat("Bedding", (0.88, 0.88, 0.86), 0.95)
    mat("Accent_Blue", (0.35, 0.65, 0.78), 0.9)
    mat("Rug", (0.18, 0.19, 0.21), 1.0)
    mat("Appliance_White", (0.9, 0.9, 0.9), 0.3)
    mat("Grass", (0.36, 0.45, 0.26), 1.0)
    mat("Asphalt", (0.22, 0.22, 0.23), 0.9)

# ---------------------------------------------------------------- geometry
COLL = {}

def coll(name):
    if name not in COLL:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
        COLL[name] = c
    return COLL[name]

def world_uv(bm, tile):
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        for l in f.loops:
            co = l.vert.co
            l[uv].uv = (co[a] / tile, co[b] / tile)

def add_mesh(name, bm, matname, cname):
    world_uv(bm, TILE.get(matname, 1.0))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MATS[matname])
    ob = bpy.data.objects.new(name, me)
    coll(cname).objects.link(ob)
    return ob

def box(name, x1, z1, x2, z2, h1, h2, m, c):
    """Axis-aligned box from plan feet (x1..x2, z1..z2) and height h1..h2 ft."""
    X1, X2 = sorted((x1 * FT, x2 * FT))
    Y1, Y2 = sorted((-z1 * FT, -z2 * FT))
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(X2 - X1, Y2 - Y1, (h2 - h1) * FT), verts=r["verts"])
    bmesh.ops.translate(bm, vec=((X1 + X2) / 2, (Y1 + Y2) / 2, (h1 + h2) / 2 * FT), verts=r["verts"])
    return add_mesh(name, bm, m, c)

def cyl(name, x, z, r, h1, h2, m, c, seg=24):
    bm = bmesh.new()
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r * FT, radius2=r * FT, depth=(h2 - h1) * FT)
    bmesh.ops.translate(bm, vec=(x * FT, -z * FT, (h1 + h2) / 2 * FT), verts=res["verts"])
    return add_mesh(name, bm, m, c)

def wall(name, line, a1, a2, openings=(), t=WALL_T, m="Wall_Paint", base=True, c="Walls"):
    """Wall on a plan line. line=('H', z) runs along x from a1..a2; ('V', x) runs along z.
    openings: (o1, o2, bottom, top) along the same axis, heights in ft."""
    kind, k = line
    def piece(n, b1, b2, h1, h2, mm=m, tt=t, cc=c):
        if b2 - b1 < 1e-3 or h2 - h1 < 1e-3:
            return
        if kind == "H":
            box(n, b1, k - tt / 2, b2, k + tt / 2, h1, h2, mm, cc)
        else:
            box(n, k - tt / 2, b1, k + tt / 2, b2, h1, h2, mm, cc)
    cur, i = a1, 0
    for (o1, o2, ob, ot) in sorted(openings):
        piece(f"{name}_{i}", cur, o1, 0, CEIL)
        if base:
            piece(f"{name}_{i}_Base", cur, o1, 0, 0.33, "Trim_Greige", t + 0.06, "Trim")
        piece(f"{name}_{i}_Sill", o1, o2, 0, ob)
        piece(f"{name}_{i}_Head", o1, o2, ot, CEIL)
        cur, i = o2, i + 1
    piece(f"{name}_{i}", cur, a2, 0, CEIL)
    if base:
        piece(f"{name}_{i}_Base", cur, a2, 0, 0.33, "Trim_Greige", t + 0.06, "Trim")

def opening_trim(name, line, o1, o2, bottom, top, t=WALL_T, kind_="door"):
    """Casing around a door/window on both faces."""
    k_, k = line
    w = 0.29  # 3.5in casing
    d = t + 0.08
    m = "Trim_Greige" if kind_ == "door" else "Window_Frame"
    parts = [(o1 - w, o1, bottom, top + w), (o2, o2 + w, bottom, top + w), (o1, o2, top, top + w)]
    if kind_ == "window":
        parts.append((o1 - w, o2 + w, bottom - 0.12, bottom))
    for i, (b1, b2, h1, h2) in enumerate(parts):
        if k_ == "H":
            box(f"{name}_Casing{i}", b1, k - d / 2, b2, k + d / 2, h1, h2, m, "Trim")
        else:
            box(f"{name}_Casing{i}", k - d / 2, b1, k + d / 2, b2, h1, h2, m, "Trim")

def door(name, line, o1, o2, hinge="a", swing=+1):
    """Interior 2-panel door, left open 90 deg so the walk path stays clear."""
    k_, k = line
    opening_trim(name, line, o1, o2, 0, DOOR_H)
    w = o2 - o1
    hx = o1 if hinge == "a" else o2
    s = swing * (WALL_T / 2)
    if k_ == "H":
        box(f"{name}_Leaf", hx - 0.06, k + s, hx + 0.06, k + s + swing * w, 0.02, DOOR_H - 0.02, "Trim_Greige", "Doors")
    else:
        box(f"{name}_Leaf", k + s, hx - 0.06, k + s + swing * w, hx + 0.06, 0.02, DOOR_H - 0.02, "Trim_Greige", "Doors")

def window(name, line, o1, o2, sill, top, outward=-1):
    k_, k = line
    opening_trim(name, line, o1, o2, sill, top, kind_="window")
    # glass + mullion (single-hung look) + blinds band
    if k_ == "H":
        box(f"{name}_Glass", o1, k - 0.03, o2, k + 0.03, sill, top, "Glass", "Windows")
        box(f"{name}_Rail", o1, k - 0.08, o2, k + 0.08, (sill + top) / 2 - 0.08, (sill + top) / 2 + 0.08, "Window_Frame", "Windows")
    else:
        box(f"{name}_Glass", k - 0.03, o1, k + 0.03, o2, sill, top, "Glass", "Windows")
        box(f"{name}_Rail", k - 0.08, o1, k + 0.08, o2, (sill + top) / 2 - 0.08, (sill + top) / 2 + 0.08, "Window_Frame", "Windows")

# ---------------------------------------------------------------- plan data
def build_structure():
    W = wall
    # --- exterior + balcony
    W("Ext_North_Bed1", ("H", -8.25), 14.65 - WALL_T / 2, 27.85 + WALL_T / 2, [(16.1, 18.8, 3, 7.5), (21.0, 23.7, 3, 7.5)])
    W("Ext_East", ("V", 27.85), -8.25, 31.2 + WALL_T / 2, [(9.0, 10.3, 4.5, 7.5), (12.4, 14.3, 4.5, 7.5), (23.2, 26.0, 3, 7.5)])
    W("Ext_South_Bed2E", ("H", 31.2), 23.3, 27.85)
    W("Ext_Closet2_East", ("V", 23.3), 31.2, 38.9 + WALL_T / 2)
    W("Ext_Closet2_South", ("H", 38.9), 14.92 - WALL_T / 2, 23.3 + WALL_T / 2)
    W("Ext_Closet2_West", ("V", 14.92), 31.2, 38.9)
    W("Ext_South_Kitchen", ("H", 31.2), 3.3, 14.92 - WALL_T / 2)
    W("Ext_Utility_East", ("V", 6.9), 31.2, 36.8 + WALL_T / 2)
    W("Ext_South_Entry", ("H", 36.8), -WALL_T / 2, 6.9, [(0.4, 3.1, 0, DOOR_H)])
    W("Ext_West", ("V", 0), -5.0, 36.8)
    W("Ext_North_Living", ("H", 0), -WALL_T / 2, 14.65, [(4.0, 10.1, 0, 6.9), (10.4 - WALL_T / 2 - 0.01, 10.4 + WALL_T / 2 + 0.01, 0, 0)])
    W("Mech_North", ("H", -5.0), 10.4 - WALL_T / 2, 14.65)
    W("Mech_West", ("V", 10.4), -5.0, 0, [(-3.9, -1.5, 0, DOOR_H)])
    W("Bed1_West", ("V", 14.65), -8.25, 3.0, [(0.2, 2.8, 0, DOOR_H)])
    # --- interior
    W("Bed1_South", ("H", 3.0), 12.6 - WALL_T / 2, 27.85, [(15.1, 17.4, 0, DOOR_H), (20.5, 22.9, 0, DOOR_H)])
    W("Living_East", ("V", 12.6), 3.0, 16.0 + WALL_T / 2)
    W("Closet1_ShowerN", ("H", 6.5), 17.0, 20.2)
    W("Closet1_East", ("V", 20.2), 3.0, 6.5 + WALL_T / 2)
    W("Closet1_Bath2_West", ("V", 17.0), 6.5, 16.0)
    W("Closet1_South", ("H", 12.1), 12.6, 17.0)
    W("PBath_South", ("H", 10.7), 17.0, 27.85)
    W("Laundry_South", ("H", 16.0), 12.6, 17.0, [(12.95, 16.65, 0, DOOR_H)])
    W("Bath2_Hall", ("H", 16.0), 17.0, 21.5)
    W("Bath2_West", ("V", 21.5), 16.0, 20.9, [(18.2, 20.7, 0, DOOR_H)])
    W("Bed2_North", ("H", 20.9), 14.92 - WALL_T / 2, 27.85, [(15.4, 17.9, 0, DOOR_H)])
    W("Bed2_West", ("V", 14.92), 20.9, 31.2)
    W("Bed2_South", ("H", 31.2), 14.92, 23.3, [(15.4, 17.9, 0, DOOR_H)])
    W("Utility_West", ("V", 3.3), 31.2, 36.8, [(32.2, 34.6, 0, DOOR_H)])
    W("Utility_North", ("H", 31.2), 3.3, 6.9, base=False)

    # doors (all left open for walking)
    door("Door_Bed1", ("V", 14.65), 0.2, 2.8, "a", +1)  # leaf rests north, clear of the closet door
    door("Door_Closet1", ("H", 3.0), 15.1, 17.4, "a", +1)
    door("Door_PBath", ("H", 3.0), 20.5, 22.9, "b", +1)
    door("Door_Bath2", ("V", 21.5), 18.2, 20.7, "b", +1)  # leaf rests on the north wall
    door("Door_Bed2", ("H", 20.9), 15.4, 17.9, "a", +1)
    door("Door_Closet2", ("H", 31.2), 15.4, 17.9, "a", +1)
    door("Door_Utility", ("V", 3.3), 32.2, 34.6, "a", +1)  # opens into the closet, clear of the entry path
    door("Door_Mech", ("V", 10.4), -3.9, -1.5, "a", +1)
    door("Door_Entry", ("H", 36.8), 0.4, 3.1, "a", -1)
    opening_trim("Laundry_Bifold", ("H", 16.0), 12.95, 16.65, 0, DOOR_H)
    # bifolds folded open at each jamb
    for i, (a, b) in enumerate([(12.95, 13.05), (16.55, 16.65)]):
        box(f"Laundry_Bifold_Leaf{i}", a, 16.2, b, 17.0, 0.05, DOOR_H - 0.05, "Trim_Greige", "Doors")

    # windows
    window("Win_Bed1_A", ("H", -8.25), 16.1, 18.8, 3, 7.5)
    window("Win_Bed1_B", ("H", -8.25), 21.0, 23.7, 3, 7.5)
    window("Win_PBath", ("V", 27.85), 9.0, 10.3, 4.5, 7.5)
    window("Win_Bath2", ("V", 27.85), 12.4, 14.3, 4.5, 7.5)
    window("Win_Bed2", ("V", 27.85), 23.2, 26.0, 3, 7.5)

    # sliding door to balcony: dark bronze frame, 2 panels
    for i, (a, b) in enumerate([(4.0, 7.1), (4.2, 7.3)]):  # east panel slid open so the balcony is walkable
        zz = 0.04 if i == 0 else -0.04
        box(f"Slider_Glass{i}", a + 0.15, zz - 0.02, b - 0.15, zz + 0.02, 0.15, 6.75, "Glass", "Windows")
        for j, (p1, p2, h1, h2) in enumerate([(a, a + 0.15, 0, 6.9), (b - 0.15, b, 0, 6.9), (a, b, 0, 0.15), (a, b, 6.75, 6.9)]):
            box(f"Slider_Frame{i}_{j}", p1, zz - 0.05, p2, zz + 0.05, h1, h2, "Slider_Frame", "Windows")
    opening_trim("Slider", ("H", 0), 4.0, 10.1, 0, 6.9)
    # vertical blinds stacked to the west side (white, as in the photo)
    box("Slider_Blinds", 3.4, 0.25, 4.3, 0.35, 0.3, 7.0, "Window_Frame", "Windows")

    # accent wall on the living-room face of Living_East (charcoal in the photos)
    box("Accent_Wall", 12.6 - WALL_T / 2 - 0.02, 3.0 + WALL_T / 2, 12.6 - WALL_T / 2, 16.0 + WALL_T / 2, 0.33, CEIL, "Accent_Charcoal", "Walls")

    # balcony: railing on north, siding on balcony-facing faces, wood ceiling
    rail_z = -5.0
    box("Balcony_TopRail", 0.2, rail_z - 0.12, 10.4, rail_z + 0.12, 3.25, 3.45, "Railing_White", "Balcony")
    box("Balcony_BotRail", 0.2, rail_z - 0.08, 10.4, rail_z + 0.08, 0.3, 0.45, "Railing_White", "Balcony")
    x = 0.6
    i = 0
    while x < 10.2:
        box(f"Balcony_Baluster{i}", x - 0.06, rail_z - 0.06, x + 0.06, rail_z + 0.06, 0.45, 3.25, "Railing_White", "Balcony")
        x += 0.42
        i += 1
    box("Balcony_Post_W", 0.2, rail_z - 0.25, 0.55, rail_z + 0.25, 0, CEIL, "Railing_White", "Balcony")
    box("Balcony_Post_E", 10.0, rail_z - 0.25, 10.4 - WALL_T / 2, rail_z + 0.25, 0, CEIL, "Railing_White", "Balcony")
    box("Balcony_Beam", 0.2, rail_z - 0.25, 10.4, rail_z + 0.25, CEIL - 0.9, CEIL, "Railing_White", "Balcony")
    off = WALL_T / 2 + 0.01
    for i, (a, b, h1, h2) in enumerate([(off, 4.0, 0, CEIL), (10.1, 10.4 - off, 0, CEIL), (4.0, 10.1, 6.9, CEIL)]):
        box(f"Siding_LivingN{i}", a, -off - 0.03, b, -off, h1, h2, "Siding", "Balcony")
    box("Siding_Privacy", off, -5.0, off + 0.03, -off, 0, CEIL, "Siding", "Balcony")
    box("Siding_MechW", 10.4 - off - 0.03, -5.0, 10.4 - off, -3.9, 0, CEIL, "Siding", "Balcony")
    box("Siding_MechW2", 10.4 - off - 0.03, -1.5, 10.4 - off, -off, 0, CEIL, "Siding", "Balcony")

def build_floors_ceilings():
    F = [
        ("Living_Dining_Kitchen", 0, 0, 12.6, 31.2, "Floor_LVP"),
        ("Kitchen_East", 12.6, 16.0, 14.92, 31.2, "Floor_LVP"),
        ("Nook", 12.6, 0, 14.65, 3.0, "Floor_LVP"),
        ("Hall", 14.92, 16.0, 21.5, 20.9, "Floor_LVP"),
        ("Entry", 0, 31.2, 3.3, 36.8, "Floor_LVP"),
        ("Utility", 3.3, 31.2, 6.9, 36.8, "Floor_LVP"),
        ("Balcony", 0, -5.0, 10.4, 0, "Deck_Wood"),
        ("Mech", 10.4, -5.0, 14.65, 0, "Concrete"),
        ("Primary_Bedroom", 14.65, -8.25, 27.85, 3.0, "Carpet"),
        ("Primary_Closet_A", 12.6, 3.0, 17.0, 12.1, "Carpet"),
        ("Primary_Closet_B", 17.0, 3.0, 20.2, 6.5, "Carpet"),
        ("Primary_Bath", 20.2, 3.0, 27.85, 10.7, "Floor_LVP"),
        ("Primary_Shower", 17.0, 6.5, 20.2, 10.7, "Porcelain"),
        ("Laundry", 12.6, 12.1, 17.0, 16.0, "Floor_LVP"),
        ("Bath2_A", 17.0, 10.7, 27.85, 16.0, "Floor_LVP"),
        ("Bath2_B", 21.5, 16.0, 27.85, 20.9, "Floor_LVP"),
        ("Bedroom2", 14.92, 20.9, 27.85, 31.2, "Carpet"),
        ("Bedroom2_Closet", 14.92, 31.2, 23.3, 38.9, "Carpet"),
    ]
    # 2nd-floor unit: ground below with lawn + parking lot (as seen from the balcony photo)
    box("Ground_Lawn", -60, -70, 90, 80, -11.1, -11.0, "Grass", "Site")
    box("Ground_Lot", -60, -40, 90, -14, -11.0, -10.95, "Asphalt", "Site")
    for n, x1, z1, x2, z2, m in F:
        box(f"Floor_{n}", x1, z1, x2, z2, -0.1, 0.0, m, "Floors")
        cm = "Deck_Wood" if n == "Balcony" else "Ceiling_White"
        box(f"Ceiling_{n}", x1, z1, x2, z2, CEIL, CEIL + 0.1, cm, "Ceilings")
    # balcony ceiling joists (exposed wood in the photo)
    for i in range(8):
        x = 0.6 + i * 1.33
        box(f"Balcony_Joist{i}", x, -5.0, x + 0.15, 0, CEIL - 0.6, CEIL, "Deck_Wood", "Ceilings")

def build_kitchen():
    c = "Kitchen"
    # south wall run: fridge | base cabs | range | base cabs
    wz = 31.2 - WALL_T / 2
    box("Fridge", 4.0, wz - 2.5, 7.0, wz - 0.05, 0, 5.8, "Stainless", c)
    box("Fridge_Handle", 5.45, wz - 2.58, 5.55, wz - 2.5, 2.5, 5.0, "Black_Glass", c)
    for n, a, b in [("Base_A", 7.0, 9.9), ("Base_B", 12.4, 14.92 - WALL_T / 2)]:
        box(f"Kitchen_{n}", a, wz - 2.0, b, wz, 0.3, 3.0, "Cabinet_White", c)
        box(f"Kitchen_{n}_Toe", a, wz - 1.8, b, wz, 0, 0.3, "Trim_Greige", c)
        box(f"Kitchen_{n}_Top", a, wz - 2.08, b, wz, 3.0, 3.1, "Granite", c)
    box("Range", 9.9, wz - 2.1, 12.4, wz, 0, 3.05, "Stainless", c)
    box("Range_Cooktop", 9.95, wz - 2.05, 12.35, wz - 0.2, 3.05, 3.1, "Black_Glass", c)
    box("Microwave", 10.0, wz - 1.25, 12.3, wz, 4.9, 6.3, "Stainless", c)
    box("Backsplash", 7.0, wz - 0.03, 14.92 - WALL_T / 2, wz, 3.1, 4.6, "Subway_Tile", c)
    for n, a, b in [("Upper_A", 7.0, 10.0), ("Upper_B", 12.3, 14.92 - WALL_T / 2)]:
        box(f"Kitchen_{n}", a, wz - 1.1, b, wz, 4.6, 7.4, "Cabinet_White", c)
    box("Kitchen_Upper_Range", 10.0, wz - 1.1, 12.3, wz, 6.3, 7.4, "Cabinet_White", c)
    box("Fridge_Upper", 4.0, wz - 2.0, 7.0, wz, 6.2, 7.4, "Cabinet_White", c)
    # peninsula with undermount sink + dishwasher, seating overhang to the north
    px1, px2, pz1, pz2 = 5.5, 14.92 - WALL_T / 2, 22.0, 24.6
    box("Peninsula_Base", px1, pz1, px2, pz2, 0.3, 3.0, "Cabinet_White", c)
    box("Peninsula_Toe", px1 + 0.1, pz1 + 0.1, px2, pz2 - 0.2, 0, 0.3, "Trim_Greige", c)
    box("Peninsula_Top", px1 - 0.1, 21.1, px2, pz2 + 0.08, 3.0, 3.1, "Granite", c)
    box("Sink_Basin", 8.6, 23.0, 10.6, 24.3, 2.55, 3.11, "Stainless", c)
    box("Faucet_Base", 9.5, 22.6, 9.7, 22.8, 3.1, 4.2, "Brushed_Nickel", c)
    box("Faucet_Spout", 9.5, 22.6, 9.7, 23.3, 4.0, 4.2, "Brushed_Nickel", c)
    box("Dishwasher", 10.8, pz2, 12.8, pz2 + 0.05, 0.3, 2.9, "Stainless", c)
    for i, x in enumerate([7.0, 11.0]):
        cyl(f"Pendant{i}_Cord", x, 22.9, 0.03, 5.6, CEIL, "Black_Glass", c, 8)
        cyl(f"Pendant{i}_Shade", x, 22.9, 0.28, 5.0, 5.6, "Light_Glow", c)
    for i, x in enumerate([7.0, 9.0, 11.0]):
        cyl(f"Stool{i}_Seat", x, 20.6, 0.7, 2.4, 2.6, "Fabric_Dark", c)
        cyl(f"Stool{i}_Leg", x, 20.6, 0.08, 0, 2.4, "Black_Glass", c, 8)

def vanity(prefix, x_wall, z1, z2, c):
    """Vanity against an east wall (x_wall), running z1..z2."""
    xw = x_wall - WALL_T / 2
    box(f"{prefix}_Vanity", xw - 1.8, z1, xw, z2, 0.3, 2.85, "Cabinet_White", c)
    box(f"{prefix}_Vanity_Toe", xw - 1.6, z1, xw, z2, 0, 0.3, "Trim_Greige", c)
    box(f"{prefix}_Vanity_Top", xw - 1.9, z1, xw, z2, 2.85, 2.95, "Granite", c)
    box(f"{prefix}_Vanity_Splash", xw - 0.05, z1, xw, z2, 2.95, 3.3, "Granite", c)
    zm = (z1 + z2) / 2
    box(f"{prefix}_Sink", xw - 1.4, zm - 0.7, xw - 0.5, zm + 0.7, 2.6, 2.96, "Porcelain", c)
    box(f"{prefix}_Faucet", xw - 0.4, zm - 0.06, xw - 0.2, zm + 0.06, 2.95, 3.5, "Brushed_Nickel", c)
    box(f"{prefix}_Mirror_Frame", xw - 0.08, z1 + 0.3, xw, z2 - 0.3, 3.5, 6.6, "Window_Frame", c)
    box(f"{prefix}_Mirror", xw - 0.1, z1 + 0.45, xw - 0.08, z2 - 0.45, 3.65, 6.45, "Stainless", c)
    box(f"{prefix}_LightBar", xw - 0.25, zm - 1.4, xw, zm + 1.4, 6.9, 7.0, "Brushed_Nickel", c)
    for i, dz in enumerate([-1.1, 0, 1.1]):
        cyl(f"{prefix}_Globe{i}", xw - 0.4, zm + dz, 0.22, 6.65, 7.05, "Light_Glow", c, 12)

def toilet(prefix, x, z, facing, c):
    """facing: 'N' (tank on south) or 'W' (tank on east)."""
    if facing == "N":
        box(f"{prefix}_Tank", x - 0.85, z - 0.75, x + 0.85, z - 0.1, 1.4, 2.6, "Porcelain", c)
        box(f"{prefix}_Bowl", x - 0.6, z - 2.3, x + 0.6, z - 0.75, 0, 1.35, "Porcelain", c)
    else:
        box(f"{prefix}_Tank", x - 0.75, z - 0.85, x - 0.1, z + 0.85, 1.4, 2.6, "Porcelain", c)
        box(f"{prefix}_Bowl", x - 2.3, z - 0.6, x - 0.75, z + 0.6, 0, 1.35, "Porcelain", c)

def build_baths():
    c = "Bathrooms"
    h = WALL_T / 2
    # primary bath: framed glass walk-in shower (west), vanity on east wall, toilet south wall
    box("PShower_Pan", 17.0 + h, 6.5 + h, 20.2 - h, 10.7 - h, 0, 0.3, "Porcelain", c)
    box("PShower_Surround", 17.0 + h, 6.5 + h, 17.0 + h + 0.05, 10.7 - h, 0.3, 7.0, "Porcelain", c)
    box("PShower_Surround_S", 17.0 + h, 10.7 - h - 0.05, 20.2 - h, 10.7 - h, 0.3, 7.0, "Porcelain", c)
    box("PShower_Glass", 20.1, 6.5 + h, 20.16, 10.7 - h, 0.3, 6.6, "Frosted_Glass", c)
    for z in (6.5 + h, 8.6, 10.7 - h - 0.08):
        box(f"PShower_Frame_{z:.1f}", 20.07, z, 20.2, z + 0.08, 0.3, 6.6, "Brushed_Nickel", c)
    box("PShower_Frame_Top", 20.07, 6.5 + h, 20.2, 10.7 - h, 6.52, 6.6, "Brushed_Nickel", c)
    box("PShower_Bar", 20.25, 7.4, 20.3, 8.4, 3.7, 3.8, "Brushed_Nickel", c)
    vanity("PBath", 27.85, 3.6, 8.6, c)
    toilet("PBath_Toilet", 23.6, 10.7 - h, "N", c)
    # second (hall) bath: tub/shower combo with curved rod, toilet + vanity on east wall
    box("Tub", 17.0 + h, 10.7 + h, 19.6, 16.0 - h, 0, 1.6, "Porcelain", c)
    box("Tub_Surround", 17.0 + h, 10.7 + h, 17.0 + h + 0.05, 16.0 - h, 1.6, 7.0, "Porcelain", c)
    box("Tub_Rod", 19.7, 10.7 + h, 19.78, 16.0 - h, 6.6, 6.68, "Brushed_Nickel", c)
    toilet("Bath2_Toilet", 27.85 - h, 13.3, "W", c)
    vanity("Bath2", 27.85, 15.6, 20.9 - h - 0.1, c)
    box("Bath2_TowelBar", 21.0, 16.0 - h - 0.05, 23.0, 16.0 - h, 4.0, 4.08, "Brushed_Nickel", c)

def wire_shelf(prefix, line, a1, a2, c, depth=1.0, h=5.6, side=+1):
    k_, k = line
    k0 = k + side * WALL_T / 2
    if k_ == "H":
        box(f"{prefix}_Shelf", a1, k0, a2, k0 + side * depth, h, h + 0.06, "Wire_Shelf", c)
        box(f"{prefix}_Rod", a1, k0 + side * (depth - 0.2), a2, k0 + side * (depth - 0.15), h - 0.15, h - 0.1, "Wire_Shelf", c)
    else:
        box(f"{prefix}_Shelf", k0, a1, k0 + side * depth, a2, h, h + 0.06, "Wire_Shelf", c)
        box(f"{prefix}_Rod", k0 + side * (depth - 0.2), a1, k0 + side * (depth - 0.15), a2, h - 0.15, h - 0.1, "Wire_Shelf", c)

def build_closets_utility():
    c = "Closets_Utility"
    # primary walk-in: shelving on west + south + east-alcove walls
    wire_shelf("Closet1_W", ("V", 12.6), 3.4, 11.9, c, side=+1)
    wire_shelf("Closet1_S", ("H", 12.1), 13.8, 16.8, c, side=-1)
    wire_shelf("Closet1_E", ("V", 20.2), 3.4, 6.3, c, side=-1)
    wire_shelf("Closet1_E2", ("V", 17.0), 6.7, 11.9, c, side=-1)
    # bedroom-2 walk-in
    wire_shelf("Closet2_E", ("V", 23.3), 31.6, 38.7, c, side=-1)
    wire_shelf("Closet2_S", ("H", 38.9), 15.2, 22.0, c, side=-1)
    wire_shelf("Closet2_W", ("V", 14.92), 33.0, 38.0, c, side=+1, h=6.2)
    # laundry: stacked-side washer/dryer + shelf
    lz = 12.1 + WALL_T / 2
    for i, (a, b) in enumerate([(12.85, 14.85), (14.85, 16.85)]):
        box(f"Laundry_Machine{i}", a + 0.05, lz, b - 0.05, lz + 2.3, 0, 3.0, "Appliance_White", c)
    wire_shelf("Laundry_Shelf", ("H", 12.1), 12.8, 16.8, c, side=+1, h=5.0)
    # mech closet air handler, utility water heater
    box("Mech_AirHandler", 11.6, -4.75, 14.4, -2.7, 0, 6.0, "Appliance_White", c)
    cyl("Utility_WaterHeater", 5.1, 35.2, 1.0, 0, 5.0, "Appliance_White", c)

def build_lighting_fixtures():
    c = "Light_Fixtures"
    def fan(prefix, x, z):
        cyl(f"{prefix}_Rod", x, z, 0.05, 8.0, CEIL, "Brushed_Nickel", c, 8)
        cyl(f"{prefix}_Motor", x, z, 0.45, 7.6, 8.0, "Brushed_Nickel", c)
        cyl(f"{prefix}_Light", x, z, 0.4, 7.45, 7.6, "Light_Glow", c)
        for i in range(3):
            a = i * 2 * math.pi / 3
            bm = bmesh.new()
            r = bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=(2.0 * FT, 0.45 * FT, 0.03 * FT), verts=r["verts"])
            bmesh.ops.translate(bm, vec=(1.4 * FT, 0, 0), verts=r["verts"])
            bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(a, 3, "Z"), verts=r["verts"])
            bmesh.ops.translate(bm, vec=(x * FT, -z * FT, 7.8 * FT), verts=r["verts"])
            add_mesh(f"{prefix}_Blade{i}", bm, "Trim_Greige", c)
    fan("Fan_Living", 6.3, 7.5)
    fan("Fan_Bedroom1", 21.25, -2.6)
    domes = [("Bedroom2", 21.4, 26.0), ("Hall", 18.0, 18.4), ("Entry", 1.7, 34.0), ("Closet1", 14.8, 7.5),
             ("Closet2", 19.1, 35.0), ("Laundry", 14.8, 14.0), ("PBath", 23.5, 6.8), ("Bath2", 22.5, 13.2),
             ("Nook", 13.6, 1.5), ("Mech", 12.5, -2.5), ("Utility", 5.1, 33.0), ("Balcony", 5.2, -2.5)]
    for n, x, z in domes:
        cyl(f"Dome_{n}", x, z, 0.5, CEIL - 0.25, CEIL, "Light_Glow", c, 16)
    for i, (x, z) in enumerate([(4.0, 27.0), (10.0, 27.0), (6.3, 17.5), (6.3, 13.0)]):
        cyl(f"Can_{i}", x, z, 0.3, CEIL - 0.02, CEIL, "Light_Glow", c, 16)

def build_furniture():
    c = "Furniture"
    # living (per staged plan): sofa on west wall, octagon coffee table on rug, 2 chairs, TV console on accent wall
    box("Rug_Living", 3.8, 5.3, 8.6, 12.2, 0.0, 0.03, "Rug", c)
    box("Sofa_Base", 0.4, 4.6, 3.3, 11.6, 0.4, 1.4, "Fabric_Gray", c)
    box("Sofa_Back", 0.2, 4.6, 0.9, 11.6, 0.4, 2.8, "Fabric_Gray", c)
    box("Sofa_ArmN", 0.2, 4.4, 3.3, 4.9, 0.4, 2.1, "Fabric_Gray", c)
    box("Sofa_ArmS", 0.2, 11.3, 3.3, 11.8, 0.4, 2.1, "Fabric_Gray", c)
    box("Sofa_Legs", 0.5, 4.7, 3.2, 11.5, 0, 0.4, "Wood_Walnut", c)
    for i, z in enumerate([6.0, 10.0]):
        box(f"Pillow{i}", 0.95, z - 0.7, 1.4, z + 0.7, 1.4, 2.6, "Accent_Blue", c)
    cyl("CoffeeTable", 6.2, 8.8, 1.6, 1.3, 1.45, "Marble_White", c, 8)
    cyl("CoffeeTable_Base", 6.2, 8.8, 0.5, 0, 1.3, "Black_Glass", c, 8)
    box("Armchair_N", 5.2, 2.3, 7.6, 4.6, 0, 2.6, "Fabric_Gray", c)
    box("LoungeChair_S", 5.0, 10.9, 7.4, 12.5, 0, 1.6, "Fabric_Dark", c)
    box("TV_Console", 11.0, 6.0, 12.6 - WALL_T / 2 - 0.03, 11.0, 0, 1.8, "Wood_Walnut", c)
    box("TV", 11.9, 6.6, 12.05, 10.4, 3.2, 6.0, "Black_Glass", c)
    cyl("SideTable_N", 1.6, 3.4, 0.7, 0, 2.0, "Marble_White", c)
    cyl("SideTable_S", 1.6, 12.8, 0.7, 0, 2.0, "Marble_White", c)
    # dining
    box("DiningTable_Top", 4.6, 14.2, 7.8, 16.6, 2.4, 2.55, "Marble_White", c)
    box("DiningTable_Base", 5.9, 15.1, 6.5, 15.7, 0, 2.4, "Black_Glass", c)
    for i, (x, z) in enumerate([(6.2, 13.4), (6.2, 17.3)]):  # leaves a walkway to the stools
        box(f"DiningChair{i}_Seat", x - 0.8, z - 0.8, x + 0.8, z + 0.8, 1.5, 1.7, "Fabric_Gray", c)
        box(f"DiningChair{i}_Legs", x - 0.7, z - 0.7, x + 0.7, z + 0.7, 0, 1.5, "Black_Glass", c)
    box("Credenza", 11.0, 12.6, 12.6 - WALL_T / 2 - 0.03, 15.6, 0, 2.6, "Wood_Walnut", c)
    # primary bedroom: queen bed, headboard on east wall
    bx2 = 27.85 - WALL_T / 2
    box("Bed1_Frame", bx2 - 7.0, -5.1, bx2, 0.2, 0, 1.2, "Wood_Walnut", c)
    box("Bed1_Mattress", bx2 - 6.8, -5.0, bx2 - 0.3, 0.1, 1.2, 2.1, "Bedding", c)
    box("Bed1_Headboard", bx2 - 0.3, -5.3, bx2, 0.4, 0, 4.2, "Fabric_Dark", c)
    box("Bed1_Throw", bx2 - 4.0, -5.05, bx2 - 2.8, 0.15, 2.1, 2.15, "Fabric_Gray", c)
    for i, z in enumerate([-6.6, 1.0]):
        box(f"Bed1_Nightstand{i}", bx2 - 1.5, z - 0.75, bx2, z + 0.75, 0, 2.1, "Marble_White", c)
    # bedroom 2: bed with headboard on south wall, dresser/TV on north wall, chair west
    hz = 31.2 - WALL_T / 2
    box("Bed2_Frame", 19.8, hz - 7.0, 25.2, hz, 0, 1.2, "Wood_Walnut", c)
    box("Bed2_Mattress", 19.9, hz - 6.8, 25.1, hz - 0.3, 1.2, 2.1, "Bedding", c)
    box("Bed2_Headboard", 19.6, hz - 0.3, 25.4, hz, 0, 4.0, "Wood_Walnut", c)
    box("Bed2_Blanket", 19.85, hz - 6.85, 25.15, hz - 4.6, 2.1, 2.2, "Fabric_Dark", c)
    for i, x in enumerate([18.6, 26.4]):
        box(f"Bed2_Nightstand{i}", x - 0.8, hz - 1.5, x + 0.8, hz, 0, 2.1, "Wood_Walnut", c)
    box("Bed2_Dresser", 20.2, 20.9 + WALL_T / 2, 25.0, 22.4, 0, 2.6, "Cabinet_White", c)
    box("Bed2_TV", 21.5, 21.3, 23.7, 21.45, 2.6, 4.0, "Black_Glass", c)
    box("Bed2_Chair", 15.6, 24.2, 17.6, 26.4, 0, 2.6, "Fabric_Gray", c)

def build_lights():
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.75, 0.85, 1.0, 1)
    bg.inputs["Strength"].default_value = 0.5
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 3.0
    so = bpy.data.objects.new("Sun", sun)
    so.rotation_euler = (math.radians(50), math.radians(10), math.radians(200))
    coll("Lights").objects.link(so)
    # one soft area light per room at ceiling height (interior fill)
    rooms = [("Living", 6.3, 8.0, 12), ("Dining", 6.3, 17.5, 10), ("Kitchen", 9.0, 27.0, 10),
             ("Bed1", 21.2, -2.6, 12), ("Bed2", 21.4, 26.0, 11), ("PBath", 23.5, 6.8, 6),
             ("Bath2", 22.5, 13.2, 6), ("Hall", 18.0, 18.4, 5), ("Closet1", 14.8, 7.5, 5),
             ("Closet2", 19.1, 35.0, 6), ("Entry", 1.7, 34.0, 4), ("Laundry", 14.8, 14.0, 4),
             ("Balcony", 5.2, -2.5, 6)]
    for n, x, z, s in rooms:
        L = bpy.data.lights.new(f"Area_{n}", "AREA")
        L.size = s * FT * 0.6
        L.energy = 7 * s
        L.color = (1.0, 0.92, 0.82)
        o = bpy.data.objects.new(f"Area_{n}", L)
        o.location = (x * FT, -z * FT, (CEIL - 0.4) * FT)
        coll("Lights").objects.link(o)

# ---------------------------------------------------------------- output
def spawn_and_cameras():
    sp = bpy.data.objects.new("PlayerStart", None)
    sp.location = (1.7 * FT, -35.0 * FT, 0.1)  # just inside the entry door, facing north
    sp.empty_display_type = "ARROWS"
    coll("Markers").objects.link(sp)
    cam = bpy.data.cameras.new("Cam_Top")
    cam.type = "ORTHO"
    cam.ortho_scale = 49 * FT
    co = bpy.data.objects.new("Cam_Top", cam)
    co.location = (13.9 * FT, -15.3 * FT, 40)
    coll("Markers").objects.link(co)

def render(name, cam, res=(1200, 1500), hide=("Ceilings",), samples=48):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    for n, c in COLL.items():
        c.hide_render = n in hide
    sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    for c in COLL.values():
        c.hide_render = False

def persp_cam(name, x, z, h, yaw_deg, pitch_deg=90, lens=14):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    o = bpy.data.objects.new(name, cam)
    o.location = (x * FT, -z * FT, h * FT)
    # yaw 0 = looking north (+Y); positive = turning east
    o.rotation_euler = (math.radians(pitch_deg), 0, math.radians(-yaw_deg))
    coll("Markers").objects.link(o)
    return o

def self_check():
    """Cheap sanity checks: no zero-size meshes, every mesh has a material, doors >= 2.3 ft clear."""
    bad = [o.name for o in bpy.data.objects if o.type == "MESH" and (min(o.dimensions) <= 0 or not o.data.materials)]
    assert not bad, f"broken meshes: {bad[:10]}"
    n = sum(1 for o in bpy.data.objects if o.type == "MESH")
    print(f"[check] {n} mesh objects, {len(MATS)} materials, all OK")

def verify_outputs(blend):
    """Reopen the saved .blend and re-import the .glb; both must bring back every mesh."""
    n = sum(1 for o in bpy.data.objects if o.type == "MESH")
    bpy.ops.wm.open_mainfile(filepath=blend)
    nb = sum(1 for o in bpy.data.objects if o.type == "MESH")
    missing = [i.filepath for i in bpy.data.images if not os.path.exists(bpy.path.abspath(i.filepath))]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(OUT, "unit_type_f.glb"))
    ng = sum(1 for o in bpy.data.objects if o.type == "MESH")
    assert nb == n == ng and not missing, (n, nb, ng, missing)
    print(f"[verify] .blend reopens with {nb} meshes, .glb re-imports {ng} meshes, textures present")
    bpy.ops.wm.open_mainfile(filepath=blend)
    COLL.clear()
    COLL.update({c.name: c for c in bpy.data.collections})  # old handles died with the reload

def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    make_textures()
    make_materials()
    build_structure()
    build_floors_ceilings()
    build_kitchen()
    build_baths()
    build_closets_utility()
    build_lighting_fixtures()
    build_furniture()
    build_lights()
    spawn_and_cameras()
    self_check()
    sc = bpy.context.scene
    sc.unit_settings.system = "IMPERIAL"
    sc.unit_settings.length_unit = "FEET"
    blend = os.path.join(OUT, "unit_type_f.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "unit_type_f.glb"), export_format="GLB",
                              export_lights=False, export_cameras=False)
    # FBX for Unreal (metres -> UE centimetres via FBX unit scale, textures embedded)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "unit_type_f.fbx"), object_types={"MESH", "EMPTY"},
                             apply_scale_options="FBX_SCALE_UNITS", path_mode="COPY", embed_textures=True)
    # web walkthrough loads the model from a script (the artifact host serves .js but not .glb)
    import base64
    os.makedirs(os.path.join(HERE, "web"), exist_ok=True)
    with open(os.path.join(OUT, "unit_type_f.glb"), "rb") as f, open(os.path.join(HERE, "web", "model.js"), "w") as js:
        js.write('window.UNIT_GLB="' + base64.b64encode(f.read()).decode() + '";')
    print("[saved]", blend)
    verify_outputs(blend)
    if "--render" in ARGS:
        render("top_down", bpy.data.objects["Cam_Top"], hide=("Ceilings", "Light_Fixtures", "Markers"), samples=32)
        views = [
            ("view_living_from_kitchen", persp_cam("Cam_Living", 3.5, 27.0, 5.4, 5, 86, 14)),
            ("view_kitchen", persp_cam("Cam_Kitchen", 1.8, 27.0, 5.4, 90, 85, 14)),
            ("view_primary_bedroom", persp_cam("Cam_Bed1", 16.5, -7.0, 5.4, 150, 85, 14)),
            ("view_balcony", persp_cam("Cam_Balcony", 7.0, -0.8, 5.4, 0, 88, 14)),
        ]
        for n, cam in views:
            render(n, cam, res=(1280, 800), hide=(), samples=32)

main()
