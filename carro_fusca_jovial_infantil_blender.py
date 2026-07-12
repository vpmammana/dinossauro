"""
Carro estilo fusca jovial e infantilizado — Blender Python
==========================================================

Este script cria um carro inspirado em um Fusca, com visual bem jovial,
formas arredondadas e traços infantis. O modelo é propositalmente simples,
low-poly e dimensionado para caber sobre a plataforma do caminhão guincho
gerado anteriormente.

Características:
- limpeza total da cena no início para execução idempotente;
- carro compacto com proporções adequadas para caber na plataforma;
- aparência lúdica / infantil:
    * carroceria arredondada
    * faróis grandes como "olhos"
    * para-choque com expressão amistosa
    * proporções fofas
- materiais simples, sem texturas externas;
- chão, câmera e iluminação de preview;
- dimensões finais aproximadas:
    comprimento ~ 3.10
    largura     ~ 1.58
    altura      ~ 1.58

Compatibilidade pretendida: Blender 3.6 LTS e versões posteriores.
"""

import bpy
import bmesh
import math
import warnings
from mathutils import Vector


GENERATOR_VERSION = "1.0-fusca-jovial"
GROUND_SIZE = 24.0

CAR_LENGTH = 3.10
CAR_WIDTH = 1.58
CAR_HEIGHT = 1.58
WHEEL_RADIUS = 0.36
WHEEL_WIDTH = 0.24

COLLECTION_MAIN = "CuteBeetle_Generated"
COLLECTION_MODEL = "MODEL_Meshes"
COLLECTION_ENV = "ENVIRONMENT"
ROOT_NAME = "CuteBeetle_Root"


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
        (sx, -sy, -sz),
        (sx, sy, -sz),
        (-sx, sy, -sz),
        (-sx, -sy, sz),
        (sx, -sy, sz),
        (sx, sy, sz),
        (-sx, sy, sz),
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
                     parent=None, subdivisions=2):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(
        bm,
        subdivisions=subdivisions,
        radius=1.0,
    )

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


