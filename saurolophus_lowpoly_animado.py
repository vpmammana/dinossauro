"""
Saurolophus low-poly colorido e animado para Blender
====================================================

O script cria:
- um Saurolophus estilizado de baixa resolução;
- materiais procedurais coloridos, sem arquivos externos de textura;
- controles de animação feitos com empties;
- um ciclo simples de caminhada de 24 quadros;
- câmera, luzes e chão para pré-visualização.

Compatibilidade pretendida: Blender 3.6+ e Blender 4.x.

Como usar:
1. Abra o Blender.
2. Vá a Scripting > New.
3. Cole este arquivo no editor de texto.
4. Clique em Run Script.
5. Pressione Espaço na Timeline para ver a animação.

Observação:
O script apaga somente a coleção chamada "Saurolophus_Python" caso ela
já exista. Ele não apaga os outros objetos da cena.
"""

import bpy
import math
from mathutils import Vector

COLLECTION_NAME = "Saurolophus_Python"
FPS = 24
FRAME_START = 1
FRAME_END = 24


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def remove_collection_if_exists(name):
    collection = bpy.data.collections.get(name)
    if collection is None:
        return

    for obj in list(collection.all_objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    bpy.data.collections.remove(collection)


def move_to_collection(obj, collection):
    if collection not in obj.users_collection:
        collection.objects.link(obj)

    for old_collection in list(obj.users_collection):
        if old_collection != collection:
            old_collection.objects.unlink(obj)


def parent_keep_world(child, parent):
    world_matrix = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = world_matrix


def set_object_smooth(obj):
    if obj.type != "MESH":
        return

    for polygon in obj.data.polygons:
        polygon.use_smooth = True


def look_at(obj, target, track_axis="-Z", up_axis="Y"):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat(track_axis, up_axis).to_euler()


# ---------------------------------------------------------------------------
# Materiais
# ---------------------------------------------------------------------------

def make_plain_material(name, color, roughness=0.75, metallic=0.0):
    old = bpy.data.materials.get(name)
    if old:
        bpy.data.materials.remove(old)

    material = bpy.data.materials.new(name)
    material.use_nodes = True

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")

    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic

    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def make_skin_material(name="MAT_Skin"):
    old = bpy.data.materials.get(name)
    if old:
        bpy.data.materials.remove(old)

    material = bpy.data.materials.new(name)
    material.use_nodes = True

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    texcoord = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    ramp = nodes.new("ShaderNodeValToRGB")
    bump = nodes.new("ShaderNodeBump")

    noise.inputs["Scale"].default_value = 4.2
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.65

    # Verde-oliva escuro, verde médio e ocre suave.
    color_ramp = ramp.color_ramp
    color_ramp.elements[0].position = 0.24
    color_ramp.elements[0].color = (0.035, 0.085, 0.020, 1.0)

    middle = color_ramp.elements.new(0.53)
    middle.color = (0.15, 0.31, 0.065, 1.0)

    color_ramp.elements[-1].position = 0.78
    color_ramp.elements[-1].color = (0.36, 0.30, 0.09, 1.0)

    shader.inputs["Roughness"].default_value = 0.82
    bump.inputs["Strength"].default_value = 0.16
    bump.inputs["Distance"].default_value = 0.08

    links.new(texcoord.outputs["Generated"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    return material


# ---------------------------------------------------------------------------
# Criação de objetos
# ---------------------------------------------------------------------------

def make_control(name, location, collection, parent=None, size=0.28):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "CIRCLE"
    obj.empty_display_size = size
    obj.location = location
    collection.objects.link(obj)

    if parent:
        parent_keep_world(obj, parent)

    return obj


def make_ellipsoid(
    name,
    location,
    scale,
    material,
    collection,
    parent=None,
    subdivisions=2,
):
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=subdivisions,
        radius=1.0,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale

    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    set_object_smooth(obj)
    obj.data.materials.append(material)
    move_to_collection(obj, collection)

    if parent:
        parent_keep_world(obj, parent)

    return obj


def make_segment(
    name,
    start,
    end,
    radius_start,
    radius_end,
    material,
    collection,
    parent=None,
    vertices=8,
):
    start = Vector(start)
    end = Vector(end)
    vector = end - start
    length = vector.length

    if length <= 0.0001:
        raise ValueError(f"Segmento sem comprimento: {name}")

    midpoint = (start + end) * 0.5

    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius_start,
        radius2=radius_end,
        depth=length,
        location=midpoint,
    )

    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = vector.to_track_quat("Z", "Y")
    obj.rotation_mode = "XYZ"

    set_object_smooth(obj)
    obj.data.materials.append(material)
    move_to_collection(obj, collection)

    if parent:
        parent_keep_world(obj, parent)

    return obj


def make_joint(name, location, radius, material, collection, parent):
    return make_ellipsoid(
        name=name,
        location=location,
        scale=(radius, radius, radius),
        material=material,
        collection=collection,
        parent=parent,
        subdivisions=1,
    )


def make_plane(name, size, location, material, collection):
    bpy.ops.mesh.primitive_plane_add(size=size, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    move_to_collection(obj, collection)
    return obj


# ---------------------------------------------------------------------------
# Animação
# ---------------------------------------------------------------------------

def key_rotation(obj, frame, x=0.0, y=0.0, z=0.0):
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = (
        math.radians(x),
        math.radians(y),
        math.radians(z),
    )
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def key_location(obj, frame, location):
    obj.location = location
    obj.keyframe_insert(data_path="location", frame=frame)


def set_action_interpolation(obj):
    animation_data = obj.animation_data
    if not animation_data or not animation_data.action:
        return

    action = animation_data.action

    # Blender 3.x/4.x mantém acesso às F-curves por esta propriedade.
    fcurves = getattr(action, "fcurves", None)
    if fcurves is None:
        return

    for fcurve in fcurves:
        for point in fcurve.keyframe_points:
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"


# ---------------------------------------------------------------------------
# Construção da cena
# ---------------------------------------------------------------------------

remove_collection_if_exists(COLLECTION_NAME)

collection = bpy.data.collections.new(COLLECTION_NAME)
bpy.context.scene.collection.children.link(collection)

skin = make_skin_material()
belly = make_plain_material(
    "MAT_Belly",
    color=(0.48, 0.39, 0.16),
    roughness=0.88,
)
crest_mat = make_plain_material(
    "MAT_Crest",
    color=(0.58, 0.12, 0.035),
    roughness=0.72,
)
eye_mat = make_plain_material(
    "MAT_Eyes",
    color=(0.004, 0.006, 0.004),
    roughness=0.18,
)
ground_mat = make_plain_material(
    "MAT_Ground",
    color=(0.12, 0.16, 0.085),
    roughness=1.0,
)

# Controle principal.
root = make_control(
    "CTRL_ROOT",
    location=(0.0, 0.0, 2.0),
    collection=collection,
    size=0.58,
)

# Corpo.
make_ellipsoid(
    "Body",
    location=(0.0, 0.0, 2.0),
    scale=(1.72, 0.70, 0.72),
    material=skin,
    collection=collection,
    parent=root,
)
make_ellipsoid(
    "Chest",
    location=(1.18, 0.0, 2.13),
    scale=(0.98, 0.61, 0.64),
    material=skin,
    collection=collection,
    parent=root,
)
make_ellipsoid(
    "Belly",
    location=(0.15, 0.0, 1.63),
    scale=(1.45, 0.64, 0.28),
    material=belly,
    collection=collection,
    parent=root,
)

# Pescoço e cabeça.
neck_ctrl = make_control(
    "CTRL_NECK",
    location=(1.65, 0.0, 2.22),
    collection=collection,
    parent=root,
    size=0.30,
)
make_segment(
    "Neck",
    start=(1.55, 0.0, 2.18),
    end=(2.48, 0.0, 2.64),
    radius_start=0.48,
    radius_end=0.31,
    material=skin,
    collection=collection,
    parent=neck_ctrl,
)

head_ctrl = make_control(
    "CTRL_HEAD",
    location=(2.45, 0.0, 2.63),
    collection=collection,
    parent=neck_ctrl,
    size=0.27,
)
make_ellipsoid(
    "Head",
    location=(2.82, 0.0, 2.74),
    scale=(0.65, 0.39, 0.43),
    material=skin,
    collection=collection,
    parent=head_ctrl,
)
make_ellipsoid(
    "Snout",
    location=(3.37, 0.0, 2.66),
    scale=(0.56, 0.31, 0.27),
    material=belly,
    collection=collection,
    parent=head_ctrl,
)
make_segment(
    "Crest",
    start=(2.73, 0.0, 3.02),
    end=(2.02, 0.0, 3.49),
    radius_start=0.18,
    radius_end=0.035,
    material=crest_mat,
    collection=collection,
    parent=head_ctrl,
    vertices=8,
)

# Olhos.
for side, y in (("L", 0.355), ("R", -0.355)):
    make_ellipsoid(
        f"Eye.{side}",
        location=(3.03, y, 2.84),
        scale=(0.085, 0.055, 0.085),
        material=eye_mat,
        collection=collection,
        parent=head_ctrl,
        subdivisions=2,
    )

# Cauda articulada.
tail_points = [
    (-1.42, 0.0, 2.00),
    (-2.52, 0.0, 1.91),
    (-3.62, 0.0, 1.76),
    (-4.58, 0.0, 1.56),
    (-5.38, 0.0, 1.35),
]
tail_radii = [0.50, 0.37, 0.27, 0.16, 0.045]

tail_controls = []
parent_ctrl = root

for index in range(len(tail_points) - 1):
    ctrl = make_control(
        f"CTRL_TAIL_{index + 1:02d}",
        location=tail_points[index],
        collection=collection,
        parent=parent_ctrl,
        size=max(0.13, 0.25 - index * 0.035),
    )
    tail_controls.append(ctrl)

    make_segment(
        f"Tail_{index + 1:02d}",
        start=tail_points[index],
        end=tail_points[index + 1],
        radius_start=tail_radii[index],
        radius_end=tail_radii[index + 1],
        material=skin,
        collection=collection,
        parent=ctrl,
    )

    make_joint(
        f"TailJoint_{index + 1:02d}",
        location=tail_points[index],
        radius=tail_radii[index] * 0.92,
        material=skin,
        collection=collection,
        parent=ctrl,
    )

    parent_ctrl = ctrl

# Pernas traseiras.
leg_controls = {}

for side, y_sign in (("L", 1.0), ("R", -1.0)):
    hip = (0.62, 0.53 * y_sign, 1.78)
    knee = (0.34, 0.62 * y_sign, 0.93)
    ankle = (0.72, 0.64 * y_sign, 0.18)
    toe = (1.48, 0.64 * y_sign, 0.14)

    hip_ctrl = make_control(
        f"CTRL_HIP.{side}",
        location=hip,
        collection=collection,
        parent=root,
        size=0.25,
    )
    knee_ctrl = make_control(
        f"CTRL_KNEE.{side}",
        location=knee,
        collection=collection,
        parent=hip_ctrl,
        size=0.20,
    )
    ankle_ctrl = make_control(
        f"CTRL_ANKLE.{side}",
        location=ankle,
        collection=collection,
        parent=knee_ctrl,
        size=0.17,
    )

    leg_controls[side] = (hip_ctrl, knee_ctrl, ankle_ctrl)

    make_segment(
        f"Thigh.{side}",
        hip,
        knee,
        0.31,
        0.22,
        skin,
        collection,
        hip_ctrl,
    )
    make_segment(
        f"Shin.{side}",
        knee,
        ankle,
        0.22,
        0.15,
        skin,
        collection,
        knee_ctrl,
    )
    make_segment(
        f"Foot.{side}",
        ankle,
        toe,
        0.16,
        0.075,
        belly,
        collection,
        ankle_ctrl,
    )

    make_joint(
        f"HipJoint.{side}",
        hip,
        0.28,
        skin,
        collection,
        hip_ctrl,
    )
    make_joint(
        f"KneeJoint.{side}",
        knee,
        0.20,
        skin,
        collection,
        knee_ctrl,
    )
    make_joint(
        f"AnkleJoint.{side}",
        ankle,
        0.14,
        belly,
        collection,
        ankle_ctrl,
    )

    # Três dedos simples.
    for toe_index, y_offset in enumerate((-0.11, 0.0, 0.11), start=1):
        toe_start = (1.15, (0.64 + y_offset) * y_sign, 0.13)
        toe_end = (1.65, (0.64 + y_offset * 1.25) * y_sign, 0.11)
        make_segment(
            f"Toe_{toe_index}.{side}",
            toe_start,
            toe_end,
            0.055,
            0.018,
            belly,
            collection,
            ankle_ctrl,
            vertices=6,
        )

# Braços dianteiros.
arm_controls = {}

for side, y_sign in (("L", 1.0), ("R", -1.0)):
    shoulder = (1.38, 0.55 * y_sign, 2.20)
    elbow = (1.38, 0.62 * y_sign, 1.52)
    wrist = (1.73, 0.64 * y_sign, 1.03)
    hand = (2.15, 0.64 * y_sign, 0.98)

    shoulder_ctrl = make_control(
        f"CTRL_SHOULDER.{side}",
        location=shoulder,
        collection=collection,
        parent=root,
        size=0.20,
    )
    elbow_ctrl = make_control(
        f"CTRL_ELBOW.{side}",
        location=elbow,
        collection=collection,
        parent=shoulder_ctrl,
        size=0.16,
    )
    wrist_ctrl = make_control(
        f"CTRL_WRIST.{side}",
        location=wrist,
        collection=collection,
        parent=elbow_ctrl,
        size=0.13,
    )

    arm_controls[side] = (shoulder_ctrl, elbow_ctrl, wrist_ctrl)

    make_segment(
        f"UpperArm.{side}",
        shoulder,
        elbow,
        0.17,
        0.12,
        skin,
        collection,
        shoulder_ctrl,
        vertices=7,
    )
    make_segment(
        f"Forearm.{side}",
        elbow,
        wrist,
        0.12,
        0.075,
        skin,
        collection,
        elbow_ctrl,
        vertices=7,
    )
    make_segment(
        f"Hand.{side}",
        wrist,
        hand,
        0.085,
        0.035,
        belly,
        collection,
        wrist_ctrl,
        vertices=6,
    )

    make_joint(
        f"ShoulderJoint.{side}",
        shoulder,
        0.16,
        skin,
        collection,
        shoulder_ctrl,
    )
    make_joint(
        f"ElbowJoint.{side}",
        elbow,
        0.11,
        skin,
        collection,
        elbow_ctrl,
    )

# Chão.
make_plane(
    "Preview_Ground",
    size=30.0,
    location=(0.0, 0.0, 0.0),
    material=ground_mat,
    collection=collection,
)

# Luz principal.
light_data = bpy.data.lights.new("Saurolophus_Key_Light", type="AREA")
light_data.energy = 1100.0
light_data.shape = "DISK"
light_data.size = 6.0
light = bpy.data.objects.new("Saurolophus_Key_Light", light_data)
light.location = (3.5, -4.5, 8.0)
collection.objects.link(light)
look_at(light, (0.0, 0.0, 1.6))

# Luz de preenchimento.
fill_data = bpy.data.lights.new("Saurolophus_Fill_Light", type="AREA")
fill_data.energy = 550.0
fill_data.size = 5.0
fill = bpy.data.objects.new("Saurolophus_Fill_Light", fill_data)
fill.location = (-4.0, 5.0, 5.5)
collection.objects.link(fill)
look_at(fill, (-0.5, 0.0, 1.7))

# Câmera.
camera_data = bpy.data.cameras.new("Saurolophus_Camera")
camera = bpy.data.objects.new("Saurolophus_Camera", camera_data)
camera.location = (8.8, -13.5, 6.4)
camera_data.lens = 52.0
collection.objects.link(camera)
look_at(camera, (-0.7, 0.0, 1.7))
bpy.context.scene.camera = camera

# ---------------------------------------------------------------------------
# Ciclo de caminhada
# ---------------------------------------------------------------------------

root_base = root.location.copy()

walk_poses = {
    1: {
        "root_z": 0.00,
        "hip_l": -18,
        "hip_r": 18,
        "knee_l": 10,
        "knee_r": 30,
        "ankle_l": 8,
        "ankle_r": -8,
        "shoulder_l": 12,
        "shoulder_r": -12,
        "elbow_l": -10,
        "elbow_r": -22,
        "tail": 7,
        "neck": 2.5,
        "head": -2.0,
    },
    7: {
        "root_z": 0.07,
        "hip_l": 0,
        "hip_r": 0,
        "knee_l": 25,
        "knee_r": 12,
        "ankle_l": -5,
        "ankle_r": 5,
        "shoulder_l": 0,
        "shoulder_r": 0,
        "elbow_l": -18,
        "elbow_r": -14,
        "tail": 0,
        "neck": 0,
        "head": 1.0,
    },
    13: {
        "root_z": 0.00,
        "hip_l": 18,
        "hip_r": -18,
        "knee_l": 30,
        "knee_r": 10,
        "ankle_l": -8,
        "ankle_r": 8,
        "shoulder_l": -12,
        "shoulder_r": 12,
        "elbow_l": -22,
        "elbow_r": -10,
        "tail": -7,
        "neck": -2.5,
        "head": 2.0,
    },
    19: {
        "root_z": 0.07,
        "hip_l": 0,
        "hip_r": 0,
        "knee_l": 12,
        "knee_r": 25,
        "ankle_l": 5,
        "ankle_r": -5,
        "shoulder_l": 0,
        "shoulder_r": 0,
        "elbow_l": -14,
        "elbow_r": -18,
        "tail": 0,
        "neck": 0,
        "head": -1.0,
    },
    25: {
        "root_z": 0.00,
        "hip_l": -18,
        "hip_r": 18,
        "knee_l": 10,
        "knee_r": 30,
        "ankle_l": 8,
        "ankle_r": -8,
        "shoulder_l": 12,
        "shoulder_r": -12,
        "elbow_l": -10,
        "elbow_r": -22,
        "tail": 7,
        "neck": 2.5,
        "head": -2.0,
    },
}

animated_controls = [root, neck_ctrl, head_ctrl]
animated_controls.extend(tail_controls)
for controls in leg_controls.values():
    animated_controls.extend(controls)
for controls in arm_controls.values():
    animated_controls.extend(controls)

for frame, pose in walk_poses.items():
    key_location(
        root,
        frame,
        (root_base.x, root_base.y, root_base.z + pose["root_z"]),
    )

    hip_l, knee_l, ankle_l = leg_controls["L"]
    hip_r, knee_r, ankle_r = leg_controls["R"]

    key_rotation(hip_l, frame, y=pose["hip_l"])
    key_rotation(hip_r, frame, y=pose["hip_r"])
    key_rotation(knee_l, frame, y=pose["knee_l"])
    key_rotation(knee_r, frame, y=pose["knee_r"])
    key_rotation(ankle_l, frame, y=pose["ankle_l"])
    key_rotation(ankle_r, frame, y=pose["ankle_r"])

    shoulder_l, elbow_l, wrist_l = arm_controls["L"]
    shoulder_r, elbow_r, wrist_r = arm_controls["R"]

    key_rotation(shoulder_l, frame, y=pose["shoulder_l"])
    key_rotation(shoulder_r, frame, y=pose["shoulder_r"])
    key_rotation(elbow_l, frame, y=pose["elbow_l"])
    key_rotation(elbow_r, frame, y=pose["elbow_r"])
    key_rotation(wrist_l, frame, y=-4)
    key_rotation(wrist_r, frame, y=-4)

    key_rotation(tail_controls[0], frame, z=pose["tail"])
    key_rotation(tail_controls[1], frame, z=pose["tail"] * 1.25)
    key_rotation(tail_controls[2], frame, z=pose["tail"] * 1.45)
    key_rotation(tail_controls[3], frame, z=pose["tail"] * 1.65)

    key_rotation(neck_ctrl, frame, y=pose["neck"])
    key_rotation(head_ctrl, frame, y=pose["head"])

for obj in animated_controls:
    set_action_interpolation(obj)

# ---------------------------------------------------------------------------
# Configuração de render e finalização
# ---------------------------------------------------------------------------

scene = bpy.context.scene
scene.frame_start = FRAME_START
scene.frame_end = FRAME_END
scene.render.fps = FPS
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100

# Seleciona Eevee quando estiver disponível.
engine_items = {
    item.identifier
    for item in scene.bl_rna.properties["render"].fixed_type.properties[
        "engine"
    ].enum_items
} if False else set()

try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except Exception:
        pass

scene.world.color = (0.035, 0.045, 0.055)
scene.frame_set(FRAME_START)

mesh_objects = [
    obj for obj in collection.all_objects
    if obj.type == "MESH" and obj.name != "Preview_Ground"
]
polygon_count = sum(len(obj.data.polygons) for obj in mesh_objects)

activate(root)

print(
    "Saurolophus criado com sucesso. "
    f"Objetos de malha: {len(mesh_objects)} | "
    f"Polígonos aproximados: {polygon_count} | "
    f"Animação: quadros {FRAME_START}-{FRAME_END} a {FPS} fps."
)
