"""
Parasaurolophus low-poly colorido, animado e controlável pelo teclado
=====================================================================

ATENÇÃO:
Este script APAGA TODOS OS OBJETOS da cena atual antes de reconstruir
o personagem. Ele também encerra e substitui qualquer controlador de
teclado criado por uma execução anterior deste mesmo script. O bloco
de texto que contém o próprio script não é apagado.

Controles no modo de caminhada:
- mantenha SETA PARA CIMA pressionada: andar para a frente;
- mantenha SETA PARA BAIXO pressionada: andar de ré;
- HOME: voltar ao centro do terreno;
- ESC: encerrar o controlador modal.

O controlador é iniciado automaticamente quando existe uma Viewport 3D.
Também há um painel "Parasauro" na barra lateral da Viewport (tecla N)
para iniciar/parar o controle, ajustar a velocidade e redefinir a posição.

Objetivos desta versão:
- preservar o modelo, as cores procedurais, a crista, a câmera e as luzes;
- execução idempotente e limpeza integral da área de desenho;
- movimento real do CTRL_MASTER sobre o terreno;
- ciclo de passada mais amplo, com apoio, transferência de peso e balanço;
- animação reproduzida para a frente ou ao contrário conforme a direção;
- câmera e luzes capazes de acompanhar o animal;
- Preview_Ground com três vezes o tamanho da versão anterior;
- validação da cauda, pescoço, dedos, crista e contato com o chão.

Compatibilidade pretendida: Blender 3.6 LTS e Blender 4.x.
"""

import bpy
import bmesh
import math
import time
from bpy.props import BoolProperty, FloatProperty
from mathutils import Vector

GENERATOR_VERSION = "4.0-teclado"
FPS = 24
FRAME_START = 1
FRAME_END = 24
LOOP_KEY = 25
CYCLE_LENGTH = float(LOOP_KEY - FRAME_START)
GROUND_CLEARANCE = 0.02
GROUND_SIZE = 90.0
GROUND_WALK_LIMIT = 39.0
CONTROLLER_TIMER_INTERVAL = 1.0 / 60.0
RUNTIME_KEY = "_PARASAURO_KEYBOARD_RUNTIME_V4"
RUNTIME_SESSION = time.time_ns()

SCENE_PROPERTY_NAMES = (
    "parasauro_walk_speed",
    "parasauro_acceleration",
    "parasauro_braking",
    "parasauro_stride_length",
    "parasauro_camera_follow",
)


def cleanup_previous_keyboard_runtime():
    """
    Encerra o operador modal e remove classes/propriedades de uma execução
    anterior. Isso complementa a limpeza dos objetos e evita controladores
    duplicados ao executar o script novamente.
    """
    namespace = bpy.app.driver_namespace
    runtime = namespace.get(RUNTIME_KEY)

    if isinstance(runtime, dict):
        controller = runtime.get("controller")
        if controller is not None:
            try:
                controller.shutdown_external()
            except Exception:
                try:
                    controller._stop_requested = True
                except Exception:
                    pass

        for cls in reversed(runtime.get("classes", ())):
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass

    # Também remove classes que possam ter sido registradas antes de uma
    # execução anterior falhar e gravar o dicionário de runtime.
    for type_name in (
        "VIEW3D_PT_parasaurolophus_keyboard",
        "WM_OT_parasaurolophus_reset_position",
        "WM_OT_parasaurolophus_stop_controller",
        "WM_OT_parasaurolophus_keyboard_controller",
    ):
        registered_type = getattr(bpy.types, type_name, None)
        if registered_type is not None:
            try:
                bpy.utils.unregister_class(registered_type)
            except Exception:
                pass

    namespace.pop(RUNTIME_KEY, None)

    for property_name in SCENE_PROPERTY_NAMES:
        if hasattr(bpy.types.Scene, property_name):
            try:
                delattr(bpy.types.Scene, property_name)
            except Exception:
                pass


cleanup_previous_keyboard_runtime()


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


def set_scene_frame_float(scene, frame_float):
    """Define quadro e subquadro sem perder a suavidade da passada."""
    frame_integer = math.floor(frame_float)
    subframe = frame_float - frame_integer
    scene.frame_set(frame_integer, subframe=subframe)


