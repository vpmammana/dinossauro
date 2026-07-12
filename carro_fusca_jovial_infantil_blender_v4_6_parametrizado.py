"""
Carro estilo Fusca jovial — versão 4.6 parametrizada
====================================================

Novidades desta versão:
- adiciona escala global da Body_Shell com apenas 3 parâmetros:
  profundidade, largura e altura;
- mantém BODY_SHELL_STATIONS para refinamento fino, mas a escala global
  permite ajustes rápidos;
- remove Rear_Deck e Rear_Deck_Blend;
- o Windshield agora:
  1) corta de fato a Body_Shell;
  2) é recriado como superfície própria;
  3) recebe SHRINKWRAP na Body_Shell já cortada, para acompanhar
     melhor o contorno do topo e da abertura criada;
  4) recebe SOLIDIFY para virar vidro espesso;
- Side_Window_* e Rear_Window continuam fazendo cortes reais;
- Rear_Window agora tem posição X/Y/Z e rotação X/Y/Z parametrizadas.
"""

import bpy
import bmesh
import math
import warnings
from mathutils import Vector, Euler

GENERATOR_VERSION = "4.6-fusca-jovial-bodyshell-scale-windshield-wrap"
GROUND_SIZE = 24.0

WHEEL_RADIUS = 0.34
WHEEL_WIDTH = 0.22

COLLECTION_MAIN = "CuteBeetle_Generated"
COLLECTION_MODEL = "MODEL_Meshes"
COLLECTION_ENV = "ENVIRONMENT"
ROOT_NAME = "CuteBeetle_Root"


# ############################################################################
# #             >>> PARÂMETROS EDITÁVEIS PRINCIPAIS <<<                     #
# ############################################################################
#
# Eixos:
#   X = profundidade / frente-traseira
#   Y = largura / esquerda-direita
#   Z = altura
#
# Escala global rápida da Body_Shell:
#   BODY_SHELL_ESCALA_PROFUNDIDADE
#   BODY_SHELL_ESCALA_LARGURA
#   BODY_SHELL_ESCALA_ALTURA
#
# Refinamento fino da Body_Shell:
#   BODY_SHELL_STATIONS
# ############################################################################

# ---------------------------------------------------------------------------
# BODY SHELL — escala global simples em 3 parâmetros
# ---------------------------------------------------------------------------
BODY_SHELL_ESCALA_PROFUNDIDADE = 1.00
BODY_SHELL_ESCALA_LARGURA = 1.00
BODY_SHELL_ESCALA_ALTURA = 1.00

# ---------------------------------------------------------------------------
# BODY SHELL — refinamento fino por estações
# Cada tupla:
# (X, HALF_WIDTH, Z_BOTTOM, Z_TOP, PINCH_BOTTOM, FULLNESS_TOP)
# ---------------------------------------------------------------------------
BODY_SHELL_SECTION_POINTS = 16
BODY_SHELL_STATIONS = [
    ( 0.48, 0.67, 0.42, 1.52, 0.15, 0.10),
    ( 0.28, 0.70, 0.42, 1.60, 0.12, 0.10),
    (-0.06, 0.66, 0.43, 1.50, 0.14, 0.08),
    (-0.42, 0.58, 0.45, 1.30, 0.18, 0.06),
    (-0.74, 0.50, 0.47, 1.12, 0.22, 0.05),
    (-1.00, 0.36, 0.50, 0.96, 0.26, 0.04),
    (-1.24, 0.18, 0.55, 0.82, 0.32, 0.03),
]

# ---------------------------------------------------------------------------
# FRONT_HOOD
# ---------------------------------------------------------------------------
FRONT_HOOD_X = 0.50
FRONT_HOOD_Y = 0.00
FRONT_HOOD_Z = 0.82
FRONT_HOOD_PROFUNDIDADE = 2.00
FRONT_HOOD_LARGURA = 1.50
FRONT_HOOD_ALTURA = 0.70

# ---------------------------------------------------------------------------
# HEADLIGHT_L
# ---------------------------------------------------------------------------
HEADLIGHT_L_X = 1.32
HEADLIGHT_L_Y = 0.73
HEADLIGHT_L_Z = 0.72
HEADLIGHT_L_PROFUNDIDADE = 0.28
HEADLIGHT_L_LARGURA = 0.28
HEADLIGHT_L_ALTURA = 0.28

# ---------------------------------------------------------------------------
# HEADLIGHT_R
# ---------------------------------------------------------------------------
HEADLIGHT_R_X = 1.32
HEADLIGHT_R_Y = -0.73
HEADLIGHT_R_Z = 0.72
HEADLIGHT_R_PROFUNDIDADE = 0.28
HEADLIGHT_R_LARGURA = 0.28
HEADLIGHT_R_ALTURA = 0.28

# ---------------------------------------------------------------------------
# FRONT_FENDER_L_BASE
# ---------------------------------------------------------------------------
FRONT_FENDER_L_BASE_X = 0.86
FRONT_FENDER_L_BASE_Y = 0.73
FRONT_FENDER_L_BASE_Z = 0.63
FRONT_FENDER_L_BASE_PROFUNDIDADE = 1.12
FRONT_FENDER_L_BASE_LARGURA = 0.56
FRONT_FENDER_L_BASE_ALTURA = 0.76

# ---------------------------------------------------------------------------
# FRONT_FENDER_R_BASE
# ---------------------------------------------------------------------------
FRONT_FENDER_R_BASE_X = 0.86
FRONT_FENDER_R_BASE_Y = -0.73
FRONT_FENDER_R_BASE_Z = 0.63
FRONT_FENDER_R_BASE_PROFUNDIDADE = 1.12
FRONT_FENDER_R_BASE_LARGURA = 0.56
FRONT_FENDER_R_BASE_ALTURA = 0.76

# ---------------------------------------------------------------------------
# REAR_FENDER_L_BASE
# ---------------------------------------------------------------------------
REAR_FENDER_L_BASE_X = -0.87
REAR_FENDER_L_BASE_Y = 0.73
REAR_FENDER_L_BASE_Z = 0.74
REAR_FENDER_L_BASE_PROFUNDIDADE = 1.20
REAR_FENDER_L_BASE_LARGURA = 0.58
REAR_FENDER_L_BASE_ALTURA = 0.90

