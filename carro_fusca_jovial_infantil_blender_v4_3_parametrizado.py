"""
Carro estilo Fusca jovial — versão 4.3 parametrizada
====================================================

OBJETIVO DESTA VERSÃO
---------------------
1) Eliminar a peça de transição do capô.
2) Fazer um "corte" em Body_Shell na região do para-brisa (Windshield),
   removendo toda a parte frontal da Body_Shell.
3) Usar os parâmetros ajustados pelo usuário para:
   - Front_Hood
   - Headlight_L
   - Headlight_R
4) Parametrizar Front_Fender_L_Base e Front_Fender_R_Base
   com 6 parâmetros cada:
   - posição: X, Y, Z
   - dimensões totais: profundidade, largura, altura

IMPORTANTE
----------
A seção de parâmetros editáveis está logo no começo do arquivo e é marcada por:

# ############################################################################
# #             >>> PARÂMETROS EDITÁVEIS PRINCIPAIS <<<                     #
# ############################################################################

SISTEMA DE EIXOS
----------------
X = profundidade / frente-traseira
Y = largura / esquerda-direita
Z = altura
"""

import bpy
import bmesh
import math
import warnings
from mathutils import Vector

GENERATOR_VERSION = "4.3-fusca-jovial-parametrizado-semcorte-frontal"
GROUND_SIZE = 24.0

TARGET_LENGTH = 3.05
TARGET_WIDTH = 1.60
TARGET_HEIGHT = 1.62
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
# Edite preferencialmente SOMENTE este bloco.
#
# Eixos:
#   X = frente/traseira
#   Y = esquerda/direita
#   Z = altura
#
# Dimensões:
#   PROFUNDIDADE = tamanho total no eixo X
#   LARGURA      = tamanho total no eixo Y
#   ALTURA       = tamanho total no eixo Z
#
# Observação:
#   As elipsoides do script são criadas por "raios".
#   Portanto, internamente o código divide estas medidas totais por 2.
# ############################################################################

# ---------------------------------------------------------------------------
# FRONT_HOOD — posição do centro
# ---------------------------------------------------------------------------
FRONT_HOOD_X = 0.98
FRONT_HOOD_Y = 0.00
FRONT_HOOD_Z = 0.82

# FRONT_HOOD — dimensões totais
FRONT_HOOD_PROFUNDIDADE = 1.00
FRONT_HOOD_LARGURA = 1.50
FRONT_HOOD_ALTURA = 0.70

# ---------------------------------------------------------------------------
# HEADLIGHT_L — farol esquerdo; posição do centro
# ---------------------------------------------------------------------------
HEADLIGHT_L_X = 1.32
HEADLIGHT_L_Y = 0.73
HEADLIGHT_L_Z = 0.72

# HEADLIGHT_L — dimensões totais
HEADLIGHT_L_PROFUNDIDADE = 0.28
HEADLIGHT_L_LARGURA = 0.28
HEADLIGHT_L_ALTURA = 0.28

# ---------------------------------------------------------------------------
# HEADLIGHT_R — farol direito; posição do centro
# ---------------------------------------------------------------------------
HEADLIGHT_R_X = 1.32
HEADLIGHT_R_Y = -0.73
HEADLIGHT_R_Z = 0.72

# HEADLIGHT_R — dimensões totais
HEADLIGHT_R_PROFUNDIDADE = 0.28
HEADLIGHT_R_LARGURA = 0.28
HEADLIGHT_R_ALTURA = 0.28

# ---------------------------------------------------------------------------
# FRONT_FENDER_L_BASE — paralama dianteiro esquerdo; posição do centro
# ---------------------------------------------------------------------------
FRONT_FENDER_L_BASE_X = 0.86
FRONT_FENDER_L_BASE_Y = 0.73
FRONT_FENDER_L_BASE_Z = 0.73

# FRONT_FENDER_L_BASE — dimensões totais
FRONT_FENDER_L_BASE_PROFUNDIDADE = 1.12
FRONT_FENDER_L_BASE_LARGURA = 0.56
FRONT_FENDER_L_BASE_ALTURA = 0.86

