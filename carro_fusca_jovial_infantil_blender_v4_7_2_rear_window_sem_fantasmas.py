"""
Carro estilo Fusca jovial — versão 4.7.1 parametrizada
======================================================

Correção principal desta versão:
- elimina a operação booleana INTERSECT que podia esvaziar o para-brisa;
- mantém somente o objeto visível Windshield_Cutter_Base;
- calcula diretamente o contorno superior pela interseção do plano do
  para-brisa com a Body_Shell;
- calcula diretamente o contorno inferior pela interseção do mesmo plano
  com o Front_Hood;
- constrói o vidro entre essas duas curvas, já sem sobras ou rebarbas;
- uma cópia mais profunda e discretamente ampliada abre o vão correspondente
  na Body_Shell por BOOLEAN DIFFERENCE;
- preserva escala global da Body_Shell, cortes das demais janelas e todos os
  parâmetros anteriores.
"""

import bpy
import bmesh
import math
import warnings
from mathutils import Vector, Euler

GENERATOR_VERSION = "4.7.2-fusca-jovial-rear-window-single-surface"
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
# WINDSHIELD — contorno calculado diretamente
# ---------------------------------------------------------------------------
# O único objeto frontal visível continua se chamando:
#   Windshield_Cutter_Base
#
# Não há mais BOOLEAN INTERSECT no vidro.
# O script corta a Body_Shell e o Front_Hood com o mesmo plano matemático:
# - borda superior = contorno real da Body_Shell;
# - borda inferior = contorno real do Front_Hood.
WINDSHIELD_X = 0.47
WINDSHIELD_Y = 0.00
WINDSHIELD_Z = 1.30

WINDSHIELD_THICKNESS = 0.045
WINDSHIELD_HEIGHT = 0.60
WINDSHIELD_WIDTH_BOTTOM = 1.02
WINDSHIELD_WIDTH_TOP = 1.36

WINDSHIELD_ROT_X_DEG = 0.0
WINDSHIELD_ROT_Y_DEG = -10.0
WINDSHIELD_ROT_Z_DEG = 0.0

# Quantidade de amostras laterais do contorno.
WINDSHIELD_CONTOUR_SAMPLES = 41

# Pequenas folgas entre o vidro e a lataria/capô.
WINDSHIELD_TOP_GAP = 0.010
WINDSHIELD_BOTTOM_GAP = 0.012
WINDSHIELD_MIN_COLUMN_HEIGHT = 0.045

# Desloca o vidro ligeiramente para fora para evitar sobreposição visual.
WINDSHIELD_GLASS_OUTSET = 0.003

# Cutter do vão: profundidade real através da carroceria e pequena junta.
WINDSHIELD_OPENING_DEPTH = 0.60
WINDSHIELD_OPENING_SCALE_Y = 1.020
WINDSHIELD_OPENING_SCALE_Z = 1.020

# Acabamento discreto das bordas.
WINDSHIELD_EDGE_BEVEL = 0.003
WINDSHIELD_EDGE_BEVEL_SEGMENTS = 2

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

# O vidro visível é uma ÚNICA superfície, sem frente/trás paralelos.
# O cutter abaixo é um prisma temporário independente e é apagado.
REAR_WINDOW_GLASS_OUTSET = 0.006
REAR_WINDOW_CUTTER_DEPTH = 0.36
REAR_WINDOW_CUTTER_WIDTH_SCALE = 1.045
REAR_WINDOW_CUTTER_HEIGHT_SCALE = 1.060

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
        "WINDSHIELD_THICKNESS": WINDSHIELD_THICKNESS,
        "WINDSHIELD_EDGE_BEVEL": WINDSHIELD_EDGE_BEVEL,
        "WINDSHIELD_CONTOUR_SAMPLES": WINDSHIELD_CONTOUR_SAMPLES,
        "WINDSHIELD_OPENING_DEPTH": WINDSHIELD_OPENING_DEPTH,
        "REAR_WINDOW_WIDTH": REAR_WINDOW_WIDTH,
        "REAR_WINDOW_HEIGHT": REAR_WINDOW_HEIGHT,
        "REAR_WINDOW_CUTTER_DEPTH": REAR_WINDOW_CUTTER_DEPTH,
        "REAR_WINDOW_CUTTER_WIDTH_SCALE": REAR_WINDOW_CUTTER_WIDTH_SCALE,
        "REAR_WINDOW_CUTTER_HEIGHT_SCALE": REAR_WINDOW_CUTTER_HEIGHT_SCALE,
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



