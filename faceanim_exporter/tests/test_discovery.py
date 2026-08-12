from __future__ import annotations

import types
import unittest

from faceanim_exporter.discovery import (
    auto_fix_rig_materials_and_drivers,
    discover_rig_objects,
    discover_scene_channels,
    ensure_unique_rig_ids,
    is_descendant_of,
)


class DummyNode:
    def __init__(self, bl_idname="ShaderNodeTexImage", source="SEQUENCE", filepath="path/to/img.png", face_export=None, name="Image Node"):
        self.bl_idname = bl_idname
        self.name = name
        self.image = types.SimpleNamespace(source=source, filepath=filepath)
        self.face_export = face_export

    def get(self, key, default=None):
        if key == "face_export":
            return self.face_export
        return default


class DummyMaterial:
    def __init__(self, name="Mat", use_nodes=True, nodes=None):
        self.name = name
        self.use_nodes = use_nodes
        self.node_tree = types.SimpleNamespace(nodes=nodes or []) if use_nodes else None


class DummyObject:
    def __init__(self, name="Obj", channel_id=None, parent=None, materials=None, obj_type="MESH", extra_props=None):
        self.name = name
        self.parent = parent
        self.type = obj_type
        self.props = {}
        if channel_id is not None:
            self.props["face_channel_id"] = channel_id
        if extra_props:
            self.props.update(extra_props)
        self.material_slots = [types.SimpleNamespace(material=m) for m in (materials or [])]

    def __contains__(self, key):
        return key in self.props

    def __getitem__(self, key):
        return self.props[key]

    def __setitem__(self, key, value):
        self.props[key] = value


class TestDiscovery(unittest.TestCase):
    def test_is_descendant_of(self):
        rig = DummyObject("Rig", obj_type="ARMATURE")
        child = DummyObject("Child", parent=rig)
        grandchild = DummyObject("Grandchild", parent=child)
        other = DummyObject("Other")

        self.assertTrue(is_descendant_of(child, rig))
        self.assertTrue(is_descendant_of(grandchild, rig))
        self.assertFalse(is_descendant_of(other, rig))
        self.assertTrue(is_descendant_of(child, None))

    def test_discover_scene_channels_ready(self):
        node = DummyNode(source="SEQUENCE", filepath="mouth.0001.png")
        mat = DummyMaterial(use_nodes=True, nodes=[node])
        obj = DummyObject("MouthObj", channel_id="mouth", materials=[mat])
        scene = types.SimpleNamespace(objects=[obj])

        results = discover_scene_channels(scene)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].channel_id, "mouth")
        self.assertEqual(results[0].status, "READY")
        self.assertEqual(results[0].object_name, "MouthObj")

    def test_discover_scene_channels_invalid_id(self):
        obj = DummyObject("BadObj", channel_id="BAD-ID!")
        scene = types.SimpleNamespace(objects=[obj])

        results = discover_scene_channels(scene)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "INVALID_CHANNEL_ID")

    def test_discover_scene_channels_no_material(self):
        obj = DummyObject("NoMatObj", channel_id="mouth", materials=[])
        scene = types.SimpleNamespace(objects=[obj])

        results = discover_scene_channels(scene)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "NO_MATERIAL")

    def test_discover_scene_channels_no_sequence_node(self):
        node = DummyNode(source="FILE", filepath="single.png")
        mat = DummyMaterial(use_nodes=True, nodes=[node])
        obj = DummyObject("NoSeqObj", channel_id="mouth", materials=[mat])
        scene = types.SimpleNamespace(objects=[obj])

        results = discover_scene_channels(scene)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "NO_SEQUENCE_NODE")

    def test_discover_scene_channels_ambiguous_node(self):
        node1 = DummyNode(name="Node1", source="SEQUENCE", filepath="a.png")
        node2 = DummyNode(name="Node2", source="SEQUENCE", filepath="b.png")
        mat = DummyMaterial(use_nodes=True, nodes=[node1, node2])
        obj = DummyObject("AmbObj", channel_id="mouth", materials=[mat])
        scene = types.SimpleNamespace(objects=[obj])

        results = discover_scene_channels(scene)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "AMBIGUOUS_NODE")

    def test_discover_scene_channels_disambiguation(self):
        node1 = DummyNode(name="Node1", source="SEQUENCE", filepath="a.png", face_export=True)
        node2 = DummyNode(name="Node2", source="SEQUENCE", filepath="b.png", face_export=False)
        mat = DummyMaterial(use_nodes=True, nodes=[node1, node2])
        obj = DummyObject("DisamObj", channel_id="mouth", materials=[mat])
        scene = types.SimpleNamespace(objects=[obj])

        results = discover_scene_channels(scene)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "READY")
        self.assertEqual(results[0].image_node_name, "Node1")

    def test_duplicate_channel_ids(self):
        nodeA = DummyNode(source="SEQUENCE", filepath="a.png")
        matA = DummyMaterial(name="MatA", use_nodes=True, nodes=[nodeA])
        objA = DummyObject("ObjA", channel_id="mouth", materials=[matA])

        nodeB = DummyNode(source="SEQUENCE", filepath="b.png")
        matB = DummyMaterial(name="MatB", use_nodes=True, nodes=[nodeB])
        objB = DummyObject("ObjB", channel_id="mouth", materials=[matB])

        scene = types.SimpleNamespace(objects=[objA, objB])
        results = discover_scene_channels(scene)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].status, "DUPLICATE_CHANNEL_ID")
        self.assertEqual(results[1].status, "DUPLICATE_CHANNEL_ID")

    def test_target_rig_filtering(self):
        rig1 = DummyObject("Rig1", obj_type="ARMATURE")
        rig2 = DummyObject("Rig2", obj_type="ARMATURE")

        node1 = DummyNode(source="SEQUENCE", filepath="a.png")
        mat1 = DummyMaterial(use_nodes=True, nodes=[node1])
        child1 = DummyObject("Child1", channel_id="eye_l", parent=rig1, materials=[mat1])

        node2 = DummyNode(source="SEQUENCE", filepath="b.png")
        mat2 = DummyMaterial(use_nodes=True, nodes=[node2])
        child2 = DummyObject("Child2", channel_id="eye_r", parent=rig2, materials=[mat2])

        scene = types.SimpleNamespace(objects=[child1, child2])

        res1 = discover_scene_channels(scene, target_rig=rig1)
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0].object_name, "Child1")

        res2 = discover_scene_channels(scene, target_rig=rig2)
        self.assertEqual(len(res2), 1)
        self.assertEqual(res2[0].object_name, "Child2")

    def test_ensure_unique_rig_ids(self):
        obj1 = DummyObject("Rig1", extra_props={"rig_id": "hero"})
        obj2 = DummyObject("Rig2", extra_props={"rig_id": "hero"})
        scene = types.SimpleNamespace(objects=[obj1, obj2])

        ensure_unique_rig_ids(scene)
        self.assertEqual(obj1["rig_id"], "hero")
        self.assertEqual(obj2["rig_id"], "hero_1")

    def test_discover_rig_objects(self):
        rig1 = DummyObject("ArmatureRig", obj_type="ARMATURE")
        rig2 = DummyObject("PropRig", extra_props={"rig_id": "custom"})
        scene = types.SimpleNamespace(objects=[rig1, rig2])

        discovered = discover_rig_objects(scene)
        self.assertEqual(len(discovered), 2)
        self.assertIn(rig1, discovered)
        self.assertIn(rig2, discovered)


if __name__ == "__main__":
    unittest.main()