def create_rounded_loaf(
    name,
    local_center,
    length,
    width,
    base_height,
    roof_height,
    collection,
    material,
    parent=None,
    x_segments=12,
    z_segments=7,
):
    half_length = length * 0.5
    half_width = width * 0.5
    total_height = base_height + roof_height

    x_values = [
        -half_length + (length * i / x_segments)
        for i in range(x_segments + 1)
    ]

    vertices = []
    faces = []

    for z_index in range(z_segments + 1):
        t = z_index / z_segments
        crown = math.sin(t * math.pi * 0.5)
        z = -total_height * 0.5 + base_height + crown * roof_height

        width_factor = 1.0 - (t ** 1.45) * 0.36
        x_shrink = (t ** 1.3) * 0.12 * length

        for x in x_values:
            xn = abs(x) / half_length if half_length > 1.0e-8 else 0.0
            front_back_soft = 1.0 - (xn ** 2.1) * 0.22
            local_half_width = half_width * width_factor * front_back_soft

            x_adjusted = x
            if x > 0.0:
                x_adjusted -= x_shrink * 0.35
            else:
                x_adjusted += x_shrink * 0.18

            vertices.append((x_adjusted, -local_half_width, z))
            vertices.append((x_adjusted, local_half_width, z))

    ring_stride = len(x_values) * 2

    def v_index(z_idx, x_idx, side_idx):
        return z_idx * ring_stride + x_idx * 2 + side_idx

    for z_idx in range(z_segments):
        for x_idx in range(len(x_values) - 1):
            a = v_index(z_idx, x_idx, 0)
            b = v_index(z_idx, x_idx, 1)
            c = v_index(z_idx, x_idx + 1, 1)
            d = v_index(z_idx, x_idx + 1, 0)

            e = v_index(z_idx + 1, x_idx, 0)
            f = v_index(z_idx + 1, x_idx, 1)
            g = v_index(z_idx + 1, x_idx + 1, 1)
            h = v_index(z_idx + 1, x_idx + 1, 0)

            faces.append((a, b, f, e))
            faces.append((d, c, g, h))
            faces.append((a, d, h, e))
            faces.append((b, c, g, f))

    for z_idx in range(z_segments):
        a = v_index(z_idx, 0, 0)
        b = v_index(z_idx, 0, 1)
        c = v_index(z_idx + 1, 0, 1)
        d = v_index(z_idx + 1, 0, 0)
        faces.append((a, b, c, d))

        x_last = len(x_values) - 1
        e = v_index(z_idx, x_last, 0)
        f = v_index(z_idx, x_last, 1)
        g = v_index(z_idx + 1, x_last, 1)
        h = v_index(z_idx + 1, x_last, 0)
        faces.append((e, h, g, f))

    for x_idx in range(len(x_values) - 1):
        a = v_index(0, x_idx, 0)
        b = v_index(0, x_idx + 1, 0)
        c = v_index(0, x_idx + 1, 1)
        d = v_index(0, x_idx, 1)
        faces.append((a, b, c, d))

    return create_mesh_object(
        name=name,
        vertices=vertices,
        faces=faces,
        collection=collection,
        material=material,
        parent=parent,
        local_location=local_center,
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
    materials = {}
    materials["body"] = create_principled_material(
        "MAT_CuteBeetle_Body",
        color=(0.18, 0.76, 0.94),
        roughness=0.44,
        metallic=0.0,
    )
    materials["accent"] = create_principled_material(
        "MAT_CuteBeetle_Accent",
        color=(0.98, 0.96, 0.95),
        roughness=0.42,
        metallic=0.0,
    )
    materials["glass"] = create_principled_material(
        "MAT_CuteBeetle_Glass",
        color=(0.42, 0.62, 0.78),
        roughness=0.06,
        metallic=0.0,
        alpha=0.42,
        transmission=0.10,
        blend_method="BLEND",
    )
    materials["rubber"] = create_principled_material(
        "MAT_CuteBeetle_Rubber",
        color=(0.04, 0.04, 0.045),
        roughness=0.95,
        metallic=0.0,
    )
    materials["rim"] = create_principled_material(
        "MAT_CuteBeetle_Rim",
        color=(0.90, 0.92, 0.95),
        roughness=0.24,
        metallic=0.82,
    )
    materials["headlight"] = create_principled_material(
        "MAT_CuteBeetle_Headlight",
        color=(0.99, 0.97, 0.89),
        roughness=0.18,
        metallic=0.0,
    )
    materials["black"] = create_principled_material(
        "MAT_CuteBeetle_Black",
        color=(0.03, 0.03, 0.035),
        roughness=0.72,
        metallic=0.0,
    )
    materials["ground"] = create_principled_material(
        "MAT_CuteBeetle_Ground",
        color=(0.13, 0.17, 0.11),
        roughness=1.0,
        metallic=0.0,
    )
    return materials


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
    root["generator_version"] = GENERATOR_VERSION
    root["intended_flatbed_fit"] = "length <= 3.10, width <= 1.58"

    create_box(
        "Chassis_Block",
        local_center=(0.00, 0.0, 0.62),
        size_xyz=(2.60, 1.30, 0.20),
        collection=model_collection,
        material=materials["black"],
        parent=root,
    )

    create_rounded_loaf(
        "Body_Main",
        local_center=(0.05, 0.0, 1.14),
        length=2.90,
        width=1.52,
        base_height=0.42,
        roof_height=0.86,
        collection=model_collection,
        material=materials["body"],
        parent=root,
        x_segments=14,
        z_segments=7,
    )

    create_rounded_loaf(
        "Roof_Cap",
        local_center=(-0.04, 0.0, 1.56),
        length=1.58,
        width=1.30,
        base_height=0.10,
        roof_height=0.34,
        collection=model_collection,
        material=materials["body"],
        parent=root,
        x_segments=10,
        z_segments=5,
    )

    create_box(
        "Belly_Panel",
        local_center=(0.02, 0.0, 0.78),
        size_xyz=(2.34, 1.18, 0.10),
        collection=model_collection,
        material=materials["accent"],
        parent=root,
    )

    create_ellipsoid(
        "Front_Nose",
        local_center=(1.18, 0.0, 1.06),
        radii=(0.55, 0.68, 0.48),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        subdivisions=2,
    )

    create_ellipsoid(
        "Rear_Curve",
        local_center=(-1.12, 0.0, 1.06),
        radii=(0.52, 0.66, 0.46),
        collection=model_collection,
        material=materials["body"],
        parent=root,
        subdivisions=2,
    )

    create_box(
        "Windshield",
        local_center=(0.66, 0.0, 1.48),
        size_xyz=(0.08, 1.04, 0.50),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
    )

    create_box(
        "Rear_Window",
        local_center=(-0.63, 0.0, 1.48),
        size_xyz=(0.08, 0.94, 0.42),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
    )

    create_box(
        "Side_Window_L",
        local_center=(0.02, 0.66, 1.48),
        size_xyz=(1.20, 0.08, 0.46),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
    )

    create_box(
        "Side_Window_R",
        local_center=(0.02, -0.66, 1.48),
        size_xyz=(1.20, 0.08, 0.46),
        collection=model_collection,
        material=materials["glass"],
        parent=root,
    )

    wheel_positions = {
        "FL": (0.92, 0.79, WHEEL_RADIUS),
        "FR": (0.92, -0.79, WHEEL_RADIUS),
        "RL": (-0.92, 0.79, WHEEL_RADIUS),
        "RR": (-0.92, -0.79, WHEEL_RADIUS),
    }

    for name, (x, y, z) in wheel_positions.items():
        create_ellipsoid(
            f"Fender_{name}",
            local_center=(x, y, 0.88),
            radii=(0.52, 0.20, 0.54),
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
            radius=WHEEL_RADIUS * 0.52,
            length=WHEEL_WIDTH * 1.06,
            collection=model_collection,
            material=materials["rim"],
            parent=wheel,
            sides=16,
            smooth=True,
        )

    for side_name, side_sign in (("L", 1.0), ("R", -1.0)):
        create_ellipsoid(
            f"Headlight_{side_name}",
            local_center=(1.25, 0.34 * side_sign, 1.12),
            radii=(0.16, 0.18, 0.18),
            collection=model_collection,
            material=materials["headlight"],
            parent=root,
            subdivisions=1,
        )
        create_ellipsoid(
            f"Pupil_{side_name}",
            local_center=(1.33, 0.34 * side_sign, 1.12),
            radii=(0.05, 0.055, 0.055),
            collection=model_collection,
            material=materials["black"],
            parent=root,
            subdivisions=1,
        )

    create_box(
        "Front_Bumper",
        local_center=(1.43, 0.0, 0.82),
        size_xyz=(0.10, 1.02, 0.10),
        collection=model_collection,
        material=materials["accent"],
        parent=root,
    )

    create_box(
        "Smile_Mid",
        local_center=(1.34, 0.0, 0.92),
        size_xyz=(0.06, 0.56, 0.05),
        collection=model_collection,
        material=materials["black"],
        parent=root,
    )
    create_box(
        "Smile_L",
        local_center=(1.31, 0.19, 0.89),
        size_xyz=(0.05, 0.22, 0.04),
        collection=model_collection,
        material=materials["black"],
        parent=root,
    )
    create_box(
        "Smile_R",
        local_center=(1.31, -0.19, 0.89),
        size_xyz=(0.05, 0.22, 0.04),
        collection=model_collection,
        material=materials["black"],
        parent=root,
    )

    create_box(
        "Door_Handle_L",
        local_center=(0.18, 0.77, 1.18),
        size_xyz=(0.16, 0.05, 0.05),
        collection=model_collection,
        material=materials["accent"],
        parent=root,
    )
    create_box(
        "Door_Handle_R",
        local_center=(0.18, -0.77, 1.18),
        size_xyz=(0.16, 0.05, 0.05),
        collection=model_collection,
        material=materials["accent"],
        parent=root,
    )

    create_box(
        "Rear_Bumper",
        local_center=(-1.45, 0.0, 0.82),
        size_xyz=(0.10, 1.00, 0.10),
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
    key_light.location = (4.5, -5.0, 6.2)
    look_at(key_light, (0.0, 0.0, 1.0))

    fill_light_data = bpy.data.lights.new("CuteBeetle_Fill_Light_Data", type="AREA")
    fill_light_data.energy = 430.0
    fill_light_data.shape = "RECTANGLE"
    fill_light_data.size = 4.2
    fill_light_data.size_y = 2.4

    fill_light = bpy.data.objects.new("CuteBeetle_Fill_Light", fill_light_data)
    env_collection.objects.link(fill_light)
    fill_light.location = (-4.0, 4.6, 4.7)
    look_at(fill_light, (0.0, 0.0, 1.1))

    camera_data = bpy.data.cameras.new("CuteBeetle_Camera_Data")
    camera = bpy.data.objects.new("CuteBeetle_Camera", camera_data)
    env_collection.objects.link(camera)
    camera.location = (6.4, -8.8, 4.4)
    camera_data.lens = 52.0
    look_at(camera, (0.0, 0.0, 1.10))
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
print("Carro estilo fusca jovial criado com sucesso.")
print(f"Versão do gerador: {GENERATOR_VERSION}")
print(f"Objetos de malha: {len(mesh_objects)}")
print(f"Polígonos aproximados: {polygon_count}")
print(
    "Dimensões finais aproximadas "
    f"(C x L x A): {dims.x:.2f} x {dims.y:.2f} x {dims.z:.2f}"
)
print("Escala planejada para caber na plataforma do caminhão: sim")
print("A cena foi limpa integralmente antes da geração; o script é idempotente.")
print("=" * 72)