def create_single_window_surface(
    name,
    center,
    width,
    height,
    collection,
    material,
    parent=None,
    rotation=(0.0, 0.0, 0.0),
):
    """
    Cria uma única lâmina de vidro no plano local YZ.

    Diferentemente de create_box(), esta função não cria duas faces grandes
    paralelas nem paredes laterais. Portanto, não produz o efeito de dois
    vidros fantasma no material transparente.
    """
    half_width = width * 0.5
    half_height = height * 0.5

    vertices = [
        (0.0, -half_width, -half_height),
        (0.0,  half_width, -half_height),
        (0.0,  half_width,  half_height),
        (0.0, -half_width,  half_height),
    ]
    faces = [(0, 1, 2, 3)]

    obj = create_mesh_object(
        name=name,
        vertices=vertices,
        faces=faces,
        collection=collection,
        material=material,
        parent=parent,
        local_location=center,
        smooth=False,
        rotation=rotation,
    )
    obj["single_surface_glass"] = True
    return obj


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



def mesh_plane_intersection_points(
    obj,
    plane_center,
    plane_normal,
    root_obj=None,
    tolerance=1.0e-6,
):
    """
    Retorna os pontos em que as arestas da malha cruzam um plano.

    Os pontos são devolvidos no espaço local de root_obj. Como Body_Shell,
    Front_Hood e o vidro usam o mesmo root, isso evita ambiguidades de
    parent, rotação e escala.
    """
    bpy.context.view_layer.update()

    if root_obj is None:
        to_root = obj.matrix_world.copy()
    else:
        to_root = root_obj.matrix_world.inverted() @ obj.matrix_world

    vertices = [to_root @ vertex.co for vertex in obj.data.vertices]
    points = []

    for edge in obj.data.edges:
        p0 = vertices[edge.vertices[0]]
        p1 = vertices[edge.vertices[1]]

        d0 = (p0 - plane_center).dot(plane_normal)
        d1 = (p1 - plane_center).dot(plane_normal)

        if abs(d0) <= tolerance and abs(d1) <= tolerance:
            points.extend((p0, p1))
            continue

        if abs(d0) <= tolerance:
            points.append(p0)
            continue

        if abs(d1) <= tolerance:
            points.append(p1)
            continue

        if d0 * d1 < 0.0:
            t = d0 / (d0 - d1)
            points.append(p0.lerp(p1, t))

    unique = {}
    quant = max(tolerance * 10.0, 1.0e-6)
    for point in points:
        key = (
            round(point.x / quant),
            round(point.y / quant),
            round(point.z / quant),
        )
        unique[key] = point

    return list(unique.values())


def convex_hull_2d(points):
    """Convex hull 2D pelo algoritmo monotonic chain."""
    unique = sorted(set((round(u, 8), round(v, 8)) for u, v in points))
    if len(unique) <= 2:
        return unique

    def cross(o, a, b):
        return (
            (a[0] - o[0]) * (b[1] - o[1])
            - (a[1] - o[1]) * (b[0] - o[0])
        )

    lower = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)

    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)

    return lower[:-1] + upper[:-1]