def approach_value(current, target, maximum_change):
    """Aproxima current de target sem ultrapassá-lo."""
    if current < target:
        return min(current + maximum_change, target)
    return max(current - maximum_change, target)


def redraw_viewports(window_manager):
    for window in window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


class WM_OT_parasaurolophus_keyboard_controller(bpy.types.Operator):
    """Controla o Parasaurolophus continuamente pelas setas do teclado."""

    bl_idname = "wm.parasaurolophus_keyboard_controller"
    bl_label = "Iniciar controle do Parasaurolophus"
    bl_description = (
        "Seta para cima anda para frente; seta para baixo anda de ré"
    )
    bl_options = {"REGISTER"}

    _timer = None
    _window_manager = None
    _window = None
    _area = None
    _scene = None
    _master = None
    _follow_rig = None
    _up_pressed = False
    _down_pressed = False
    _stop_requested = False
    _last_time = 0.0
    _velocity = 0.0
    _phase = 0.0
    _distance_total = 0.0

    def _runtime_is_current(self):
        runtime = bpy.app.driver_namespace.get(RUNTIME_KEY)
        return (
            isinstance(runtime, dict)
            and runtime.get("session") == RUNTIME_SESSION
            and runtime.get("controller") is self
        )

    def _set_header(self, text):
        if self._area is None:
            return
        try:
            self._area.header_text_set(text)
        except Exception:
            pass

    def _clear_header(self):
        if self._area is None:
            return
        try:
            self._area.header_text_set(None)
        except Exception:
            pass

    def _set_phase_frame(self):
        frame_float = FRAME_START + (self._phase % CYCLE_LENGTH)
        set_scene_frame_float(self._scene, frame_float)

    def _reset_position(self):
        if self._master is None:
            return

        self._master.location.x = 0.0
        self._master.location.y = 0.0
        self._velocity = 0.0
        self._phase = 0.0
        self._up_pressed = False
        self._down_pressed = False
        self._set_phase_frame()

        if self._follow_rig is not None:
            self._follow_rig.location.x = 0.0
            self._follow_rig.location.y = 0.0

    def shutdown_external(self):
        """
        Finalização segura que também pode ser chamada por uma nova execução
        do script antes de as classes antigas serem removidas.
        """
        self._stop_requested = True
        self._up_pressed = False
        self._down_pressed = False
        self._velocity = 0.0

        if self._timer is not None and self._window_manager is not None:
            try:
                self._window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None

        self._clear_header()

        runtime = bpy.app.driver_namespace.get(RUNTIME_KEY)
        if isinstance(runtime, dict) and runtime.get("controller") is self:
            runtime["controller"] = None

        if self._scene is not None:
            self._scene["parasauro_controller_running"] = False

    def _finish(self, context):
        self.shutdown_external()
        redraw_viewports(context.window_manager)
        return {"CANCELLED"}

    def _tick(self, context):
        if self._master is None or self._master.name not in bpy.data.objects:
            self._stop_requested = True
            return

        now = time.perf_counter()
        delta_time = max(0.0, min(now - self._last_time, 0.075))
        self._last_time = now

        direction = int(self._up_pressed) - int(self._down_pressed)
        target_velocity = (
            direction * float(self._scene.parasauro_walk_speed)
        )

        rate = (
            float(self._scene.parasauro_acceleration)
            if direction != 0
            else float(self._scene.parasauro_braking)
        )
        self._velocity = approach_value(
            self._velocity,
            target_velocity,
            rate * delta_time,
        )

        if direction == 0 and abs(self._velocity) < 0.01:
            self._velocity = 0.0

        requested_distance = self._velocity * delta_time
        actual_distance = 0.0
        reached_limit = False

        if abs(requested_distance) > 1.0e-7:
            forward = (
                self._master.matrix_world.to_quaternion()
                @ Vector((1.0, 0.0, 0.0))
            )
            forward.z = 0.0

            if forward.length <= 1.0e-7:
                forward = Vector((1.0, 0.0, 0.0))
            else:
                forward.normalize()

            old_location = self._master.location.copy()
            proposed_location = (
                old_location + forward * requested_distance
            )

            proposed_location.x = max(
                -GROUND_WALK_LIMIT,
                min(GROUND_WALK_LIMIT, proposed_location.x),
            )
            proposed_location.y = max(
                -GROUND_WALK_LIMIT,
                min(GROUND_WALK_LIMIT, proposed_location.y),
            )

            displacement = proposed_location - old_location
            actual_distance = displacement.dot(forward)
            self._master.location = proposed_location

            if (
                abs(actual_distance - requested_distance) > 1.0e-5
                or (
                    abs(proposed_location.x) >= GROUND_WALK_LIMIT
                    and abs(forward.x) > 0.2
                )
                or (
                    abs(proposed_location.y) >= GROUND_WALK_LIMIT
                    and abs(forward.y) > 0.2
                )
            ):
                reached_limit = True
                self._velocity = 0.0

            stride_length = max(
                0.25,
                float(self._scene.parasauro_stride_length),
            )
            phase_increment = (
                actual_distance / stride_length
            ) * CYCLE_LENGTH
            self._phase = (
                self._phase + phase_increment
            ) % CYCLE_LENGTH
            self._distance_total += abs(actual_distance)
            self._set_phase_frame()

        if (
            self._follow_rig is not None
            and self._scene.parasauro_camera_follow
        ):
            self._follow_rig.location.x = self._master.location.x
            self._follow_rig.location.y = self._master.location.y

        position = self._master.location
        limit_text = " | LIMITE DO TERRENO" if reached_limit else ""
        self._set_header(
            "Parasaurolophus: ↑ frente  ↓ ré  HOME centralizar  "
            f"ESC sair | velocidade {abs(self._velocity):.2f} | "
            f"posição ({position.x:.1f}, {position.y:.1f})"
            f"{limit_text}"
        )

        redraw_viewports(context.window_manager)

    def invoke(self, context, event):
        master = bpy.data.objects.get("CTRL_MASTER")
        if master is None:
            self.report(
                {"ERROR"},
                "CTRL_MASTER não foi encontrado. Execute o gerador primeiro.",
            )
            return {"CANCELLED"}

        runtime = bpy.app.driver_namespace.get(RUNTIME_KEY)
        if (
            not isinstance(runtime, dict)
            or runtime.get("session") != RUNTIME_SESSION
        ):
            self.report(
                {"ERROR"},
                "A sessão do controlador não corresponde ao modelo atual.",
            )
            return {"CANCELLED"}

        previous = runtime.get("controller")
        if previous is not None and previous is not self:
            try:
                previous.shutdown_external()
            except Exception:
                pass

        # A reprodução normal da Timeline concorreria com o quadro
        # controlado pela distância percorrida. Interrompe-a, se necessário.
        try:
            if (
                context.screen is not None
                and context.screen.is_animation_playing
            ):
                bpy.ops.screen.animation_cancel(restore_frame=False)
        except Exception:
            pass

        self._window_manager = context.window_manager
        self._window = context.window
        self._area = (
            context.area
            if context.area is not None and context.area.type == "VIEW_3D"
            else None
        )
        self._scene = context.scene
        self._master = master
        self._follow_rig = bpy.data.objects.get("CTRL_CAMERA_LIGHT_FOLLOW")
        self._up_pressed = False
        self._down_pressed = False
        self._stop_requested = False
        self._velocity = 0.0
        self._last_time = time.perf_counter()
        current_frame = (
            float(self._scene.frame_current)
            + float(getattr(self._scene, "frame_subframe", 0.0))
        )
        self._phase = (
            current_frame - FRAME_START
        ) % CYCLE_LENGTH
        self._distance_total = 0.0

        self._timer = context.window_manager.event_timer_add(
            CONTROLLER_TIMER_INTERVAL,
            window=context.window,
        )
        context.window_manager.modal_handler_add(self)
        runtime["controller"] = self
        self._scene["parasauro_controller_running"] = True

        self._set_header(
            "Parasaurolophus: mantenha ↑ ou ↓ pressionada | "
            "HOME centraliza | ESC encerra"
        )
        self.report(
            {"INFO"},
            "Controle ativo: use as setas para cima e para baixo.",
        )
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if self._stop_requested or not self._runtime_is_current():
            return self._finish(context)

        if event.type == "ESC" and event.value == "PRESS":
            return self._finish(context)

        if event.type == "HOME" and event.value == "PRESS":
            self._reset_position()
            redraw_viewports(context.window_manager)
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

        if event.type == "WINDOW_DEACTIVATE":
            self._up_pressed = False
            self._down_pressed = False
            return {"PASS_THROUGH"}

        if event.type == "TIMER" and event.timer == self._timer:
            self._tick(context)
            return {"RUNNING_MODAL"}

        return {"PASS_THROUGH"}