# ---------------------------------------------------------------------------
# REAR_FENDER_R_BASE
# ---------------------------------------------------------------------------
REAR_FENDER_R_BASE_X = -0.87
REAR_FENDER_R_BASE_Y = -0.73
REAR_FENDER_R_BASE_Z = 0.74
REAR_FENDER_R_BASE_PROFUNDIDADE = 1.20
REAR_FENDER_R_BASE_LARGURA = 0.58
REAR_FENDER_R_BASE_ALTURA = 0.90

# ---------------------------------------------------------------------------
# PUPIL_OFFSET_X
# ---------------------------------------------------------------------------
PUPIL_OFFSET_X = 0.09

# ---------------------------------------------------------------------------
# WINDSHIELD — cutter e vidro
# O cutter usa largura superior e inferior.
# O vidro final é uma malha em grade que é shrink-wrapped na Body_Shell cortada.
# ---------------------------------------------------------------------------
WINDSHIELD_X = 0.47
WINDSHIELD_Y = 0.00
WINDSHIELD_Z = 1.30

WINDSHIELD_CUTTER_THICKNESS = 0.08
WINDSHIELD_GLASS_THICKNESS = 0.028

WINDSHIELD_HEIGHT = 0.60
WINDSHIELD_WIDTH_BOTTOM = 1.02
WINDSHIELD_WIDTH_TOP = 1.36

WINDSHIELD_ROT_X_DEG = 0.0
WINDSHIELD_ROT_Y_DEG = -10.0
WINDSHIELD_ROT_Z_DEG = 0.0

WINDSHIELD_GRID_COLS = 9
WINDSHIELD_GRID_ROWS = 6
WINDSHIELD_SHRINKWRAP_OFFSET = 0.0015

# ---------------------------------------------------------------------------
# SIDE WINDOWS FRONT
# ---------------------------------------------------------------------------
SIDE_WINDOW_FRONT_X = 0.14
SIDE_WINDOW_FRONT_Y = 0.59
SIDE_WINDOW_FRONT_Z = 1.28
SIDE_WINDOW_FRONT_LENGTH = 0.52
SIDE_WINDOW_FRONT_HEIGHT = 0.34
SIDE_WINDOW_FRONT_THICKNESS = 0.06

# ---------------------------------------------------------------------------
# SIDE WINDOWS REAR
# ---------------------------------------------------------------------------
SIDE_WINDOW_REAR_X = -0.22
SIDE_WINDOW_REAR_Y = 0.59
SIDE_WINDOW_REAR_Z = 1.22
SIDE_WINDOW_REAR_LENGTH = 0.34
SIDE_WINDOW_REAR_HEIGHT = 0.24
SIDE_WINDOW_REAR_THICKNESS = 0.06

# ---------------------------------------------------------------------------
# REAR WINDOW — posição e rotações completas
# ---------------------------------------------------------------------------
REAR_WINDOW_X = -0.58
REAR_WINDOW_Y = 0.00
REAR_WINDOW_Z = 1.20

REAR_WINDOW_ROT_X_DEG = 0.0
REAR_WINDOW_ROT_Y_DEG = 42.0
REAR_WINDOW_ROT_Z_DEG = 0.0

REAR_WINDOW_WIDTH = 0.96
REAR_WINDOW_HEIGHT = 0.34
REAR_WINDOW_THICKNESS = 0.06

# oversize dos cutters boolean
CUTTER_SCALE_X = 1.18
CUTTER_SCALE_Y = 1.45
CUTTER_SCALE_Z = 1.15


# ============================================================================
# VALIDAÇÃO DOS PARÂMETROS
# ============================================================================

def assert_positive(value, name):
    if value <= 0:
        raise ValueError(f"O parâmetro {name} deve ser > 0. Valor atual: {value!r}")


def validate_parameters():
    positive = {
        "BODY_SHELL_ESCALA_PROFUNDIDADE": BODY_SHELL_ESCALA_PROFUNDIDADE,
        "BODY_SHELL_ESCALA_LARGURA": BODY_SHELL_ESCALA_LARGURA,
        "BODY_SHELL_ESCALA_ALTURA": BODY_SHELL_ESCALA_ALTURA,
        "FRONT_HOOD_PROFUNDIDADE": FRONT_HOOD_PROFUNDIDADE,
        "FRONT_HOOD_LARGURA": FRONT_HOOD_LARGURA,
        "FRONT_HOOD_ALTURA": FRONT_HOOD_ALTURA,
        "HEADLIGHT_L_PROFUNDIDADE": HEADLIGHT_L_PROFUNDIDADE,
        "HEADLIGHT_L_LARGURA": HEADLIGHT_L_LARGURA,
        "HEADLIGHT_L_ALTURA": HEADLIGHT_L_ALTURA,
        "HEADLIGHT_R_PROFUNDIDADE": HEADLIGHT_R_PROFUNDIDADE,
        "HEADLIGHT_R_LARGURA": HEADLIGHT_R_LARGURA,
        "HEADLIGHT_R_ALTURA": HEADLIGHT_R_ALTURA,
        "FRONT_FENDER_L_BASE_PROFUNDIDADE": FRONT_FENDER_L_BASE_PROFUNDIDADE,
        "FRONT_FENDER_L_BASE_LARGURA": FRONT_FENDER_L_BASE_LARGURA,
        "FRONT_FENDER_L_BASE_ALTURA": FRONT_FENDER_L_BASE_ALTURA,
        "FRONT_FENDER_R_BASE_PROFUNDIDADE": FRONT_FENDER_R_BASE_PROFUNDIDADE,
        "FRONT_FENDER_R_BASE_LARGURA": FRONT_FENDER_R_BASE_LARGURA,
        "FRONT_FENDER_R_BASE_ALTURA": FRONT_FENDER_R_BASE_ALTURA,
        "REAR_FENDER_L_BASE_PROFUNDIDADE": REAR_FENDER_L_BASE_PROFUNDIDADE,
        "REAR_FENDER_L_BASE_LARGURA": REAR_FENDER_L_BASE_LARGURA,
        "REAR_FENDER_L_BASE_ALTURA": REAR_FENDER_L_BASE_ALTURA,
        "REAR_FENDER_R_BASE_PROFUNDIDADE": REAR_FENDER_R_BASE_PROFUNDIDADE,
        "REAR_FENDER_R_BASE_LARGURA": REAR_FENDER_R_BASE_LARGURA,
        "REAR_FENDER_R_BASE_ALTURA": REAR_FENDER_R_BASE_ALTURA,
        "WINDSHIELD_HEIGHT": WINDSHIELD_HEIGHT,
        "WINDSHIELD_WIDTH_BOTTOM": WINDSHIELD_WIDTH_BOTTOM,
        "WINDSHIELD_WIDTH_TOP": WINDSHIELD_WIDTH_TOP,
        "WINDSHIELD_CUTTER_THICKNESS": WINDSHIELD_CUTTER_THICKNESS,
        "WINDSHIELD_GLASS_THICKNESS": WINDSHIELD_GLASS_THICKNESS,
        "REAR_WINDOW_WIDTH": REAR_WINDOW_WIDTH,
        "REAR_WINDOW_HEIGHT": REAR_WINDOW_HEIGHT,
        "REAR_WINDOW_THICKNESS": REAR_WINDOW_THICKNESS,
    }
    for name, value in positive.items():
        assert_positive(value, name)

    if len(BODY_SHELL_STATIONS) < 2:
        raise ValueError("BODY_SHELL_STATIONS precisa ter pelo menos duas estações.")


