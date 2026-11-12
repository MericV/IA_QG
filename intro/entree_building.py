# Intro "QG du Bureau" (8 s, matin lumineux) : la camera s'approche de l'immeuble au soleil levant,
# les portes vitrees s'ouvrent, elle traverse le hall jusqu'a l'ascenseur, se retourne, les portes se
# ferment, le compteur d'etages monte jusqu'a "QG" et les portes s'ouvrent sur la lumiere (fondu vers l'app).
# Rendu : Blender --background --python entree_building.py
#   env INTRO_FRAMES="1,90,150,200,235" pour ne rendre que quelques images de test.
import bpy, math, os, random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "frames", "f_")
random.seed(7)

def hexc(h, a=1.0):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, a)

# ---------- scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
END = 240
sc.frame_start, sc.frame_end = 1, END
sc.render.fps = 30
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in engines else 'BLENDER_EEVEE'
sc.eevee.taa_render_samples = 32
for attr, val in (("use_shadows", True), ("use_gtao", True), ("use_raytracing", True), ("shadow_ray_count", 2), ("shadow_step_count", 8)):
    if hasattr(sc.eevee, attr):
        setattr(sc.eevee, attr, val)
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.35
for vt, look in (("AgX", "AgX - Medium High Contrast"), ("AgX", "Medium High Contrast"), ("Filmic", "Medium High Contrast"), ("Standard", "None")):
    try:
        sc.view_settings.view_transform = vt
        try:
            sc.view_settings.look = look
        except TypeError:
            pass
        break
    except TypeError:
        continue
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = OUT

# ---------- materials ----------
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
    return m

FACADE = mat("facade", "#f3ede3", 0.6)
STONE = mat("pierre", "#d9c7ad", 0.75)
TRIM = mat("corniche", "#e8e1d5", 0.5)
GLASS = mat("verre", "#6f97c4", 0.04, metal=0.6)
GLASS_LIT = mat("verre_allume", "#a9b9c9", 0.08, emit="#ffd9a0", strength=1.6)
GLASS_DOOR = mat("verre_porte", "#cfe0f2", 0.03, metal=0.35)
LAWN = mat("pelouse", "#9cc27a", 0.9)
PAVE = mat("parvis", "#e9dfcf", 0.8)
ROAD = mat("route", "#5f646c", 0.85)
LINE = mat("ligne", "#f5f2ea", 0.6)
OAK = mat("chene", "#d9b384", 0.4)
OAK_DARK = mat("chene_fonce", "#a97d52", 0.45)
TRUNK = mat("tronc", "#7d5c42", 0.8)
LEAVES = [mat("feuillage1", "#7fb35e", 0.8), mat("feuillage2", "#5f9a4f", 0.8), mat("feuillage3", "#a3c768", 0.8)]
POT = mat("pot", "#efe9e0", 0.6)
BLUE = mat("bleu", "#2f5bff", 0.3, emit="#3d67ff", strength=1.2)
BLUE_GLOW = mat("bleu_lumineux", "#2f5bff", 0.2, emit="#4a72ff", strength=6.0)
WARM_LIGHT = mat("lumiere_chaude", "#fff4dc", 0.3, emit="#ffe9c4", strength=3.0)
STEEL = mat("acier", "#b9bec6", 0.22, metal=1.0)
STEEL_DARK = mat("acier_fonce", "#6d737c", 0.3, metal=1.0)
AMBER = mat("ambre", "#ffb347", 0.4, emit="#ffb347", strength=8.0)
WHITE_OUT = mat("lumiere_finale", "#ffffff", 0.5, emit="#fffaf2", strength=12.0)

# ---------- helpers ----------
def box(name, loc, size, m, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)  # garder la position : les portes sont animees
    if bevel:
        mod = o.modifiers.new("biseau", 'BEVEL')
        mod.width, mod.segments = bevel, 2
    o.data.materials.append(m)
    return o

