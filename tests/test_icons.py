"""Tests for Apple HIG 1024x1024 icon geometry, sRGB metadata, G^2 squircles, and SVGs."""

from __future__ import annotations

import struct
import sys
import unittest
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_icons  # noqa: E402


def _read_png_meta(path: Path) -> tuple[int, int, int, set[bytes], bytes]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    chunks: set[bytes] = set()
    idat = bytearray()
    width = height = color_type = 0
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        chunks.add(tag)
        if tag == b"IHDR":
            width, height, _, color_type = struct.unpack(">IIBB", payload[:10])
        elif tag == b"IDAT":
            idat.extend(payload)
        pos += 12 + length
    raw = zlib.decompress(bytes(idat))
    return width, height, color_type, chunks, raw


class IconDesignSystemTests(unittest.TestCase):
    NAMES = (
        "myanmar-essential",
        "google-ai-auth-proxy",
        "meta-pixel-mitm",
        "telemetry-shield",
        "youtube-myanmar-enhance",
    )

    def test_unmasked_masters_are_1024_opaque_srgb(self) -> None:
        paths = [ROOT / "icon.png"] + [ROOT / "assets/icons" / f"{n}.png" for n in self.NAMES]
        for path in paths:
            self.assertTrue(path.is_file(), f"Missing {path}")
            w, h, color_type, chunks, _ = _read_png_meta(path)
            self.assertEqual((w, h), (1024, 1024), f"{path} must be 1024x1024")
            self.assertEqual(color_type, 2, f"{path} must be opaque RGB (unmasked square)")
            self.assertIn(b"sRGB", chunks, f"{path} missing sRGB chunk")

    def test_squircle_exports_use_g2_mask_boundaries(self) -> None:
        sd = generate_icons._build_squircle_sd()
        # Corner (0,0) -> (-511.5, -511.5) is outside G^2 squircle; center is well inside;
        # edge midpoint (511.5, 0) is inside flat side of squircle.
        self.assertGreater(sd(-511.5, -511.5), 50.0)
        self.assertLess(sd(0.0, 0.0), -400.0)
        self.assertLess(sd(0.0, 500.0), -10.0)

        for name in self.NAMES:
            path = ROOT / "assets/icons/squircle" / f"{name}.png"
            self.assertTrue(path.is_file(), f"Missing {path}")
            w, h, color_type, chunks, raw = _read_png_meta(path)
            self.assertEqual((w, h), (1024, 1024))
            self.assertEqual(color_type, 6, f"{path} must be RGBA")
            self.assertIn(b"sRGB", chunks)
            stride = 1 + w * 4
            top_left_alpha = raw[4]  # filter byte (1) + RGBA[3]
            center_offset = (512 * stride) + 1 + (512 * 4) + 3
            center_alpha = raw[center_offset]
            self.assertEqual(top_left_alpha, 0, f"{path} top-left corner should be transparent")
            self.assertEqual(center_alpha, 255, f"{path} center should be opaque")

    def test_layered_svgs_are_valid_and_liquid_glass_ready(self) -> None:
        for name in self.NAMES:
            full_svg = ROOT / "assets/icons/svg" / f"{name}.svg"
            fg_svg = ROOT / "assets/icons/svg" / f"{name}-foreground.svg"
            for svg in (full_svg, fg_svg):
                self.assertTrue(svg.is_file(), f"Missing {svg}")
                txt = svg.read_text(encoding="utf-8")
                self.assertNotIn("feDropShadow", txt)
                self.assertNotIn("feGaussianBlur", txt)
                root = ET.fromstring(txt)
                self.assertEqual(root.attrib.get("viewBox"), "0 0 1024 1024")
                ids = {el.attrib.get("id") for el in root.iter() if "id" in el.attrib}
                self.assertIn("foreground", ids)
                if svg == full_svg:
                    self.assertIn("background", ids)


if __name__ == "__main__":
    unittest.main()