class WM_OT_parasaurolophus_stop_controller(bpy.types.Operator):
    bl_idname = "wm.parasaurolophus_stop_controller"
    bl_label = "Parar controle"
    bl_description = "Encerra o controlador modal do Parasaurolophus"

    def execute(self, context):
        runtime = bpy.app.driver_namespace.get(RUNTIME_KEY)
        controller = (
            runtime.get("controller")
            if isinstance(runtime, dict)
            else None
        )

        if controller is None:
            self.report({"INFO"}, "O controlador já está parado.")
            return {"FINISHED"}

        controller._stop_requested = True
        self.report({"INFO"}, "Controlador encerrado.")
        return {"FINISHED"}


class WM_OT_parasaurolophus_reset_position(bpy.types.Operator):
    bl_idname = "wm.parasaurolophus_reset_position"
    bl_label = "Voltar ao centro"
    bl_description = "Reposiciona o animal no centro do Preview_Ground"

    def execute(self, context):
        master = bpy.data.objects.get("CTRL_MASTER")
        follow_rig = bpy.data.objects.get("CTRL_CAMERA_LIGHT_FOLLOW")

        if master is None:
            self.report({"ERROR"}, "CTRL_MASTER não foi encontrado.")
            return {"CANCELLED"}

        master.location.x = 0.0
        master.location.y = 0.0

        if follow_rig is not None:
            follow_rig.location.x = 0.0
            follow_rig.location.y = 0.0

        runtime = bpy.app.driver_namespace.get(RUNTIME_KEY)
        controller = (
            runtime.get("controller")
            if isinstance(runtime, dict)
            else None
        )

        if controller is not None:
            controller._velocity = 0.0
            controller._phase = 0.0
            controller._up_pressed = False
            controller._down_pressed = False

        set_scene_frame_float(context.scene, float(FRAME_START))
        redraw_viewports(context.window_manager)
        return {"FINISHED"}