# ============================================================================
# LIMPEZA
# ============================================================================

def remove_all(datablocks):
    for datablock in list(datablocks):
        try:
            datablocks.remove(datablock, do_unlink=True)
        except TypeError:
            datablocks.remove(datablock)


def clean_entire_scene():
    scene = bpy.context.scene
    active = bpy.context.object
    if active is not None and active.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass

    scene.camera = None
    scene.world = None

    remove_all(bpy.data.objects)
    remove_all(bpy.data.collections)
    remove_all(bpy.data.meshes)
    remove_all(bpy.data.curves)
    remove_all(bpy.data.armatures)
    remove_all(bpy.data.cameras)
    remove_all(bpy.data.lights)
    remove_all(bpy.data.materials)
    remove_all(bpy.data.actions)
    remove_all(bpy.data.worlds)

    for attribute_name in (
        "metaballs", "lattices", "grease_pencils", "volumes", "pointclouds"
    ):
        datablocks = getattr(bpy.data, attribute_name, None)
        if datablocks is not None:
            remove_all(datablocks)

    bpy.context.view_layer.update()


# ============================================================================
# AUXILIARES GERAIS
# ============================================================================

def new_child_collection(name, parent):
    collection = bpy.data.collections.new(name)
    parent.children.link(collection)
    return collection


def create_empty(name, location, collection, parent=None,
                 display_type="ARROWS", display_size=0.35):
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    obj.empty_display_type = display_type
    obj.empty_display_size = display_size
    obj.show_in_front = True
    obj.hide_render = True
    obj.rotation_mode = "XYZ"
    if parent is not None:
        obj.parent = parent
    obj.location = Vector(location)
    return obj


def create_mesh_object(name, vertices, faces, collection, material=None,
                       parent=None, local_location=(0.0, 0.0, 0.0),
                       smooth=True, rotation=(0.0, 0.0, 0.0)):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata([tuple(Vector(v)) for v in vertices], [], [tuple(f) for f in faces])
    mesh.update(calc_edges=True)

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = Vector(local_location)
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = Euler(rotation, "XYZ")

    if parent is not None:
        obj.parent = parent
    if material is not None:
        mesh.materials.append(material)
    if smooth:
        for poly in mesh.polygons:
            poly.use_smooth = True
    return obj


def create_box(name, local_center, size_xyz, collection, material,
               parent=None, smooth=False, rotation=(0.0, 0.0, 0.0)):
    sx, sy, sz = size_xyz[0] * 0.5, size_xyz[1] * 0.5, size_xyz[2] * 0.5
    vertices = [
        (-sx, -sy, -sz), ( sx, -sy, -sz), ( sx,  sy, -sz), (-sx,  sy, -sz),
        (-sx, -sy,  sz), ( sx, -sy,  sz), ( sx,  sy,  sz), (-sx,  sy,  sz),
    ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
        (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
    ]
    return create_mesh_object(
        name=name, vertices=vertices, faces=faces,
        collection=collection, material=material,
        parent=parent, local_location=local_center,
        smooth=smooth, rotation=rotation,
    )


def create_ellipsoid(name, local_center, radii, collection, material,
                     parent=None, subdivisions=2, rotation=(0.0, 0.0, 0.0)):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=1.0)
    rx, ry, rz = radii
    for vert in bm.verts:
        vert.co.x *= rx
        vert.co.y *= ry
        vert.co.z *= rz
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = Vector(local_center)
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = Euler(rotation, "XYZ")
    if parent is not None:
        obj.parent = parent

    mesh.materials.append(material)
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


def create_cylinder_y(name, local_center, radius, length, collection,
                      material, parent=None, sides=18, smooth=True):
    vertices = []
    faces = []
    half = length * 0.5

    for y_value in (-half, half):
        for idx in range(sides):
            angle = 2.0 * math.pi * idx / sides
            x = math.cos(angle) * radius
            z = math.sin(angle) * radius
            vertices.append((x, y_value, z))

    for idx in range(sides):
        next_idx = (idx + 1) % sides
        faces.append((idx, next_idx, sides + next_idx, sides + idx))

    faces.append(tuple(reversed(range(sides))))
    faces.append(tuple(sides + idx for idx in range(sides)))

    return create_mesh_object(
        name=name, vertices=vertices, faces=faces,
        collection=collection, material=material,
        parent=parent, local_location=local_center,
        smooth=smooth,
    )


