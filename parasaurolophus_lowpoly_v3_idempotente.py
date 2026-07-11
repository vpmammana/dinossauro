"""
Parasaurolophus low-poly colorido e animado — gerador idempotente
=================================================================

ATENÇÃO:
Este script APAGA TODOS OS OBJETOS da cena atual antes de reconstruir
o personagem. Ele também remove coleções, materiais, malhas, câmeras,
luzes e ações sem uso da cena anterior. O bloco de texto que contém
este próprio script não é apagado.

Objetivos desta versão:
- execução idempotente: rodar novamente produz a mesma cena limpa;
- cauda, pescoço, pernas, pés e dedos construídos em coordenadas locais;
- nenhuma peça depende de "parent keep transform";
- tubos são modelados diretamente no eixo correto, sem girar cones 90°;
- crista longa orientada para trás, característica de Parasaurolophus;
- pele procedural colorida, sem arquivos externos de textura;
- ciclo leve de caminhada no lugar;
- ajuste automático da altura global para manter os pés acima do chão;
- validações estruturais antes e depois da animação.

Compatibilidade pretendida: Blender 3.6 LTS e Blender 4.x.
"""

import bpy
import bmesh
import math
from mathutils import Vector

GENERATOR_VERSION = "3.0-idempotente"
FPS = 24
FRAME_START = 1
FRAME_END = 24
LOOP_KEY = 25
GROUND_CLEARANCE = 0.02


# ---------------------------------------------------------------------------
# LIMPEZA TOTAL DA CENA
# ---------------------------------------------------------------------------

def remove_all(datablocks):
    """Remove todos os datablocks de uma coleção do bpy.data."""
    for datablock in list(datablocks):
        try:
            datablocks.remove(datablock, do_unlink=True)
        except TypeError:
            datablocks.remove(datablock)


def clean_entire_scene():
    """
    Limpa toda a área de desenho para tornar a execução idempotente.

    Não remove bpy.data.texts, porque o script pode estar sendo executado
    diretamente no Text Editor do Blender.
    """
    scene = bpy.context.scene

    active = bpy.context.object
    if active is not None and active.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass

    # A remoção direta dos datablocks não depende de o Text Editor ou
    # a Viewport 3D ser a área ativa, ao contrário de object.delete().
    scene.camera = None
    scene.world = None
    remove_all(bpy.data.objects)

    # Remove coleções comuns; a Scene Collection raiz não aparece aqui
    # como uma coleção removível normal.
    remove_all(bpy.data.collections)

    # Remove dados da cena anterior para evitar nomes .001 e resíduos.
    remove_all(bpy.data.meshes)
    remove_all(bpy.data.curves)
    remove_all(bpy.data.armatures)
    remove_all(bpy.data.cameras)
    remove_all(bpy.data.lights)
    remove_all(bpy.data.materials)
    remove_all(bpy.data.actions)
    remove_all(bpy.data.worlds)

    # Outros tipos que também podem ocupar a cena em versões recentes.
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


# ---------------------------------------------------------------------------
# COLEÇÕES E OBJETOS
# ---------------------------------------------------------------------------

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

    # Coordenadas explicitamente LOCAIS ao pai.
    obj.location = Vector(local_location)
    obj.rotation_euler = (0.0, 0.0, 0.0)
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


def create_ellipsoid(name, local_center, radii, collection, material,
                     parent=None, subdivisions=2):
    """
    Cria uma icosfera já deformada na própria malha.
    O objeto permanece sem escala e sem rotação herdada problemática.
    """
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


def segment_basis(start, end):
    axis = Vector(end) - Vector(start)
    length = axis.length
    if length <= 1.0e-7:
        raise ValueError("Tentativa de criar um segmento de comprimento zero.")

    direction = axis.normalized()
    reference = Vector((0.0, 0.0, 1.0))

    if abs(direction.dot(reference)) > 0.92:
        reference = Vector((0.0, 1.0, 0.0))

    side = direction.cross(reference).normalized()
    normal = direction.cross(side).normalized()
    return direction, side, normal


def create_tapered_tube(
    name,
    local_start,
    local_end,
    radius_start,
    radius_end,
    collection,
    material,
    parent=None,
    sides=8,
    overlap=0.0,
):
    """
    Cria o tubo diretamente entre start e end em coordenadas locais.

    Não cria um cone no eixo Z para depois rotacioná-lo. Assim, Tail_N,
    Neck_N, membros, pés e dedos já nascem no eixo correto.
    """
    start = Vector(local_start)
    end = Vector(local_end)
    direction, side, normal = segment_basis(start, end)

    start = start - direction * overlap
    end = end + direction * overlap

    vertices = []
    faces = []

    for ring_center, radius in ((start, radius_start), (end, radius_end)):
        for index in range(sides):
            angle = 2.0 * math.pi * index / sides
            offset = (
                side * (math.cos(angle) * radius)
                + normal * (math.sin(angle) * radius)
            )
            vertices.append(ring_center + offset)

    for index in range(sides):
        next_index = (index + 1) % sides
        faces.append(
            (
                index,
                next_index,
                sides + next_index,
                sides + index,
            )
        )

    faces.append(tuple(reversed(range(sides))))
    faces.append(tuple(sides + index for index in range(sides)))

    return create_mesh_object(
        name=name,
        vertices=vertices,
        faces=faces,
        collection=collection,
        material=material,
        parent=parent,
        smooth=True,
    )


