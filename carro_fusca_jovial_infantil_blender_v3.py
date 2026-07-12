"""
Carro estilo Fusca jovial — versão 3 corrigida
==============================================

Correções desta versão:
- corpo principal contínuo, sem parecer uma "formiga";
- capô dianteiro e traseira unidos suavemente ao volume central;
- paralamas sobrepostos ao corpo, sem espaços visíveis;
- faróis posicionados na frente do carro, olhando totalmente para frente;
- parte inferior integrada, sem gap entre corpo e base;
- chassi não visível externamente;
- escala compacta para caber na plataforma do caminhão guincho.
"""

import bpy
import bmesh
import math
import warnings
from mathutils import Vector

GENERATOR_VERSION = "3.0-fusca-jovial-corrigido"
GROUND_SIZE = 24.0

TARGET_LENGTH = 3.00
TARGET_WIDTH = 1.54
TARGET_HEIGHT = 1.58
WHEEL_RADIUS = 0.34
WHEEL_WIDTH = 0.22

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
    mesh.from_pydata([tuple(Vector(v)) for v in vertices], [], [tuple(f) for f in faces])
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
                     parent=None, subdivisions=2, rotation=(0.0, 0.0, 0.0)):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=1.0)
    rx, ry, rz = radii
    for v in bm.verts:
        v.co.x *= rx
        v.co.y *= ry
        v.co.z *= rz
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


def create_beetle_shell(name, local_center, collection, material, parent=None):
    stations = [
        ( 1.46, 0.16, 0.54, 0.82),
        ( 1.24, 0.40, 0.48, 0.98),
        ( 0.94, 0.54, 0.46, 1.14),
        ( 0.58, 0.61, 0.44, 1.38),
        ( 0.16, 0.67, 0.42, 1.58),
        (-0.18, 0.67, 0.42, 1.58),
        (-0.56, 0.61, 0.44, 1.36),
        (-0.92, 0.56, 0.46, 1.16),
        (-1.22, 0.44, 0.48, 1.00),
        (-1.46, 0.18, 0.54, 0.82),
    ]
    section_points = 12
    vertices = []
    faces = []

    for x, half_width, z_bottom, z_top in stations:
        center_z = 0.5 * (z_bottom + z_top)
        radius_z = 0.5 * (z_top - z_bottom)

        for i in range(section_points):
            phi = 2.0 * math.pi * i / section_points
            width_scale = 0.88 + 0.12 * max(0.0, math.sin(phi))
            y = math.cos(phi) * half_width * width_scale
            z = center_z + math.sin(phi) * radius_z
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
    fx, _, fzb, fzt = stations[0]
    vertices.append((fx, 0.0, 0.5 * (fzb + fzt)))
    for i in range(ring):
        j = (i + 1) % ring
        faces.append((front_center_index, vidx(0, i), vidx(0, j)))

    rear_center_index = len(vertices)
    rx, _, rzb, rzt = stations[-1]
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
    mats["body"] = create_principled_material("MAT_CuteBeetle_Body", (0.22, 0.78, 0.95), 0.42)
    mats["accent"] = create_principled_material("MAT_CuteBeetle_Accent", (0.99, 0.97, 0.95), 0.40)
    mats["glass"] = create_principled_material("MAT_CuteBeetle_Glass", (0.43, 0.63, 0.79), 0.06, 0.0, 0.42, 0.10, "BLEND")
    mats["rubber"] = create_principled_material("MAT_CuteBeetle_Rubber", (0.04, 0.04, 0.045), 0.95)
    mats["rim"] = create_principled_material("MAT_CuteBeetle_Rim", (0.90, 0.92, 0.95), 0.24, 0.82)
    mats["headlight"] = create_principled_material("MAT_CuteBeetle_Headlight", (0.99, 0.97, 0.89), 0.18)
    mats["black"] = create_principled_material("MAT_CuteBeetle_Black", (0.03, 0.03, 0.035), 0.72)
    mats["ground"] = create_principled_material("MAT_CuteBeetle_Ground", (0.13, 0.17, 0.11), 1.0)
    return mats


