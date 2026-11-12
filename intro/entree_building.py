# Intro "QG du Bureau" : la camera s'approche d'un immeuble et entre dans le hall.
# Rendu : Blender --background --python entree_building.py
#   env INTRO_FRAMES="1,60,120" pour ne rendre que quelques images de test.
import bpy, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "frames", "f_")

def hexc(h, a=1.0):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, a)

# ---------- scene reset ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 120
sc.render.fps = 30
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in engines else 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = 24
for attr, val in (("use_shadows", True), ("use_gtao", True), ("use_raytracing", False)):
    if hasattr(sc.eevee, attr):
        setattr(sc.eevee, attr, val)
try:
    sc.view_settings.view_transform = 'Standard'
except Exception:
    pass
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = OUT

# ---------- materials ----------
MATS = {}
def mat(name, color, rough=0.6, emit=None, strength=0.0, metal=0.0):
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(p.outputs[0], o.inputs['Surface'])
    p.inputs['Base Color'].default_value = hexc(color)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if emit:
        p.inputs['Emission Color'].default_value = hexc(emit)
        p.inputs['Emission Strength'].default_value = strength
    m.diffuse_color = hexc(color)
    MATS[name] = m
    return m

WHITE = mat("blanc", "#f4f5f7", 0.55)
GREY = mat("gris", "#d9dde3", 0.7)
GLASS = mat("verre", "#9fc3ec", 0.08, metal=0.3)
GLASS_IN = mat("verre_porte", "#bcd6f5", 0.05, metal=0.2)
GROUND = mat("sol", "#e6e9ee", 0.85)
PAVE = mat("parvis", "#cfd5dd", 0.8)
OAK = mat("chene", "#dcb98f", 0.45)
OAK_DARK = mat("chene_fonce", "#c49a6c", 0.5)
TRUNK = mat("tronc", "#9a7a5a", 0.8)
LEAF = mat("feuillage", "#8fbf7a", 0.75)
LEAF2 = mat("feuillage2", "#6fa865", 0.75)
POT = mat("pot", "#f0ece6", 0.6)
BLUE = mat("bleu", "#2f5bff", 0.3, emit="#2f5bff", strength=0.6)
BLUE_GLOW = mat("bleu_lumineux", "#2f5bff", 0.3, emit="#2f5bff", strength=2.5)
LAMP = mat("lampe", "#fff4dc", 0.3, emit="#fff1d0", strength=4.0)
METAL = mat("metal", "#8a919c", 0.35, metal=0.8)

# ---------- helpers ----------
def box(name, loc, size, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(m)
    return o

def cyl(name, loc, r, d, m, verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d, location=loc)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    return o

def sphere(name, loc, r, m):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=r, location=loc)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    return o

def text(name, body, loc, size, m, rot=(math.radians(90), 0, 0), extrude=0.06):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.align_x, cu.align_y = 'CENTER', 'CENTER'
    o = bpy.data.objects.new(name, cu)
    sc.collection.objects.link(o)
    o.location, o.rotation_euler = loc, rot
    cu.materials.append(m)
    return o

# ---------- dimensions ----------
W, D = 22.0, 18.0          # largeur (x), profondeur (y)
FY = -D / 2                # facade avant
LH = 5.0                   # hauteur du hall
FLOORS, FH = 4, 3.6        # etages au-dessus du hall
TOP = LH + FLOORS * FH
DOOR_W, DOOR_H = 4.0, 3.2

# ---------- ground ----------
box("terrain", (0, -20, -0.05), (200, 200, 0.1), GROUND)
box("parvis", (0, -16, 0.01), (30, 18, 0.04), PAVE)
box("allee", (0, -40, 0.012), (5, 30, 0.04), PAVE)