class VIEW3D_PT_parasaurolophus_keyboard(bpy.types.Panel):
    bl_label = "Controle do Parasaurolophus"
    bl_idname = "VIEW3D_PT_parasaurolophus_keyboard"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Parasauro"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        master = bpy.data.objects.get("CTRL_MASTER")

        instructions = layout.box()
        instructions.label(text="Mantenha ↑ pressionada: frente")
        instructions.label(text="Mantenha ↓ pressionada: ré")
        instructions.label(text="HOME: centro | ESC: parar")

        layout.prop(scene, "parasauro_walk_speed")
        layout.prop(scene, "parasauro_camera_follow")

        advanced = layout.box()
        advanced.label(text="Ajustes da passada")
        advanced.prop(scene, "parasauro_acceleration")
        advanced.prop(scene, "parasauro_braking")
        advanced.prop(scene, "parasauro_stride_length")

        runtime = bpy.app.driver_namespace.get(RUNTIME_KEY)
        controller = (
            runtime.get("controller")
            if isinstance(runtime, dict)
            else None
        )
        running = (
            controller is not None
            and not getattr(controller, "_stop_requested", False)
        )

        row = layout.row(align=True)
        if running:
            row.operator(
                "wm.parasaurolophus_stop_controller",
                icon="PAUSE",
            )
        else:
            row.operator(
                "wm.parasaurolophus_keyboard_controller",
                icon="PLAY",
            )

        row.operator(
            "wm.parasaurolophus_reset_position",
            icon="LOOP_BACK",
            text="Centro",
        )

        if master is not None:
            layout.label(
                text=(
                    f"Posição: X {master.location.x:.2f} | "
                    f"Y {master.location.y:.2f}"
                )
            )


