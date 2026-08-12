from __future__ import annotations

from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from faceanim_exporter.exporter import FaceChannelConfig, calculate_sequence_frame, export_face_animation, get_export_range, texture_key, validate_document, validate_integer_fps
from faceanim_exporter.manifest import build_sequence_manifest, parse_filename_suffix, resolve_sequence_file


class Render:
    def __init__(self, fps=60, fps_base=1.0):
        self.fps, self.fps_base = fps, fps_base


class Scene:
    def __init__(self, preview=False, fps=60, fps_base=1.0):
        self.use_preview_range = preview
        self.frame_preview_start, self.frame_preview_end = 1001, 1005
        self.frame_start, self.frame_end = -5, 90
        self.render = Render(fps, fps_base)


class ContractTests(unittest.TestCase):
    def test_sequence_math_preserved(self):
        self.assertEqual(calculate_sequence_frame(1, 0, 2, -1, False), 1)
        self.assertEqual(calculate_sequence_frame(2, 0, 2, 20, False), 22)
        self.assertEqual(calculate_sequence_frame(12, 0, 2, 61, False), 63)
        self.assertEqual(calculate_sequence_frame(3, 0, 2, 0, True), 2)
        with self.assertRaises(ValueError):
            calculate_sequence_frame(1, 0, 2, 1.5, False)

    def test_range_and_fps(self):
        self.assertEqual(get_export_range(Scene(True)), (1001, 1005, "preview"))
        self.assertEqual(get_export_range(Scene(False)), (-5, 90, "scene"))
        self.assertEqual(validate_integer_fps(Scene()), 60)
        with self.assertRaises(ValueError):
            validate_integer_fps(Scene(fps=24, fps_base=1.001))

    def test_texture_key_is_importer_canonical(self):
        self.assertEqual(texture_key("mouth", 1), "mouth/0001")
        self.assertEqual(texture_key("misc_fx", 63), "misc_fx/0063")
        with self.assertRaises(ValueError):
            texture_key("mouth", 0)
        with self.assertRaises(ValueError):
            texture_key("mouth", 10000)


    def test_full_export_streams_change_points_and_restores_frame(self):
        class Box:
            pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for number in range(1, 4):
                (root / f"mouth.{number:04d}.png").write_bytes(b"png")

            user = Box()
            user.frame_start = 1
            user.frame_duration = 3
            user.frame_offset = 0
            user.use_cyclic = False

            image = Box()
            image.source = "SEQUENCE"
            image.filepath = str(root / "mouth.0001.png")

            node = Box()
            node.bl_idname = "ShaderNodeTexImage"
            node.image = image
            node.image_user = user

            class Nodes:
                def get(self, name):
                    return node if name == "FaceTexture" else None

            material = Box()
            material.name = "Face"
            material.use_nodes = True
            material.node_tree = Box()
            material.node_tree.nodes = Nodes()
            slot = Box()
            slot.material = material
            obj = Box()
            obj.material_slots = [slot]

            class Objects(dict):
                pass

            scene = Box()
            scene.objects = Objects({"Mouth": obj})
            scene.use_preview_range = False
            scene.frame_start = 1
            scene.frame_end = 4
            scene.frame_current = 77
            scene.render = Render(60, 1.0)
            scene.faceanim_export = Box()
            scene.faceanim_export.animation_id = "talk"
            scene.faceanim_export.rig_id = "hero"

            offsets = {1: 0, 2: 0, 3: -1, 4: 0}
            def frame_set(frame):
                scene.frame_current = frame
                user.frame_offset = offsets.get(frame, 0)
            scene.frame_set = frame_set

            fake_bpy = types.SimpleNamespace(
                path=types.SimpleNamespace(abspath=lambda value: value),
                context=types.SimpleNamespace(view_layer=types.SimpleNamespace(update=lambda: None)),
            )
            config = FaceChannelConfig("mouth", "Mouth", "Face", "FaceTexture")
            with patch.dict("sys.modules", {"bpy": fake_bpy}):
                document = export_face_animation(scene, [config])

            self.assertEqual(scene.frame_current, 77)
            self.assertEqual(document["tracks"][0]["keys"], [
                {"tick": 0, "texture_key": "mouth/0001"},
                {"tick": 1, "texture_key": "mouth/0002"},
                {"tick": 3, "texture_key": "mouth/0003"},
            ])
            validate_document(document)

    def test_minimal_document_matches_lua_decoder_contract(self):
        document = {
            "schema": "faceanim/1",
            "animation_id": "face",
            "rig_id": "rig",
            "timeline": {"duration_ticks": 2, "fps_num": 60, "fps_den": 1},
            "tracks": [{
                "channel_id": "mouth",
                "property_adapter": "decal_image",
                "keys": [{"tick": 0, "texture_key": "mouth/0001"}, {"tick": 2, "texture_key": "mouth/0002"}],
            }],
        }
        validate_document(document)
        self.assertEqual(set(document), {"schema", "animation_id", "rig_id", "timeline", "tracks"})
        self.assertEqual(set(document["timeline"]), {"duration_ticks", "fps_num", "fps_den"})
        self.assertEqual(set(document["tracks"][0]["keys"][0]), {"tick", "texture_key"})

        document["tracks"][0]["keys"][0]["tick"] = 1
        with self.assertRaisesRegex(ValueError, "tick 0"):
            validate_document(document)


class ManifestTests(unittest.TestCase):
    def make(self, root: Path, names: list[str]) -> Path:
        for name in names:
            (root / name).write_bytes(b"png")
        return root / names[0]

    def test_padding_is_not_part_of_interchange_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make(root, ["texture.1.png", "texture.2.png"])
            manifest = build_sequence_manifest(str(source))
            self.assertEqual(resolve_sequence_file(manifest, 2), 2)
            self.assertEqual(texture_key("misc_fx", resolve_sequence_file(manifest, 2)), "misc_fx/0002")
        self.assertEqual(parse_filename_suffix("texture.0001.png"), ("texture.", 1, ".png"))

    def test_non_one_start_is_preserved_as_file_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make(root, ["mouth.0100.png", "mouth.0101.png"])
            manifest = build_sequence_manifest(str(source))
            self.assertEqual(resolve_sequence_file(manifest, 1), 100)
            self.assertEqual(texture_key("mouth", resolve_sequence_file(manifest, 1)), "mouth/0100")

    def test_missing_duplicate_and_out_of_registry_range_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make(root, ["x.0001.png", "x.0003.png"])
            with self.assertRaisesRegex(ValueError, "missing"):
                build_sequence_manifest(str(source))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make(root, ["x.1.png", "x.01.png"])
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                build_sequence_manifest(str(source))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make(root, ["x.0000.png"])
            with self.assertRaisesRegex(ValueError, "1..9999"):
                build_sequence_manifest(str(source))


if __name__ == "__main__":
    unittest.main()