# ---------- building shell ----------
box("bloc_etages", (0, 0, (LH + TOP) / 2), (W, D, TOP - LH), WHITE)
box("toit", (0, 0, TOP + 0.3), (W + 0.4, D + 0.4, 0.6), GREY)
box("dalle_hall", (0, 0, LH - 0.15), (W, D, 0.3), WHITE)
# fenetres en bandeaux sur 3 faces
for f in range(FLOORS):
    z = LH + f * FH + FH * 0.55
    h = FH * 0.62
    box(f"bandeau_av_{f}", (0, FY - 0.03, z), (W - 1.2, 0.08, h), GLASS)
    box(f"bandeau_g_{f}", (-W / 2 - 0.03, 0, z), (0.08, D - 1.2, h), GLASS)
    box(f"bandeau_d_{f}", (W / 2 + 0.03, 0, z), (0.08, D - 1.2, h), GLASS)
    for i in range(1, 8):  # meneaux blancs
        x = -W / 2 + 0.6 + i * (W - 1.2) / 8
        box(f"meneau_{f}_{i}", (x, FY - 0.09, z), (0.18, 0.08, h), WHITE)
    for i in range(1, 5):
        y = -D / 2 + 0.6 + i * (D - 1.2) / 5
        box(f"meneau_g_{f}_{i}", (-W / 2 - 0.09, y, z), (0.08, 0.18, h), WHITE)
        box(f"meneau_d_{f}_{i}", (W / 2 + 0.09, y, z), (0.08, 0.18, h), WHITE)

# hall : murs (epaisseur 0.3), facade vitree avec ouverture
box("mur_fond", (0, D / 2 - 0.15, LH / 2), (W, 0.3, LH), WHITE)
box("mur_g", (-W / 2 + 0.15, 0, LH / 2), (0.3, D, LH), WHITE)
box("mur_d", (W / 2 - 0.15, 0, LH / 2), (0.3, D, LH), WHITE)
side_w = (W - DOOR_W) / 2
for s in (-1, 1):
    cx = s * (DOOR_W / 2 + side_w / 2)
    box(f"vitrage_rdc_{s}", (cx, FY + 0.1, LH / 2), (side_w, 0.12, LH), GLASS)
    for i in range(1, 4):
        box(f"montant_{s}_{i}", (s * (DOOR_W / 2 + i * side_w / 4), FY, LH / 2), (0.15, 0.2, LH), WHITE)
    box(f"cadre_porte_{s}", (s * (DOOR_W / 2 + 0.1), FY, LH / 2), (0.2, 0.3, LH), WHITE)
box("linteau", (0, FY + 0.05, (DOOR_H + LH) / 2), (DOOR_W, 0.3, LH - DOOR_H), WHITE)
# auvent + enseigne QG sur la facade
box("auvent", (0, FY - 1.5, LH + 0.15), (8, 3.0, 0.25), WHITE)
box("enseigne_fond", (0, FY - 0.12, LH + 1.6), (3.6, 0.12, 1.6), WHITE)
text("enseigne_QG", "QG", (0, FY - 0.2, LH + 1.6), 1.4, BLUE)

# portes coulissantes
doors = []
for s in (-1, 1):
    d = box(f"porte_{s}", (s * DOOR_W / 4, FY + 0.25, DOOR_H / 2), (DOOR_W / 2 - 0.04, 0.06, DOOR_H - 0.02), GLASS_IN)
    d.keyframe_insert("location", frame=38)
    d.location.x = s * (DOOR_W / 4 + DOOR_W / 2 - 0.1)
    d.keyframe_insert("location", frame=72)
    doors.append(d)

# ---------- interior ----------
box("parquet", (0, 0, 0.02), (W - 0.6, D - 0.6, 0.04), OAK)
box("plafond_lumineux", (0, 1, LH - 0.31), (8, 4, 0.02), mat("plafond", "#fff4dc", 0.3, emit="#fff1d0", strength=1.2))
box("accueil", (0, 5.6, 0.55), (4.2, 0.9, 1.1), OAK_DARK)
box("accueil_plateau", (0, 5.55, 1.12), (4.4, 1.05, 0.06), WHITE)
box("accueil_bande", (0, 5.12, 0.55), (4.2, 0.04, 0.12), BLUE)
box("panneau_mur", (0, D / 2 - 0.32, 2.9), (6.5, 0.04, 2.2), OAK)
text("QG_hall", "QG", (0, D / 2 - 0.4, 2.9), 1.5, BLUE_GLOW, extrude=0.08)
text("sous_titre", "Bureau IA", (0, D / 2 - 0.36, 1.85), 0.32, BLUE, extrude=0.01)
for x in (-6.5, 6.5):  # plantes
    cyl(f"pot_{x}", (x, 6.8, 0.4), 0.45, 0.8, POT)
    sphere(f"plante_{x}", (x, 6.8, 1.45), 0.8, LEAF2)