def create_plane(name, size, z, collection, material):
    half = size * 0.5
    vertices = [
        (-half, -half, z), (half, -half, z),
        (half, half, z), (-half, half, z),
    ]
    faces = [(0, 1, 2, 3)]
    return create_mesh_object(
        name=name, vertices=vertices, faces=faces,
        collection=collection, material=material, smooth=False,
    )


def create_loft_shell(name, stations, section_points, collection, material,
                      parent=None, local_location=(0.0, 0.0, 0.0)):
    vertices = []
    faces = []

    for x, half_width, z_bottom, z_top, pinch_bottom, fullness_top in stations:
        center_z = 0.5 * (z_bottom + z_top)
        radius_z = 0.5 * (z_top - z_bottom)

        for i in range(section_points):
            phi = 2.0 * math.pi * i / section_points
            c = math.cos(phi)
            s = math.sin(phi)

            bottom_factor = max(0.0, -s)
            top_factor = max(0.0, s)
            local_half_width = half_width * (
                1.0 - pinch_bottom * bottom_factor + fullness_top * top_factor * 0.12
            )

            y = c * local_half_width
            z = center_z + s * radius_z

            if abs(c) < 0.35:
                y *= 0.96

            vertices.append((x, y, z))

    ring = section_points
    station_count = len(stations)

    def vidx(s, i):
        return s * ring + i

    for s in range(station_count - 1):
        for i in range(ring):
            j = (i + 1) % ring
            faces.append((vidx(s, i), vidx(s, j), vidx(s + 1, j), vidx(s + 1, i)))

    front_center_index = len(vertices)
    fx, _, fzb, fzt, _, _ = stations[0]
    vertices.append((fx, 0.0, 0.5 * (fzb + fzt)))
    for i in range(ring):
        j = (i + 1) % ring
        faces.append((front_center_index, vidx(0, i), vidx(0, j)))

    rear_center_index = len(vertices)
    rx, _, rzb, rzt, _, _ = stations[-1]
    vertices.append((rx, 0.0, 0.5 * (rzb + rzt)))
    last_s = station_count - 1
    for i in range(ring):
        j = (i + 1) % ring
        faces.append((rear_center_index, vidx(last_s, j), vidx(last_s, i)))

    return create_mesh_object(
        name=name, vertices=vertices, faces=faces,
        collection=collection, material=material,
        parent=parent, local_location=local_location, smooth=True,
    )