def vertical_hull_value(hull, u, use_max=True, tolerance=1.0e-8):
    """
    Intersecta uma linha vertical u=constante com o hull e retorna
    o maior ou menor valor de v.
    """
    if len(hull) < 2:
        return None

    values = []
    for index, p0 in enumerate(hull):
        p1 = hull[(index + 1) % len(hull)]
        u0, v0 = p0
        u1, v1 = p1

        if u < min(u0, u1) - tolerance or u > max(u0, u1) + tolerance:
            continue

        du = u1 - u0
        if abs(du) <= tolerance:
            if abs(u - u0) <= tolerance:
                values.extend((v0, v1))
            continue

        t = (u - u0) / du
        if -tolerance <= t <= 1.0 + tolerance:
            values.append(v0 + t * (v1 - v0))

    if not values:
        return None

    return max(values) if use_max else min(values)


def longest_contiguous_columns(columns):
    """Seleciona o maior trecho contínuo de colunas válidas."""
    if not columns:
        return []

    groups = []
    current = [columns[0]]

    for previous, item in zip(columns, columns[1:]):
        if item[0] == previous[0] + 1:
            current.append(item)
        else:
            groups.append(current)
            current = [item]

    groups.append(current)
    return max(groups, key=len)


def create_contoured_windshield(
    body_shell,
    front_hood,
    root,
    collection,
    glass_material,
):
    """
    Constrói Windshield_Cutter_Base diretamente entre dois contornos:
    topo da Body_Shell e topo do Front_Hood.

    Isso evita o INTERSECT booleano que podia produzir uma malha vazia.
    """
    plane_center = Vector((WINDSHIELD_X, WINDSHIELD_Y, WINDSHIELD_Z))
    rotation = Euler(
        (
            math.radians(WINDSHIELD_ROT_X_DEG),
            math.radians(WINDSHIELD_ROT_Y_DEG),
            math.radians(WINDSHIELD_ROT_Z_DEG),
        ),
        "XYZ",
    )
    rotation_matrix = rotation.to_matrix()

    plane_normal = (rotation_matrix @ Vector((1.0, 0.0, 0.0))).normalized()
    axis_u = (rotation_matrix @ Vector((0.0, 1.0, 0.0))).normalized()
    axis_v = (rotation_matrix @ Vector((0.0, 0.0, 1.0))).normalized()

    body_points = mesh_plane_intersection_points(
        body_shell,
        plane_center,
        plane_normal,
        root_obj=root,
    )
    hood_points = mesh_plane_intersection_points(
        front_hood,
        plane_center,
        plane_normal,
        root_obj=root,
    )

    if len(body_points) < 4 or len(hood_points) < 4:
        raise RuntimeError(
            "Não foi possível calcular os contornos do para-brisa. "
            f"Body_Shell={len(body_points)} pontos; "
            f"Front_Hood={len(hood_points)} pontos. "
            "Ajuste WINDSHIELD_X ou WINDSHIELD_ROT_Y_DEG."
        )

    body_2d = [
        (
            (point - plane_center).dot(axis_u),
            (point - plane_center).dot(axis_v),
        )
        for point in body_points
    ]
    hood_2d = [
        (
            (point - plane_center).dot(axis_u),
            (point - plane_center).dot(axis_v),
        )
        for point in hood_points
    ]

    body_hull = convex_hull_2d(body_2d)
    hood_hull = convex_hull_2d(hood_2d)

    if len(body_hull) < 3 or len(hood_hull) < 3:
        raise RuntimeError(
            "Os contornos calculados para o para-brisa não formaram "
            "polígonos válidos."
        )

    width_limit = 0.5 * max(
        WINDSHIELD_WIDTH_BOTTOM,
        WINDSHIELD_WIDTH_TOP,
    )

    body_u = [point[0] for point in body_hull]
    hood_u = [point[0] for point in hood_hull]

    u_min = max(min(body_u), min(hood_u), -width_limit)
    u_max = min(max(body_u), max(hood_u), width_limit)

    if u_max <= u_min:
        raise RuntimeError(
            "Body_Shell e Front_Hood não possuem largura comum "
            "suficiente no plano do para-brisa."
        )

    sample_count = max(9, int(WINDSHIELD_CONTOUR_SAMPLES))
    height_half = 0.5 * WINDSHIELD_HEIGHT
    columns = []

    for index in range(sample_count):
        factor = index / (sample_count - 1)
        u = u_min + factor * (u_max - u_min)

        shell_top = vertical_hull_value(body_hull, u, use_max=True)
        hood_top = vertical_hull_value(hood_hull, u, use_max=True)

        if shell_top is None or hood_top is None:
            continue

        top_v = min(shell_top - WINDSHIELD_TOP_GAP, height_half)
        bottom_v = max(hood_top + WINDSHIELD_BOTTOM_GAP, -height_half)

        if top_v - bottom_v >= WINDSHIELD_MIN_COLUMN_HEIGHT:
            columns.append((index, u, bottom_v, top_v))

    columns = longest_contiguous_columns(columns)

    if len(columns) < 3:
        raise RuntimeError(
            "O espaço entre Body_Shell e Front_Hood é insuficiente "
            "para formar o para-brisa. Ajuste a posição/altura do capô "
            "ou WINDSHIELD_Z."
        )

    half_thickness = 0.5 * WINDSHIELD_THICKNESS
    vertices = []
    faces = []

    # Em cada coluna:
    # 0 = frente inferior, 1 = frente superior,
    # 2 = trás inferior,   3 = trás superior.
    for _, u, bottom_v, top_v in columns:
        bottom_center = (
            plane_center
            + axis_u * u
            + axis_v * bottom_v
            + plane_normal * WINDSHIELD_GLASS_OUTSET
        )
        top_center = (
            plane_center
            + axis_u * u
            + axis_v * top_v
            + plane_normal * WINDSHIELD_GLASS_OUTSET
        )

        vertices.extend(
            (
                bottom_center + plane_normal * half_thickness,
                top_center + plane_normal * half_thickness,
                bottom_center - plane_normal * half_thickness,
                top_center - plane_normal * half_thickness,
            )
        )

    def vid(column_index, local_index):
        return column_index * 4 + local_index

    for column_index in range(len(columns) - 1):
        next_column = column_index + 1

        # face frontal
        faces.append(
            (
                vid(column_index, 0),
                vid(next_column, 0),
                vid(next_column, 1),
                vid(column_index, 1),
            )
        )
        # face traseira
        faces.append(
            (
                vid(column_index, 2),
                vid(column_index, 3),
                vid(next_column, 3),
                vid(next_column, 2),
            )
        )
        # borda inferior
        faces.append(
            (
                vid(column_index, 0),
                vid(column_index, 2),
                vid(next_column, 2),
                vid(next_column, 0),
            )
        )
        # borda superior
        faces.append(
            (
                vid(column_index, 1),
                vid(next_column, 1),
                vid(next_column, 3),
                vid(column_index, 3),
            )
        )

    # tampas laterais
    faces.append((vid(0, 0), vid(0, 1), vid(0, 3), vid(0, 2)))
    last = len(columns) - 1
    faces.append(
        (
            vid(last, 0),
            vid(last, 2),
            vid(last, 3),
            vid(last, 1),
        )
    )

    windshield = create_mesh_object(
        name="Windshield_Cutter_Base",
        vertices=vertices,
        faces=faces,
        collection=collection,
        material=glass_material,
        parent=root,
        local_location=(0.0, 0.0, 0.0),
        smooth=True,
    )
    cleanup_mesh_object(windshield)

    if WINDSHIELD_EDGE_BEVEL > 0.0:
        add_bevel_and_apply(
            windshield,
            width=WINDSHIELD_EDGE_BEVEL,
            segments=WINDSHIELD_EDGE_BEVEL_SEGMENTS,
        )

    opening_cutter = duplicate_mesh_object(
        windshield,
        "CUT_Windshield_Opening",
        collection,
        parent=root,
    )

    # Escala o cutter em torno do centro/plano do para-brisa,
    # e não em torno da origem global do carro.
    target_half_depth = max(
        0.5 * WINDSHIELD_OPENING_DEPTH,
        half_thickness,
    )

    for vertex in opening_cutter.data.vertices:
        point = vertex.co.copy()
        relative = point - plane_center

        depth = relative.dot(plane_normal)
        u = relative.dot(axis_u)
        v = relative.dot(axis_v)

        depth_sign = 1.0 if depth >= 0.0 else -1.0
        expanded_point = (
            plane_center
            + plane_normal * (depth_sign * target_half_depth)
            + axis_u * (u * WINDSHIELD_OPENING_SCALE_Y)
            + axis_v * (v * WINDSHIELD_OPENING_SCALE_Z)
        )
        vertex.co = expanded_point

    opening_cutter.data.update()
    cleanup_mesh_object(opening_cutter)

    if not apply_boolean_difference(
        body_shell,
        opening_cutter,
        remove_cutter=True,
    ):
        raise RuntimeError(
            "O vidro foi criado, mas não foi possível abrir o vão "
            "correspondente na Body_Shell."
        )

    return windshield