for x in (-7.5, 7.5):  # banquettes
    box(f"banc_{x}", (x, -1, 0.25), (1.0, 3.0, 0.5), OAK_DARK)

# ---------- outside props ----------
def tree(x, y, s=1.0):
    cyl(f"tronc_{x}_{y}", (x, y, 1.2 * s), 0.15 * s, 2.4 * s, TRUNK, 12)
    sphere(f"arbre_{x}_{y}", (x, y, 3.0 * s), 1.4 * s, LEAF if (x + y) % 2 else LEAF2)
for x, y, s in ((-13, -10, 1.1), (13, -11, 1.0), (-14, -20, 1.2), (14, -21, 0.9), (-8, -26, 1.0), (9, -28, 1.1), (-17, 2, 1.3), (17, 3, 1.2)):
    tree(x, y, s)
for x in (-4, 4):
    for y in (-14, -24, -34):
        cyl(f"lampadaire_{x}_{y}", (x, y, 1.8), 0.06, 3.6, METAL, 10)
        sphere(f"globe_{x}_{y}", (x, y, 3.7), 0.22, LAMP)
for x in (-6, 6):
    box(f"bac_{x}", (x, -10.5, 0.3), (2.4, 1.0, 0.6), WHITE)
    sphere(f"buisson_{x}", (x, -10.5, 0.8), 0.6, LEAF)

# ---------- lights ----------
world = bpy.data.worlds.new("ciel")
sc.world = world
if world.node_tree is None:
    world.use_nodes = True
wn = world.node_tree
wn.nodes.clear()
bg = wn.nodes.new('ShaderNodeBackground')
wo = wn.nodes.new('ShaderNodeOutputWorld')
wn.links.new(bg.outputs[0], wo.inputs[0])
bg.inputs['Color'].default_value = hexc("#dbe7f7")
bg.inputs['Strength'].default_value = 0.85

sun = bpy.data.objects.new("soleil", bpy.data.lights.new("soleil", 'SUN'))
sc.collection.objects.link(sun)
sun.data.energy = 2.6
sun.data.color = hexc("#fff4e4")[:3]
sun.data.angle = math.radians(8)
sun.rotation_euler = (math.radians(50), 0, math.radians(-35))

def area(name, loc, size, energy, col="#fff6ea"):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA'))
    sc.collection.objects.link(l)
    l.data.shape = 'RECTANGLE'
    l.data.size, l.data.size_y = size
    l.data.energy = energy
    l.data.color = hexc(col)[:3]
    l.location = loc
    return l
area("hall_lum", (0, 0, LH - 0.4), (W - 2, D - 2), 800)
area("fond_lum", (0, 2, 3.5), (6, 2), 150)
l = area("bleu_lum", (0, D / 2 - 1.2, 2.9), (4, 1.5), 40, "#4a72ff")
l.rotation_euler = (math.radians(-90), 0, 0)

# ---------- camera ----------
cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 26
cam.data.clip_start = 0.05
target = bpy.data.objects.new("visee", None)
sc.collection.objects.link(target)
c = cam.constraints.new('TRACK_TO')
c.target = target
c.track_axis, c.up_axis = 'TRACK_NEGATIVE_Z', 'UP_Y'

for f, cl, tl in (
    (1,   (14, -50, 15), (0, FY, 9)),
    (60,  (2.0, -22, 4.0), (0, FY, 2.6)),
    (95,  (0, -5.6, 1.75), (0, D / 2, 2.2)),
    (120, (0, -4.2, 1.7), (0, D / 2, 2.4)),
):
    cam.location = cl
    cam.keyframe_insert("location", frame=f)
    target.location = tl
    target.keyframe_insert("location", frame=f)

for o in (cam, target, *doors):
    ad = o.animation_data
    if ad and ad.action:
        fcs = getattr(ad.action, "fcurves", None)
        if fcs is None:  # actions par couches (Blender 4.4+)
            fcs = [fc for layer in ad.action.layers for strip in layer.strips
                   for bag in strip.channelbags for fc in bag.fcurves]
        for fc in fcs:
            for k in fc.keyframe_points:
                k.interpolation = 'BEZIER'
                k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
            fc.update()

# ---------- render ----------
only = os.environ.get("INTRO_FRAMES")
if only:
    for f in map(int, only.split(",")):
        sc.frame_set(f)
        sc.render.filepath = f"{OUT}{f:04d}"
        bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