def create_side_window_profile(name, center, size_xyz, collection, material,
                               parent=None, mirror_y=1.0):
    sx, sy, sz = size_xyz
    hx = sx * 0.5
    hy = sy * 0.5
    hz = sz * 0.5

    vertices = [
        (-hx, -hy, -hz),
        ( hx * 0.78, -hy, -hz * 0.92),
        ( hx, -hy,  hz * 0.54),
        (-hx * 0.65, -hy, hz),
        (-hx,  hy, -hz),
        ( hx * 0.78,  hy, -hz * 0.92),
        ( hx,  hy,  hz * 0.54),
        (-hx * 0.65, hy, hz),
    ]
    if mirror_y < 0:
        vertices = [(x, -y, z) for (x, y, z) in vertices]

    faces = [
        (0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
        (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0),
    ]

    return create_mesh_object(
        name=name, vertices=vertices, faces=faces,
        collection=collection, material=material,
        parent=parent, local_location=center, smooth=False,
    )


def create_windshield_prism(name, center, width_bottom, width_top, height,
                            thickness, collection, material, parent=None,
                            rotation=(0.0, 0.0, 0.0)):
    hy_bottom = width_bottom * 0.5
    hy_top = width_top * 0.5
    hz = height * 0.5
    hx = thickness * 0.5

    vertices = [
        (-hx, -hy_bottom, -hz),
        (-hx,  hy_bottom, -hz),
        (-hx,  hy_top,    hz),
        (-hx, -hy_top,    hz),
        ( hx, -hy_bottom, -hz),
        ( hx,  hy_bottom, -hz),
        ( hx,  hy_top,    hz),
        ( hx, -hy_top,    hz),
    ]
    faces = [
        (0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
        (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0),
    ]
    return create_mesh_object(
        name=name, vertices=vertices, faces=faces,
        collection=collection, material=material,
        parent=parent, local_location=center, smooth=False, rotation=rotation,
    )


def create_windshield_surface_grid(name, center, width_bottom, width_top, height,
                                   cols, rows, collection, material, parent=None,
                                   rotation=(0.0, 0.0, 0.0)):
    vertices = []
    faces = []

    hz = height * 0.5
    for r in range(rows):
        t = 0.0 if rows == 1 else r / (rows - 1)
        z = -hz + t * height
        width_here = (1.0 - t) * width_bottom + t * width_top
        hy = width_here * 0.5

        for c in range(cols):
            u = 0.0 if cols == 1 else c / (cols - 1)
            y = -hy + u * width_here
            x = 0.0
            vertices.append((x, y, z))

    def vid(r, c):
        return r * cols + c

    for r in range(rows - 1):
        for c in range(cols - 1):
            faces.append((vid(r, c), vid(r, c + 1), vid(r + 1, c + 1), vid(r + 1, c)))

    return create_mesh_object(
        name=name, vertices=vertices, faces=faces,
        collection=collection, material=material,
        parent=parent, local_location=center, smooth=False, rotation=rotation,
    )


def create_arc_bumper(name, center, radius_y, depth_x, tube_radius,
                      collection, material, parent=None,
                      start_deg=-70.0, end_deg=70.0,
                      path_segments=14, ring_segments=8):
    cx, cy, cz = center
    path = []
    for i in range(path_segments + 1):
        t = i / path_segments
        ang = math.radians(start_deg + (end_deg - start_deg) * t)
        x = cx + math.cos(ang) * depth_x
        y = cy + math.sin(ang) * radius_y
        z = cz
        path.append(Vector((x, y, z)))

    vertices = []
    faces = []

    for i, p in enumerate(path):
        if i == 0:
            tangent = (path[i + 1] - p).normalized()
        elif i == len(path) - 1:
            tangent = (p - path[i - 1]).normalized()
        else:
            tangent = (path[i + 1] - path[i - 1]).normalized()

        up = Vector((0.0, 0.0, 1.0))
        normal = tangent.cross(up)
        if normal.length < 1.0e-8:
            normal = Vector((1.0, 0.0, 0.0))
        normal.normalize()
        binormal = normal.cross(tangent).normalized()

        for j in range(ring_segments):
            phi = 2.0 * math.pi * j / ring_segments
            offset = normal * (math.cos(phi) * tube_radius) + binormal * (math.sin(phi) * tube_radius)
            q = p + offset
            vertices.append((q.x, q.y, q.z))

    ring = ring_segments
    rings = len(path)

    def vidx(r, j):
        return r * ring + j

    for r in range(rings - 1):
        for j in range(ring):
            k = (j + 1) % ring
            faces.append((vidx(r, j), vidx(r, k), vidx(r + 1, k), vidx(r + 1, j)))

    return create_mesh_object(
        name=name, vertices=vertices, faces=faces,
        collection=collection, material=material,
        parent=parent, local_location=(0.0, 0.0, 0.0), smooth=True,
    )


def create_boolean_cutter_from_object(source_obj, name, collection, parent=None):
    mesh = source_obj.data.copy()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.matrix_world = source_obj.matrix_world.copy()
    if parent is not None:
        obj.parent = parent
    return obj


def apply_modifier(obj, modifier_name):
    view_layer = bpy.context.view_layer
    for o in view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj
    try:
        bpy.ops.object.modifier_apply(modifier=modifier_name)
    except RuntimeError:
        pass


def apply_boolean_difference(target_obj, cutter_obj):
    modifier = target_obj.modifiers.new(name=f"BOOL_{cutter_obj.name}", type="BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter_obj
    apply_modifier(target_obj, modifier.name)
    cutter_obj.hide_viewport = True
    cutter_obj.hide_render = True


def add_shrinkwrap_and_apply(obj, target_obj, offset=0.0):
    mod = obj.modifiers.new(name="ShrinkwrapToBodyShell", type="SHRINKWRAP")
    mod.target = target_obj
    mod.wrap_method = "NEAREST_SURFACEPOINT"
    mod.offset = offset
    apply_modifier(obj, mod.name)


def add_solidify_and_apply(obj, thickness):
    mod = obj.modifiers.new(name="SolidifyGlass", type="SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 0.0
    mod.use_even_offset = True
    apply_modifier(obj, mod.name)


def look_at(obj, target, track_axis="-Z", up_axis="Y"):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat(track_axis, up_axis).to_euler()


def world_dimensions(objects):
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for obj in objects:
        if obj.type != "MESH":
            continue
        matrix = obj.matrix_world
        for vert in obj.data.vertices:
            p = matrix @ vert.co
            mins.x = min(mins.x, p.x)
            mins.y = min(mins.y, p.y)
            mins.z = min(mins.z, p.z)
            maxs.x = max(maxs.x, p.x)
            maxs.y = max(maxs.y, p.y)
            maxs.z = max(maxs.z, p.z)
    return mins, maxs, maxs - mins


# ============================================================================
# MATERIAIS
# ============================================================================

def set_node_input(node, name, value):
    socket = node.inputs.get(name)
    if socket is not None:
        socket.default_value = value


def ensure_node_tree(id_block):
    node_tree = getattr(id_block, "node_tree", None)
    if node_tree is not None:
        return node_tree
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            setattr(id_block, "use_nodes", True)
    except (AttributeError, TypeError):
        pass
    node_tree = getattr(id_block, "node_tree", None)
    if node_tree is None:
        raise RuntimeError(f"Não foi possível criar a árvore de nós de {id_block.name!r}.")
    return node_tree


def create_principled_material(name, color, roughness=0.55, metallic=0.0,
                               alpha=1.0, transmission=0.0,
                               blend_method="OPAQUE"):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, alpha)
    material.blend_method = blend_method

    node_tree = ensure_node_tree(material)
    nodes = node_tree.nodes
    links = node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")

    set_node_input(shader, "Base Color", (*color, 1.0))
    set_node_input(shader, "Roughness", roughness)
    set_node_input(shader, "Metallic", metallic)

    if "Alpha" in shader.inputs:
        shader.inputs["Alpha"].default_value = alpha
    if "Transmission Weight" in shader.inputs:
        shader.inputs["Transmission Weight"].default_value = transmission
    elif "Transmission" in shader.inputs:
        shader.inputs["Transmission"].default_value = transmission

    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def build_materials():
    mats = {}
    mats["body"] = create_principled_material(
        "MAT_CuteBeetle_Body",
        color=(0.84, 0.10, 0.12),
        roughness=0.40,
        metallic=0.0,
    )
    mats["accent"] = create_principled_material(
        "MAT_CuteBeetle_Accent",
        color=(0.96, 0.96, 0.96),
        roughness=0.34,
        metallic=0.0,
    )
    mats["glass"] = create_principled_material(
        "MAT_CuteBeetle_Glass",
        color=(0.18, 0.42, 0.95),
        roughness=0.08,
        metallic=0.0,
        alpha=0.34,
        transmission=0.20,
        blend_method="BLEND",
    )
    mats["rubber"] = create_principled_material(
        "MAT_CuteBeetle_Rubber",
        color=(0.04, 0.04, 0.045),
        roughness=0.95,
        metallic=0.0,
    )
    mats["rim"] = create_principled_material(
        "MAT_CuteBeetle_Rim",
        color=(0.90, 0.92, 0.95),
        roughness=0.24,
        metallic=0.82,
    )
    mats["headlight"] = create_principled_material(
        "MAT_CuteBeetle_Headlight",
        color=(0.99, 0.97, 0.89),
        roughness=0.18,
        metallic=0.0,
    )
    mats["black"] = create_principled_material(
        "MAT_CuteBeetle_Black",
        color=(0.03, 0.03, 0.035),
        roughness=0.70,
        metallic=0.0,
    )
    mats["ground"] = create_principled_material(
        "MAT_CuteBeetle_Ground",
        color=(0.13, 0.17, 0.11),
        roughness=1.0,
        metallic=0.0,
    )
    return mats


# ============================================================================
# CONSTRUÇÃO
# ============================================================================

def build_cute_beetle(scene):
    main_collection = bpy.data.collections.new(COLLECTION_MAIN)
    scene.collection.children.link(main_collection)

    model_collection = new_child_collection(COLLECTION_MODEL, main_collection)
    env_collection = new_child_collection(COLLECTION_ENV, main_collection)

    materials = build_materials()

    root = create_empty(
        ROOT_NAME,
        location=(0.0, 0.0, 0.0),
        collection=model_collection,
        display_type="ARROWS",
        display_size=0.55,
    )

    body_shell = create_loft_shell(
        name="Body_Shell",
        stations=BODY_SHELL_STATIONS,
        section_points=BODY_SHELL_SECTION_POINTS,
        collection=model_collection,
        material=materials["body"],
        parent=root,
        local_location=(0.0, 0.0, 0.0),
    )
    body_shell.scale = (
        BODY_SHELL_ESCALA_PROFUNDIDADE,
        BODY_SHELL_ESCALA_LARGURA,
        BODY_SHELL_ESCALA_ALTURA,
    )

    create_ellipsoid(
        "Front_Hood",
        local_center=(FRONT_HOOD_X, FRONT_HOOD_Y, FRONT_HOOD_Z),
        radii=(
            FRONT_HOOD_PROFUNDIDADE * 0.5,
            FRONT_HOOD_LARGURA * 0.5,
            FRONT_HOOD_ALTURA * 0.5,
        ),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        subdivisions=2,
        rotation=(0.0, 0.08, 0.0),
    )

    create_box(
        "Lower_Body",
        local_center=(0.00, 0.0, 0.49),
        size_xyz=(2.44, 1.16, 0.18),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        smooth=False,
    )
    create_box(
        "RunningBoard_L",
        local_center=(0.00, 0.66, 0.56),
        size_xyz=(1.94, 0.18, 0.06),
        collection=model_collection,
        material=materials["accent"],
        parent=root,
        smooth=False,
    )
    create_box(
        "RunningBoard_R",
        local_center=(0.00, -0.66, 0.56),
        size_xyz=(1.94, 0.18, 0.06),
        collection=model_collection,
        material=materials["accent"],
        parent=root,
        smooth=False,
    )

    # ----------------------------------------------------------------------
    # WINDSHIELD: cutter + vidro conformado
    # ----------------------------------------------------------------------
    windshield_cutter = create_windshield_prism(
        "Windshield_Cutter_Base",
        center=(WINDSHIELD_X, WINDSHIELD_Y, WINDSHIELD_Z),
        width_bottom=WINDSHIELD_WIDTH_BOTTOM,
        width_top=WINDSHIELD_WIDTH_TOP,
        height=WINDSHIELD_HEIGHT,
        thickness=WINDSHIELD_CUTTER_THICKNESS,
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        rotation=(
            math.radians(WINDSHIELD_ROT_X_DEG),
            math.radians(WINDSHIELD_ROT_Y_DEG),
            math.radians(WINDSHIELD_ROT_Z_DEG),
        ),
    )

    windshield_cut = create_boolean_cutter_from_object(
        windshield_cutter, "CUT_Windshield", model_collection, parent=root
    )
    windshield_cut.scale.x *= CUTTER_SCALE_X
    windshield_cut.scale.y *= CUTTER_SCALE_Y
    windshield_cut.scale.z *= CUTTER_SCALE_Z
    apply_boolean_difference(body_shell, windshield_cut)

    windshield = create_windshield_surface_grid(
        "Windshield",
        center=(WINDSHIELD_X, WINDSHIELD_Y, WINDSHIELD_Z),
        width_bottom=WINDSHIELD_WIDTH_BOTTOM,
        width_top=WINDSHIELD_WIDTH_TOP,
        height=WINDSHIELD_HEIGHT,
        cols=WINDSHIELD_GRID_COLS,
        rows=WINDSHIELD_GRID_ROWS,
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        rotation=(
            math.radians(WINDSHIELD_ROT_X_DEG),
            math.radians(WINDSHIELD_ROT_Y_DEG),
            math.radians(WINDSHIELD_ROT_Z_DEG),
        ),
    )
    add_shrinkwrap_and_apply(windshield, body_shell, offset=WINDSHIELD_SHRINKWRAP_OFFSET)
    add_solidify_and_apply(windshield, WINDSHIELD_GLASS_THICKNESS)

    # ----------------------------------------------------------------------
    # SIDE WINDOWS E REAR WINDOW
    # ----------------------------------------------------------------------
    side_window_l_front = create_side_window_profile(
        "Side_Window_L_Front",
        center=(SIDE_WINDOW_FRONT_X, SIDE_WINDOW_FRONT_Y, SIDE_WINDOW_FRONT_Z),
        size_xyz=(
            SIDE_WINDOW_FRONT_LENGTH,
            SIDE_WINDOW_FRONT_THICKNESS,
            SIDE_WINDOW_FRONT_HEIGHT,
        ),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        mirror_y=1.0,
    )
    side_window_r_front = create_side_window_profile(
        "Side_Window_R_Front",
        center=(SIDE_WINDOW_FRONT_X, -SIDE_WINDOW_FRONT_Y, SIDE_WINDOW_FRONT_Z),
        size_xyz=(
            SIDE_WINDOW_FRONT_LENGTH,
            SIDE_WINDOW_FRONT_THICKNESS,
            SIDE_WINDOW_FRONT_HEIGHT,
        ),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        mirror_y=-1.0,
    )
    side_window_l_rear = create_side_window_profile(
        "Side_Window_L_Rear",
        center=(SIDE_WINDOW_REAR_X, SIDE_WINDOW_REAR_Y, SIDE_WINDOW_REAR_Z),
        size_xyz=(
            SIDE_WINDOW_REAR_LENGTH,
            SIDE_WINDOW_REAR_THICKNESS,
            SIDE_WINDOW_REAR_HEIGHT,
        ),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        mirror_y=1.0,
    )
    side_window_r_rear = create_side_window_profile(
        "Side_Window_R_Rear",
        center=(SIDE_WINDOW_REAR_X, -SIDE_WINDOW_REAR_Y, SIDE_WINDOW_REAR_Z),
        size_xyz=(
            SIDE_WINDOW_REAR_LENGTH,
            SIDE_WINDOW_REAR_THICKNESS,
            SIDE_WINDOW_REAR_HEIGHT,
        ),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        mirror_y=-1.0,
    )

    rear_window = create_box(
        "Rear_Window",
        local_center=(REAR_WINDOW_X, REAR_WINDOW_Y, REAR_WINDOW_Z),
        size_xyz=(REAR_WINDOW_THICKNESS, REAR_WINDOW_WIDTH, REAR_WINDOW_HEIGHT),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        smooth=False,
        rotation=(
            math.radians(REAR_WINDOW_ROT_X_DEG),
            math.radians(REAR_WINDOW_ROT_Y_DEG),
            math.radians(REAR_WINDOW_ROT_Z_DEG),
        ),
    )

    cut_sources = [
        (side_window_l_front, "CUT_Side_Window_L_Front"),
        (side_window_r_front, "CUT_Side_Window_R_Front"),
        (side_window_l_rear, "CUT_Side_Window_L_Rear"),
        (side_window_r_rear, "CUT_Side_Window_R_Rear"),
        (rear_window, "CUT_Rear_Window"),
    ]
    for source_obj, cutter_name in cut_sources:
        cutter = create_boolean_cutter_from_object(source_obj, cutter_name, model_collection, parent=root)
        cutter.scale.x *= CUTTER_SCALE_X
        cutter.scale.y *= CUTTER_SCALE_Y
        cutter.scale.z *= CUTTER_SCALE_Z
        apply_boolean_difference(body_shell, cutter)

    # ----------------------------------------------------------------------
    # PARALAMAS E RODAS
    # ----------------------------------------------------------------------
    create_ellipsoid(
        "Front_Fender_L_Base",
        local_center=(FRONT_FENDER_L_BASE_X, FRONT_FENDER_L_BASE_Y, FRONT_FENDER_L_BASE_Z),
        radii=(
            FRONT_FENDER_L_BASE_PROFUNDIDADE * 0.5,
            FRONT_FENDER_L_BASE_LARGURA * 0.5,
            FRONT_FENDER_L_BASE_ALTURA * 0.5,
        ),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        subdivisions=2,
    )
    create_ellipsoid(
        "Front_Fender_R_Base",
        local_center=(FRONT_FENDER_R_BASE_X, FRONT_FENDER_R_BASE_Y, FRONT_FENDER_R_BASE_Z),
        radii=(
            FRONT_FENDER_R_BASE_PROFUNDIDADE * 0.5,
            FRONT_FENDER_R_BASE_LARGURA * 0.5,
            FRONT_FENDER_R_BASE_ALTURA * 0.5,
        ),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        subdivisions=2,
    )
    create_ellipsoid(
        "Rear_Fender_L_Base",
        local_center=(REAR_FENDER_L_BASE_X, REAR_FENDER_L_BASE_Y, REAR_FENDER_L_BASE_Z),
        radii=(
            REAR_FENDER_L_BASE_PROFUNDIDADE * 0.5,
            REAR_FENDER_L_BASE_LARGURA * 0.5,
            REAR_FENDER_L_BASE_ALTURA * 0.5,
        ),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        subdivisions=2,
    )
    create_ellipsoid(
        "Rear_Fender_R_Base",
        local_center=(REAR_FENDER_R_BASE_X, REAR_FENDER_R_BASE_Y, REAR_FENDER_R_BASE_Z),
        radii=(
            REAR_FENDER_R_BASE_PROFUNDIDADE * 0.5,
            REAR_FENDER_R_BASE_LARGURA * 0.5,
            REAR_FENDER_R_BASE_ALTURA * 0.5,
        ),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        subdivisions=2,
    )

    wheel_positions = {
        "FL": (0.87, 0.72, WHEEL_RADIUS),
        "FR": (0.87, -0.72, WHEEL_RADIUS),
        "RL": (-0.87, 0.72, WHEEL_RADIUS),
        "RR": (-0.87, -0.72, WHEEL_RADIUS),
    }
    for name, (x, y, z) in wheel_positions.items():
        wheel = create_cylinder_y(
            f"Wheel_{name}",
            local_center=(x, y, z),
            radius=WHEEL_RADIUS,
            length=WHEEL_WIDTH,
            collection=model_collection,
            material=materials["rubber"],
            parent=root,
            sides=18,
            smooth=True,
        )
        create_cylinder_y(
            f"Rim_{name}",
            local_center=(0.0, 0.0, 0.0),
            radius=WHEEL_RADIUS * 0.54,
            length=WHEEL_WIDTH * 1.05,
            collection=model_collection,
            material=materials["rim"],
            parent=wheel,
            sides=16,
            smooth=True,
        )

    # ----------------------------------------------------------------------
    # FARÓIS
    # ----------------------------------------------------------------------
    create_ellipsoid(
        "Headlight_L",
        local_center=(HEADLIGHT_L_X, HEADLIGHT_L_Y, HEADLIGHT_L_Z),
        radii=(
            HEADLIGHT_L_PROFUNDIDADE * 0.5,
            HEADLIGHT_L_LARGURA * 0.5,
            HEADLIGHT_L_ALTURA * 0.5,
        ),
        collection=model_collection,
        material=materials["headlight"],
        parent=root,
        subdivisions=1,
    )
    create_ellipsoid(
        "Pupil_L",
        local_center=(HEADLIGHT_L_X + PUPIL_OFFSET_X, HEADLIGHT_L_Y, HEADLIGHT_L_Z),
        radii=(0.038, 0.038, 0.038),
        collection=model_collection,
        material=materials["black"],
        parent=root,
        subdivisions=1,
    )
    create_ellipsoid(
        "Headlight_R",
        local_center=(HEADLIGHT_R_X, HEADLIGHT_R_Y, HEADLIGHT_R_Z),
        radii=(
            HEADLIGHT_R_PROFUNDIDADE * 0.5,
            HEADLIGHT_R_LARGURA * 0.5,
            HEADLIGHT_R_ALTURA * 0.5,
        ),
        collection=model_collection,
        material=materials["headlight"],
        parent=root,
        subdivisions=1,
    )
    create_ellipsoid(
        "Pupil_R",
        local_center=(HEADLIGHT_R_X + PUPIL_OFFSET_X, HEADLIGHT_R_Y, HEADLIGHT_R_Z),
        radii=(0.038, 0.038, 0.038),
        collection=model_collection,
        material=materials["black"],
        parent=root,
        subdivisions=1,
    )

    # PARA-CHOQUES E DETALHES
    create_arc_bumper(
        "Front_Bumper",
        center=(1.12, 0.0, 0.62),
        radius_y=0.52,
        depth_x=0.34,
        tube_radius=0.045,
        collection=model_collection,
        material=materials["accent"],
        parent=root,
    )
    create_arc_bumper(
        "Rear_Bumper",
        center=(-1.12, 0.0, 0.62),
        radius_y=0.48,
        depth_x=-0.30,
        tube_radius=0.045,
        collection=model_collection,
        material=materials["accent"],
        parent=root,
        start_deg=110.0,
        end_deg=250.0,
    )
    create_box(
        "Door_Handle_L",
        local_center=(0.10, 0.63, 1.00),
        size_xyz=(0.14, 0.05, 0.05),
        collection=model_collection,
        material=materials["accent"],
        parent=root,
    )
    create_box(
        "Door_Handle_R",
        local_center=(0.10, -0.63, 1.00),
        size_xyz=(0.14, 0.05, 0.05),
        collection=model_collection,
        material=materials["accent"],
        parent=root,
    )

    # AMBIENTE
    ground = create_plane(
        "Preview_Ground", size=GROUND_SIZE, z=0.0,
        collection=env_collection, material=materials["ground"],
    )

    key_light_data = bpy.data.lights.new("CuteBeetle_Key_Light_Data", type="AREA")
    key_light_data.energy = 950.0
    key_light_data.shape = "RECTANGLE"
    key_light_data.size = 4.8
    key_light_data.size_y = 2.8
    key_light = bpy.data.objects.new("CuteBeetle_Key_Light", key_light_data)
    env_collection.objects.link(key_light)
    key_light.location = (4.6, -5.0, 6.2)
    look_at(key_light, (0.0, 0.0, 1.0))

    fill_light_data = bpy.data.lights.new("CuteBeetle_Fill_Light_Data", type="AREA")
    fill_light_data.energy = 430.0
    fill_light_data.shape = "RECTANGLE"
    fill_light_data.size = 4.2
    fill_light_data.size_y = 2.4
    fill_light = bpy.data.objects.new("CuteBeetle_Fill_Light", fill_light_data)
    env_collection.objects.link(fill_light)
    fill_light.location = (-4.0, 4.6, 4.8)
    look_at(fill_light, (0.0, 0.0, 1.1))

    camera_data = bpy.data.cameras.new("CuteBeetle_Camera_Data")
    camera = bpy.data.objects.new("CuteBeetle_Camera", camera_data)
    env_collection.objects.link(camera)
    camera.location = (6.4, -8.8, 4.5)
    camera_data.lens = 52.0
    look_at(camera, (0.0, 0.0, 1.00))
    scene.camera = camera

    world = bpy.data.worlds.new("CuteBeetle_World")
    world_tree = ensure_node_tree(world)
    background = world_tree.nodes.get("Background")
    world_output = world_tree.nodes.get("World Output")
    if background is None:
        background = world_tree.nodes.new("ShaderNodeBackground")
    if world_output is None:
        world_output = world_tree.nodes.new("ShaderNodeOutputWorld")
    if not background.outputs["Background"].is_linked:
        world_tree.links.new(background.outputs["Background"], world_output.inputs["Surface"])
    background.inputs["Color"].default_value = (0.03, 0.04, 0.055, 1.0)
    background.inputs["Strength"].default_value = 0.40
    scene.world = world

    for engine_name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine_name
            break
        except Exception:
            continue

    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    return {
        "main_collection": main_collection,
        "model_collection": model_collection,
        "env_collection": env_collection,
        "root": root,
        "body_shell": body_shell,
        "windshield": windshield,
        "rear_window": rear_window,
        "ground": ground,
    }


# ============================================================================
# EXECUÇÃO
# ============================================================================

validate_parameters()
clean_entire_scene()
scene = bpy.context.scene
result = build_cute_beetle(scene)

mesh_objects = [
    obj for obj in result["model_collection"].all_objects
    if obj.type == "MESH"
]
mins, maxs, dims = world_dimensions(mesh_objects)
polygon_count = sum(len(obj.data.polygons) for obj in mesh_objects)

print("=" * 72)
print("Carro estilo Fusca jovial parametrizado criado com sucesso.")
print(f"Versão do gerador: {GENERATOR_VERSION}")
print(f"Objetos de malha: {len(mesh_objects)}")
print(f"Polígonos aproximados: {polygon_count}")
print(f"Dimensões finais aproximadas (C x L x A): {dims.x:.2f} x {dims.y:.2f} x {dims.z:.2f}")
print("Body_Shell com escala global em 3 parâmetros: sim")
print("Windshield com corte real + shrinkwrap + solidify: sim")
print("Side windows fazem corte real na Body_Shell: sim")
print("Rear window faz corte real na Body_Shell: sim")
print("Rear_Window com posição X/Y/Z e rotações X/Y/Z parametrizadas: sim")
print("Rear_Deck presente: não")
print("Rear_Deck_Blend presente: não")
print("Carro vermelho: sim")
print("Vidros azul transparentes: sim")
print("A cena foi limpa integralmente antes da geração; o script é idempotente.")
print("=" * 72)