def cyl(name, loc, r, d, m, verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d, location=loc)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(m)
    bpy.ops.object.shade_smooth()
    return o

def blob(name, loc, r, m):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=r, location=loc)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(m)
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

def visible(o, frames):
    """Affiche o seulement entre frames[0] et frames[1] (images incluses)."""
    a, b = frames
    for f, hide in ((1, a > 1), (a, False), (b + 1, True)):
        if f < 1:
            continue
        o.hide_render = o.hide_viewport = hide
        o.keyframe_insert("hide_render", frame=f)
        o.keyframe_insert("hide_viewport", frame=f)

ANIMATED = []
def slide(o, axis, keys):
    for f, v in keys:
        setattr(o.location, axis, v)
        o.keyframe_insert("location", frame=f)
    ANIMATED.append(o)

# ---------- dimensions ----------
W, D = 24.0, 18.0          # largeur (x), profondeur (y)
FY = -D / 2                # facade avant
BY = D / 2                 # mur du fond du hall (ascenseur)
LH = 5.0                   # hauteur du hall
FLOORS, FH = 4, 3.6
TOP = LH + FLOORS * FH
DOOR_W, DOOR_H = 4.0, 3.2
LIFT_W, LIFT_H, LIFT_D = 2.0, 2.5, 3.2
CAB_H = 3.2  # hauteur de la cabine : bandeau au-dessus des portes pour l'indicateur

# ---------- sol : pelouse, parvis, route ----------
box("pelouse", (0, -20, -0.05), (1600, 1600, 0.1), LAWN)
box("parvis", (0, -15, 0.01), (34, 14, 0.04), PAVE)
box("allee", (0, -33, 0.012), (6, 24, 0.04), PAVE)
box("route", (0, -48, 0.015), (1600, 9, 0.04), ROAD)
for i in range(-40, 41):
    box(f"pointille_{i}", (i * 6, -48, 0.04), (2.4, 0.18, 0.01), LINE)

# ---------- immeuble ----------
box("socle_pierre", (0, 0, LH / 2), (W + 0.4, D + 0.4, LH), STONE)
box("bloc_etages", (0, 0, (LH + TOP) / 2), (W, D, TOP - LH), FACADE)
box("corniche", (0, 0, TOP + 0.35), (W + 1.0, D + 1.0, 0.7), TRIM, 0.05)
BAYS = 8
for f in range(FLOORS):
    z0 = LH + f * FH
    box(f"dalle_{f}", (0, FY - 0.35, z0 + 0.1), (W + 0.6, 0.7, 0.22), TRIM, 0.03)  # nez de dalle : ombres horizontales
    for i in range(BAYS):
        x = -W / 2 + (i + 0.5) * W / BAYS
        box(f"vitre_{f}_{i}", (x, FY - 0.04, z0 + FH * 0.55), (W / BAYS - 0.7, 0.08, FH * 0.66),
            GLASS_LIT if random.random() < 0.3 else GLASS)
    for s in (-1, 1):
        for i in range(5):
            y = -D / 2 + (i + 0.5) * D / 5
            box(f"vitre_c_{s}_{f}_{i}", (s * (W / 2 + 0.04), y, z0 + FH * 0.55), (0.08, D / 5 - 0.7, FH * 0.66),
                GLASS_LIT if random.random() < 0.2 else GLASS)
for i in range(BAYS + 1):  # ailettes verticales : longues ombres du matin sur la facade
    x = -W / 2 + i * W / BAYS
    box(f"ailette_{i}", (x, FY - 0.45, (LH + TOP) / 2), (0.16, 0.9, TOP - LH), FACADE, 0.02)