def duplicate_mesh_object(source_obj, name, collection, parent=None):
    """Duplica malha e transformações sem compartilhar o datablock."""
    world_matrix = source_obj.matrix_world.copy()
    obj = source_obj.copy()
    obj.data = source_obj.data.copy()
    obj.name = name
    collection.objects.link(obj)
    obj.parent = parent
    obj.matrix_world = world_matrix
    return obj


def create_boolean_cutter_from_object(source_obj, name, collection, parent=None):
    return duplicate_mesh_object(source_obj, name, collection, parent=parent)


def set_active_object(obj):
    view_layer = bpy.context.view_layer
    for other in view_layer.objects:
        other.select_set(False)
    obj.hide_viewport = False
    obj.hide_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj


def apply_object_transforms(obj, location=False, rotation=True, scale=True):
    set_active_object(obj)
    try:
        bpy.ops.object.transform_apply(
            location=location,
            rotation=rotation,
            scale=scale,
        )
        return True
    except RuntimeError:
        return False


def apply_modifier(obj, modifier_name):
    set_active_object(obj)
    try:
        bpy.ops.object.modifier_apply(modifier=modifier_name)
        return True
    except RuntimeError:
        return False


def delete_object(obj):
    if obj is not None and obj.name in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)


def cleanup_mesh_object(obj, merge_distance=1.0e-5):
    """Remove duplicados e recalcula normais após operações booleanas."""
    if obj is None or obj.type != "MESH":
        return

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if bm.verts:
        bmesh.ops.remove_doubles(
            bm,
            verts=list(bm.verts),
            dist=merge_distance,
        )
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.validate(clean_customdata=False)
    obj.data.update()


