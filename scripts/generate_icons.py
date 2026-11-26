#!/usr/bin/env python3
"""Generate crisp 512x512 RGBA rounded-square PNG icons for Loon plugins.

Uses only Python stdlib (zlib/struct/math) so CI and local environments
require zero third-party image dependencies.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIZE = 512


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(pixels[start : start + stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    compressed = zlib.compress(bytes(raw), level=9)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else (hi if v > hi else v)


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = _clamp((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def _sd_rounded_box(px: float, py: float, bx: float, by: float, r: float) -> float:
    qx = abs(px) - bx + r
    qy = abs(py) - by + r
    out_x = max(qx, 0.0)
    out_y = max(qy, 0.0)
    return math.hypot(out_x, out_y) + min(max(qx, qy), 0.0) - r


def _sd_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    pax, pay = px - ax, py - ay
    bax, bay = bx - ax, by - ay
    denom = bax * bax + bay * bay
    h = _clamp((pax * bax + pay * bay) / denom) if denom > 0 else 0.0
    return math.hypot(pax - bax * h, pay - bay * h)


def _sd_star5(px: float, py: float, r: float, rf: float = 0.42) -> float:
    # Exact 5-pointed star SDF (negative inside, positive outside)
    py = -py
    k1x, k1y = 0.809016994375, -0.587785252292
    k2x, k2y = -k1x, k1y
    px = abs(px)
    dot1 = max(k1x * px + k1y * py, 0.0)
    px -= 2.0 * dot1 * k1x
    py -= 2.0 * dot1 * k1y
    dot2 = max(k2x * px + k2y * py, 0.0)
    px -= 2.0 * dot2 * k2x
    py -= 2.0 * dot2 * k2y
    px = abs(px)
    py -= r
    bax = rf * (-k1y)
    bay = rf * k1x - 1.0
    h = _clamp((px * bax + py * bay) / (bax * bax + bay * bay)) * r
    dx = px - bax * h
    dy = py - bay * h
    sign = 1.0 if (py * bax - px * bay) >= 0.0 else -1.0
    return math.hypot(dx, dy) * sign


def _sd_shield(px: float, py: float, w: float, h: float) -> float:
    # Clean symmetric shield with smooth pointed bottom tip
    ax = abs(px)
    if py < -h * 0.12:
        return _sd_rounded_box(px, py + h * 0.25, w, h * 0.52, 24.0)
    t = _clamp((py + h * 0.12) / (h * 0.94))
    half_w = w * max(0.0, 1.0 - t ** 1.75)
    if py >= h * 0.82:
        return math.hypot(ax, py - h * 0.82)
    return max(-h * 0.77 - py, ax - half_w)


def _blend(
    bg: tuple[float, float, float, float],
    fg: tuple[float, float, float, float],
    alpha: float,
) -> tuple[float, float, float, float]:
    a = _clamp(alpha * fg[3])
    inv = 1.0 - a
    out_a = a + bg[3] * inv
    if out_a <= 1e-6:
        return (0.0, 0.0, 0.0, 0.0)
    r = (fg[0] * a + bg[0] * bg[3] * inv) / out_a
    g = (fg[1] * a + bg[1] * bg[3] * inv) / out_a
    b = (fg[2] * a + bg[2] * bg[3] * inv) / out_a
    return (r, g, b, out_a)


def render_icon(
    path: Path,
    top_rgb: tuple[float, float, float],
    bot_rgb: tuple[float, float, float],
    motif: str,
) -> None:
    pixels = bytearray(SIZE * SIZE * 4)
    half = SIZE / 2.0
    corner_r = 112.0
    box_half = 236.0

    for y in range(SIZE):
        py = (y + 0.5) - half
        grad_t = _clamp((y / (SIZE - 1)))
        bg_r = top_rgb[0] * (1.0 - grad_t) + bot_rgb[0] * grad_t
        bg_g = top_rgb[1] * (1.0 - grad_t) + bot_rgb[1] * grad_t
        bg_b = top_rgb[2] * (1.0 - grad_t) + bot_rgb[2] * grad_t

        for x in range(SIZE):
            px = (x + 0.5) - half
            d_box = _sd_rounded_box(px, py, box_half, box_half, corner_r)
            box_alpha = 1.0 - _smoothstep(-1.5, 1.5, d_box)
            if box_alpha <= 0.0:
                continue

            # Subtle radial top-left sheen
            glow = max(0.0, 1.0 - math.hypot(px + 80.0, py + 95.0) / 360.0) * 0.14
            col = (
                _clamp(bg_r + glow),
                _clamp(bg_g + glow),
                _clamp(bg_b + glow),
                box_alpha,
            )

            # Inner hairline border
            border_d = abs(d_box + 3.0) - 2.0
            border_a = (1.0 - _smoothstep(-1.2, 1.2, border_d)) * 0.18
            if border_a > 0.0:
                col = _blend(col, (1.0, 1.0, 1.0, 1.0), border_a)

            if motif == "myanmar":
                # Outer white ring + inner Myanmar star + routing arc
                d_ring = abs(math.hypot(px, py) - 134.0) - 12.0
                ring_a = 1.0 - _smoothstep(-1.5, 1.5, d_ring)
                col = _blend(col, (1.0, 1.0, 1.0, 0.92), ring_a)

                # Three subtle Myanmar flag-inspired accent arcs inside outer ring
                # Gold / Emerald / Crimson soft glow dots at cardinal routing points
                d_star = _sd_star5(px, py + 4.0, 82.0, 0.40)
                star_a = 1.0 - _smoothstep(-1.5, 1.5, d_star)
                col = _blend(col, (1.0, 0.88, 0.36, 0.98), star_a)

                # Two subtle satellite routing nodes
                for nx, ny, nrgb in [(-134.0, 0.0, (0.28, 0.88, 0.56)), (134.0, 0.0, (0.98, 0.42, 0.42))]:
                    nd = math.hypot(px - nx, py - ny) - 18.0
                    na = 1.0 - _smoothstep(-1.5, 1.5, nd)
                    col = _blend(col, (*nrgb, 1.0), na)

            elif motif == "shield":
                d_sh = _sd_shield(px, py, 122.0, 148.0)
                sh_a = 1.0 - _smoothstep(-1.5, 1.5, d_sh)
                col = _blend(col, (1.0, 1.0, 1.0, 0.94), sh_a)
                # Inner checkmark / lock dot
                d_s1 = _sd_segment(px, py, -46.0, 6.0, -10.0, 44.0) - 14.0
                d_s2 = _sd_segment(px, py, -10.0, 44.0, 56.0, -34.0) - 14.0
                chk_a = 1.0 - _smoothstep(-1.5, 1.5, min(d_s1, d_s2))
                col = _blend(col, (top_rgb[0], top_rgb[1], top_rgb[2], 1.0), chk_a)

            elif motif == "pixel":
                # Crossed eye / pixel grid blocked slash
                for gx in (-54.0, 0.0, 54.0):
                    for gy in (-54.0, 0.0, 54.0):
                        gd = _sd_rounded_box(px - gx, py - gy, 18.0, 18.0, 6.0)
                        ga = 1.0 - _smoothstep(-1.5, 1.5, gd)
                        col = _blend(col, (1.0, 1.0, 1.0, 0.86), ga)
                d_slash = _sd_segment(px, py, -110.0, 110.0, 110.0, -110.0) - 16.0
                sl_a = 1.0 - _smoothstep(-1.5, 1.5, d_slash)
                col = _blend(col, (1.0, 0.36, 0.42, 1.0), sl_a)

            elif motif == "ai":
                # 4-point AI spark diamond + subtle orbit ring
                d_ring = abs(math.hypot(px, py) - 138.0) - 9.0
                ra = 1.0 - _smoothstep(-1.5, 1.5, d_ring)
                col = _blend(col, (1.0, 1.0, 1.0, 0.35), ra)
                # Four-point star via scaled diamond distance
                ax, ay = abs(px), abs(py)
                d_spark = (ax ** 0.68 + ay ** 0.68) ** (1.0 / 0.68) - 108.0
                sa = 1.0 - _smoothstep(-2.0, 2.0, d_spark)
                col = _blend(col, (1.0, 1.0, 1.0, 0.96), sa)
                d_core = math.hypot(px, py) - 22.0
                ca = 1.0 - _smoothstep(-1.5, 1.5, d_core)
                col = _blend(col, (0.35, 0.95, 0.85, 1.0), ca)

            idx = (y * SIZE + x) * 4
            pixels[idx] = int(round(_clamp(col[0]) * 255))
            pixels[idx + 1] = int(round(_clamp(col[1]) * 255))
            pixels[idx + 2] = int(round(_clamp(col[2]) * 255))
            pixels[idx + 3] = int(round(_clamp(col[3]) * 255))

    _write_png(path, SIZE, SIZE, pixels)


def main() -> None:
    specs = [
        (ROOT / "icon.png", (0.09, 0.24, 0.48), (0.04, 0.42, 0.44), "myanmar"),
        (ROOT / "assets/icons/myanmar-essential.png", (0.09, 0.24, 0.48), (0.04, 0.42, 0.44), "myanmar"),
        (ROOT / "assets/icons/meta-pixel-mitm.png", (0.20, 0.16, 0.46), (0.36, 0.12, 0.42), "pixel"),
        (ROOT / "assets/icons/telemetry-shield.png", (0.08, 0.34, 0.32), (0.05, 0.20, 0.38), "shield"),
        (ROOT / "assets/icons/google-ai-auth-proxy.png", (0.12, 0.28, 0.56), (0.07, 0.48, 0.52), "ai"),
    ]
    for path, top_rgb, bot_rgb, motif in specs:
        render_icon(path, top_rgb, bot_rgb, motif)
        print(f"Generated {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