# ---------------------------------------------------------------------------
# FRONT_FENDER_R_BASE — paralama dianteiro direito; posição do centro
# ---------------------------------------------------------------------------
FRONT_FENDER_R_BASE_X = 0.86
FRONT_FENDER_R_BASE_Y = -0.73
FRONT_FENDER_R_BASE_Z = 0.73

# FRONT_FENDER_R_BASE — dimensões totais
FRONT_FENDER_R_BASE_PROFUNDIDADE = 1.12
FRONT_FENDER_R_BASE_LARGURA = 0.56
FRONT_FENDER_R_BASE_ALTURA = 0.86

# ---------------------------------------------------------------------------
# PUPIL_OFFSET_X
# Deslocamento da pupila para frente em relação ao centro do farol
# ---------------------------------------------------------------------------
PUPIL_OFFSET_X = 0.09

# ---------------------------------------------------------------------------
# WINDSHIELD_CUT_X
# Posição de corte frontal da BODY_SHELL.
# Tudo que estiver à frente disso NÃO entra na Body_Shell.
# O capô passa a dominar a frente do carro.
# ---------------------------------------------------------------------------
WINDSHIELD_CUT_X = 0.48


# ============================================================================
# VALIDAÇÃO DOS PARÂMETROS
# ============================================================================

def assert_positive(value, name):
    if value <= 0:
        raise ValueError(f"O parâmetro {name} deve ser > 0. Valor atual: {value!r}")


def validate_parameters():
    positive_params = {
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
    }
    for name, value in positive_params.items():
        assert_positive(value, name)


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
        "metaballs",
        "lattices",
        "grease_pencils",
        "volumes",
        "pointclouds",
    ):
        datablocks = getattr(bpy.data, attribute_name, None)
        if datablocks is not None:
            remove_all(datablocks)

    bpy.context.view_layer.update()


# ============================================================================
# AUXILIARES
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
                       smooth=True):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(
        [tuple(Vector(v)) for v in vertices],
        [],
        [tuple(f) for f in faces],
    )
    mesh.update(calc_edges=True)

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)

    if parent is not None:
        obj.parent = parent

    obj.location = Vector(local_location)
    obj.rotation_mode = "XYZ"

    if material is not None:
        mesh.materials.append(material)

    if smooth:
        for poly in mesh.polygons:
            poly.use_smooth = True

    return obj


def create_box(name, local_center, size_xyz, collection, material,
               parent=None, smooth=False):
    sx, sy, sz = (
        size_xyz[0] * 0.5,
        size_xyz[1] * 0.5,
        size_xyz[2] * 0.5,
    )
    vertices = [
        (-sx, -sy, -sz),
        ( sx, -sy, -sz),
        ( sx,  sy, -sz),
        (-sx,  sy, -sz),
        (-sx, -sy,  sz),
        ( sx, -sy,  sz),
        ( sx,  sy,  sz),
        (-sx,  sy,  sz),
    ]
    faces = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    return create_mesh_object(
        name=name,
        vertices=vertices,
        faces=faces,
        collection=collection,
        material=material,
        parent=parent,
        local_location=local_center,
        smooth=smooth,
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
    if parent is not None:
        obj.parent = parent
    obj.location = Vector(local_center)
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = rotation

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
        name=name,
        vertices=vertices,
        faces=faces,
        collection=collection,
        material=material,
        parent=parent,
        local_location=local_center,
        smooth=smooth,
    )


def create_plane(name, size, z, collection, material):
    half = size * 0.5
    vertices = [
        (-half, -half, z),
        ( half, -half, z),
        ( half,  half, z),
        (-half,  half, z),
    ]
    faces = [(0, 1, 2, 3)]
    return create_mesh_object(
        name=name,
        vertices=vertices,
        faces=faces,
        collection=collection,
        material=material,
        smooth=False,
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
                1.0
                - pinch_bottom * bottom_factor
                + fullness_top * top_factor * 0.12
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
            a = vidx(s, i)
            b = vidx(s, j)
            c = vidx(s + 1, j)
            d = vidx(s + 1, i)
            faces.append((a, b, c, d))

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
        name=name,
        vertices=vertices,
        faces=faces,
        collection=collection,
        material=material,
        parent=parent,
        local_location=local_location,
        smooth=True,
    )


