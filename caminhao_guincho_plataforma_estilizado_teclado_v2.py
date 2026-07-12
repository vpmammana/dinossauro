"""
Caminhão guincho plataforma estilizado — Blender Python
=======================================================

Este script cria um caminhão guincho do tipo plataforma, estilizado,
com linguagem visual inspirada em uma pickup simplificada da década de 50.

Recursos principais:
- limpeza total da cena no início para execução idempotente;
- modelo low-poly com materiais procedurais simples;
- caminhão dirigível por teclado;
- mesmos comandos de controle do dinossauro:
    ↑ frente
    ↓ ré
    ← virar à esquerda
    → virar à direita
    HOME centralizar
    ESC encerrar o controlador
- câmera e luzes podem acompanhar o veículo;
- painel lateral na Viewport 3D para iniciar/parar/resetar;
- rotação real das rodas de acordo com a distância percorrida;
- direção visual das rodas dianteiras;
- leve inclinação e balanço de carroceria para dar vida ao movimento;
- terreno de preview amplo.

Compatibilidade pretendida: Blender 3.6 LTS e versões posteriores.
"""

import bpy
import bmesh
import math
import warnings
from mathutils import Vector
from bpy.props import BoolProperty, FloatProperty


# ============================================================================
# CONSTANTES E NOMES
# ============================================================================

GENERATOR_VERSION = "1.1-styletruck-branco-arredondado"
GROUND_SIZE = 90.0
GROUND_MARGIN = 7.0
TIMER_INTERVAL = 1.0 / 60.0

COLLECTION_MAIN = "StyleTruck_Generated"
COLLECTION_MODEL = "MODEL_Meshes"
COLLECTION_CONTROLS = "RIG_Controls"
COLLECTION_ENV = "ENVIRONMENT"

MASTER_NAME = "CTRL_STYLETRUCK_MASTER"
BODY_CTRL_NAME = "CTRL_STYLETRUCK_BODY"
FOLLOW_RIG_NAME = "CTRL_CAMERA_LIGHT_FOLLOW"
GROUND_NAME = "Preview_Ground"

WHEEL_RADIUS = 0.82
WHEEL_WIDTH = 0.42
MAX_STEER_ANGLE_DEG = 28.0
DEFAULT_SPEED = 8.0
DEFAULT_TURN_SPEED_DEG = 90.0
DEFAULT_ACCEL = 14.0
DEFAULT_DECEL = 16.0
DEFAULT_STEER_RETURN = 170.0

SCENE_PROPERTY_NAMES = (
    "styletruck_drive_speed",
    "styletruck_turn_speed",
    "styletruck_acceleration",
    "styletruck_deceleration",
    "styletruck_steer_return_speed",
    "styletruck_camera_follow",
)

WHEEL_OBJECT_NAMES = {
    "FL": "Wheel_FL",
    "FR": "Wheel_FR",
    "RL": "Wheel_RL",
    "RR": "Wheel_RR",
}

STEER_PIVOT_NAMES = {
    "FL": "CTRL_WHEEL_FL_STEER",
    "FR": "CTRL_WHEEL_FR_STEER",
}

ALL_CLASS_NAMES = (
    "WM_OT_styletruck_keyboard_controller",
    "WM_OT_styletruck_start_controller",
    "WM_OT_styletruck_stop_controller",
    "WM_OT_styletruck_reset_vehicle",
    "VIEW3D_PT_styletruck_controls",
)


# ============================================================================
# LIMPEZA TOTAL DA CENA
# ============================================================================

def remove_all(datablocks):
    for datablock in list(datablocks):
        try:
            datablocks.remove(datablock, do_unlink=True)
        except TypeError:
            datablocks.remove(datablock)


def clear_scene_properties():
    scene_type = bpy.types.Scene
    for property_name in SCENE_PROPERTY_NAMES:
        if hasattr(scene_type, property_name):
            delattr(scene_type, property_name)


def unregister_previous_classes():
    for class_name in ALL_CLASS_NAMES:
        cls = getattr(bpy.types, class_name, None)
        if cls is not None:
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass


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
# FUNÇÕES AUXILIARES DE CENA
# ============================================================================

def new_child_collection(name, parent):
    collection = bpy.data.collections.new(name)
    parent.children.link(collection)
    return collection


def create_empty(name, local_location, collection, parent=None,
                 display_type="CIRCLE", display_size=0.25):
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    obj.empty_display_type = display_type
    obj.empty_display_size = display_size
    obj.show_in_front = True
    obj.hide_render = True
    obj.rotation_mode = "XYZ"

    if parent is not None:
        obj.parent = parent

    obj.location = Vector(local_location)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    return obj


def create_mesh_object(name, vertices, faces, collection, material=None,
                       parent=None, local_location=(0.0, 0.0, 0.0),
                       smooth=True):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(
        [tuple(Vector(vertex)) for vertex in vertices],
        [],
        [tuple(face) for face in faces],
    )
    mesh.update(calc_edges=True)

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)

    if parent is not None:
        obj.parent = parent

    obj.location = Vector(local_location)
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)

    if material is not None:
        mesh.materials.append(material)

    if smooth:
        for polygon in mesh.polygons:
            polygon.use_smooth = True

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
        (sx, -sy, -sz),
        (sx, sy, -sz),
        (-sx, sy, -sz),
        (-sx, -sy, sz),
        (sx, -sy, sz),
        (sx, sy, sz),
        (-sx, sy, sz),
    ]

    faces = [
        (0, 1, 2, 3),
        (4, 5, 6, 7),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
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
                     parent=None, subdivisions=2):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm = bmesh.new()

    bmesh.ops.create_icosphere(
        bm,
        subdivisions=subdivisions,
        radius=1.0,
    )

    rx, ry, rz = radii
    for vertex in bm.verts:
        vertex.co.x *= rx
        vertex.co.y *= ry
        vertex.co.z *= rz

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)

    if parent is not None:
        obj.parent = parent

    obj.location = Vector(local_center)
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)

    mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True

    return obj


