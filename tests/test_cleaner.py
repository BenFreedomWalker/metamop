import tempfile
import unittest
from pathlib import Path

from PIL import Image, PngImagePlugin

from metamop import clean_image


class CleanerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / "cleaned"

    def tearDown(self):
        self.temp.cleanup()

    def test_png_text_metadata_is_removed(self):
        source = self.root / "with_metadata.png"
        info = PngImagePlugin.PngInfo()
        info.add_text("Comment", "private test note")
        Image.new("RGB", (8, 8), "red").save(source, pnginfo=info)

        result = clean_image(source, self.output)

        with Image.open(result) as cleaned:
            self.assertNotIn("Comment", cleaned.info)
        self.assertTrue(source.exists())

    def test_jpeg_exif_is_removed_and_source_is_unchanged(self):
        source = self.root / "with_exif.jpg"
        exif = Image.Exif()
        exif[270] = "private test description"
        Image.new("RGB", (16, 12), "blue").save(source, exif=exif, quality=100)
        original_bytes = source.read_bytes()

        result = clean_image(source, self.output)

        with Image.open(result) as cleaned:
            self.assertEqual(len(cleaned.getexif()), 0)
        self.assertEqual(source.read_bytes(), original_bytes)

    def test_existing_output_is_not_overwritten(self):
        source = self.root / "sample.bmp"
        Image.new("RGB", (4, 4), "green").save(source)
        self.output.mkdir()
        existing = self.output / source.name
        existing.write_bytes(b"keep this file")

        result = clean_image(source, self.output)

        self.assertEqual(existing.read_bytes(), b"keep this file")
        self.assertEqual(result.name, "sample_1.bmp")

    def test_animated_images_are_skipped(self):
        source = self.root / "animated.gif"
        frames = [Image.new("RGB", (4, 4), color) for color in ("red", "blue")]
        frames[0].save(source, save_all=True, append_images=frames[1:], duration=100, loop=0)

        with self.assertRaisesRegex(ValueError, "Animated or multi-page"):
            clean_image(source, self.output)


if __name__ == "__main__":
    unittest.main()