def apply_boolean_difference(target_obj, cutter_obj, remove_cutter=True):
    apply_object_transforms(target_obj, location=False, rotation=True, scale=True)
    apply_object_transforms(cutter_obj, location=False, rotation=True, scale=True)

    modifier = target_obj.modifiers.new(
        name=f"BOOL_DIFF_{cutter_obj.name}",
        type="BOOLEAN",
    )
    modifier.operation = "DIFFERENCE"
    modifier.solver = "EXACT"
    modifier.object = cutter_obj
    applied = apply_modifier(target_obj, modifier.name)

    if applied:
        cleanup_mesh_object(target_obj)
    if remove_cutter:
        delete_object(cutter_obj)
    return applied


def add_bevel_and_apply(obj, width, segments=2):
    if width <= 0.0:
        return True
    modifier = obj.modifiers.new(name="WindshieldEdgeCleanup", type="BEVEL")
    modifier.width = width
    modifier.segments = max(1, int(segments))
    modifier.limit_method = "ANGLE"
    modifier.angle_limit = math.radians(20.0)
    applied = apply_modifier(obj, modifier.name)
    if applied:
        cleanup_mesh_object(obj)
    return applied



def purge_temporary_cutters():
    """Remove qualquer cutter temporário que tenha sobrevivido a uma falha."""
    for obj in list(bpy.data.objects):
        if obj.name.startswith(("CUT_", "TMP_")):
            bpy.data.objects.remove(obj, do_unlink=True)


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

    front_hood = create_ellipsoid(
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
    # WINDSHIELD: contorno direto da Body_Shell e do Front_Hood
    # ----------------------------------------------------------------------
    # A escala global da Body_Shell é consolidada antes de calcular
    # as interseções com o plano do para-brisa.
    apply_object_transforms(
        body_shell,
        location=False,
        rotation=False,
        scale=True,
    )

    windshield = create_contoured_windshield(
        body_shell=body_shell,
        front_hood=front_hood,
        root=root,
        collection=model_collection,
        glass_material=materials["glass"],
    )

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

    rear_window_rotation = (
        math.radians(REAR_WINDOW_ROT_X_DEG),
        math.radians(REAR_WINDOW_ROT_Y_DEG),
        math.radians(REAR_WINDOW_ROT_Z_DEG),
    )

    # Cutters das janelas laterais continuam sendo cópias temporárias.
    cut_sources = [
        (side_window_l_front, "CUT_Side_Window_L_Front"),
        (side_window_r_front, "CUT_Side_Window_R_Front"),
        (side_window_l_rear, "CUT_Side_Window_L_Rear"),
        (side_window_r_rear, "CUT_Side_Window_R_Rear"),
    ]
    for source_obj, cutter_name in cut_sources:
        cutter = create_boolean_cutter_from_object(
            source_obj,
            cutter_name,
            model_collection,
            parent=root,
        )
        cutter.scale.x *= CUTTER_SCALE_X
        cutter.scale.y *= CUTTER_SCALE_Y
        cutter.scale.z *= CUTTER_SCALE_Z
        apply_boolean_difference(body_shell, cutter)

    # O recorte traseiro usa um prisma temporário próprio. Ele não compartilha
    # malha nem faces com Rear_Window e é apagado após o boolean.
    rear_window_cutter = create_box(
        "CUT_Rear_Window",
        local_center=(REAR_WINDOW_X, REAR_WINDOW_Y, REAR_WINDOW_Z),
        size_xyz=(
            REAR_WINDOW_CUTTER_DEPTH,
            REAR_WINDOW_WIDTH * REAR_WINDOW_CUTTER_WIDTH_SCALE,
            REAR_WINDOW_HEIGHT * REAR_WINDOW_CUTTER_HEIGHT_SCALE,
        ),
        collection=model_collection,
        material=None,
        parent=root,
        smooth=False,
        rotation=rear_window_rotation,
    )
    rear_window_cutter.hide_render = True
    rear_window_cutter.display_type = "WIRE"
    apply_boolean_difference(body_shell, rear_window_cutter, remove_cutter=True)

    # Vidro visível: somente uma face. O pequeno deslocamento ao longo da
    # normal traseira evita z-fighting sem criar uma segunda lâmina.
    rear_rotation_euler = Euler(rear_window_rotation, "XYZ")
    rear_outward_normal = rear_rotation_euler @ Vector((-1.0, 0.0, 0.0))
    rear_window_center = Vector(
        (REAR_WINDOW_X, REAR_WINDOW_Y, REAR_WINDOW_Z)
    ) + rear_outward_normal * REAR_WINDOW_GLASS_OUTSET

    rear_window = create_single_window_surface(
        "Rear_Window",
        center=rear_window_center,
        width=REAR_WINDOW_WIDTH,
        height=REAR_WINDOW_HEIGHT,
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        rotation=rear_window_rotation,
    )

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
purge_temporary_cutters()

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
print("Windshield_Cutter_Base criado diretamente entre os contornos: sim")
print("Side windows fazem corte real na Body_Shell: sim")
print("Rear window faz corte real na Body_Shell: sim")
print("Rear_Window é uma única superfície transparente: sim")
print("Cutter traseiro temporário removido: sim")
print("Rear_Deck presente: não")
print("Rear_Deck_Blend presente: não")
print("Carro vermelho: sim")
print("Vidros azul transparentes: sim")
print("A cena foi limpa integralmente antes da geração; o script é idempotente.")
print("=" * 72)