# rez-de-chaussee vitre, portes et auvent
box("dalle_hall", (0, 0, LH - 0.15), (W, D, 0.3), FACADE)
side_w = (W - DOOR_W) / 2
for s in (-1, 1):
    cx = s * (DOOR_W / 2 + side_w / 2)
    box(f"vitrage_rdc_{s}", (cx, FY - 0.2, LH / 2), (side_w, 0.12, LH), GLASS_DOOR)
    for i in range(1, 5):
        box(f"montant_{s}_{i}", (s * (DOOR_W / 2 + i * side_w / 5), FY - 0.25, LH / 2), (0.14, 0.24, LH), STEEL_DARK)
    box(f"cadre_porte_{s}", (s * (DOOR_W / 2 + 0.1), FY - 0.25, LH / 2), (0.2, 0.3, LH), STEEL_DARK)
box("linteau", (0, FY - 0.2, (DOOR_H + LH) / 2), (DOOR_W, 0.3, LH - DOOR_H), STEEL_DARK)
box("auvent", (0, FY - 2.2, LH + 0.1), (9, 4.0, 0.3), TRIM, 0.05)
for s in (-1, 1):
    cyl(f"poteau_auvent_{s}", (s * 4.1, FY - 3.9, LH / 2), 0.12, LH, STEEL, 16)
box("enseigne_fond", (0, FY - 0.6, LH + 1.7), (4.2, 0.2, 1.7), FACADE, 0.04)
text("enseigne_QG", "QG", (0, FY - 0.72, LH + 1.75), 1.45, BLUE, extrude=0.08)
# le socle en pierre est creuse par le hall vitre : on retire sa face avant en le remplacant par deux piliers
bpy.data.objects.remove(bpy.data.objects["socle_pierre"], do_unlink=True)
for s in (-1, 1):
    box(f"pilier_{s}", (s * (W / 2 + 0.05), 0, LH / 2), (0.5, D + 0.4, LH), STONE)

doors = []
for s in (-1, 1):
    d = box(f"porte_{s}", (s * DOOR_W / 4, FY - 0.05, DOOR_H / 2), (DOOR_W / 2 - 0.04, 0.06, DOOR_H - 0.02), GLASS_DOOR)
    slide(d, "x", ((48, s * DOOR_W / 4), (78, s * (DOOR_W / 4 + DOOR_W / 2 - 0.1))))
    doors.append(d)

# ---------- hall ----------
box("sol_hall", (0, 0, 0.02), (W - 0.4, D - 0.4, 0.04), OAK)
box("tapis", (0, -1, 0.045), (3.2, 12, 0.01), mat("tapis", "#c9b79c", 0.95))
box("plafond", (0, 0, LH - 0.32), (W - 0.4, D - 0.4, 0.04), FACADE)
for y in (-5, 0, 5):
    box(f"rampe_lum_{y}", (0, y, LH - 0.35), (10, 0.3, 0.03), WARM_LIGHT)
# mur du fond en bois, ouverture d'ascenseur au centre
for s in (-1, 1):
    seg = (W - LIFT_W) / 2
    box(f"mur_fond_{s}", (s * (LIFT_W / 2 + seg / 2), BY - 0.2, LH / 2), (seg, 0.2, LH), OAK)
box("mur_fond_linteau", (0, BY - 0.2, (LIFT_H + LH) / 2), (LIFT_W, 0.2, LH - LIFT_H), OAK)
for s in (-1, 1):  # encadrement inox (montants + traverse), pas une plaque pleine
    box(f"cadre_asc_{s}", (s * (LIFT_W / 2 + 0.08), BY - 0.32, LIFT_H / 2), (0.16, 0.08, LIFT_H), STEEL)