def create_cylinder_y(name, local_center, radius, length, collection,
                      material, parent=None, sides=18, smooth=True):
    vertices = []
    faces = []
    half = length * 0.5

    for y_value in (-half, half):
        for index in range(sides):
            angle = 2.0 * math.pi * index / sides
            x = math.cos(angle) * radius
            z = math.sin(angle) * radius
            vertices.append((x, y_value, z))

    for index in range(sides):
        next_index = (index + 1) % sides
        faces.append((index, next_index, sides + next_index, sides + index))

    faces.append(tuple(reversed(range(sides))))
    faces.append(tuple(sides + index for index in range(sides)))

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
        (half, -half, z),
        (half, half, z),
        (-half, half, z),
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


def look_at(obj, target, track_axis="-Z", up_axis="Y"):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat(track_axis, up_axis).to_euler()


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


def create_principled_material(name, color, roughness=0.6, metallic=0.0,
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
    materials = {}

    body_white = create_principled_material(
        "MAT_Body_White",
        color=(0.92, 0.92, 0.92),
        roughness=0.48,
        metallic=0.0,
    )
    materials["body_red"] = body_white
    materials["body_cream"] = body_white

    materials["chassis"] = create_principled_material(
        "MAT_Chassis",
        color=(0.11, 0.11, 0.12),
        roughness=0.84,
        metallic=0.04,
    )
    materials["bed"] = create_principled_material(
        "MAT_Bed_Surface",
        color=(0.52, 0.54, 0.58),
        roughness=0.88,
        metallic=0.04,
    )
    materials["chrome"] = create_principled_material(
        "MAT_Chrome",
        color=(0.76, 0.78, 0.81),
        roughness=0.16,
        metallic=0.86,
    )
    materials["glass"] = create_principled_material(
        "MAT_Glass",
        color=(0.33, 0.50, 0.64),
        roughness=0.05,
        alpha=0.42,
        transmission=0.10,
        blend_method="BLEND",
    )
    materials["rubber"] = create_principled_material(
        "MAT_Rubber",
        color=(0.035, 0.035, 0.038),
        roughness=0.95,
    )
    materials["hubcap"] = create_principled_material(
        "MAT_Hubcap",
        color=(0.84, 0.86, 0.88),
        roughness=0.20,
        metallic=0.92,
    )
    materials["light_white"] = create_principled_material(
        "MAT_Light_White",
        color=(0.98, 0.96, 0.88),
        roughness=0.20,
    )
    materials["light_red"] = create_principled_material(
        "MAT_Light_Red",
        color=(0.76, 0.08, 0.07),
        roughness=0.25,
    )
    materials["ground"] = create_principled_material(
        "MAT_Ground",
        color=(0.115, 0.155, 0.075),
        roughness=1.0,
    )

    return materials


# ============================================================================
# CONSTRUÇÃO DO CAMINHÃO
# ============================================================================

def create_wheel(name, center, collection, parent, materials):
    wheel = create_cylinder_y(
        name=name,
        local_center=center,
        radius=WHEEL_RADIUS,
        length=WHEEL_WIDTH,
        collection=collection,
        material=materials["rubber"],
        parent=parent,
        sides=20,
        smooth=True,
    )

    create_cylinder_y(
        name=f"{name}_Hubcap_Outer",
        local_center=(0.0, 0.0, 0.0),
        radius=WHEEL_RADIUS * 0.54,
        length=WHEEL_WIDTH * 1.05,
        collection=collection,
        material=materials["hubcap"],
        parent=wheel,
        sides=18,
        smooth=True,
    )

    create_cylinder_y(
        name=f"{name}_Hubcap_Inner",
        local_center=(0.0, 0.0, 0.0),
        radius=WHEEL_RADIUS * 0.30,
        length=WHEEL_WIDTH * 1.14,
        collection=collection,
        material=materials["chrome"],
        parent=wheel,
        sides=18,
        smooth=True,
    )

    return wheel


def build_styletruck_model(scene):
    main_collection = bpy.data.collections.new(COLLECTION_MAIN)
    scene.collection.children.link(main_collection)

    model_collection = new_child_collection(COLLECTION_MODEL, main_collection)
    control_collection = new_child_collection(COLLECTION_CONTROLS, main_collection)
    env_collection = new_child_collection(COLLECTION_ENV, main_collection)

    materials = build_materials()

    master = create_empty(
        MASTER_NAME,
        local_location=(0.0, 0.0, 0.0),
        collection=control_collection,
        display_type="ARROWS",
        display_size=1.0,
    )
    master["generator"] = "StyleTruck Tow Platform"
    master["generator_version"] = GENERATOR_VERSION

    body_ctrl = create_empty(
        BODY_CTRL_NAME,
        local_location=(0.0, 0.0, 0.0),
        collection=control_collection,
        parent=master,
        display_type="CIRCLE",
        display_size=0.65,
    )

    follow_rig = create_empty(
        FOLLOW_RIG_NAME,
        local_location=(0.0, 0.0, 0.0),
        collection=control_collection,
        parent=master,
        display_type="CIRCLE",
        display_size=0.50,
    )

    # ------------------------------------------------------------------
    # Dimensões gerais e referência de proporções
    # ------------------------------------------------------------------
    chassis_length = 6.35
    cab_fraction = 1.0 / 3.0
    cab_total_length = chassis_length * cab_fraction  # ~2.12
    cab_rear_x = 0.42
    cab_front_x = cab_rear_x + cab_total_length
    hood_length = 0.92
    cab_passenger_length = cab_total_length - hood_length

    # ------------------------------------------------------------------
    # Chassi contínuo
    # ------------------------------------------------------------------
    create_box(
        "Chassis_Main",
        local_center=(0.00, 0.0, 1.03),
        size_xyz=(chassis_length, 1.72, 0.26),
        collection=model_collection,
        material=materials["chassis"],
        parent=master,
    )
    create_box(
        "Chassis_FrontCross",
        local_center=(2.80, 0.0, 1.02),
        size_xyz=(0.44, 1.90, 0.22),
        collection=model_collection,
        material=materials["chassis"],
        parent=master,
    )
    create_box(
        "Chassis_RearCross",
        local_center=(-2.90, 0.0, 1.02),
        size_xyz=(0.44, 1.90, 0.22),
        collection=model_collection,
        material=materials["chassis"],
        parent=master,
    )

    create_box(
        "Axle_Front",
        local_center=(2.08, 0.0, 0.84),
        size_xyz=(0.20, 2.56, 0.20),
        collection=model_collection,
        material=materials["chassis"],
        parent=master,
    )
    create_box(
        "Axle_Rear",
        local_center=(-1.86, 0.0, 0.84),
        size_xyz=(0.22, 2.62, 0.22),
        collection=model_collection,
        material=materials["chassis"],
        parent=master,
    )

    # ------------------------------------------------------------------
    # Cabine: apenas 1/3 do comprimento do chassi.
    # Sem espaço vazio entre cabine e chassi.
    # ------------------------------------------------------------------
    create_box(
        "Cab_Base",
        local_center=(1.38, 0.0, 1.56),
        size_xyz=(2.18, 2.24, 0.98),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_box(
        "Cab_Lower",
        local_center=(1.18, 0.0, 2.00),
        size_xyz=(1.34, 2.18, 0.96),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_box(
        "Cab_Rear_Panel",
        local_center=(0.56, 0.0, 2.16),
        size_xyz=(0.16, 2.06, 1.12),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )

    # Teto arredondado da cabine
    create_box(
        "Cab_Roof_Base",
        local_center=(1.08, 0.0, 2.69),
        size_xyz=(1.48, 1.96, 0.18),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_ellipsoid(
        "Cab_Roof_Round",
        local_center=(1.05, 0.0, 2.82),
        radii=(0.84, 0.98, 0.32),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
        subdivisions=2,
    )
    create_ellipsoid(
        "Cab_Crown",
        local_center=(0.98, 0.0, 2.96),
        radii=(0.56, 0.82, 0.18),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
        subdivisions=1,
    )

    # Colunas e moldura frontal
    create_box(
        "Cab_A_Pillar_Bar",
        local_center=(1.88, 0.0, 2.42),
        size_xyz=(0.14, 1.88, 0.72),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )

    # Capô / capuz do motor arredondado
    create_box(
        "Hood_Base",
        local_center=(2.38, 0.0, 1.73),
        size_xyz=(1.02, 2.00, 0.66),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_ellipsoid(
        "Hood_Round_Top",
        local_center=(2.48, 0.0, 2.00),
        radii=(0.62, 0.92, 0.30),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
        subdivisions=2,
    )
    create_ellipsoid(
        "Nose_Round",
        local_center=(2.96, 0.0, 1.83),
        radii=(0.30, 0.86, 0.34),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
        subdivisions=2,
    )

    # Vidros
    create_box(
        "Windshield",
        local_center=(1.79, 0.0, 2.44),
        size_xyz=(0.08, 1.66, 0.58),
        collection=model_collection,
        material=materials["glass"],
        parent=body_ctrl,
    )
    create_box(
        "Rear_Window",
        local_center=(0.57, 0.0, 2.42),
        size_xyz=(0.08, 1.40, 0.46),
        collection=model_collection,
        material=materials["glass"],
        parent=body_ctrl,
    )
    create_box(
        "Side_Window_L",
        local_center=(1.18, 0.90, 2.44),
        size_xyz=(1.06, 0.08, 0.52),
        collection=model_collection,
        material=materials["glass"],
        parent=body_ctrl,
    )
    create_box(
        "Side_Window_R",
        local_center=(1.18, -0.90, 2.44),
        size_xyz=(1.06, 0.08, 0.52),
        collection=model_collection,
        material=materials["glass"],
        parent=body_ctrl,
    )

    # Saia inferior / rocker para eliminar vazio entre cabine e chassi
    create_box(
        "Cab_Rocker_L",
        local_center=(1.14, 1.10, 1.30),
        size_xyz=(1.78, 0.12, 0.20),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_box(
        "Cab_Rocker_R",
        local_center=(1.14, -1.10, 1.30),
        size_xyz=(1.78, 0.12, 0.20),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )

    # ------------------------------------------------------------------
    # Paralamas cobrindo integralmente as rodas
    # ------------------------------------------------------------------
    for side_name, side_sign in (("L", 1.0), ("R", -1.0)):
        create_ellipsoid(
            f"Front_Fender_{side_name}",
            local_center=(2.12, 1.24 * side_sign, 1.38),
            radii=(1.02, 0.40, 0.82),
            collection=model_collection,
            material=materials["body_red"],
            parent=body_ctrl,
            subdivisions=2,
        )
        create_ellipsoid(
            f"Front_Fender_Cap_{side_name}",
            local_center=(2.14, 1.02 * side_sign, 1.56),
            radii=(0.88, 0.18, 0.38),
            collection=model_collection,
            material=materials["body_red"],
            parent=body_ctrl,
            subdivisions=1,
        )
        create_ellipsoid(
            f"Rear_Fender_{side_name}",
            local_center=(-1.88, 1.26 * side_sign, 1.50),
            radii=(1.24, 0.42, 0.92),
            collection=model_collection,
            material=materials["body_red"],
            parent=body_ctrl,
            subdivisions=2,
        )
        create_ellipsoid(
            f"Rear_Fender_Cap_{side_name}",
            local_center=(-1.84, 1.02 * side_sign, 1.70),
            radii=(1.02, 0.20, 0.42),
            collection=model_collection,
            material=materials["body_red"],
            parent=body_ctrl,
            subdivisions=1,
        )

    # Grade frontal e para-choque
    create_box(
        "Grille",
        local_center=(3.06, 0.0, 1.72),
        size_xyz=(0.14, 1.56, 0.64),
        collection=model_collection,
        material=materials["chrome"],
        parent=body_ctrl,
    )
    create_box(
        "Front_Bumper",
        local_center=(3.31, 0.0, 1.08),
        size_xyz=(0.18, 2.08, 0.16),
        collection=model_collection,
        material=materials["chrome"],
        parent=body_ctrl,
    )

    for side_name, side_sign in (("L", 1.0), ("R", -1.0)):
        create_ellipsoid(
            f"Headlight_{side_name}",
            local_center=(3.02, 0.66 * side_sign, 1.80),
            radii=(0.12, 0.16, 0.16),
            collection=model_collection,
            material=materials["light_white"],
            parent=body_ctrl,
            subdivisions=1,
        )

    # ------------------------------------------------------------------
    # Plataforma do guincho
    # Laterais não avançam sobre a região da cabine.
    # Superfície superior cinza.
    # ------------------------------------------------------------------
    create_box(
        "Flatbed_Main",
        local_center=(-1.32, 0.0, 1.72),
        size_xyz=(4.46, 2.28, 0.18),
        collection=model_collection,
        material=materials["bed"],
        parent=body_ctrl,
    )
    create_box(
        "Flatbed_Transition_Block",
        local_center=(0.10, 0.0, 1.72),
        size_xyz=(0.56, 2.16, 0.18),
        collection=model_collection,
        material=materials["bed"],
        parent=body_ctrl,
    )
    create_box(
        "Flatbed_Edge_L",
        local_center=(-1.48, 1.08, 1.84),
        size_xyz=(4.12, 0.08, 0.16),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_box(
        "Flatbed_Edge_R",
        local_center=(-1.48, -1.08, 1.84),
        size_xyz=(4.12, 0.08, 0.16),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_box(
        "Flatbed_Rear_Lip",
        local_center=(-3.53, 0.0, 1.78),
        size_xyz=(0.10, 2.22, 0.14),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_box(
        "Flatbed_Undersupport_1",
        local_center=(-2.10, 0.0, 1.47),
        size_xyz=(0.24, 1.56, 0.42),
        collection=model_collection,
        material=materials["chassis"],
        parent=body_ctrl,
    )
    create_box(
        "Flatbed_Undersupport_2",
        local_center=(-0.82, 0.0, 1.47),
        size_xyz=(0.24, 1.56, 0.42),
        collection=model_collection,
        material=materials["chassis"],
        parent=body_ctrl,
    )
    create_box(
        "Flatbed_Undersupport_3",
        local_center=(0.18, 0.0, 1.47),
        size_xyz=(0.18, 1.48, 0.40),
        collection=model_collection,
        material=materials["chassis"],
        parent=body_ctrl,
    )

    # Estrutura do guincho atrás da cabine
    create_box(
        "Tow_Post_L",
        local_center=(0.34, 0.74, 2.42),
        size_xyz=(0.16, 0.16, 1.14),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_box(
        "Tow_Post_R",
        local_center=(0.34, -0.74, 2.42),
        size_xyz=(0.16, 0.16, 1.14),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_box(
        "Tow_Crossbar",
        local_center=(0.34, 0.0, 2.96),
        size_xyz=(0.16, 1.70, 0.14),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_box(
        "Tow_Winch_Box",
        local_center=(-0.02, 0.0, 2.06),
        size_xyz=(0.42, 0.92, 0.26),
        collection=model_collection,
        material=materials["body_red"],
        parent=body_ctrl,
    )
    create_cylinder_y(
        "Tow_Winch_Drum",
        local_center=(-0.04, 0.0, 2.08),
        radius=0.09,
        length=0.68,
        collection=model_collection,
        material=materials["chrome"],
        parent=body_ctrl,
        sides=18,
        smooth=True,
    )

    # Barra de luz e traseira
    create_box(
        "Roof_Light_Bar",
        local_center=(0.98, 0.0, 3.14),
        size_xyz=(0.74, 0.18, 0.12),
        collection=model_collection,
        material=materials["chrome"],
        parent=body_ctrl,
    )
    create_box(
        "Roof_Light_Red",
        local_center=(0.84, -0.10, 3.18),
        size_xyz=(0.18, 0.10, 0.10),
        collection=model_collection,
        material=materials["light_red"],
        parent=body_ctrl,
    )
    create_box(
        "Roof_Light_White",
        local_center=(1.12, 0.10, 3.18),
        size_xyz=(0.18, 0.10, 0.10),
        collection=model_collection,
        material=materials["light_white"],
        parent=body_ctrl,
    )

    create_box(
        "Rear_Bumper",
        local_center=(-3.66, 0.0, 1.08),
        size_xyz=(0.18, 2.18, 0.16),
        collection=model_collection,
        material=materials["chrome"],
        parent=body_ctrl,
    )
    for side_name, side_sign in (("L", 1.0), ("R", -1.0)):
        create_box(
            f"TailLight_{side_name}",
            local_center=(-3.54, 0.78 * side_sign, 1.60),
            size_xyz=(0.10, 0.16, 0.22),
            collection=model_collection,
            material=materials["light_red"],
            parent=body_ctrl,
        )

    create_box(
        "Step_L",
        local_center=(1.16, 1.16, 1.22),
        size_xyz=(1.16, 0.16, 0.08),
        collection=model_collection,
        material=materials["chrome"],
        parent=body_ctrl,
    )
    create_box(
        "Step_R",
        local_center=(1.16, -1.16, 1.22),
        size_xyz=(1.16, 0.16, 0.08),
        collection=model_collection,
        material=materials["chrome"],
        parent=body_ctrl,
    )

    # ------------------------------------------------------------------
    # Rodas
    # ------------------------------------------------------------------
    steer_fl = create_empty(
        STEER_PIVOT_NAMES["FL"],
        local_location=(2.08, 1.38, WHEEL_RADIUS),
        collection=control_collection,
        parent=master,
        display_type="CIRCLE",
        display_size=0.18,
    )
    steer_fr = create_empty(
        STEER_PIVOT_NAMES["FR"],
        local_location=(2.08, -1.38, WHEEL_RADIUS),
        collection=control_collection,
        parent=master,
        display_type="CIRCLE",
        display_size=0.18,
    )

    wheel_fl = create_wheel(
        WHEEL_OBJECT_NAMES["FL"],
        center=(0.0, 0.0, 0.0),
        collection=model_collection,
        parent=steer_fl,
        materials=materials,
    )
    wheel_fr = create_wheel(
        WHEEL_OBJECT_NAMES["FR"],
        center=(0.0, 0.0, 0.0),
        collection=model_collection,
        parent=steer_fr,
        materials=materials,
    )
    wheel_rl = create_wheel(
        WHEEL_OBJECT_NAMES["RL"],
        center=(-1.86, 1.38, WHEEL_RADIUS),
        collection=model_collection,
        parent=master,
        materials=materials,
    )
    wheel_rr = create_wheel(
        WHEEL_OBJECT_NAMES["RR"],
        center=(-1.86, -1.38, WHEEL_RADIUS),
        collection=model_collection,
        parent=master,
        materials=materials,
    )

    master["wheel_fl"] = wheel_fl.name
    master["wheel_fr"] = wheel_fr.name
    master["wheel_rl"] = wheel_rl.name
    master["wheel_rr"] = wheel_rr.name
    master["steer_fl"] = steer_fl.name
    master["steer_fr"] = steer_fr.name
    master["body_ctrl"] = body_ctrl.name
    master["follow_rig"] = follow_rig.name

    # ------------------------------------------------------------------
    # Terreno, câmera e luzes
    # ------------------------------------------------------------------
    ground = create_plane(
        name=GROUND_NAME,
        size=GROUND_SIZE,
        z=0.0,
        collection=env_collection,
        material=materials["ground"],
    )

    key_light_data = bpy.data.lights.new("StyleTruck_Key_Light_Data", type="AREA")
    key_light_data.energy = 1200.0
    key_light_data.shape = "RECTANGLE"
    key_light_data.size = 6.5
    key_light_data.size_y = 3.5

    key_light = bpy.data.objects.new("StyleTruck_Key_Light", key_light_data)
    env_collection.objects.link(key_light)
    key_light.parent = follow_rig
    key_light.location = (5.2, -5.4, 8.2)
    look_at(key_light, (0.0, 0.0, 1.6))

    fill_light_data = bpy.data.lights.new("StyleTruck_Fill_Light_Data", type="AREA")
    fill_light_data.energy = 650.0
    fill_light_data.shape = "RECTANGLE"
    fill_light_data.size = 5.0
    fill_light_data.size_y = 3.0

    fill_light = bpy.data.objects.new("StyleTruck_Fill_Light", fill_light_data)
    env_collection.objects.link(fill_light)
    fill_light.parent = follow_rig
    fill_light.location = (-4.5, 4.4, 5.8)
    look_at(fill_light, (0.0, 0.0, 1.8))

    camera_data = bpy.data.cameras.new("StyleTruck_Camera_Data")
    camera = bpy.data.objects.new("StyleTruck_Camera", camera_data)
    env_collection.objects.link(camera)
    camera.parent = follow_rig
    camera.location = (-10.5, -12.2, 6.2)
    camera_data.lens = 48.0
    look_at(camera, (0.0, 0.0, 1.7))
    scene.camera = camera

    world = bpy.data.worlds.new("StyleTruck_World")
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

    background.inputs["Color"].default_value = (0.028, 0.037, 0.048, 1.0)
    background.inputs["Strength"].default_value = 0.45
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
        "control_collection": control_collection,
        "env_collection": env_collection,
        "master": master,
        "body_ctrl": body_ctrl,
        "follow_rig": follow_rig,
        "ground": ground,
    }


# ============================================================================
# FUNÇÕES DE ESTADO DO VEÍCULO
# ============================================================================

def get_master_object():
    return bpy.data.objects.get(MASTER_NAME)


def get_body_control():
    return bpy.data.objects.get(BODY_CTRL_NAME)


def get_follow_rig():
    return bpy.data.objects.get(FOLLOW_RIG_NAME)


def get_wheel_object(position_code):
    return bpy.data.objects.get(WHEEL_OBJECT_NAMES[position_code])


def get_steer_pivot(position_code):
    return bpy.data.objects.get(STEER_PIVOT_NAMES[position_code])


def reset_vehicle_pose():
    master = get_master_object()
    body_ctrl = get_body_control()
    follow_rig = get_follow_rig()

    if master is None:
        return False

    master.location = Vector((0.0, 0.0, 0.0))
    master.rotation_mode = "XYZ"
    master.rotation_euler = (0.0, 0.0, 0.0)

    if body_ctrl is not None:
        body_ctrl.location = Vector((0.0, 0.0, 0.0))
        body_ctrl.rotation_mode = "XYZ"
        body_ctrl.rotation_euler = (0.0, 0.0, 0.0)

    if follow_rig is not None:
        follow_rig.location = Vector((0.0, 0.0, 0.0))
        follow_rig.rotation_mode = "XYZ"
        follow_rig.rotation_euler = (0.0, 0.0, 0.0)

    for code in ("FL", "FR", "RL", "RR"):
        wheel = get_wheel_object(code)
        if wheel is not None:
            wheel.rotation_mode = "XYZ"
            wheel.rotation_euler = (0.0, 0.0, 0.0)

    for code in ("FL", "FR"):
        pivot = get_steer_pivot(code)
        if pivot is not None:
            pivot.rotation_mode = "XYZ"
            pivot.rotation_euler = (0.0, 0.0, 0.0)

    bpy.context.view_layer.update()
    return True


def model_statistics(model_collection):
    mesh_objects = [
        obj for obj in model_collection.all_objects
        if obj.type == "MESH"
    ]
    polygon_count = sum(len(obj.data.polygons) for obj in mesh_objects)
    return len(mesh_objects), polygon_count


# ============================================================================
# CONTROLADOR MODAL DO TECLADO
# ============================================================================

class WM_OT_styletruck_keyboard_controller(bpy.types.Operator):
    bl_idname = "wm.styletruck_keyboard_controller"
    bl_label = "Controlador do caminhão guincho"
    bl_description = "Setas movem o caminhão; HOME centraliza; ESC encerra"

    _active_instance = None

    _timer = None
    _window_manager = None
    _area = None

    _master = None
    _body_ctrl = None
    _follow_rig = None
    _steer_fl = None
    _steer_fr = None
    _wheel_fl = None
    _wheel_fr = None
    _wheel_rl = None
    _wheel_rr = None

    _up_pressed = False
    _down_pressed = False
    _left_pressed = False
    _right_pressed = False
    _stop_requested = False

    _velocity = 0.0
    _steer_angle = 0.0
    _wheel_spin = 0.0
    _phase = 0.0
    _last_time = 0.0

    def _set_header(self, text):
        if self._area is not None:
            try:
                self._area.header_text_set(text)
            except Exception:
                pass

    def _clear_header(self):
        if self._area is not None:
            try:
                self._area.header_text_set(None)
            except Exception:
                pass

    def _bind_objects(self):
        self._master = get_master_object()
        self._body_ctrl = get_body_control()
        self._follow_rig = get_follow_rig()
        self._steer_fl = get_steer_pivot("FL")
        self._steer_fr = get_steer_pivot("FR")
        self._wheel_fl = get_wheel_object("FL")
        self._wheel_fr = get_wheel_object("FR")
        self._wheel_rl = get_wheel_object("RL")
        self._wheel_rr = get_wheel_object("RR")

        return all(
            obj is not None for obj in (
                self._master,
                self._body_ctrl,
                self._follow_rig,
                self._steer_fl,
                self._steer_fr,
                self._wheel_fl,
                self._wheel_fr,
                self._wheel_rl,
                self._wheel_rr,
            )
        )

    def _reset_runtime_state(self):
        self._up_pressed = False
        self._down_pressed = False
        self._left_pressed = False
        self._right_pressed = False
        self._stop_requested = False
        self._velocity = 0.0
        self._steer_angle = 0.0
        self._wheel_spin = 0.0
        self._phase = 0.0
        self._last_time = 0.0

    def _shutdown(self, context):
        self._up_pressed = False
        self._down_pressed = False
        self._left_pressed = False
        self._right_pressed = False
        self._velocity = 0.0

        if self._timer is not None and self._window_manager is not None:
            try:
                self._window_manager.event_timer_remove(self._timer)
            except Exception:
                pass

        self._timer = None
        self._window_manager = None
        self._clear_header()

        if WM_OT_styletruck_keyboard_controller._active_instance is self:
            WM_OT_styletruck_keyboard_controller._active_instance = None

        return {"CANCELLED"}

    def _apply_steering(self, delta_time, scene):
        target_steer = 0.0
        if self._left_pressed and not self._right_pressed:
            target_steer = math.radians(MAX_STEER_ANGLE_DEG)
        elif self._right_pressed and not self._left_pressed:
            target_steer = -math.radians(MAX_STEER_ANGLE_DEG)

        return_speed = float(scene.styletruck_steer_return_speed)
        move_speed = return_speed * 0.95

        if target_steer > self._steer_angle:
            self._steer_angle = min(
                target_steer,
                self._steer_angle + move_speed * delta_time,
            )
        elif target_steer < self._steer_angle:
            self._steer_angle = max(
                target_steer,
                self._steer_angle - move_speed * delta_time,
            )

    def _update_velocity(self, delta_time, scene):
        direction = int(self._up_pressed) - int(self._down_pressed)
        max_speed = float(scene.styletruck_drive_speed)

        target_velocity = direction * max_speed
        accel = float(scene.styletruck_acceleration)
        decel = float(scene.styletruck_deceleration)

        if direction == 0:
            if self._velocity > 0.0:
                self._velocity = max(0.0, self._velocity - decel * delta_time)
            elif self._velocity < 0.0:
                self._velocity = min(0.0, self._velocity + decel * delta_time)
        else:
            same_direction = (
                self._velocity == 0.0
                or (self._velocity > 0.0 and target_velocity > 0.0)
                or (self._velocity < 0.0 and target_velocity < 0.0)
            )
            rate = accel if same_direction else decel * 1.35

            if self._velocity < target_velocity:
                self._velocity = min(target_velocity, self._velocity + rate * delta_time)
            elif self._velocity > target_velocity:
                self._velocity = max(target_velocity, self._velocity - rate * delta_time)

        if abs(self._velocity) < 0.01 and direction == 0:
            self._velocity = 0.0

    def _move_master(self, delta_time, scene):
        turn_speed = float(scene.styletruck_turn_speed)
        max_speed = max(float(scene.styletruck_drive_speed), 0.001)
        speed_ratio = min(1.0, abs(self._velocity) / max_speed)
        velocity_sign = 1.0 if self._velocity >= 0.0 else -1.0

        heading_delta = (
            math.sin(self._steer_angle)
            * turn_speed
            * speed_ratio
            * velocity_sign
            * delta_time
        )

        new_heading = self._master.rotation_euler.z + heading_delta
        self._master.rotation_euler.z = math.atan2(
            math.sin(new_heading),
            math.cos(new_heading),
        )

        requested_distance = self._velocity * delta_time
        heading = self._master.rotation_euler.z
        forward = Vector((math.cos(heading), math.sin(heading), 0.0))

        current_location = self._master.location.copy()
        proposed_location = current_location + forward * requested_distance

        limit = GROUND_SIZE * 0.5 - GROUND_MARGIN
        proposed_location.x = max(-limit, min(limit, proposed_location.x))
        proposed_location.y = max(-limit, min(limit, proposed_location.y))
        proposed_location.z = 0.0

        actual_delta = Vector((
            proposed_location.x - current_location.x,
            proposed_location.y - current_location.y,
            0.0,
        ))
        actual_distance = actual_delta.dot(forward)

        self._master.location = proposed_location
        return actual_distance, speed_ratio

    def _update_wheels(self, distance_travelled):
        spin_delta = -(distance_travelled / max(WHEEL_RADIUS, 0.001))
        self._wheel_spin += spin_delta

        for wheel in (
            self._wheel_fl,
            self._wheel_fr,
            self._wheel_rl,
            self._wheel_rr,
        ):
            wheel.rotation_mode = "XYZ"
            wheel.rotation_euler.y = self._wheel_spin

        self._steer_fl.rotation_euler.z = self._steer_angle
        self._steer_fr.rotation_euler.z = self._steer_angle

    def _update_body_secondary_motion(self, distance_travelled, speed_ratio):
        self._phase += abs(distance_travelled) * 2.6

        bounce = math.sin(self._phase * 1.2) * 0.045 * speed_ratio
        pitch = (-self._velocity / max(DEFAULT_SPEED, 0.001)) * 0.032
        lean = -self._steer_angle * 0.16 * speed_ratio

        self._body_ctrl.location.z = bounce
        self._body_ctrl.rotation_euler.x = pitch
        self._body_ctrl.rotation_euler.z = lean

    def _update_follow_rig(self, scene):
        if bool(scene.styletruck_camera_follow):
            self._follow_rig.location.x = self._master.location.x
            self._follow_rig.location.y = self._master.location.y
            self._follow_rig.location.z = 0.0
            self._follow_rig.rotation_euler.z = self._master.rotation_euler.z
        else:
            self._follow_rig.location = Vector((0.0, 0.0, 0.0))
            self._follow_rig.rotation_euler.z = 0.0

    def _tick(self, context):
        scene = context.scene

        if self._stop_requested:
            return self._shutdown(context)

        if self._master is None or self._master.name not in bpy.data.objects:
            return self._shutdown(context)

        delta_time = TIMER_INTERVAL
        self._apply_steering(delta_time, scene)
        self._update_velocity(delta_time, scene)

        distance_travelled, speed_ratio = self._move_master(delta_time, scene)
        self._update_wheels(distance_travelled)
        self._update_body_secondary_motion(distance_travelled, speed_ratio)
        self._update_follow_rig(scene)

        heading_deg = math.degrees(self._master.rotation_euler.z)
        self._set_header(
            "StyleTruck: ↑ frente  ↓ ré  ←/→ virar  HOME centralizar  "
            f"ESC sair | velocidade {abs(self._velocity):.2f} | "
            f"heading {heading_deg:.1f}°"
        )

        bpy.context.view_layer.update()
        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        active = WM_OT_styletruck_keyboard_controller._active_instance
        if active is not None and active._timer is not None:
            self.report({"INFO"}, "O controlador já está ativo.")
            return {"CANCELLED"}

        if not self._bind_objects():
            self.report({"ERROR"}, "Não foi possível localizar o caminhão na cena.")
            return {"CANCELLED"}

        self._reset_runtime_state()
        self._window_manager = context.window_manager
        self._timer = self._window_manager.event_timer_add(
            TIMER_INTERVAL,
            window=context.window,
        )
        self._window_manager.modal_handler_add(self)

        self._area = context.area
        self._set_header(
            "StyleTruck: ↑/↓ deslocam | ←/→ viram | HOME centraliza | ESC encerra"
        )

        WM_OT_styletruck_keyboard_controller._active_instance = self
        self.report({"INFO"}, "Controle ativo: ↑/↓ deslocam e ←/→ viram.")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC" and event.value == "PRESS":
            self._stop_requested = True
            return {"RUNNING_MODAL"}

        if event.type == "HOME" and event.value == "PRESS":
            reset_vehicle_pose()
            self._reset_runtime_state()
            return {"RUNNING_MODAL"}

        if event.type == "UP_ARROW":
            if event.value == "PRESS":
                self._up_pressed = True
            elif event.value == "RELEASE":
                self._up_pressed = False
            return {"RUNNING_MODAL"}

        if event.type == "DOWN_ARROW":
            if event.value == "PRESS":
                self._down_pressed = True
            elif event.value == "RELEASE":
                self._down_pressed = False
            return {"RUNNING_MODAL"}

        if event.type == "LEFT_ARROW":
            if event.value == "PRESS":
                self._left_pressed = True
            elif event.value == "RELEASE":
                self._left_pressed = False
            return {"RUNNING_MODAL"}

        if event.type == "RIGHT_ARROW":
            if event.value == "PRESS":
                self._right_pressed = True
            elif event.value == "RELEASE":
                self._right_pressed = False
            return {"RUNNING_MODAL"}

        if event.type == "WINDOW_DEACTIVATE":
            self._up_pressed = False
            self._down_pressed = False
            self._left_pressed = False
            self._right_pressed = False
            return {"PASS_THROUGH"}

        if event.type == "TIMER":
            event_timer = getattr(event, "timer", None)
            if event_timer is None or event_timer == self._timer:
                return self._tick(context)
            return {"PASS_THROUGH"}

        return {"PASS_THROUGH"}


# ============================================================================
# OPERADORES AUXILIARES E PAINEL
# ============================================================================

class WM_OT_styletruck_start_controller(bpy.types.Operator):
    bl_idname = "wm.styletruck_start_controller"
    bl_label = "Iniciar controle"
    bl_description = "Inicia o controle do caminhão pelo teclado"

    def execute(self, context):
        result = bpy.ops.wm.styletruck_keyboard_controller("INVOKE_DEFAULT")
        if "CANCELLED" in result:
            return {"CANCELLED"}
        return {"FINISHED"}


class WM_OT_styletruck_stop_controller(bpy.types.Operator):
    bl_idname = "wm.styletruck_stop_controller"
    bl_label = "Parar controle"
    bl_description = "Pede encerramento do controle modal"

    def execute(self, context):
        active = WM_OT_styletruck_keyboard_controller._active_instance
        if active is None:
            self.report({"INFO"}, "Nenhum controlador ativo.")
            return {"CANCELLED"}

        active._stop_requested = True
        self.report({"INFO"}, "Encerramento solicitado.")
        return {"FINISHED"}


class WM_OT_styletruck_reset_vehicle(bpy.types.Operator):
    bl_idname = "wm.styletruck_reset_vehicle"
    bl_label = "Resetar caminhão"
    bl_description = "Retorna o caminhão ao centro do terreno"

    def execute(self, context):
        if not reset_vehicle_pose():
            self.report({"ERROR"}, "Caminhão não encontrado na cena.")
            return {"CANCELLED"}

        active = WM_OT_styletruck_keyboard_controller._active_instance
        if active is not None:
            active._reset_runtime_state()

        self.report({"INFO"}, "Caminhão resetado.")
        return {"FINISHED"}


class VIEW3D_PT_styletruck_controls(bpy.types.Panel):
    bl_label = "Guincho Estilizado"
    bl_idname = "VIEW3D_PT_styletruck_controls"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Guincho"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.label(text="Controles de teclado")
        box.label(text="↑ frente")
        box.label(text="↓ ré")
        box.label(text="←/→ virar")
        box.label(text="HOME centralizar")
        box.label(text="ESC parar")

        row = layout.row(align=True)
        row.operator("wm.styletruck_start_controller", icon="PLAY")
        row.operator("wm.styletruck_stop_controller", icon="PAUSE")

        layout.operator("wm.styletruck_reset_vehicle", icon="LOOP_BACK")

        layout.separator()
        layout.prop(scene, "styletruck_drive_speed")
        layout.prop(scene, "styletruck_turn_speed")
        layout.prop(scene, "styletruck_acceleration")
        layout.prop(scene, "styletruck_deceleration")
        layout.prop(scene, "styletruck_steer_return_speed")
        layout.prop(scene, "styletruck_camera_follow")


# ============================================================================
# REGISTRO
# ============================================================================

CLASSES = (
    WM_OT_styletruck_keyboard_controller,
    WM_OT_styletruck_start_controller,
    WM_OT_styletruck_stop_controller,
    WM_OT_styletruck_reset_vehicle,
    VIEW3D_PT_styletruck_controls,
)


def register():
    clear_scene_properties()
    unregister_previous_classes()

    bpy.types.Scene.styletruck_drive_speed = FloatProperty(
        name="Velocidade",
        description="Velocidade máxima do caminhão",
        default=DEFAULT_SPEED,
        min=0.5,
        max=25.0,
        soft_max=15.0,
    )
    bpy.types.Scene.styletruck_turn_speed = FloatProperty(
        name="Velocidade de giro",
        description="Velocidade base de rotação nas curvas",
        default=math.radians(DEFAULT_TURN_SPEED_DEG),
        min=math.radians(10.0),
        max=math.radians(220.0),
        soft_max=math.radians(130.0),
        subtype="ANGLE",
    )
    bpy.types.Scene.styletruck_acceleration = FloatProperty(
        name="Aceleração",
        description="Taxa de aceleração",
        default=DEFAULT_ACCEL,
        min=1.0,
        max=60.0,
        soft_max=24.0,
    )
    bpy.types.Scene.styletruck_deceleration = FloatProperty(
        name="Desaceleração",
        description="Taxa de desaceleração / frenagem",
        default=DEFAULT_DECEL,
        min=1.0,
        max=80.0,
        soft_max=28.0,
    )
    bpy.types.Scene.styletruck_steer_return_speed = FloatProperty(
        name="Retorno da direção",
        description="Velocidade de retorno das rodas ao centro",
        default=math.radians(DEFAULT_STEER_RETURN),
        min=math.radians(20.0),
        max=math.radians(360.0),
        soft_max=math.radians(220.0),
        subtype="ANGLE",
    )
    bpy.types.Scene.styletruck_camera_follow = BoolProperty(
        name="Câmera e luzes acompanham",
        description="Se ativo, câmera e luzes acompanham o caminhão",
        default=True,
    )

    for cls in CLASSES:
        bpy.utils.register_class(cls)


# ============================================================================
# EXECUÇÃO PRINCIPAL
# ============================================================================

clean_entire_scene()
register()

current_scene = bpy.context.scene
current_scene.styletruck_drive_speed = DEFAULT_SPEED
current_scene.styletruck_turn_speed = math.radians(DEFAULT_TURN_SPEED_DEG)
current_scene.styletruck_acceleration = DEFAULT_ACCEL
current_scene.styletruck_deceleration = DEFAULT_DECEL
current_scene.styletruck_steer_return_speed = math.radians(DEFAULT_STEER_RETURN)
current_scene.styletruck_camera_follow = True

build_result = build_styletruck_model(current_scene)
reset_vehicle_pose()

mesh_count, polygon_count = model_statistics(build_result["model_collection"])

try:
    bpy.ops.wm.styletruck_keyboard_controller("INVOKE_DEFAULT")
    controller_message = "Controle por teclado: iniciado automaticamente."
except Exception as exc:
    controller_message = (
        "Controle por teclado: não foi iniciado automaticamente "
        f"({exc}). Use o painel lateral."
    )

print("=" * 72)
print("Caminhão guincho plataforma estilizado branco reconstruído com sucesso.")
print(f"Versão do gerador: {GENERATOR_VERSION}")
print(f"Objetos de malha do modelo: {mesh_count}")
print(f"Polígonos aproximados: {polygon_count}")
print(f"{GROUND_NAME}: {GROUND_SIZE:.1f} x {GROUND_SIZE:.1f}, em Z=0.0000.")
print("A cena foi limpa integralmente antes da geração; o script é idempotente.")
print(controller_message)
print("Segure ↑ para frente, ↓ para ré, ←/→ para virar, HOME para o centro e ESC para sair.")
print("=" * 72)