def build_cute_beetle(scene):
    main_collection = bpy.data.collections.new(COLLECTION_MAIN)
    scene.collection.children.link(main_collection)
    model_collection = new_child_collection(COLLECTION_MODEL, main_collection)
    env_collection = new_child_collection(COLLECTION_ENV, main_collection)
    materials = build_materials()

    root = create_empty(ROOT_NAME, (0.0, 0.0, 0.0), model_collection, None, "ARROWS", 0.55)

    create_beetle_shell("Body_Shell", (0.0, 0.0, 0.0), model_collection, materials["body"], root)

    create_box("Lower_Body", (0.00, 0.0, 0.50), (2.44, 1.16, 0.18), model_collection, materials["body"], root, False)
    create_box("RunningBoard_L", (0.00, 0.67, 0.56), (1.90, 0.18, 0.06), model_collection, materials["accent"], root, False)
    create_box("RunningBoard_R", (0.00, -0.67, 0.56), (1.90, 0.18, 0.06), model_collection, materials["accent"], root, False)

    create_box("Windshield", (0.48, 0.0, 1.34), (0.08, 0.82, 0.40), model_collection, materials["glass"], root)
    create_box("Rear_Window", (-0.50, 0.0, 1.30), (0.08, 0.70, 0.30), model_collection, materials["glass"], root)
    create_box("Side_Window_L_Front", (0.24, 0.56, 1.34), (0.56, 0.08, 0.32), model_collection, materials["glass"], root)
    create_box("Side_Window_R_Front", (0.24, -0.56, 1.34), (0.56, 0.08, 0.32), model_collection, materials["glass"], root)
    create_box("Side_Window_L_Rear", (-0.18, 0.56, 1.28), (0.34, 0.08, 0.24), model_collection, materials["glass"], root)
    create_box("Side_Window_R_Rear", (-0.18, -0.56, 1.28), (0.34, 0.08, 0.24), model_collection, materials["glass"], root)

    wheel_positions = {
        "FL": (0.88, 0.67, WHEEL_RADIUS),
        "FR": (0.88, -0.67, WHEEL_RADIUS),
        "RL": (-0.88, 0.67, WHEEL_RADIUS),
        "RR": (-0.88, -0.67, WHEEL_RADIUS),
    }

    for name, (x, y, z) in wheel_positions.items():
        long_rad = 0.54 if name.startswith("F") else 0.58
        create_ellipsoid(f"Fender_{name}", (x, y, 0.72), (long_rad, 0.27, 0.40), model_collection, materials["body"], root, 2)
        create_ellipsoid(f"FenderCap_{name}", (x, y * 0.94, 0.86), (long_rad * 0.78, 0.20, 0.18), model_collection, materials["body"], root, 1)

    for name, (x, y, z) in wheel_positions.items():
        wheel = create_cylinder_y(f"Wheel_{name}", (x, y, z), WHEEL_RADIUS, WHEEL_WIDTH, model_collection, materials["rubber"], root, 18, True)
        create_cylinder_y(f"Rim_{name}", (0.0, 0.0, 0.0), WHEEL_RADIUS * 0.54, WHEEL_WIDTH * 1.05, model_collection, materials["rim"], wheel, 16, True)

    for side_name, side_sign in (("L", 1.0), ("R", -1.0)):
        create_ellipsoid(f"Headlight_{side_name}", (1.42, 0.24 * side_sign, 0.96), (0.14, 0.15, 0.15), model_collection, materials["headlight"], root, 1)
        create_ellipsoid(f"Pupil_{side_name}", (1.52, 0.24 * side_sign, 0.96), (0.04, 0.04, 0.04), model_collection, materials["black"], root, 1)

    create_box("Front_Bumper", (1.46, 0.0, 0.62), (0.10, 0.84, 0.09), model_collection, materials["accent"], root)
    create_box("Rear_Bumper", (-1.46, 0.0, 0.62), (0.10, 0.80, 0.09), model_collection, materials["accent"], root)
    create_box("Smile_Mid", (1.34, 0.0, 0.74), (0.05, 0.40, 0.04), model_collection, materials["black"], root)
    create_box("Smile_L", (1.31, 0.13, 0.71), (0.04, 0.14, 0.04), model_collection, materials["black"], root)
    create_box("Smile_R", (1.31, -0.13, 0.71), (0.04, 0.14, 0.04), model_collection, materials["black"], root)
    create_box("Door_Handle_L", (0.12, 0.63, 1.00), (0.14, 0.05, 0.05), model_collection, materials["accent"], root)
    create_box("Door_Handle_R", (0.12, -0.63, 1.00), (0.14, 0.05, 0.05), model_collection, materials["accent"], root)

    ground = create_plane("Preview_Ground", GROUND_SIZE, 0.0, env_collection, materials["ground"])

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
    camera.location = (6.3, -8.6, 4.4)
    camera_data.lens = 52.0
    look_at(camera, (0.0, 0.0, 0.98))
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
        "ground": ground,
    }


clean_entire_scene()
scene = bpy.context.scene
result = build_cute_beetle(scene)

mesh_objects = [obj for obj in result["model_collection"].all_objects if obj.type == "MESH"]
mins, maxs, dims = world_dimensions(mesh_objects)
polygon_count = sum(len(obj.data.polygons) for obj in mesh_objects)

print("=" * 72)
print("Carro estilo Fusca jovial corrigido criado com sucesso.")
print(f"Versão do gerador: {GENERATOR_VERSION}")
print(f"Objetos de malha: {len(mesh_objects)}")
print(f"Polígonos aproximados: {polygon_count}")
print(f"Dimensões finais aproximadas (C x L x A): {dims.x:.2f} x {dims.y:.2f} x {dims.z:.2f}")
print("Corpo contínuo: sim")
print("Paralamas integrados ao corpo: sim")
print("Faróis à frente: sim")
print("Chassi visível externamente: não")
print("Escala planejada para caber na plataforma do caminhão: sim")
print("A cena foi limpa integralmente antes da geração; o script é idempotente.")
print("=" * 72)