KEYBOARD_CLASSES = (
    WM_OT_parasaurolophus_keyboard_controller,
    WM_OT_parasaurolophus_stop_controller,
    WM_OT_parasaurolophus_reset_position,
    VIEW3D_PT_parasaurolophus_keyboard,
)


def register_keyboard_runtime():
    """Registra propriedades, operadores e painel desta sessão."""
    bpy.types.Scene.parasauro_walk_speed = FloatProperty(
        name="Velocidade",
        description="Velocidade de deslocamento pelo terreno",
        default=2.8,
        min=0.25,
        max=8.0,
        soft_max=5.0,
    )
    bpy.types.Scene.parasauro_acceleration = FloatProperty(
        name="Aceleração",
        description="Rapidez com que o animal entra em movimento",
        default=7.0,
        min=0.5,
        max=20.0,
        soft_max=12.0,
    )
    bpy.types.Scene.parasauro_braking = FloatProperty(
        name="Frenagem",
        description="Rapidez com que o animal para após soltar a seta",
        default=9.0,
        min=0.5,
        max=25.0,
        soft_max=15.0,
    )
    bpy.types.Scene.parasauro_stride_length = FloatProperty(
        name="Comprimento da passada",
        description=(
            "Distância percorrida por ciclo completo de caminhada"
        ),
        default=2.75,
        min=0.8,
        max=6.0,
        soft_max=4.0,
        subtype="DISTANCE",
    )
    bpy.types.Scene.parasauro_camera_follow = BoolProperty(
        name="Câmera e luzes acompanham",
        description=(
            "Mantém câmera e iluminação acompanhando o deslocamento"
        ),
        default=True,
    )

    # Valores explícitos tornam a execução determinística mesmo quando a
    # mesma Scene já possuía dados de propriedades de uma sessão anterior.
    current_scene = bpy.context.scene
    current_scene.parasauro_walk_speed = 2.8
    current_scene.parasauro_acceleration = 7.0
    current_scene.parasauro_braking = 9.0
    current_scene.parasauro_stride_length = 2.75
    current_scene.parasauro_camera_follow = True
    current_scene["parasauro_controller_running"] = False

    runtime = {
        "session": RUNTIME_SESSION,
        "classes": [],
        "controller": None,
    }
    bpy.app.driver_namespace[RUNTIME_KEY] = runtime

    try:
        for cls in KEYBOARD_CLASSES:
            bpy.utils.register_class(cls)
            runtime["classes"].append(cls)
    except Exception:
        for cls in reversed(runtime["classes"]):
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass
        bpy.app.driver_namespace.pop(RUNTIME_KEY, None)
        raise

    started = False
    window_manager = bpy.context.window_manager

    for window in window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue

            region = next(
                (
                    candidate
                    for candidate in area.regions
                    if candidate.type == "WINDOW"
                ),
                None,
            )
            if region is None:
                continue

            try:
                with bpy.context.temp_override(
                    window=window,
                    screen=screen,
                    area=area,
                    region=region,
                ):
                    result = bpy.ops.wm.parasaurolophus_keyboard_controller(
                        "INVOKE_DEFAULT"
                    )
                started = "RUNNING_MODAL" in result
            except Exception as error:
                print(
                    "Não foi possível iniciar automaticamente o "
                    f"controlador: {error}"
                )
                started = False

            return started

    return started


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
master["keyboard_controls"] = "UP_ARROW, DOWN_ARROW, HOME, ESC"
master["ground_size"] = GROUND_SIZE
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
# ANIMAÇÃO DE CAMINHADA: PASSADA AMPLA E TRANSFERÊNCIA DE PESO.
# ---------------------------------------------------------------------------