def create_poly_tube(
    name,
    local_points,
    radii,
    collection,
    material,
    parent=None,
    sides=10,
):
    """Cria um tubo curvo único, usado para a crista."""
    points = [Vector(point) for point in local_points]

    if len(points) < 2 or len(points) != len(radii):
        raise ValueError("Pontos e raios incompatíveis em create_poly_tube.")

    vertices = []
    faces = []

    for point_index, point in enumerate(points):
        if point_index == 0:
            tangent = (points[1] - points[0]).normalized()
        elif point_index == len(points) - 1:
            tangent = (points[-1] - points[-2]).normalized()
        else:
            tangent = (points[point_index + 1] - points[point_index - 1])
            tangent.normalize()

        # A crista está no plano XZ. Y é uma referência lateral estável.
        side = Vector((0.0, 1.0, 0.0))
        normal = tangent.cross(side)

        if normal.length <= 1.0e-7:
            _, side, normal = segment_basis(
                point,
                point + tangent,
            )
        else:
            normal.normalize()

        radius = radii[point_index]
        for side_index in range(sides):
            angle = 2.0 * math.pi * side_index / sides
            offset = (
                side * (math.cos(angle) * radius)
                + normal * (math.sin(angle) * radius)
            )
            vertices.append(point + offset)

    ring_count = len(points)

    for ring_index in range(ring_count - 1):
        ring_a = ring_index * sides
        ring_b = (ring_index + 1) * sides

        for side_index in range(sides):
            next_side = (side_index + 1) % sides
            faces.append(
                (
                    ring_a + side_index,
                    ring_a + next_side,
                    ring_b + next_side,
                    ring_b + side_index,
                )
            )

    faces.append(tuple(reversed(range(sides))))
    last_ring = (ring_count - 1) * sides
    faces.append(tuple(last_ring + index for index in range(sides)))

    return create_mesh_object(
        name=name,
        vertices=vertices,
        faces=faces,
        collection=collection,
        material=material,
        parent=parent,
        smooth=True,
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


# ---------------------------------------------------------------------------
# MATERIAIS
# ---------------------------------------------------------------------------

def set_node_input(node, name, value):
    socket = node.inputs.get(name)
    if socket is not None:
        socket.default_value = value


def create_plain_material(name, color, roughness=0.75, metallic=0.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (*color, 1.0)

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")

    set_node_input(shader, "Base Color", (*color, 1.0))
    set_node_input(shader, "Roughness", roughness)
    set_node_input(shader, "Metallic", metallic)

    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def create_skin_material():
    material = bpy.data.materials.new("MAT_Skin_Procedural")
    material.use_nodes = True
    material.diffuse_color = (0.16, 0.34, 0.07, 1.0)

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    texcoord = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    ramp = nodes.new("ShaderNodeValToRGB")
    bump = nodes.new("ShaderNodeBump")

    set_node_input(noise, "Scale", 3.8)
    set_node_input(noise, "Detail", 3.0)
    set_node_input(noise, "Roughness", 0.62)

    color_ramp = ramp.color_ramp
    color_ramp.elements[0].position = 0.22
    color_ramp.elements[0].color = (0.025, 0.075, 0.018, 1.0)

    middle = color_ramp.elements.new(0.52)
    middle.color = (0.12, 0.31, 0.045, 1.0)

    color_ramp.elements[-1].position = 0.80
    color_ramp.elements[-1].color = (0.42, 0.31, 0.08, 1.0)

    set_node_input(shader, "Roughness", 0.82)
    set_node_input(bump, "Strength", 0.12)
    set_node_input(bump, "Distance", 0.055)

    links.new(texcoord.outputs["Generated"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    return material


# ---------------------------------------------------------------------------
# TRANSFORMADAS, VALIDAÇÃO E ANIMAÇÃO
# ---------------------------------------------------------------------------

def world_vertices(obj):
    matrix = obj.matrix_world
    return [matrix @ vertex.co for vertex in obj.data.vertices]


def world_center(obj):
    vertices = world_vertices(obj)
    if not vertices:
        return obj.matrix_world.translation.copy()

    total = Vector((0.0, 0.0, 0.0))
    for vertex in vertices:
        total += vertex
    return total / len(vertices)


def world_min_z(objects):
    minimum = float("inf")

    for obj in objects:
        for vertex in world_vertices(obj):
            minimum = min(minimum, vertex.z)

    return minimum


def world_max_z(obj):
    return max(vertex.z for vertex in world_vertices(obj))


def validate_rest_pose(tail_objects, neck_objects, toe_objects,
                       crest_object, head_object):
    bpy.context.view_layer.update()

    tail_centers = [world_center(obj) for obj in tail_objects]
    invalid_tail = [
        (obj.name, center.x, center.z)
        for obj, center in zip(tail_objects, tail_centers)
        if center.x > -1.0 or center.z < 1.15
    ]
    if invalid_tail:
        raise RuntimeError(
            "Validação da cauda falhou. Segmentos fora da região esperada: "
            f"{invalid_tail}"
        )

    neck_centers = [world_center(obj) for obj in neck_objects]
    invalid_neck = [
        (obj.name, center.x, center.z)
        for obj, center in zip(neck_objects, neck_centers)
        if center.x < 1.15 or center.z < 2.15
    ]
    if invalid_neck:
        raise RuntimeError(
            "Validação do pescoço falhou. Segmentos fora da região esperada: "
            f"{invalid_neck}"
        )

    invalid_toes = []
    for obj in toe_objects:
        center = world_center(obj)
        if center.z < 0.0 or center.z > 0.65:
            invalid_toes.append((obj.name, center.x, center.y, center.z))

    if invalid_toes:
        raise RuntimeError(
            "Validação dos dedos falhou. Peças fora da região dos pés: "
            f"{invalid_toes}"
        )

    crest_center = world_center(crest_object)
    head_center = world_center(head_object)

    if crest_center.x >= head_center.x:
        raise RuntimeError(
            "A crista não está apontando para trás no eixo -X."
        )

    if world_max_z(crest_object) <= world_max_z(head_object):
        raise RuntimeError(
            "A crista não está acima do crânio como esperado."
        )


def key_rotation(obj, frame, x=0.0, y=0.0, z=0.0):
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = (
        math.radians(x),
        math.radians(y),
        math.radians(z),
    )
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def key_location(obj, frame, location):
    obj.location = Vector(location)
    obj.keyframe_insert(data_path="location", frame=frame)


def clamp_interpolation(obj):
    animation_data = obj.animation_data
    if animation_data is None or animation_data.action is None:
        return

    fcurves = getattr(animation_data.action, "fcurves", None)
    if fcurves is None:
        return

    for fcurve in fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = "BEZIER"
            keyframe.handle_left_type = "AUTO_CLAMPED"
            keyframe.handle_right_type = "AUTO_CLAMPED"


def set_cycles_if_available(obj):
    animation_data = obj.animation_data
    if animation_data is None or animation_data.action is None:
        return

    fcurves = getattr(animation_data.action, "fcurves", None)
    if fcurves is None:
        return

    for fcurve in fcurves:
        if not any(modifier.type == "CYCLES" for modifier in fcurve.modifiers):
            fcurve.modifiers.new(type="CYCLES")


def look_at(obj, target, track_axis="-Z", up_axis="Y"):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat(
        track_axis,
        up_axis,
    ).to_euler()


# ---------------------------------------------------------------------------
# CONSTRUÇÃO
# ---------------------------------------------------------------------------

clean_entire_scene()
scene = bpy.context.scene

main_collection = bpy.data.collections.new("Parasaurolophus_Generated")
scene.collection.children.link(main_collection)

model_collection = new_child_collection(
    "MODEL_Meshes",
    main_collection,
)
control_collection = new_child_collection(
    "RIG_Controls",
    main_collection,
)
environment_collection = new_child_collection(
    "ENVIRONMENT",
    main_collection,
)

skin_material = create_skin_material()
belly_material = create_plain_material(
    "MAT_Belly",
    color=(0.52, 0.40, 0.16),
    roughness=0.88,
)
crest_material = create_plain_material(
    "MAT_Crest",
    color=(0.62, 0.13, 0.035),
    roughness=0.72,
)
claw_material = create_plain_material(
    "MAT_Claws",
    color=(0.075, 0.055, 0.032),
    roughness=0.66,
)
eye_material = create_plain_material(
    "MAT_Eyes",
    color=(0.003, 0.006, 0.003),
    roughness=0.18,
)
nostril_material = create_plain_material(
    "MAT_Nostrils",
    color=(0.025, 0.015, 0.012),
    roughness=0.58,
)
ground_material = create_plain_material(
    "MAT_Ground",
    color=(0.115, 0.155, 0.075),
    roughness=1.0,
)

master = create_empty(
    "CTRL_MASTER",
    local_location=(0.0, 0.0, 0.0),
    collection=control_collection,
    display_type="ARROWS",
    display_size=0.80,
)
master["generator"] = "Parasaurolophus low-poly"
master["generator_version"] = GENERATOR_VERSION
master["warning"] = "Executar novamente apaga e reconstrói toda a cena."

root = create_empty(
    "CTRL_ROOT",
    local_location=(0.0, 0.0, 0.0),
    collection=control_collection,
    parent=master,
    display_type="CIRCLE",
    display_size=0.58,
)

# Corpo contínuo por interseção de volumes.
pelvis = create_ellipsoid(
    "Pelvis",
    local_center=(-0.62, 0.0, 2.20),
    radii=(1.05, 0.73, 0.70),
    collection=model_collection,
    material=skin_material,
    parent=root,
)
torso = create_ellipsoid(
    "Torso",
    local_center=(0.10, 0.0, 2.27),
    radii=(1.42, 0.68, 0.72),
    collection=model_collection,
    material=skin_material,
    parent=root,
)
chest = create_ellipsoid(
    "Chest",
    local_center=(0.98, 0.0, 2.37),
    radii=(0.88, 0.62, 0.65),
    collection=model_collection,
    material=skin_material,
    parent=root,
)
belly = create_ellipsoid(
    "Belly",
    local_center=(0.14, 0.0, 1.82),
    radii=(1.36, 0.61, 0.31),
    collection=model_collection,
    material=belly_material,
    parent=root,
)

# ---------------------------------------------------------------------------
# CAUDA: todos os segmentos são locais aos próprios pivôs.
# ---------------------------------------------------------------------------

tail_offsets = [
    Vector((-1.15, 0.0, -0.08)),
    Vector((-1.05, 0.0, -0.11)),
    Vector((-0.95, 0.0, -0.13)),
    Vector((-0.82, 0.0, -0.14)),
    Vector((-0.68, 0.0, -0.13)),
]
tail_radii = [
    (0.47, 0.36),
    (0.36, 0.27),
    (0.27, 0.19),
    (0.19, 0.11),
    (0.11, 0.035),
]

tail_controls = []
tail_objects = []

current_tail_control = create_empty(
    "CTRL_TAIL_01",
    local_location=(-1.38, 0.0, 2.22),
    collection=control_collection,
    parent=root,
    display_type="CIRCLE",
    display_size=0.27,
)

for index, (offset, radii) in enumerate(
    zip(tail_offsets, tail_radii),
    start=1,
):
    tail_controls.append(current_tail_control)

    create_ellipsoid(
        f"TailJoint_{index:02d}",
        local_center=(0.0, 0.0, 0.0),
        radii=(radii[0] * 0.95,) * 3,
        collection=model_collection,
        material=skin_material,
        parent=current_tail_control,
        subdivisions=1,
    )

    tail_segment = create_tapered_tube(
        name=f"Tail_{index:02d}",
        local_start=(0.0, 0.0, 0.0),
        local_end=offset,
        radius_start=radii[0],
        radius_end=radii[1],
        collection=model_collection,
        material=skin_material,
        parent=current_tail_control,
        sides=9,
        overlap=0.065,
    )
    tail_objects.append(tail_segment)

    next_tail_control = create_empty(
        f"CTRL_TAIL_{index + 1:02d}",
        local_location=offset,
        collection=control_collection,
        parent=current_tail_control,
        display_type="CIRCLE",
        display_size=max(0.12, 0.25 - index * 0.025),
    )
    current_tail_control = next_tail_control

create_ellipsoid(
    "TailTip",
    local_center=(0.0, 0.0, 0.0),
    radii=(0.045, 0.045, 0.045),
    collection=model_collection,
    material=skin_material,
    parent=current_tail_control,
    subdivisions=1,
)

# ---------------------------------------------------------------------------
# PESCOÇO, CABEÇA E CRISTA.
# ---------------------------------------------------------------------------

neck_base = create_empty(
    "CTRL_NECK_BASE",
    local_location=(1.32, 0.0, 2.43),
    collection=control_collection,
    parent=root,
    display_type="CIRCLE",
    display_size=0.29,
)

neck_offset_1 = Vector((0.50, 0.0, 0.28))
neck_01 = create_tapered_tube(
    "Neck_01",
    local_start=(0.0, 0.0, 0.0),
    local_end=neck_offset_1,
    radius_start=0.43,
    radius_end=0.35,
    collection=model_collection,
    material=skin_material,
    parent=neck_base,
    sides=9,
    overlap=0.08,
)

create_ellipsoid(
    "NeckBaseJoint",
    local_center=(0.0, 0.0, 0.0),
    radii=(0.42, 0.42, 0.42),
    collection=model_collection,
    material=skin_material,
    parent=neck_base,
    subdivisions=1,
)

neck_mid = create_empty(
    "CTRL_NECK_MID",
    local_location=neck_offset_1,
    collection=control_collection,
    parent=neck_base,
    display_type="CIRCLE",
    display_size=0.25,
)

neck_offset_2 = Vector((0.48, 0.0, 0.22))
neck_02 = create_tapered_tube(
    "Neck_02",
    local_start=(0.0, 0.0, 0.0),
    local_end=neck_offset_2,
    radius_start=0.35,
    radius_end=0.28,
    collection=model_collection,
    material=skin_material,
    parent=neck_mid,
    sides=9,
    overlap=0.075,
)

create_ellipsoid(
    "NeckMidJoint",
    local_center=(0.0, 0.0, 0.0),
    radii=(0.34, 0.34, 0.34),
    collection=model_collection,
    material=skin_material,
    parent=neck_mid,
    subdivisions=1,
)

head_control = create_empty(
    "CTRL_HEAD",
    local_location=neck_offset_2,
    collection=control_collection,
    parent=neck_mid,
    display_type="CIRCLE",
    display_size=0.27,
)

create_ellipsoid(
    "HeadNeckJoint",
    local_center=(0.0, 0.0, 0.0),
    radii=(0.29, 0.29, 0.29),
    collection=model_collection,
    material=skin_material,
    parent=head_control,
    subdivisions=1,
)

head = create_ellipsoid(
    "Head",
    local_center=(0.36, 0.0, 0.08),
    radii=(0.59, 0.38, 0.40),
    collection=model_collection,
    material=skin_material,
    parent=head_control,
)
snout = create_ellipsoid(
    "Snout",
    local_center=(0.85, 0.0, -0.025),
    radii=(0.49, 0.31, 0.24),
    collection=model_collection,
    material=belly_material,
    parent=head_control,
)
lower_beak = create_ellipsoid(
    "LowerBeak",
    local_center=(0.91, 0.0, -0.145),
    radii=(0.37, 0.275, 0.115),
    collection=model_collection,
    material=belly_material,
    parent=head_control,
    subdivisions=1,
)

for side_name, y in (("L", 0.335), ("R", -0.335)):
    create_ellipsoid(
        f"Eye.{side_name}",
        local_center=(0.52, y, 0.16),
        radii=(0.075, 0.048, 0.075),
        collection=model_collection,
        material=eye_material,
        parent=head_control,
    )
    create_ellipsoid(
        f"Nostril.{side_name}",
        local_center=(1.08, y * 0.70, 0.015),
        radii=(0.042, 0.028, 0.025),
        collection=model_collection,
        material=nostril_material,
        parent=head_control,
        subdivisions=1,
    )

create_ellipsoid(
    "CrestBase",
    local_center=(0.23, 0.0, 0.36),
    radii=(0.24, 0.22, 0.22),
    collection=model_collection,
    material=crest_material,
    parent=head_control,
    subdivisions=1,
)

crest_points = [
    (0.24, 0.0, 0.36),
    (0.12, 0.0, 0.55),
    (-0.20, 0.0, 0.72),
    (-0.62, 0.0, 0.79),
    (-1.06, 0.0, 0.72),
    (-1.43, 0.0, 0.57),
]
crest_radii = [0.22, 0.205, 0.18, 0.135, 0.075, 0.025]

crest = create_poly_tube(
    "Crest",
    local_points=crest_points,
    radii=crest_radii,
    collection=model_collection,
    material=crest_material,
    parent=head_control,
    sides=10,
)

# ---------------------------------------------------------------------------
# PERNAS TRASEIRAS E PÉS.
# ---------------------------------------------------------------------------

leg_controls = {}
contact_objects = []
toe_objects = []

for side_name, side_sign in (("L", 1.0), ("R", -1.0)):
    hip_position = Vector((-0.35, 0.54 * side_sign, 1.95))
    knee_offset = Vector((0.15, 0.0, -0.88))
    ankle_offset = Vector((0.30, 0.0, -0.78))
    foot_offset = Vector((0.50, 0.0, -0.04))

    hip_control = create_empty(
        f"CTRL_HIP.{side_name}",
        local_location=hip_position,
        collection=control_collection,
        parent=root,
        display_type="CIRCLE",
        display_size=0.25,
    )

    create_ellipsoid(
        f"HipJoint.{side_name}",
        local_center=(0.0, 0.0, 0.0),
        radii=(0.29, 0.29, 0.29),
        collection=model_collection,
        material=skin_material,
        parent=hip_control,
        subdivisions=1,
    )

    thigh = create_tapered_tube(
        f"Thigh.{side_name}",
        local_start=(0.0, 0.0, 0.0),
        local_end=knee_offset,
        radius_start=0.31,
        radius_end=0.22,
        collection=model_collection,
        material=skin_material,
        parent=hip_control,
        sides=8,
        overlap=0.075,
    )

    knee_control = create_empty(
        f"CTRL_KNEE.{side_name}",
        local_location=knee_offset,
        collection=control_collection,
        parent=hip_control,
        display_type="CIRCLE",
        display_size=0.20,
    )

    create_ellipsoid(
        f"KneeJoint.{side_name}",
        local_center=(0.0, 0.0, 0.0),
        radii=(0.215, 0.215, 0.215),
        collection=model_collection,
        material=skin_material,
        parent=knee_control,
        subdivisions=1,
    )

    shin = create_tapered_tube(
        f"Shin.{side_name}",
        local_start=(0.0, 0.0, 0.0),
        local_end=ankle_offset,
        radius_start=0.22,
        radius_end=0.145,
        collection=model_collection,
        material=skin_material,
        parent=knee_control,
        sides=8,
        overlap=0.055,
    )

    ankle_control = create_empty(
        f"CTRL_ANKLE.{side_name}",
        local_location=ankle_offset,
        collection=control_collection,
        parent=knee_control,
        display_type="CIRCLE",
        display_size=0.16,
    )

    ankle_joint = create_ellipsoid(
        f"AnkleJoint.{side_name}",
        local_center=(0.0, 0.0, 0.0),
        radii=(0.145, 0.145, 0.145),
        collection=model_collection,
        material=belly_material,
        parent=ankle_control,
        subdivisions=1,
    )

    foot = create_tapered_tube(
        f"Foot.{side_name}",
        local_start=(0.0, 0.0, 0.0),
        local_end=foot_offset,
        radius_start=0.155,
        radius_end=0.105,
        collection=model_collection,
        material=belly_material,
        parent=ankle_control,
        sides=8,
        overlap=0.04,
    )

    foot_control = create_empty(
        f"CTRL_FOOT.{side_name}",
        local_location=foot_offset,
        collection=control_collection,
        parent=ankle_control,
        display_type="CIRCLE",
        display_size=0.14,
    )

    foot_pad = create_ellipsoid(
        f"FootPad.{side_name}",
        local_center=(0.10, 0.0, -0.018),
        radii=(0.35, 0.22, 0.115),
        collection=model_collection,
        material=belly_material,
        parent=foot_control,
        subdivisions=1,
    )

    contact_objects.extend(
        [ankle_joint, foot, foot_pad]
    )

    toe_y_values = (-0.11, 0.0, 0.11)

    for toe_index, local_y in enumerate(toe_y_values, start=1):
        toe_start = Vector((0.14, local_y, -0.020))
        toe_end = Vector(
            (
                0.62,
                local_y * 1.45,
                -0.070,
            )
        )

        toe = create_tapered_tube(
            f"Toe_{toe_index}.{side_name}",
            local_start=toe_start,
            local_end=toe_end,
            radius_start=0.063,
            radius_end=0.038,
            collection=model_collection,
            material=belly_material,
            parent=foot_control,
            sides=7,
            overlap=0.018,
        )

        claw_end = toe_end + Vector((0.15, 0.0, -0.032))
        claw = create_tapered_tube(
            f"Claw_{toe_index}.{side_name}",
            local_start=toe_end,
            local_end=claw_end,
            radius_start=0.040,
            radius_end=0.008,
            collection=model_collection,
            material=claw_material,
            parent=foot_control,
            sides=7,
            overlap=0.008,
        )

        toe_objects.extend([toe, claw])
        contact_objects.extend([toe, claw])

    leg_controls[side_name] = {
        "hip": hip_control,
        "knee": knee_control,
        "ankle": ankle_control,
        "foot": foot_control,
    }

# ---------------------------------------------------------------------------
# MEMBROS DIANTEIROS.
# ---------------------------------------------------------------------------

arm_controls = {}

for side_name, side_sign in (("L", 1.0), ("R", -1.0)):
    shoulder_position = Vector((0.95, 0.55 * side_sign, 2.25))
    elbow_offset = Vector((0.05, 0.0, -0.61))
    wrist_offset = Vector((0.28, 0.0, -0.48))
    hand_offset = Vector((0.38, 0.0, -0.02))

    shoulder_control = create_empty(
        f"CTRL_SHOULDER.{side_name}",
        local_location=shoulder_position,
        collection=control_collection,
        parent=root,
        display_type="CIRCLE",
        display_size=0.20,
    )

    create_ellipsoid(
        f"ShoulderJoint.{side_name}",
        local_center=(0.0, 0.0, 0.0),
        radii=(0.18, 0.18, 0.18),
        collection=model_collection,
        material=skin_material,
        parent=shoulder_control,
        subdivisions=1,
    )

    create_tapered_tube(
        f"UpperArm.{side_name}",
        local_start=(0.0, 0.0, 0.0),
        local_end=elbow_offset,
        radius_start=0.18,
        radius_end=0.115,
        collection=model_collection,
        material=skin_material,
        parent=shoulder_control,
        sides=7,
        overlap=0.045,
    )

    elbow_control = create_empty(
        f"CTRL_ELBOW.{side_name}",
        local_location=elbow_offset,
        collection=control_collection,
        parent=shoulder_control,
        display_type="CIRCLE",
        display_size=0.16,
    )

    create_ellipsoid(
        f"ElbowJoint.{side_name}",
        local_center=(0.0, 0.0, 0.0),
        radii=(0.115, 0.115, 0.115),
        collection=model_collection,
        material=skin_material,
        parent=elbow_control,
        subdivisions=1,
    )

    create_tapered_tube(
        f"Forearm.{side_name}",
        local_start=(0.0, 0.0, 0.0),
        local_end=wrist_offset,
        radius_start=0.115,
        radius_end=0.070,
        collection=model_collection,
        material=skin_material,
        parent=elbow_control,
        sides=7,
        overlap=0.035,
    )

    wrist_control = create_empty(
        f"CTRL_WRIST.{side_name}",
        local_location=wrist_offset,
        collection=control_collection,
        parent=elbow_control,
        display_type="CIRCLE",
        display_size=0.13,
    )

    create_ellipsoid(
        f"WristJoint.{side_name}",
        local_center=(0.0, 0.0, 0.0),
        radii=(0.075, 0.075, 0.075),
        collection=model_collection,
        material=belly_material,
        parent=wrist_control,
        subdivisions=1,
    )

    create_tapered_tube(
        f"Hand.{side_name}",
        local_start=(0.0, 0.0, 0.0),
        local_end=hand_offset,
        radius_start=0.078,
        radius_end=0.030,
        collection=model_collection,
        material=belly_material,
        parent=wrist_control,
        sides=7,
        overlap=0.025,
    )

    arm_controls[side_name] = {
        "shoulder": shoulder_control,
        "elbow": elbow_control,
        "wrist": wrist_control,
    }

# Validação ANTES de qualquer keyframe.
validate_rest_pose(
    tail_objects=tail_objects,
    neck_objects=[neck_01, neck_02],
    toe_objects=toe_objects,
    crest_object=crest,
    head_object=head,
)

# ---------------------------------------------------------------------------
# ANIMAÇÃO LEVE DE CAMINHADA NO LUGAR.
# ---------------------------------------------------------------------------

poses = {
    1: {
        "root_z": 0.020,
        "hip_l": -8.0,
        "knee_l": 8.0,
        "ankle_l": 0.0,
        "hip_r": 8.0,
        "knee_r": 2.0,
        "ankle_r": -10.0,
        "shoulder_l": 8.0,
        "shoulder_r": -8.0,
        "elbow_l": -7.0,
        "elbow_r": -12.0,
        "tail": 4.0,
        "neck_base": 1.2,
        "neck_mid": 1.0,
        "head": -1.5,
    },
    7: {
        "root_z": 0.060,
        "hip_l": 0.0,
        "knee_l": 12.0,
        "ankle_l": -12.0,
        "hip_r": 0.0,
        "knee_r": 4.0,
        "ankle_r": -4.0,
        "shoulder_l": 0.0,
        "shoulder_r": 0.0,
        "elbow_l": -10.0,
        "elbow_r": -8.0,
        "tail": 0.0,
        "neck_base": 0.0,
        "neck_mid": 0.0,
        "head": 1.0,
    },
    13: {
        "root_z": 0.020,
        "hip_l": 8.0,
        "knee_l": 2.0,
        "ankle_l": -10.0,
        "hip_r": -8.0,
        "knee_r": 8.0,
        "ankle_r": 0.0,
        "shoulder_l": -8.0,
        "shoulder_r": 8.0,
        "elbow_l": -12.0,
        "elbow_r": -7.0,
        "tail": -4.0,
        "neck_base": -1.2,
        "neck_mid": -1.0,
        "head": 1.5,
    },
    19: {
        "root_z": 0.060,
        "hip_l": 0.0,
        "knee_l": 4.0,
        "ankle_l": -4.0,
        "hip_r": 0.0,
        "knee_r": 12.0,
        "ankle_r": -12.0,
        "shoulder_l": 0.0,
        "shoulder_r": 0.0,
        "elbow_l": -8.0,
        "elbow_r": -10.0,
        "tail": 0.0,
        "neck_base": 0.0,
        "neck_mid": 0.0,
        "head": -1.0,
    },
    LOOP_KEY: {
        "root_z": 0.020,
        "hip_l": -8.0,
        "knee_l": 8.0,
        "ankle_l": 0.0,
        "hip_r": 8.0,
        "knee_r": 2.0,
        "ankle_r": -10.0,
        "shoulder_l": 8.0,
        "shoulder_r": -8.0,
        "elbow_l": -7.0,
        "elbow_r": -12.0,
        "tail": 4.0,
        "neck_base": 1.2,
        "neck_mid": 1.0,
        "head": -1.5,
    },
}

animated_controls = [root, neck_base, neck_mid, head_control]
animated_controls.extend(tail_controls)

for controls in leg_controls.values():
    animated_controls.extend(controls.values())

for controls in arm_controls.values():
    animated_controls.extend(controls.values())

for frame, pose in poses.items():
    key_location(root, frame, (0.0, 0.0, pose["root_z"]))

    key_rotation(
        leg_controls["L"]["hip"],
        frame,
        y=pose["hip_l"],
    )
    key_rotation(
        leg_controls["L"]["knee"],
        frame,
        y=pose["knee_l"],
    )
    key_rotation(
        leg_controls["L"]["ankle"],
        frame,
        y=pose["ankle_l"],
    )

    key_rotation(
        leg_controls["R"]["hip"],
        frame,
        y=pose["hip_r"],
    )
    key_rotation(
        leg_controls["R"]["knee"],
        frame,
        y=pose["knee_r"],
    )
    key_rotation(
        leg_controls["R"]["ankle"],
        frame,
        y=pose["ankle_r"],
    )

    key_rotation(
        arm_controls["L"]["shoulder"],
        frame,
        y=pose["shoulder_l"],
    )
    key_rotation(
        arm_controls["R"]["shoulder"],
        frame,
        y=pose["shoulder_r"],
    )
    key_rotation(
        arm_controls["L"]["elbow"],
        frame,
        y=pose["elbow_l"],
    )
    key_rotation(
        arm_controls["R"]["elbow"],
        frame,
        y=pose["elbow_r"],
    )

    key_rotation(neck_base, frame, y=pose["neck_base"])
    key_rotation(neck_mid, frame, y=pose["neck_mid"])
    key_rotation(head_control, frame, y=pose["head"])

    tail_angle = pose["tail"]
    tail_multipliers = (0.70, 0.95, 1.15, 1.30, 1.45)

    for control, multiplier in zip(
        tail_controls,
        tail_multipliers,
    ):
        key_rotation(
            control,
            frame,
            z=tail_angle * multiplier,
        )

for control in animated_controls:
    clamp_interpolation(control)
    set_cycles_if_available(control)

# Ajuste automático da altura global:
# o menor ponto dos pés em todo o ciclo ficará a 2 cm do chão.
scene.frame_start = FRAME_START
scene.frame_end = FRAME_END
scene.render.fps = FPS

minimum_contact_z = float("inf")
minimum_contact_frame = FRAME_START

for frame in range(FRAME_START, FRAME_END + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()

    frame_minimum = world_min_z(contact_objects)
    if frame_minimum < minimum_contact_z:
        minimum_contact_z = frame_minimum
        minimum_contact_frame = frame

master.location.z += GROUND_CLEARANCE - minimum_contact_z
bpy.context.view_layer.update()

# Confirmação pós-ajuste.
verified_minimum_z = float("inf")
verified_minimum_frame = FRAME_START

for frame in range(FRAME_START, FRAME_END + 1):
    scene.frame_set(frame)
    bpy.context.view_layer.update()

    frame_minimum = world_min_z(contact_objects)
    if frame_minimum < verified_minimum_z:
        verified_minimum_z = frame_minimum
        verified_minimum_frame = frame

if verified_minimum_z < GROUND_CLEARANCE - 0.001:
    raise RuntimeError(
        "Falha ao ajustar o contato com o chão: "
        f"mínimo Z={verified_minimum_z:.4f}, "
        f"quadro={verified_minimum_frame}."
    )

# ---------------------------------------------------------------------------
# AMBIENTE, CÂMERA E LUZES.
# ---------------------------------------------------------------------------

ground = create_plane(
    "Preview_Ground",
    size=30.0,
    z=0.0,
    collection=environment_collection,
    material=ground_material,
)

key_light_data = bpy.data.lights.new(
    "Parasaurolophus_Key_Light_Data",
    type="AREA",
)
key_light_data.energy = 1050.0
key_light_data.shape = "DISK"
key_light_data.size = 5.5

key_light = bpy.data.objects.new(
    "Parasaurolophus_Key_Light",
    key_light_data,
)
environment_collection.objects.link(key_light)
key_light.location = (4.0, -4.5, 8.0)
look_at(key_light, (-0.5, 0.0, 1.8))

fill_light_data = bpy.data.lights.new(
    "Parasaurolophus_Fill_Light_Data",
    type="AREA",
)
fill_light_data.energy = 480.0
fill_light_data.size = 5.0

fill_light = bpy.data.objects.new(
    "Parasaurolophus_Fill_Light",
    fill_light_data,
)
environment_collection.objects.link(fill_light)
fill_light.location = (-4.0, 4.5, 5.8)
look_at(fill_light, (-0.7, 0.0, 1.8))

camera_data = bpy.data.cameras.new("Parasaurolophus_Camera_Data")
camera = bpy.data.objects.new(
    "Parasaurolophus_Camera",
    camera_data,
)
environment_collection.objects.link(camera)
camera.location = (7.4, -13.8, 5.7)
camera_data.lens = 52.0
look_at(camera, (-0.8, 0.0, 1.8))
scene.camera = camera

world = bpy.data.worlds.new("Parasaurolophus_World")
world.use_nodes = True
background = world.node_tree.nodes.get("Background")
if background is not None:
    background.inputs["Color"].default_value = (
        0.025,
        0.035,
        0.045,
        1.0,
    )
    background.inputs["Strength"].default_value = 0.42
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
scene.render.film_transparent = False

# Metadados de diagnóstico.
master["minimum_contact_before_adjustment"] = minimum_contact_z
master["minimum_contact_frame_before_adjustment"] = minimum_contact_frame
master["verified_minimum_contact_z"] = verified_minimum_z
master["verified_minimum_contact_frame"] = verified_minimum_frame

scene.frame_set(FRAME_START)
bpy.context.view_layer.update()

bpy.ops.object.select_all(action="DESELECT")
master.select_set(True)
bpy.context.view_layer.objects.active = master

mesh_objects = [
    obj
    for obj in model_collection.all_objects
    if obj.type == "MESH"
]
polygon_count = sum(
    len(obj.data.polygons)
    for obj in mesh_objects
)

print("=" * 72)
print("Parasaurolophus reconstruído com sucesso.")
print(f"Versão do gerador: {GENERATOR_VERSION}")
print(f"Objetos de malha do modelo: {len(mesh_objects)}")
print(f"Polígonos aproximados: {polygon_count}")
print(
    "Contato mínimo validado: "
    f"Z={verified_minimum_z:.4f} no quadro "
    f"{verified_minimum_frame}"
)
print("Preview_Ground permanece em Z=0.0000.")
print(
    "A cena foi limpa integralmente antes da geração; "
    "o script é idempotente."
)
print("=" * 72)