box("cadre_asc_haut", (0, BY - 0.32, LIFT_H + 0.08), (LIFT_W + 0.32, 0.08, 0.16), STEEL)
text("QG_hall", "QG", (-6.2, BY - 0.36, 2.9), 1.5, BLUE_GLOW, extrude=0.08)
text("sous_titre", "Bureau IA", (-6.2, BY - 0.33, 1.95), 0.34, BLUE, extrude=0.01)
cyl("bouton_appel", (1.4, BY - 0.33, 1.2), 0.07, 0.04, AMBER, 16).rotation_euler = (math.radians(90), 0, 0)
# accueil sur le cote, plantes, banquettes
box("accueil", (6.5, 4.5, 0.55), (4.2, 1.0, 1.1), OAK_DARK, 0.04)
box("accueil_plateau", (6.5, 4.45, 1.13), (4.4, 1.15, 0.06), FACADE, 0.02)
box("accueil_bande", (6.5, 3.98, 0.6), (4.2, 0.04, 0.1), BLUE)
for x, y in ((-3, 7.4), (3, 7.4), (-9.5, -6), (9.5, -6)):
    cyl(f"pot_{x}_{y}", (x, y, 0.4), 0.45, 0.8, POT)
    blob(f"plante_{x}_{y}", (x, y, 1.4), 0.75, LEAVES[1])
    blob(f"plante2_{x}_{y}", (x + 0.3, y, 1.95), 0.45, LEAVES[0])
for x in (-8.5, 8.5):
    box(f"banc_{x}", (x, 0, 0.25), (1.0, 3.4, 0.5), OAK_DARK, 0.06)

# ---------- ascenseur (cabine derriere le mur du fond) ----------
CY = BY + LIFT_D / 2  # centre de la cabine
box("cabine_sol", (0, CY, 0.02), (LIFT_W, LIFT_D, 0.04), STEEL_DARK)
box("cabine_fond", (0, BY + LIFT_D + 0.05, CAB_H / 2), (LIFT_W + 0.2, 0.1, CAB_H), OAK)
box("cabine_bandeau", (0, BY + 0.03, (LIFT_H + CAB_H) / 2), (LIFT_W + 0.2, 0.06, CAB_H - LIFT_H), STEEL_DARK)
for s in (-1, 1):
    box(f"cabine_paroi_{s}", (s * (LIFT_W / 2 + 0.05), CY, CAB_H / 2), (0.1, LIFT_D + 0.2, CAB_H), OAK_DARK)
    box(f"cabine_liseret_{s}", (s * (LIFT_W / 2 - 0.01), CY, 2.2), (0.02, LIFT_D - 0.2, 0.04), WARM_LIGHT)
    box(f"main_courante_{s}", (s * (LIFT_W / 2 - 0.06), CY, 0.95), (0.05, LIFT_D - 0.4, 0.05), OAK_DARK)
box("cabine_plafond", (0, CY, CAB_H + 0.05), (LIFT_W + 0.2, LIFT_D + 0.2, 0.1), STEEL)
box("cabine_lumiere", (0, CY, CAB_H - 0.01), (LIFT_W - 0.5, LIFT_D - 0.6, 0.02), WARM_LIGHT)
# portes palieres : ouvertes pendant la traversee, fermees pour la montee, rouvertes sur la lumiere
lift_doors = []
for s in (-1, 1):
    d = box(f"porte_asc_{s}", (s * LIFT_W / 4, BY - 0.05, LIFT_H / 2), (LIFT_W / 2 - 0.03, 0.05, LIFT_H - 0.02), mat(f"inox_{s}", "#cfd3d8", 0.45, metal=0.35))
    closed, opened = s * LIFT_W / 4, s * (LIFT_W / 4 + LIFT_W / 2 - 0.05)
    slide(d, "x", ((92, closed), (112, opened), (168, opened), (184, closed), (220, closed), (236, opened)))
    lift_doors.append(d)
# indicateur d'etage au-dessus des portes, cote cabine (lu par la camera retournee)
IZ = (LIFT_H + CAB_H) / 2
box("indicateur_fond", (0, BY + 0.08, IZ), (0.9, 0.04, 0.42), mat("ecran", "#14181f", 0.4))
FLIP = (math.radians(90), 0, math.radians(180))
steps = [("0", 1, 188), ("1", 189, 196), ("2", 197, 203), ("3", 204, 209), ("4", 210, 214), ("QG", 215, END)]
for label, a, b in steps:
    t = text(f"etage_{label}", label, (-0.05, BY + 0.11, IZ), 0.3, AMBER, rot=FLIP, extrude=0.005)
    visible(t, (a, b))