# O ciclo tem oito poses principais. As pernas traseiras alternam:
# contato, absorção, apoio, impulso, balanço e novo contato. O pé possui
# controle próprio para elevar os dedos durante a fase aérea.
poses = {
    1: {
        "root_z": -0.045,
        "root_y": -0.025,
        "root_roll": 0.7,
        "root_pitch": 0.8,
        "hip_l": -12.8,
        "knee_l": 12.0,
        "ankle_l": -1.6,
        "foot_l": -3.6,
        "hip_r": 35.8,
        "knee_r": 15.2,
        "ankle_r": -41.5,
        "foot_r": -10.4,
        "shoulder_l": 16.0,
        "shoulder_r": -16.0,
        "elbow_l": 5.0,
        "elbow_r": -18.0,
        "wrist_l": 3.0,
        "wrist_r": -7.0,
        "tail_sway": -3.5,
        "tail_pitch": 0.8,
        "neck_base": 1.2,
        "neck_mid": 0.8,
        "head": -1.8,
    },
    4: {
        "root_z": 0.000,
        "root_y": 0.060,
        "root_roll": -1.2,
        "root_pitch": 0.3,
        "hip_l": 1.3,
        "knee_l": 12.8,
        "ankle_l": -17.2,
        "foot_l": -2.9,
        "hip_r": 34.1,
        "knee_r": 14.5,
        "ankle_r": -68.2,
        "foot_r": 1.6,
        "shoulder_l": 12.0,
        "shoulder_r": -12.0,
        "elbow_l": 3.0,
        "elbow_r": -22.0,
        "wrist_l": 2.0,
        "wrist_r": -9.0,
        "tail_sway": -6.5,
        "tail_pitch": 0.4,
        "neck_base": 1.8,
        "neck_mid": 1.0,
        "head": -0.8,
    },
    7: {
        "root_z": -0.005,
        "root_y": 0.080,
        "root_roll": -1.0,
        "root_pitch": 0.0,
        "hip_l": 17.7,
        "knee_l": 13.4,
        "ankle_l": -34.1,
        "foot_l": -3.0,
        "hip_r": 0.0,
        "knee_r": 44.7,
        "ankle_r": -70.0,
        "foot_r": 1.4,
        "shoulder_l": 3.0,
        "shoulder_r": -3.0,
        "elbow_l": -2.0,
        "elbow_r": -24.0,
        "wrist_l": 0.0,
        "wrist_r": -10.0,
        "tail_sway": -4.0,
        "tail_pitch": 0.0,
        "neck_base": 0.4,
        "neck_mid": 0.2,
        "head": 0.8,
    },
    10: {
        "root_z": -0.045,
        "root_y": 0.035,
        "root_roll": -0.5,
        "root_pitch": -0.8,
        "hip_l": 35.8,
        "knee_l": 15.2,
        "ankle_l": -41.5,
        "foot_l": -10.4,
        "hip_r": -6.8,
        "knee_r": 8.9,
        "ankle_r": -20.5,
        "foot_r": 2.4,
        "shoulder_l": -12.0,
        "shoulder_r": 12.0,
        "elbow_l": -18.0,
        "elbow_r": 3.0,
        "wrist_l": -7.0,
        "wrist_r": 2.0,
        "tail_sway": 0.0,
        "tail_pitch": -0.7,
        "neck_base": -1.2,
        "neck_mid": -0.7,
        "head": 1.8,
    },
    13: {
        "root_z": -0.045,
        "root_y": 0.025,
        "root_roll": -0.7,
        "root_pitch": 0.8,
        "hip_l": 35.8,
        "knee_l": 15.2,
        "ankle_l": -41.5,
        "foot_l": -10.4,
        "hip_r": -12.8,
        "knee_r": 12.0,
        "ankle_r": -1.6,
        "foot_r": -3.6,
        "shoulder_l": -16.0,
        "shoulder_r": 16.0,
        "elbow_l": -18.0,
        "elbow_r": 5.0,
        "wrist_l": -7.0,
        "wrist_r": 3.0,
        "tail_sway": 3.5,
        "tail_pitch": 0.8,
        "neck_base": 1.2,
        "neck_mid": 0.8,
        "head": -1.8,
    },
    16: {
        "root_z": 0.000,
        "root_y": -0.060,
        "root_roll": 1.2,
        "root_pitch": 0.3,
        "hip_l": 34.1,
        "knee_l": 14.5,
        "ankle_l": -68.2,
        "foot_l": 1.6,
        "hip_r": 1.3,
        "knee_r": 12.8,
        "ankle_r": -17.2,
        "foot_r": -2.9,
        "shoulder_l": -12.0,
        "shoulder_r": 12.0,
        "elbow_l": -22.0,
        "elbow_r": 3.0,
        "wrist_l": -9.0,
        "wrist_r": 2.0,
        "tail_sway": 6.5,
        "tail_pitch": 0.4,
        "neck_base": 1.8,
        "neck_mid": 1.0,
        "head": -0.8,
    },
    19: {
        "root_z": -0.005,
        "root_y": -0.080,
        "root_roll": 1.0,
        "root_pitch": 0.0,
        "hip_l": 0.0,
        "knee_l": 44.7,
        "ankle_l": -70.0,
        "foot_l": 1.4,
        "hip_r": 17.7,
        "knee_r": 13.4,
        "ankle_r": -34.1,
        "foot_r": -3.0,
        "shoulder_l": -3.0,
        "shoulder_r": 3.0,
        "elbow_l": -24.0,
        "elbow_r": -2.0,
        "wrist_l": -10.0,
        "wrist_r": 0.0,
        "tail_sway": 4.0,
        "tail_pitch": 0.0,
        "neck_base": 0.4,
        "neck_mid": 0.2,
        "head": 0.8,
    },
    22: {
        "root_z": -0.045,
        "root_y": -0.035,
        "root_roll": 0.5,
        "root_pitch": -0.8,
        "hip_l": -6.8,
        "knee_l": 8.9,
        "ankle_l": -20.5,
        "foot_l": 2.4,
        "hip_r": 35.8,
        "knee_r": 15.2,
        "ankle_r": -41.5,
        "foot_r": -10.4,
        "shoulder_l": 12.0,
        "shoulder_r": -12.0,
        "elbow_l": 3.0,
        "elbow_r": -18.0,
        "wrist_l": 2.0,
        "wrist_r": -7.0,
        "tail_sway": 0.0,
        "tail_pitch": -0.7,
        "neck_base": -1.2,
        "neck_mid": -0.7,
        "head": 1.8,
    },
}