def create_trapezoid_window(name, center, size_xyz, collection, material,
                            parent=None, mirror_y=1.0):
    sx, sy, sz = size_xyz
    hx = sx * 0.5
    hz = sz * 0.5

    vertices = [
        (-hx, 0.0, -hz),
        ( hx * 0.78, 0.0, -hz * 0.95),
        ( hx, 0.0,  hz * 0.58),
        (-hx * 0.65, 0.0, hz),
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
    )
    obj.scale.y = sy if sy != 0 else 0.01
    return obj


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
            offset = (
                normal * (math.cos(phi) * tube_radius) +
                binormal * (math.sin(phi) * tube_radius)
            )
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
        name=name,
        vertices=vertices,
        faces=faces,
        collection=collection,
        material=material,
        parent=parent,
        local_location=(0.0, 0.0, 0.0),
        smooth=True,
    )


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
        raise RuntimeError(
            f"Não foi possível criar a árvore de nós de {id_block.name!r}."
        )
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
        color=(0.22, 0.79, 0.95),
        roughness=0.42,
        metallic=0.0,
    )
    mats["accent"] = create_principled_material(
        "MAT_CuteBeetle_Accent",
        color=(0.99, 0.97, 0.95),
        roughness=0.38,
        metallic=0.0,
    )
    mats["glass"] = create_principled_material(
        "MAT_CuteBeetle_Glass",
        color=(0.44, 0.64, 0.80),
        roughness=0.06,
        metallic=0.0,
        alpha=0.42,
        transmission=0.10,
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

    body_stations = [
        ( WINDSHIELD_CUT_X,      0.60, 0.42, 1.46, 0.15, 0.10),
        ( WINDSHIELD_CUT_X-0.18, 0.66, 0.42, 1.58, 0.12, 0.10),
        ( WINDSHIELD_CUT_X-0.54, 0.64, 0.43, 1.50, 0.14, 0.08),
        ( WINDSHIELD_CUT_X-0.90, 0.57, 0.45, 1.30, 0.18, 0.06),
        ( WINDSHIELD_CUT_X-1.20, 0.49, 0.47, 1.12, 0.22, 0.05),
        ( WINDSHIELD_CUT_X-1.46, 0.36, 0.50, 0.96, 0.26, 0.04),
        ( WINDSHIELD_CUT_X-1.68, 0.18, 0.55, 0.82, 0.32, 0.03),
    ]
    create_loft_shell(
        name="Body_Shell",
        stations=body_stations,
        section_points=16,
        collection=model_collection,
        material=materials["body"],
        parent=root,
        local_location=(0.0, 0.0, 0.0),
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
        rotation=(0.0, 0.10, 0.0),
    )

    create_ellipsoid(
        "Rear_Deck",
        local_center=(-1.06, 0.0, 0.94),
        radii=(0.44, 0.42, 0.24),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        subdivisions=2,
        rotation=(0.0, -0.05, 0.0),
    )
    create_ellipsoid(
        "Rear_Deck_Blend",
        local_center=(-0.78, 0.0, 1.05),
        radii=(0.28, 0.44, 0.16),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        subdivisions=1,
        rotation=(0.0, -0.03, 0.0),
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

    create_box(
        "Windshield",
        local_center=(0.46, 0.0, 1.31),
        size_xyz=(0.08, 0.80, 0.40),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
    )
    create_box(
        "Rear_Window",
        local_center=(-0.52, 0.0, 1.26),
        size_xyz=(0.08, 0.66, 0.28),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
    )

    create_trapezoid_window(
        "Side_Window_L_Front",
        center=(0.24, 0.57, 1.30),
        size_xyz=(0.54, 0.01, 0.34),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        mirror_y=1.0,
    )
    create_trapezoid_window(
        "Side_Window_R_Front",
        center=(0.24, -0.57, 1.30),
        size_xyz=(0.54, 0.01, 0.34),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        mirror_y=-1.0,
    )
    create_trapezoid_window(
        "Side_Window_L_Rear",
        center=(-0.18, 0.57, 1.24),
        size_xyz=(0.34, 0.01, 0.24),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        mirror_y=1.0,
    )
    create_trapezoid_window(
        "Side_Window_R_Rear",
        center=(-0.18, -0.57, 1.24),
        size_xyz=(0.34, 0.01, 0.24),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
        mirror_y=-1.0,
    )

    wheel_positions = {
        "FL": (0.87, 0.72, WHEEL_RADIUS),
        "FR": (0.87, -0.72, WHEEL_RADIUS),
        "RL": (-0.87, 0.72, WHEEL_RADIUS),
        "RR": (-0.87, -0.72, WHEEL_RADIUS),
    }

    create_ellipsoid(
        "Front_Fender_L_Base",
        local_center=(
            FRONT_FENDER_L_BASE_X,
            FRONT_FENDER_L_BASE_Y,
            FRONT_FENDER_L_BASE_Z,
        ),
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
        local_center=(
            FRONT_FENDER_R_BASE_X,
            FRONT_FENDER_R_BASE_Y,
            FRONT_FENDER_R_BASE_Z,
        ),
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
        local_center=(-0.87, 0.73, 0.74),
        radii=(0.60, 0.29, 0.45),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        subdivisions=2,
    )
    create_ellipsoid(
        "Rear_Fender_R_Base",
        local_center=(-0.87, -0.73, 0.74),
        radii=(0.60, 0.29, 0.45),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        subdivisions=2,
    )

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
        local_center=(
            HEADLIGHT_L_X + PUPIL_OFFSET_X,
            HEADLIGHT_L_Y,
            HEADLIGHT_L_Z,
        ),
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
        local_center=(
            HEADLIGHT_R_X + PUPIL_OFFSET_X,
            HEADLIGHT_R_Y,
            HEADLIGHT_R_Z,
        ),
        radii=(0.038, 0.038, 0.038),
        collection=model_collection,
        material=materials["black"],
        parent=root,
        subdivisions=1,
    )

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
        "Smile_Mid",
        local_center=(1.30, 0.0, 0.75),
        size_xyz=(0.05, 0.38, 0.04),
        collection=model_collection,
        material=materials["black"],
        parent=root,
    )
    create_box(
        "Smile_L",
        local_center=(1.27, 0.12, 0.72),
        size_xyz=(0.04, 0.12, 0.04),
        collection=model_collection,
        material=materials["black"],
        parent=root,
    )
    create_box(
        "Smile_R",
        local_center=(1.27, -0.12, 0.72),
        size_xyz=(0.04, 0.12, 0.04),
        collection=model_collection,
        material=materials["black"],
        parent=root,
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

    ground = create_plane(
        "Preview_Ground",
        size=GROUND_SIZE,
        z=0.0,
        collection=env_collection,
        material=materials["ground"],
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
        world_tree.links.new(
            background.outputs["Background"],
            world_output.inputs["Surface"],
        )
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
        "ground": ground,
    }


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
print(
    f"Dimensões finais aproximadas (C x L x A): "
    f"{dims.x:.2f} x {dims.y:.2f} x {dims.z:.2f}"
)
print("Peça de transição do capô presente: não")
print("Body_Shell cortada na região do para-brisa: sim")
print("Front_Hood parametrizado: sim")
print("Headlight_L parametrizado: sim")
print("Headlight_R parametrizado: sim")
print("Front_Fender_L_Base parametrizado em 6 parâmetros: sim")
print("Front_Fender_R_Base parametrizado em 6 parâmetros: sim")
print("A cena foi limpa integralmente antes da geração; o script é idempotente.")
print("=" * 72)