me = bpy.data.meshes.new("fleche")  # triangle pointe en haut, a droite du chiffre (vu depuis la cabine)
me.from_pydata([(-0.32, BY + 0.11, IZ - 0.07), (-0.2, BY + 0.11, IZ - 0.07), (-0.26, BY + 0.11, IZ + 0.08)], [], [(0, 1, 2)])
fleche = bpy.data.objects.new("fleche", me)
sc.collection.objects.link(fleche)
me.materials.append(AMBER)
visible(fleche, (186, 214))
# a l'arrivee, ce qui attend derriere les portes : la lumiere (le hall disparait)
lumiere = box("lumiere_arrivee", (0, BY - 1.2, LIFT_H / 2), (6, 0.1, 5), WHITE_OUT)
visible(lumiere, (200, END))

# ---------- exterieur : arbres, lampadaires, bacs ----------
def tree(x, y, s=1.0):
    cyl(f"tronc_{x}_{y}", (x, y, 1.3 * s), 0.16 * s, 2.6 * s, TRUNK, 10)
    for k, (dx, dy, dz, r) in enumerate(((0, 0, 3.2, 1.4), (0.8, 0.3, 2.7, 1.0), (-0.7, -0.2, 2.8, 1.05), (0.1, 0.4, 3.9, 0.9))):
        blob(f"arbre_{x}_{y}_{k}", (x + dx * s, y + dy * s, dz * s), r * s, LEAVES[(k + int(x)) % 3])
for x, y, s in ((-14, -9, 1.1), (14, -10, 1.0), (-15, -19, 1.25), (15, -20, 0.95), (-9, -27, 1.0), (10, -29, 1.15),
                (-19, 3, 1.3), (19, 4, 1.2), (-24, -34, 1.4), (25, -36, 1.3), (-30, -12, 1.5), (31, -14, 1.4)):
    tree(x, y, s)
for x in (-6.5, 6.5):
    for y in (-14, -24, -34):
        cyl(f"lampadaire_{x}_{y}", (x, y, 1.9), 0.06, 3.8, STEEL_DARK, 10)
        blob(f"globe_{x}_{y}", (x, y, 3.85), 0.2, WARM_LIGHT)
for x in (-7, 7):
    box(f"bac_{x}", (x, -11.2, 0.3), (2.8, 1.1, 0.6), STONE, 0.05)
    for k in range(3):
        blob(f"buisson_{x}_{k}", (x - 0.8 + k * 0.8, -11.2, 0.85), 0.5, LEAVES[k % 3])

# ---------- lumiere : soleil levant, ciel ----------
world = bpy.data.worlds.new("ciel")
sc.world = world
if world.node_tree is None:
    world.use_nodes = True
wn = world.node_tree
wn.nodes.clear()
bg = wn.nodes.new('ShaderNodeBackground')
wo = wn.nodes.new('ShaderNodeOutputWorld')
wn.links.new(bg.outputs[0], wo.inputs[0])
sky = wn.nodes.new('ShaderNodeTexSky')
types = [e.identifier for e in sky.bl_rna.properties['sky_type'].enum_items]
for t in ('MULTIPLE_SCATTERING', 'NISHITA', 'SINGLE_SCATTERING'):
    if t in types:
        sky.sky_type = t
        break
for attr, val in (("sun_elevation", math.radians(9)), ("sun_rotation", math.radians(125)), ("sun_disc", False),
                  ("air_density", 1.0), ("dust_density", 2.0), ("altitude", 100.0)):
    if hasattr(sky, attr):
        setattr(sky, attr, val)