# O quadro 25 repete exatamente o quadro 1 para fechar o ciclo.
poses[LOOP_KEY] = dict(poses[FRAME_START])

animated_controls = [root, neck_base, neck_mid, head_control]
animated_controls.extend(tail_controls)

for controls in leg_controls.values():
    animated_controls.extend(controls.values())

for controls in arm_controls.values():
    animated_controls.extend(controls.values())

for frame, pose in poses.items():
    key_location(
        root,
        frame,
        (0.0, pose["root_y"], pose["root_z"]),
    )
    key_rotation(
        root,
        frame,
        x=pose["root_roll"],
        y=pose["root_pitch"],
    )

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
        leg_controls["L"]["foot"],
        frame,
        y=pose["foot_l"],
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
        leg_controls["R"]["foot"],
        frame,
        y=pose["foot_r"],
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
    key_rotation(
        arm_controls["L"]["wrist"],
        frame,
        y=pose["wrist_l"],
    )
    key_rotation(
        arm_controls["R"]["wrist"],
        frame,
        y=pose["wrist_r"],
    )

    key_rotation(neck_base, frame, y=pose["neck_base"])
    key_rotation(neck_mid, frame, y=pose["neck_mid"])
    key_rotation(head_control, frame, y=pose["head"])

    tail_sway = pose["tail_sway"]
    tail_pitch = pose["tail_pitch"]
    sway_multipliers = (0.65, 0.90, 1.10, 1.28, 1.42)
    pitch_multipliers = (0.50, 0.72, 0.90, 1.05, 1.15)

    for control, sway_multiplier, pitch_multiplier in zip(
        tail_controls,
        sway_multipliers,
        pitch_multipliers,
    ):
        key_rotation(
            control,
            frame,
            y=tail_pitch * pitch_multiplier,
            z=tail_sway * sway_multiplier,
        )