wn.links.new(sky.outputs[0], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 0.22

sun = bpy.data.objects.new("soleil", bpy.data.lights.new("soleil", 'SUN'))
sc.collection.objects.link(sun)
sun.data.energy = 7.5
sun.data.color = hexc("#ffb565")[:3]
sun.data.angle = math.radians(1.5)
sun.rotation_euler = (math.radians(74), 0, math.radians(-55))  # soleil bas, venant de la gauche : ombres longues

def area(name, loc, size, energy, col="#fff1dc", rot=(0, 0, 0)):
    l = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA'))
    sc.collection.objects.link(l)
    l.data.shape = 'RECTANGLE'
    l.data.size, l.data.size_y = size
    l.data.energy = energy
    l.data.color = hexc(col)[:3]
    l.location, l.rotation_euler = loc, rot
    return l
area("hall_lum", (0, 0, LH - 0.5), (W - 3, D - 3), 900)
area("cabine_lum", (0, CY, CAB_H - 0.08), (LIFT_W - 0.4, LIFT_D - 0.4), 80)
area("qg_lum", (-6.2, BY - 1.5, 2.9), (3, 1.4), 40, "#4a72ff", (math.radians(-90), 0, 0))

# ---------- camera ----------
cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 22
cam.data.clip_start = 0.05
target = bpy.data.objects.new("visee", None)
sc.collection.objects.link(target)
c = cam.constraints.new('TRACK_TO')
c.target = target
c.track_axis, c.up_axis = 'TRACK_NEGATIVE_Z', 'UP_Y'
cam.data.dof.use_dof = True
cam.data.dof.aperture_fstop = 8.0
for f, dist in ((1, 55), (55, 19), (88, 11), (125, 7), (146, 4), (168, 3.0), (226, 3.0), (END, 4)):
    cam.data.dof.focus_distance = dist
    cam.data.dof.keyframe_insert("focus_distance", frame=f)

KEYS = (
    # image, camera, visee
    (1,   (17, -58, 17),       (0, FY, 10)),       # vue d'ensemble, immeuble au soleil
    (55,  (2.2, -27, 4.0),      (0, FY, 3.4)),      # on descend vers l'entree
    (88,  (0.4, -10.5, 1.75),   (0, BY, 1.9)),      # devant les portes ouvertes, on voit l'ascenseur
    (125, (0, 3.5, 1.7),        (0, BY + 2, 1.6)),  # traversee du hall
    (146, (0, CY + 0.3, 1.65),  (0, BY + 8, 1.7)),  # dans la cabine
    (160, (0, CY + 0.7, 1.65),  (-4, CY + 0.7, 1.9)), # on se retourne...
    (174, (0, BY + 2.9, 1.62),  (0, BY - 6, 2.3)),  # ...face aux portes et a l'indicateur
    (200, (0, BY + 2.9, 1.67),  (0, BY - 6, 2.35)), # la cabine monte (leger mouvement)
    (226, (0, BY + 2.85, 1.66), (0, BY - 6, 2.0)),
    (END, (0, BY + 1.6, 1.66),  (0, BY - 6, 1.8)),  # on avance dans la lumiere
)
for f, cl, tl in KEYS:
    cam.location = cl
    cam.keyframe_insert("location", frame=f)
    target.location = tl
    target.keyframe_insert("location", frame=f)
ANIMATED += [cam, target]

def fcurves(o):
    ad = o.animation_data
    if not (ad and ad.action):
        return []
    fcs = getattr(ad.action, "fcurves", None)
    if fcs is None:  # actions par couches (Blender 4.4+)
        fcs = [fc for layer in ad.action.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
    return list(fcs)

for o in ANIMATED:
    for fc in fcurves(o):
        for k in fc.keyframe_points:
            k.interpolation = 'BEZIER'
            k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
        fc.update()
for o in bpy.data.objects:  # les apparitions/disparitions sont franches
    for fc in fcurves(o):
        if fc.data_path.startswith("hide_"):
            for k in fc.keyframe_points:
                k.interpolation = 'CONSTANT'

# ---------- rendu ----------
only = os.environ.get("INTRO_FRAMES")
if only:
    for f in map(int, only.split(",")):
        sc.frame_set(f)
        sc.render.filepath = f"{OUT}{f:04d}"
        bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