for control in animated_controls:
    clamp_interpolation(control)
    set_cycles_if_available(control)

# Ajuste automático da altura global:
# o menor ponto dos pés em todo o ciclo ficará a 2 cm do chão. São
# verificados quatro subquadros por quadro para detectar mínimos entre
# as poses principais da passada.
scene.frame_start = FRAME_START
scene.frame_end = FRAME_END
scene.render.fps = FPS

contact_sample_frames = [
    FRAME_START + sample_index / 4.0
    for sample_index in range(int(CYCLE_LENGTH * 4.0))
]

minimum_contact_z = float("inf")
minimum_contact_frame = float(FRAME_START)

for frame_float in contact_sample_frames:
    set_scene_frame_float(scene, frame_float)
    bpy.context.view_layer.update()

    frame_minimum = world_min_z(contact_objects)
    if frame_minimum < minimum_contact_z:
        minimum_contact_z = frame_minimum
        minimum_contact_frame = frame_float

master.location.z += GROUND_CLEARANCE - minimum_contact_z
bpy.context.view_layer.update()

# Confirmação pós-ajuste.
verified_minimum_z = float("inf")
verified_minimum_frame = float(FRAME_START)

for frame_float in contact_sample_frames:
    set_scene_frame_float(scene, frame_float)
    bpy.context.view_layer.update()

    frame_minimum = world_min_z(contact_objects)
    if frame_minimum < verified_minimum_z:
        verified_minimum_z = frame_minimum
        verified_minimum_frame = frame_float

if verified_minimum_z < GROUND_CLEARANCE - 0.001:
    raise RuntimeError(
        "Falha ao ajustar o contato com o chão: "
        f"mínimo Z={verified_minimum_z:.4f}, "
        f"quadro={verified_minimum_frame:.2f}."
    )

# ---------------------------------------------------------------------------
# AMBIENTE, CÂMERA E LUZES.
# ---------------------------------------------------------------------------

ground = create_plane(
    "Preview_Ground",
    size=GROUND_SIZE,
    z=0.0,
    collection=environment_collection,
    material=ground_material,
)

# Câmera e luzes são filhas deste controle. O operador move somente o
# follow rig, enquanto o chão permanece parado e evidencia o deslocamento.
follow_rig = create_empty(
    "CTRL_CAMERA_LIGHT_FOLLOW",
    local_location=(0.0, 0.0, 0.0),
    collection=environment_collection,
    display_type="PLAIN_AXES",
    display_size=0.45,
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
key_light.parent = follow_rig
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
fill_light.parent = follow_rig
fill_light.location = (-4.0, 4.5, 5.8)
look_at(fill_light, (-0.7, 0.0, 1.8))

camera_data = bpy.data.cameras.new("Parasaurolophus_Camera_Data")
camera = bpy.data.objects.new(
    "Parasaurolophus_Camera",
    camera_data,
)
environment_collection.objects.link(camera)
camera.parent = follow_rig
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

controller_started = register_keyboard_runtime()

print("=" * 72)
print("Parasaurolophus reconstruído com sucesso.")
print(f"Versão do gerador: {GENERATOR_VERSION}")
print(f"Objetos de malha do modelo: {len(mesh_objects)}")
print(f"Polígonos aproximados: {polygon_count}")
print(
    "Contato mínimo validado: "
    f"Z={verified_minimum_z:.4f} no quadro "
    f"{verified_minimum_frame:.2f}"
)
print(
    f"Preview_Ground: {GROUND_SIZE:.1f} x {GROUND_SIZE:.1f}, "
    "em Z=0.0000."
)
print(
    "A cena foi limpa integralmente antes da geração; "
    "o script é idempotente."
)
print(
    "Controle por teclado: "
    + (
        "iniciado automaticamente."
        if controller_started
        else (
            "registrado, mas não iniciado automaticamente. "
            "Abra uma Viewport 3D e use F3 > "
            "'Iniciar controle do Parasaurolophus'."
        )
    )
)
print("Segure ↑ para frente, ↓ para ré, HOME para o centro e ESC para sair.")
print("=" * 72)
