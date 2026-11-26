#!/usr/bin/env python3
"""Generate Apple HIG-compliant 1024x1024 icon assets and layered vector SVGs.

Architecture:
1. Unmasked Square Masters (`icon.png`, `assets/icons/*.png`):
   - 1024x1024 sRGB PNG, full-bleed background, zero pre-rounded corners,
     zero baked drop shadows/bevels/glows. Ready for Loon / iOS / macOS
     hardware-concentric continuous-curvature masking and Liquid Glass.
2. Apple G^2 Continuous-Curvature Squircle Exports (`assets/icons/squircle/*.png`):
   - 1024x1024 RGBA sRGB PNG clipped to the exact Figma/Apple G^2 squircle
     (corner radius = 22.37% of width, corner smoothing = 60%) for web/README.
3. Vector Layered SVGs (`assets/icons/svg/*.svg`):
   - 1024x1024 vector masters separating `<g id="background">` and `<g id="foreground">`,
     plus standalone `<name>-foreground.svg` for Apple Icon Composer (iOS 26+).
"""

from __future__ import annotations

import argparse
import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIZE = 1024
HALF = SIZE / 2.0
PRIMARY_CIRCLE_R = SIZE * 0.40  # 80% diameter = 819.2 px -> radius 409.6 px
SQUIRCLE_RADIUS_RATIO = 0.2237
SQUIRCLE_SMOOTHING = 0.60


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else (hi if v > hi else v)


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = _clamp((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def _hex_to_rgb01(hex_str: str) -> tuple[float, float, float]:
    h = hex_str.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _write_png(path: Path, width: int, height: int, pixels: bytearray, rgba: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    channels = 4 if rgba else 3
    color_type = 6 if rgba else 2
    stride = width * channels
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(pixels[start : start + stride])

    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    srgb = struct.pack(">B", 0)
    gama = struct.pack(">I", 45455)
    compressed = zlib.compress(bytes(raw), level=6)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"sRGB", srgb)
        + _png_chunk(b"gAMA", gama)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def squircle_corner_params(
    size: float = SIZE,
    radius_ratio: float = SQUIRCLE_RADIUS_RATIO,
    smoothing: float = SQUIRCLE_SMOOTHING,
) -> dict[str, float]:
    """Compute exact Apple/Figma G^2 continuous-curvature corner geometry."""
    r = size * radius_ratio
    p = min((1.0 + smoothing) * r, size / 2.0)
    arc_measure_deg = 90.0 * (1.0 - smoothing)
    arc_measure = math.radians(arc_measure_deg)
    arc_section_length = math.sin(arc_measure / 2.0) * r * math.sqrt(2.0)
    alpha = math.radians((90.0 - arc_measure_deg) / 2.0)
    p3_to_p4 = r * math.tan(alpha / 2.0)
    beta = math.radians(45.0 * smoothing)
    c = p3_to_p4 * math.cos(beta)
    d = c * math.tan(beta)
    b = (p - arc_section_length - c - d) / 3.0
    a = 2.0 * b
    return {
        "r": r,
        "p": p,
        "a": a,
        "b": b,
        "c": c,
        "d": d,
        "arc_section_length": arc_section_length,
        "size": size,
    }


def squircle_svg_path(
    size: float = SIZE,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    radius_ratio: float = SQUIRCLE_RADIUS_RATIO,
    smoothing: float = SQUIRCLE_SMOOTHING,
) -> str:
    """Return an SVG path string matching Figma/Apple G^2 continuous curvature."""
    par = squircle_corner_params(size, radius_ratio, smoothing)
    r = par["r"]
    p = par["p"]
    a = par["a"]
    b = par["b"]
    c = par["c"]
    d = par["d"]

    w = size
    h = size
    tr_p0 = (w - p, 0.0)
    tr_c1 = (w - (p - a), 0.0)
    tr_c2 = (w - (p - a - b), 0.0)
    tr_p1 = (w - (p - a - b - c), d)
    tr_arc_end = (w - d, p - a - b - c)
    tr_c3 = (w, p - a - b)
    tr_c4 = (w, p - a)
    tr_p2 = (w, p)

    br_p0 = (w, h - p)
    br_c1 = (w, h - (p - a))
    br_c2 = (w, h - (p - a - b))
    br_p1 = (w - d, h - (p - a - b - c))
    br_arc_end = (w - (p - a - b - c), h - d)
    br_c3 = (w - (p - a - b), h)
    br_c4 = (w - (p - a), h)
    br_p2 = (w - p, h)

    bl_p0 = (p, h)
    bl_c1 = (p - a, h)
    bl_c2 = (p - a - b, h)
    bl_p1 = (p - a - b - c, h - d)
    bl_arc_end = (d, h - (p - a - b - c))
    bl_c3 = (0.0, h - (p - a - b))
    bl_c4 = (0.0, h - (p - a))
    bl_p2 = (0.0, h - p)

    tl_p0 = (0.0, p)
    tl_c1 = (0.0, p - a)
    tl_c2 = (0.0, p - a - b)
    tl_p1 = (d, p - a - b - c)
    tl_arc_end = (p - a - b - c, d)
    tl_c3 = (p - a - b, 0.0)
    tl_c4 = (p - a, 0.0)
    tl_p2 = (p, 0.0)

    def pt(xy: tuple[float, float]) -> str:
        return f"{xy[0] + offset_x:.3f} {xy[1] + offset_y:.3f}"

    cmds = [
        f"M {pt(tr_p0)}",
        f"C {pt(tr_c1)}, {pt(tr_c2)}, {pt(tr_p1)}",
        f"A {r:.3f} {r:.3f} 0 0 1 {pt(tr_arc_end)}",
        f"C {pt(tr_c3)}, {pt(tr_c4)}, {pt(tr_p2)}",
        f"L {pt(br_p0)}",
        f"C {pt(br_c1)}, {pt(br_c2)}, {pt(br_p1)}",
        f"A {r:.3f} {r:.3f} 0 0 1 {pt(br_arc_end)}",
        f"C {pt(br_c3)}, {pt(br_c4)}, {pt(br_p2)}",
        f"L {pt(bl_p0)}",
        f"C {pt(bl_c1)}, {pt(bl_c2)}, {pt(bl_p1)}",
        f"A {r:.3f} {r:.3f} 0 0 1 {pt(bl_arc_end)}",
        f"C {pt(bl_c3)}, {pt(bl_c4)}, {pt(bl_p2)}",
        f"L {pt(tl_p0)}",
        f"C {pt(tl_c1)}, {pt(tl_c2)}, {pt(tl_p1)}",
        f"A {r:.3f} {r:.3f} 0 0 1 {pt(tl_arc_end)}",
        f"C {pt(tl_c3)}, {pt(tl_c4)}, {pt(tl_p2)}",
        "Z",
    ]
    return " ".join(cmds)


def _eval_cubic(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    u = 1.0 - t
    u2 = u * u
    t2 = t * t
    return (
        u2 * u * p0[0] + 3.0 * u2 * t * p1[0] + 3.0 * u * t2 * p2[0] + t2 * t * p3[0],
        u2 * u * p0[1] + 3.0 * u2 * t * p1[1] + 3.0 * u * t2 * p2[1] + t2 * t * p3[1],
    )


def _sample_squircle_quadrant(
    size: float = SIZE,
    radius_ratio: float = SQUIRCLE_RADIUS_RATIO,
    smoothing: float = SQUIRCLE_SMOOTHING,
    steps: int = 96,
) -> tuple[float, list[tuple[float, float]]]:
    """Sample top-right quadrant boundary centered around (0, 0) in first quadrant (+x, +y)."""
    par = squircle_corner_params(size, radius_ratio, smoothing)
    half = size / 2.0
    r = par["r"]
    p = par["p"]
    a = par["a"]
    b = par["b"]
    c = par["c"]
    d = par["d"]

    def to_q(cx: float, cy: float) -> tuple[float, float]:
        return (cx - half, half - cy)

    w = size
    p0 = to_q(w - p, 0.0)
    c1 = to_q(w - (p - a), 0.0)
    c2 = to_q(w - (p - a - b), 0.0)
    p1 = to_q(w - (p - a - b - c), d)
    arc_end = to_q(w - d, p - a - b - c)
    c3 = to_q(w, p - a - b)
    c4 = to_q(w, p - a)
    p2 = to_q(w, p)

    pts: list[tuple[float, float]] = []
    for i in range(steps):
        pts.append(_eval_cubic(p0, c1, c2, p1, i / steps))
    cx_arc, cy_arc = half - r, half - r
    ang0 = math.atan2(p1[1] - cy_arc, p1[0] - cx_arc)
    ang1 = math.atan2(arc_end[1] - cy_arc, arc_end[0] - cx_arc)
    for i in range(steps):
        t = i / steps
        ang = ang0 + (ang1 - ang0) * t
        pts.append((cx_arc + r * math.cos(ang), cy_arc + r * math.sin(ang)))
    for i in range(steps + 1):
        pts.append(_eval_cubic(arc_end, c3, c4, p2, i / steps))
    return half - p, pts


def _build_squircle_sd(
    size: float = SIZE,
    radius_ratio: float = SQUIRCLE_RADIUS_RATIO,
    smoothing: float = SQUIRCLE_SMOOTHING,
):
    """Return an O(1)-fast exact SDF closure for the G^2 continuous-curvature squircle."""
    flat_limit, pts = _sample_squircle_quadrant(size, radius_ratio, smoothing, steps=72)
    half = size / 2.0
    segs: list[tuple[float, float, float, float, float]] = []
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        if l2 > 1e-12:
            segs.append((ax, ay, dx, dy, 1.0 / l2))

    n_segs = len(segs)
    ang_bins = 256
    seg_angles = [
        math.atan2(s[1] - flat_limit + s[3] * 0.5, s[0] - flat_limit + s[2] * 0.5)
        for s in segs
    ]
    lut: list[int] = []
    for k in range(ang_bins + 1):
        th = (math.pi / 2.0) * (1.0 - k / ang_bins)
        best_i = 0
        best_diff = 999.0
        for i, sa in enumerate(seg_angles):
            diff = abs(sa - th)
            if diff < best_diff:
                best_diff = diff
                best_i = i
        lut.append(best_i)

    def sd(px: float, py: float) -> float:
        qx, qy = abs(px), abs(py)
        if qx <= flat_limit and qy <= flat_limit:
            return max(qx, qy) - half
        if qx <= flat_limit:
            return qy - half
        if qy <= flat_limit:
            return qx - half

        th = math.atan2(qy - flat_limit, qx - flat_limit)
        b_idx = int((1.0 - th / (math.pi / 2.0)) * ang_bins)
        b_idx = 0 if b_idx < 0 else (ang_bins if b_idx > ang_bins else b_idx)
        center = lut[b_idx]
        lo = max(0, center - 14)
        hi = min(n_segs, center + 15)

        min_d2 = 1e18
        best_cross = 1.0
        for i in range(lo, hi):
            ax, ay, dx, dy, inv_l2 = segs[i]
            pax, pay = qx - ax, qy - ay
            h = (pax * dx + pay * dy) * inv_l2
            if h < 0.0:
                h = 0.0
            elif h > 1.0:
                h = 1.0
            rx = pax - dx * h
            ry = pay - dy * h
            d2 = rx * rx + ry * ry
            if d2 < min_d2:
                min_d2 = d2
                best_cross = pax * dy - pay * dx
        dist = math.sqrt(min_d2)
        return -dist if best_cross > 0.0 else dist

    return sd


def _precompute_squircle_alpha() -> bytearray:
    """Compute the 1024x1024 G^2 squircle alpha byte grid ONCE (exploiting 4-way symmetry)."""
    squircle_sd = _build_squircle_sd()
    alpha = bytearray(SIZE * SIZE)
    flat = SIZE * 0.5 - SIZE * SQUIRCLE_RADIUS_RATIO * (1.0 + SQUIRCLE_SMOOTHING) - 4.0
    for y in range(SIZE // 2):
        py = (y + 0.5) - HALF
        y_mir = SIZE - 1 - y
        row_a = y * SIZE
        row_b = y_mir * SIZE
        if abs(py) <= flat:
            alpha[row_a : row_a + SIZE] = b"\xff" * SIZE
            alpha[row_b : row_b + SIZE] = b"\xff" * SIZE
            continue
        for x in range(SIZE // 2):
            px = (x + 0.5) - HALF
            if abs(px) <= flat:
                a8 = 255
            else:
                a8 = int(round((1.0 - _smoothstep(-1.1, 1.1, squircle_sd(px, py))) * 255))
            x_mir = SIZE - 1 - x
            alpha[row_a + x] = a8
            alpha[row_a + x_mir] = a8
            alpha[row_b + x] = a8
            alpha[row_b + x_mir] = a8
    return alpha


def _sd_circle(px: float, py: float, r: float) -> float:
    return math.hypot(px, py) - r


def _sd_ring(px: float, py: float, r_mid: float, half_thick: float) -> float:
    return abs(math.hypot(px, py) - r_mid) - half_thick


def _sd_arc(px: float, py: float, r_mid: float, half_thick: float, center_deg: float, half_span_deg: float) -> float:
    """SDF of a circular arc with round caps centered at `center_deg`."""
    ang = math.atan2(py, px)
    c_rad = math.radians(center_deg)
    span_rad = math.radians(half_span_deg)
    da = (ang - c_rad + math.pi) % (2.0 * math.pi) - math.pi
    if abs(da) <= span_rad:
        return abs(math.hypot(px, py) - r_mid) - half_thick
    end_ang = c_rad + (span_rad if da > 0.0 else -span_rad)
    ex, ey = r_mid * math.cos(end_ang), r_mid * math.sin(end_ang)
    return math.hypot(px - ex, py - ey) - half_thick


def _sd_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    pax, pay = px - ax, py - ay
    bax, bay = bx - ax, by - ay
    denom = bax * bax + bay * bay
    h = _clamp((pax * bax + pay * bay) / denom) if denom > 0 else 0.0
    return math.hypot(pax - bax * h, pay - bay * h)


def _sd_rounded_box(px: float, py: float, bx: float, by: float, r: float) -> float:
    qx = abs(px) - bx + r
    qy = abs(py) - by + r
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r


def _eval_bezier_poly(
    segments: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]],
    steps: int = 40,
) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for p0, c1, c2, p1 in segments:
        for i in range(steps):
            pts.append(_eval_cubic(p0, c1, c2, p1, i / steps))
    return pts


def _sd_polygon(px: float, py: float, poly: list[tuple[float, float]]) -> float:
    """Exact signed distance to a closed polygon (negative inside)."""
    n = len(poly)
    d = 1e18
    inside = False
    j = n - 1
    for i in range(n):
        ix, iy = poly[i]
        jx, jy = poly[j]
        ex, ey = jx - ix, jy - iy
        wx, wy = px - ix, py - iy
        denom = ex * ex + ey * ey
        t = _clamp((wx * ex + wy * ey) / denom) if denom > 0 else 0.0
        bx = wx - ex * t
        by = wy - ey * t
        d = min(d, bx * bx + by * by)
        if ((iy > py) != (jy > py)) and (px < (jx - ix) * (py - iy) / (jy - iy + 1e-18) + ix):
            inside = not inside
        j = i
    dist = math.sqrt(d)
    return -dist if inside else dist


def _sd_octagon(px: float, py: float, r: float) -> float:
    """Exact signed distance to a regular octagon with apothem `r`."""
    kx, ky, kz = -0.9238795325, 0.3826834323, 0.4142135623
    x, y = abs(px), abs(py)
    dot1 = min(kx * x + ky * y, 0.0)
    x -= 2.0 * dot1 * kx
    y -= 2.0 * dot1 * ky
    dot2 = min(-kx * x + ky * y, 0.0)
    x -= 2.0 * dot2 * (-kx)
    y -= 2.0 * dot2 * ky
    x -= _clamp(x, -kz * r, kz * r)
    y -= r
    d = math.hypot(x, y)
    return -d if y < 0.0 else d


def _build_shield_poly() -> list[tuple[float, float]]:
    segs = [
        ((0.0, -328.0), (140.0, -328.0), (242.0, -312.0), (268.0, -254.0)),
        ((268.0, -254.0), (284.0, -214.0), (282.0, -90.0), (272.0, 26.0)),
        ((272.0, 26.0), (254.0, 178.0), (144.0, 286.0), (18.0, 338.0)),
        ((18.0, 338.0), (6.0, 343.0), (-6.0, 343.0), (-18.0, 338.0)),
        ((-18.0, 338.0), (-144.0, 286.0), (-254.0, 178.0), (-272.0, 26.0)),
        ((-272.0, 26.0), (-282.0, -90.0), (-284.0, -214.0), (-268.0, -254.0)),
        ((-268.0, -254.0), (-242.0, -312.0), (-140.0, -328.0), (0.0, -328.0)),
    ]
    return _eval_bezier_poly(segs, steps=36)


def _build_astroid_poly(radius: float = 236.0, round_tip: float = 14.0) -> list[tuple[float, float]]:
    k = 56.0
    r = radius - round_tip
    segs = [
        ((0.0, -r), (12.0, -r), (28.0, -k), (k, -28.0)),
        ((k, -28.0), (88.0, -14.0), (r, -12.0), (r, 0.0)),
        ((r, 0.0), (r, 12.0), (88.0, 14.0), (k, 28.0)),
        ((k, 28.0), (28.0, k), (12.0, r), (0.0, r)),
        ((0.0, r), (-12.0, r), (-28.0, k), (-k, 28.0)),
        ((-k, 28.0), (-88.0, 14.0), (-r, 12.0), (-r, 0.0)),
        ((-r, 0.0), (-r, -12.0), (-88.0, -14.0), (-k, -28.0)),
        ((-k, -28.0), (-28.0, -k), (-12.0, -r), (0.0, -r)),
    ]
    return _eval_bezier_poly(segs, steps=28)


def _build_star_poly(cx: float, cy: float, r_outer: float, r_inner: float) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for i in range(10):
        ang = -math.pi / 2.0 + i * math.pi / 5.0
        r = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def _build_balloon_poly() -> list[tuple[float, float]]:
    segs = [
        ((0.0, -328.0), (148.0, -328.0), (246.0, -230.0), (246.0, -104.0)),
        ((246.0, -104.0), (246.0, 12.0), (166.0, 102.0), (112.0, 154.0)),
        ((112.0, 154.0), (50.0, 164.0), (-50.0, 164.0), (-112.0, 154.0)),
        ((-112.0, 154.0), (-166.0, 102.0), (-246.0, 12.0), (-246.0, -104.0)),
        ((-246.0, -104.0), (-246.0, -230.0), (-148.0, -328.0), (0.0, -328.0)),
    ]
    return _eval_bezier_poly(segs, steps=40)


def _build_flame_poly() -> list[tuple[float, float]]:
    segs = [
        ((0.0, 206.0), (38.0, 240.0), (52.0, 274.0), (34.0, 308.0)),
        ((34.0, 308.0), (18.0, 332.0), (-18.0, 332.0), (-34.0, 308.0)),
        ((-34.0, 308.0), (-52.0, 274.0), (-38.0, 240.0), (0.0, 206.0)),
    ]
    return _eval_bezier_poly(segs, steps=24)


def _build_balloon_ribs() -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    left_rib = _eval_bezier_poly(
        [(( -16.0, -312.0), (-118.0, -242.0), (-146.0, -112.0), (-78.0, 144.0))],
        steps=48,
    )
    right_rib = _eval_bezier_poly(
        [((16.0, -312.0), (118.0, -242.0), (146.0, -112.0), (78.0, 144.0))],
        steps=48,
    )
    return left_rib, right_rib


BALLOON_STAR_POLY = _build_star_poly(0.0, -110.0, 92.0, 38.0)
BALLOON_POLY = _build_balloon_poly()
FLAME_POLY = _build_flame_poly()
BALLOON_LEFT_RIB, BALLOON_RIGHT_RIB = _build_balloon_ribs()
SHIELD_POLY = _build_shield_poly()
ASTROID_POLY = _build_astroid_poly()
PLAY_TRI_POLY = [(-56.0, -112.0), (84.0, -34.0), (-56.0, 44.0)]
CENTER_PLAY_POLY = [(-52.0, -86.0), (86.0, 0.0), (-52.0, 86.0)]
BOLT_POLY = [
    (44.0, -214.0),
    (-112.0, 18.0),
    (-6.0, 18.0),
    (-44.0, 214.0),
    (112.0, -18.0),
    (6.0, -18.0),
]
MAPLE_POLY = [
    (x * 0.78, y * 0.78)
    for x, y in [
        (0.0, -158.0), (26.0, -110.0), (54.0, -120.0), (42.0, -52.0),
        (96.0, -90.0), (96.0, -56.0), (144.0, -54.0), (126.0, -18.0),
        (148.0, 6.0), (72.0, 56.0), (84.0, 86.0), (12.0, 74.0),
        (14.0, 146.0), (-14.0, 146.0), (-12.0, 74.0), (-84.0, 86.0),
        (-72.0, 56.0), (-148.0, 6.0), (-126.0, -18.0), (-144.0, -54.0),
        (-96.0, -56.0), (-96.0, -90.0), (-42.0, -52.0), (-54.0, -120.0),
        (-26.0, -110.0),
    ]
]
HK_PETAL_CENTERS = [
    (math.cos(math.radians(-90.0 + i * 72.0)), math.sin(math.radians(-90.0 + i * 72.0)))
    for i in range(5)
]


def _blend_rgb(
    bg: tuple[float, float, float],
    fg: tuple[float, float, float],
    alpha: float,
) -> tuple[float, float, float]:
    a = _clamp(alpha)
    inv = 1.0 - a
    return (fg[0] * a + bg[0] * inv, fg[1] * a + bg[1] * inv, fg[2] * a + bg[2] * inv)


def _svg_star_points(cx: float, cy: float, r_outer: float, r_inner: float) -> str:
    pts = []
    for i in range(10):
        ang = -math.pi / 2.0 + i * math.pi / 5.0
        r = r_outer if i % 2 == 0 else r_inner
        pts.append(f"{cx + r * math.cos(ang):.2f},{cy + r * math.sin(ang):.2f}")
    return " ".join(pts)


def _svg_arc_path(cx: float, cy: float, r: float, start_deg: float, end_deg: float) -> str:
    a0, a1 = math.radians(start_deg), math.radians(end_deg)
    x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
    x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
    large = 1 if abs(end_deg - start_deg) > 180.0 else 0
    return f"M {x0:.2f} {y0:.2f} A {r:.2f} {r:.2f} 0 {large} 1 {x1:.2f} {y1:.2f}"


def _svg_poly_path(poly: list[tuple[float, float]], cx: float = HALF, cy: float = HALF) -> str:
    pts = [f"{x + cx:.2f} {y + cy:.2f}" for x, y in poly]
    return "M " + " L ".join(pts) + " Z"


def _write_svgs(
    name: str,
    top_hex: str,
    bot_hex: str,
    fg_elements_color: list[str],
    fg_elements_mono: list[str],
    defs_extra: list[str] | None = None,
) -> None:
    svg_dir = ROOT / "assets/icons/svg"
    svg_dir.mkdir(parents=True, exist_ok=True)
    defs_block = "\n".join(defs_extra or [])

    full_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}">
  <defs>
    <linearGradient id="bg-grad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{top_hex}"/>
      <stop offset="100%" stop-color="{bot_hex}"/>
    </linearGradient>
{defs_block}
  </defs>
  <g id="background">
    <rect x="0" y="0" width="{SIZE}" height="{SIZE}" fill="url(#bg-grad)"/>
  </g>
  <g id="foreground">
    {"".join(fg_elements_color)}
  </g>
</svg>
"""
    (svg_dir / f"{name}.svg").write_text(full_svg, encoding="utf-8")

    fg_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}">
  <defs>
{defs_block}
  </defs>
  <g id="foreground">
    {"".join(fg_elements_mono)}
  </g>
</svg>
"""
    (svg_dir / f"{name}-foreground.svg").write_text(fg_svg, encoding="utf-8")


def write_grid_overlay_svg() -> None:
    """Write the Apple Icon Grid & G^2 Squircle reference SVG."""
    svg_dir = ROOT / "assets/icons/svg"
    svg_dir.mkdir(parents=True, exist_ok=True)
    sq_path = squircle_svg_path(SIZE)
    inner_sq_path = squircle_svg_path(SIZE * 0.72, offset_x=SIZE * 0.14, offset_y=SIZE * 0.14)
    grid_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}">
  <rect x="0" y="0" width="{SIZE}" height="{SIZE}" fill="#0F172A"/>
  <path d="{sq_path}" fill="#1E293B" stroke="#38BDF8" stroke-width="4"/>
  <circle cx="512" cy="512" r="{PRIMARY_CIRCLE_R:.2f}" fill="none" stroke="#FBBF24" stroke-width="3" stroke-dasharray="12 10"/>
  <path d="{inner_sq_path}" fill="none" stroke="#94A3B8" stroke-width="2" stroke-dasharray="8 8"/>
  <circle cx="512" cy="512" r="{SIZE * 0.26:.2f}" fill="none" stroke="#94A3B8" stroke-width="2" stroke-dasharray="8 8"/>
  <line x1="512" y1="0" x2="512" y2="1024" stroke="#475569" stroke-width="2"/>
  <line x1="0" y1="512" x2="1024" y2="512" stroke="#475569" stroke-width="2"/>
  <line x1="0" y1="0" x2="1024" y2="1024" stroke="#334155" stroke-width="2"/>
  <line x1="1024" y1="0" x2="0" y2="1024" stroke="#334155" stroke-width="2"/>
</svg>
"""
    (svg_dir / "apple-icon-grid.svg").write_text(grid_svg, encoding="utf-8")


def _sd_polyline(px: float, py: float, pts: list[tuple[float, float]]) -> float:
    min_d2 = 1e18
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx, dy = bx - ax, by - ay
        denom = dx * dx + dy * dy
        if denom <= 1e-12:
            continue
        t = _clamp(((px - ax) * dx + (py - ay) * dy) / denom)
        rx = px - (ax + dx * t)
        ry = py - (ay + dy * t)
        d2 = rx * rx + ry * ry
        if d2 < min_d2:
            min_d2 = d2
    return math.sqrt(min_d2)


def _flag_medallion_color(
    flag: str, px: float, py: float, bg: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Render a crisp circular r=244 flag disc framed by a silver-slate rim inside r<=272."""
    r = math.hypot(px, py)
    disc_r = 244.0
    outer_rim_r = 266.0
    white = _hex_to_rgb01("#F8FAFC")
    rim_col = _hex_to_rgb01("#CBD5E1")
    red = _hex_to_rgb01("#DC2626")
    crimson = _hex_to_rgb01("#E11D48")
    navy = _hex_to_rgb01("#1E3A8A")
    cobalt = _hex_to_rgb01("#1D4ED8")
    gold = _hex_to_rgb01("#FACC15")
    dark = _hex_to_rgb01("#18181B")

    # Outer bezel ring
    col = bg
    rim_a = 1.0 - _smoothstep(-1.1, 1.1, max(r - outer_rim_r, disc_r - 2.0 - r))
    if rim_a > 0.0:
        col = _blend_rgb(col, rim_col, rim_a * 0.72)

    disc_a = 1.0 - _smoothstep(-1.1, 1.1, r - disc_r)
    if disc_a <= 0.0:
        return col

    fc = white
    if flag == "sg":
        # Red upper half, white lower half, crisp white crescent & 5 stars in upper-left
        half_a = 1.0 - _smoothstep(-1.1, 1.1, py)
        fc = _blend_rgb(white, crimson, half_a)
        d_outer = math.hypot(px + 68.0, py + 94.0) - 56.0
        d_inner = math.hypot(px + 42.0, py + 94.0) - 52.0
        cresc_a = 1.0 - _smoothstep(-1.1, 1.1, max(d_outer, -d_inner))
        fc = _blend_rgb(fc, white, cresc_a)
        for sx, sy in ((-38.0, -124.0), (-14.0, -104.0), (-24.0, -76.0), (-54.0, -76.0), (-64.0, -104.0)):
            sa = 1.0 - _smoothstep(-1.1, 1.1, math.hypot(px - sx, py - sy) - 10.5)
            if sa > 0.0:
                fc = _blend_rgb(fc, white, sa)
    elif flag == "us":
        stripe_idx = math.floor((py + disc_r) / (2.0 * disc_r / 9.0))
        fc = red if (stripe_idx % 2 == 0) else white
        canton_a = 1.0 - _smoothstep(-1.1, 1.1, max(px - 10.0, py - 10.0))
        if canton_a > 0.0:
            fc = _blend_rgb(fc, navy, canton_a)
            if px <= 8.0 and py <= 8.0:
                for gx in (-145.0, -95.0, -45.0):
                    for gy in (-145.0, -95.0, -45.0):
                        sa = 1.0 - _smoothstep(-1.1, 1.1, math.hypot(px - gx, py - gy) - 10.0)
                        if sa > 0.0:
                            fc = _blend_rgb(fc, white, sa)
    elif flag == "jp":
        sun_a = 1.0 - _smoothstep(-1.1, 1.1, r - 106.0)
        fc = _blend_rgb(white, red, sun_a)
    elif flag == "hk":
        fc = crimson
        for cx, cy in HK_PETAL_CENTERS:
            px0, py0 = cx * 62.0, cy * 62.0
            pa = 1.0 - _smoothstep(-1.1, 1.1, math.hypot(px - px0, py - py0) - 48.0)
            if pa > 0.0:
                fc = _blend_rgb(fc, white, pa)
        center_a = 1.0 - _smoothstep(-1.1, 1.1, r - 20.0)
        if center_a > 0.0:
            fc = _blend_rgb(fc, crimson, center_a * 0.85)
    elif flag == "kr":
        fc = white
        tae_r = 96.0
        ang_rot = (px * 0.8 + py * 0.6)
        perp = (-px * 0.6 + py * 0.8)
        top_half = 1.0 - _smoothstep(-1.1, 1.1, perp)
        tc = _blend_rgb(cobalt, red, top_half)
        u_a = 1.0 - _smoothstep(-1.1, 1.1, math.hypot(px - 38.4, py + 28.8) - tae_r * 0.5)
        l_a = 1.0 - _smoothstep(-1.1, 1.1, math.hypot(px + 38.4, py - 28.8) - tae_r * 0.5)
        _ = ang_rot
        tc = _blend_rgb(tc, red, u_a)
        tc = _blend_rgb(tc, cobalt, l_a)
        tae_a = 1.0 - _smoothstep(-1.1, 1.1, r - tae_r)
        if tae_a > 0.0:
            fc = _blend_rgb(fc, tc, tae_a)
        for sx, sy in ((-128.0, -108.0), (128.0, -108.0), (-128.0, 108.0), (128.0, 108.0)):
            b_a = 1.0 - _smoothstep(-1.1, 1.1, _sd_rounded_box(px - sx, py - sy, 32.0, 11.0, 4.0))
            if b_a > 0.0:
                fc = _blend_rgb(fc, dark, b_a)
    elif flag == "ca":
        side_a = 1.0 - _smoothstep(-1.1, 1.1, 128.0 - abs(px))
        fc = _blend_rgb(white, red, side_a)
        if abs(px) <= 160.0 and abs(py) <= 170.0:
            ma = 1.0 - _smoothstep(-1.1, 1.1, _sd_polygon(px, py, MAPLE_POLY))
            if ma > 0.0:
                fc = _blend_rgb(fc, red, ma)
    elif flag == "nl":
        t_a = 1.0 - _smoothstep(-1.1, 1.1, py + 82.0)
        b_a = 1.0 - _smoothstep(-1.1, 1.1, 82.0 - py)
        fc = _blend_rgb(white, red, t_a)
        fc = _blend_rgb(fc, cobalt, b_a)
    elif flag == "fr":
        l_a = 1.0 - _smoothstep(-1.1, 1.1, px + 82.0)
        r_a = 1.0 - _smoothstep(-1.1, 1.1, 82.0 - px)
        fc = _blend_rgb(white, cobalt, l_a)
        fc = _blend_rgb(fc, red, r_a)
    elif flag == "de":
        t_a = 1.0 - _smoothstep(-1.1, 1.1, py + 82.0)
        b_a = 1.0 - _smoothstep(-1.1, 1.1, 82.0 - py)
        fc = _blend_rgb(red, dark, t_a)
        fc = _blend_rgb(fc, gold, b_a)
    elif flag == "uk":
        fc = navy
        d_d1 = _sd_segment(px, py, -240.0, -240.0, 240.0, 240.0)
        d_d2 = _sd_segment(px, py, -240.0, 240.0, 240.0, -240.0)
        diag_w = 1.0 - _smoothstep(-1.1, 1.1, min(d_d1, d_d2) - 34.0)
        diag_r = 1.0 - _smoothstep(-1.1, 1.1, min(d_d1, d_d2) - 14.0)
        fc = _blend_rgb(fc, white, diag_w)
        fc = _blend_rgb(fc, red, diag_r)
        cw_a = 1.0 - _smoothstep(-1.1, 1.1, min(abs(px), abs(py)) - 44.0)
        cr_a = 1.0 - _smoothstep(-1.1, 1.1, min(abs(px), abs(py)) - 26.0)
        fc = _blend_rgb(fc, white, cw_a)
        fc = _blend_rgb(fc, red, cr_a)

    return _blend_rgb(col, fc, disc_a)


def _motif_pixel(
    motif: str,
    px: float,
    py: float,
    bg_col: tuple[float, float, float],
) -> tuple[float, float, float]:
    white = (1.0, 1.0, 1.0)
    gold = _hex_to_rgb01("#FFD452")
    amber = _hex_to_rgb01("#FF9233")
    lantern_warm = _hex_to_rgb01("#FFF3D6")
    moon_silver = _hex_to_rgb01("#FDE68A")
    mint = _hex_to_rgb01("#5CF2D6")
    coral = _hex_to_rgb01("#FF5263")
    slate_hi = _hex_to_rgb01("#E2E8F0")

    col = bg_col

    if motif.startswith("flag_"):
        return _flag_medallion_color(motif[5:], px, py, col)

    if motif == "myanmar":
        d_moon = math.hypot(px - 264.0, py + 252.0) - 34.0
        moon_a = 1.0 - _smoothstep(-1.1, 1.1, d_moon)
        if moon_a > 0.0:
            col = _blend_rgb(col, moon_silver, moon_a * 0.94)
        if abs(px) <= 258.0 and -336.0 <= py <= 176.0:
            d_env = _sd_polygon(px, py, BALLOON_POLY)
            if d_env <= 4.0:
                d_rib = min(
                    _sd_polyline(px, py, BALLOON_LEFT_RIB),
                    _sd_polyline(px, py, BALLOON_RIGHT_RIB),
                ) - 10.0
                d_star_cut = _sd_polygon(px, py, BALLOON_STAR_POLY) - 4.0
                d_canopy = max(d_env, -d_rib, -d_star_cut)
                can_a = 1.0 - _smoothstep(-1.1, 1.1, d_canopy)
                if can_a > 0.0:
                    env_t = _clamp((py + 328.0) / 485.0)
                    env_rgb = (
                        lantern_warm[0] * (1.0 - env_t) + gold[0] * env_t,
                        lantern_warm[1] * (1.0 - env_t) + gold[1] * env_t,
                        lantern_warm[2] * (1.0 - env_t) + gold[2] * env_t,
                    )
                    col = _blend_rgb(col, env_rgb, can_a)
        if abs(px) <= 130.0 and 164.0 <= py <= 345.0:
            d_rim = _sd_rounded_box(px, py - 186.0, 108.0, 11.0, 10.0)
            rim_a = 1.0 - _smoothstep(-1.1, 1.1, d_rim)
            if rim_a > 0.0:
                col = _blend_rgb(col, white, rim_a * 0.95)
            d_flame = _sd_polygon(px, py, FLAME_POLY)
            fl_a = 1.0 - _smoothstep(-1.1, 1.1, d_flame)
            if fl_a > 0.0:
                col = _blend_rgb(col, amber, fl_a)
            d_flame_core = _sd_circle(px, py - 284.0, 18.0)
            fc_a = 1.0 - _smoothstep(-1.1, 1.1, d_flame_core)
            if fc_a > 0.0:
                col = _blend_rgb(col, lantern_warm, fc_a)

    elif motif == "ai":
        d_arc1 = _sd_arc(px, py, 336.0, 26.0, -45.0, 56.0)
        d_arc2 = _sd_arc(px, py, 336.0, 26.0, 135.0, 56.0)
        arc_a = 1.0 - _smoothstep(-1.1, 1.1, min(d_arc1, d_arc2))
        if arc_a > 0.0:
            col = _blend_rgb(col, white, arc_a * 0.55)
        if abs(px) <= 245.0 and abs(py) <= 245.0:
            d_ast = _sd_polygon(px, py, ASTROID_POLY) - 10.0
            d_hole = _sd_circle(px, py, 44.0)
            sp_a = 1.0 - _smoothstep(-1.1, 1.1, max(d_ast, -d_hole))
            if sp_a > 0.0:
                col = _blend_rgb(col, white, sp_a * 0.98)
            core_a = 1.0 - _smoothstep(-1.1, 1.1, _sd_circle(px, py, 24.0))
            if core_a > 0.0:
                col = _blend_rgb(col, mint, core_a)

    elif motif == "pixel":
        d_slash_core = _sd_segment(px, py, -264.0, 264.0, 264.0, -264.0) - 30.0
        d_slash_gap = d_slash_core - 28.0
        if abs(px) <= 250.0 and abs(py) <= 250.0:
            d_tiles = 1e9
            for gx in (-164.0, 0.0, 164.0):
                if abs(px - gx) > 68.0:
                    continue
                for gy in (-164.0, 0.0, 164.0):
                    if abs(py - gy) > 68.0:
                        continue
                    d_tiles = min(d_tiles, _sd_rounded_box(px - gx, py - gy, 60.0, 60.0, 18.0))
            tile_a = 1.0 - _smoothstep(-1.1, 1.1, max(d_tiles, -d_slash_gap))
            if tile_a > 0.0:
                col = _blend_rgb(col, white, tile_a * 0.92)
        slash_a = 1.0 - _smoothstep(-1.1, 1.1, d_slash_core)
        if slash_a > 0.0:
            col = _blend_rgb(col, coral, slash_a)

    elif motif == "shield":
        if abs(px) <= 295.0 and abs(py) <= 355.0:
            d_sh = _sd_polygon(px, py, SHIELD_POLY)
            d_c1 = _sd_segment(px, py, -110.0, 6.0, -22.0, 96.0) - 34.0
            d_c2 = _sd_segment(px, py, -22.0, 96.0, 128.0, -76.0) - 34.0
            sh_a = 1.0 - _smoothstep(-1.1, 1.1, max(d_sh, -min(d_c1, d_c2)))
            if sh_a > 0.0:
                col = _blend_rgb(col, white, sh_a * 0.96)

    elif motif == "youtube":
        if abs(px) <= 280.0 and -215.0 <= py <= 145.0:
            d_screen = _sd_rounded_box(px, py + 34.0, 260.0, 164.0, 64.0)
            d_play = _sd_polygon(px, py, PLAY_TRI_POLY) - 10.0
            sc_a = 1.0 - _smoothstep(-1.1, 1.1, max(d_screen, -d_play))
            if sc_a > 0.0:
                col = _blend_rgb(col, white, sc_a * 0.96)
        if abs(px) <= 240.0 and 155.0 <= py <= 315.0:
            b1_a = 1.0 - _smoothstep(-1.1, 1.1, _sd_rounded_box(px, py - 186.0, 196.0, 18.0, 16.0))
            if b1_a > 0.0:
                col = _blend_rgb(col, white, b1_a * 0.94)
            b2_a = 1.0 - _smoothstep(-1.1, 1.1, _sd_rounded_box(px, py - 246.0, 142.0, 18.0, 16.0))
            if b2_a > 0.0:
                col = _blend_rgb(col, gold, b2_a * 0.98)

    elif motif == "ytmusic":
        # Concentric Apple-style vinyl ring + warm gold accent ring + crisp center play triangle
        d_outer = _sd_ring(px, py, 246.0, 22.0)
        oa = 1.0 - _smoothstep(-1.1, 1.1, d_outer)
        if oa > 0.0:
            col = _blend_rgb(col, white, oa * 0.95)
        d_inner = _sd_ring(px, py, 168.0, 12.0)
        ia = 1.0 - _smoothstep(-1.1, 1.1, d_inner)
        if ia > 0.0:
            col = _blend_rgb(col, gold, ia * 0.96)
        if abs(px) <= 105.0 and abs(py) <= 105.0:
            d_tri = _sd_polygon(px, py, CENTER_PLAY_POLY) - 12.0
            ta = 1.0 - _smoothstep(-1.1, 1.1, d_tri)
            if ta > 0.0:
                col = _blend_rgb(col, white, ta * 0.98)

    elif motif == "linkcheck":
        d_l1 = _sd_segment(px, py, -210.0, 90.0, 0.0, -140.0) - 24.0
        d_l2 = _sd_segment(px, py, 0.0, -140.0, 210.0, 90.0) - 24.0
        l_a = 1.0 - _smoothstep(-1.1, 1.1, min(d_l1, d_l2))
        if l_a > 0.0:
            col = _blend_rgb(col, white, l_a * 0.65)
        for cx, cy, cr, accent in ((-210.0, 90.0, 74.0, white), (0.0, -140.0, 82.0, mint), (210.0, 90.0, 74.0, white)):
            na = 1.0 - _smoothstep(-1.1, 1.1, _sd_circle(px - cx, py - cy, cr))
            if na > 0.0:
                col = _blend_rgb(col, accent, na * 0.96)

    elif motif == "geo":
        d_ring = _sd_ring(px, py, 240.0, 26.0)
        d_eq = _sd_rounded_box(px, py, 240.0, 18.0, 10.0)
        d_mer = _sd_rounded_box(px, py, 18.0, 240.0, 10.0)
        ga = 1.0 - _smoothstep(-1.1, 1.1, min(d_ring, d_eq, d_mer))
        if ga > 0.0:
            col = _blend_rgb(col, white, ga * 0.92)
        ca = 1.0 - _smoothstep(-1.1, 1.1, _sd_circle(px, py, 64.0))
        if ca > 0.0:
            col = _blend_rgb(col, mint, ca * 0.98)

    elif motif == "media":
        if abs(px) <= 290.0 and abs(py) <= 230.0:
            d_box = _sd_rounded_box(px, py, 260.0, 186.0, 56.0)
            d_c1 = _sd_segment(px, py, -110.0, 10.0, -24.0, 96.0) - 30.0
            d_c2 = _sd_segment(px, py, -24.0, 96.0, 128.0, -78.0) - 30.0
            ma = 1.0 - _smoothstep(-1.1, 1.1, max(d_box, -min(d_c1, d_c2)))
            if ma > 0.0:
                col = _blend_rgb(col, white, ma * 0.96)

    elif motif == "shadowshare":
        # Interlocking rounded gateway rings + luminous mint core diamond
        d_r1 = _sd_ring(px + 68.0, py, 166.0, 28.0)
        d_r2 = _sd_ring(px - 68.0, py, 166.0, 28.0)
        ra = 1.0 - _smoothstep(-1.1, 1.1, min(d_r1, d_r2))
        if ra > 0.0:
            col = _blend_rgb(col, white, ra * 0.94)
        da = 1.0 - _smoothstep(-1.1, 1.1, (abs(px) + abs(py)) * 0.7071 - 56.0)
        if da > 0.0:
            col = _blend_rgb(col, mint, da * 0.98)

    elif motif == "streaming":
        if abs(px) <= 285.0 and abs(py) <= 215.0:
            d_sc = _sd_rounded_box(px, py, 262.0, 184.0, 58.0)
            d_tr = _sd_polygon(px, py, CENTER_PLAY_POLY) - 10.0
            sa = 1.0 - _smoothstep(-1.1, 1.1, max(d_sc, -d_tr))
            if sa > 0.0:
                col = _blend_rgb(col, white, sa * 0.96)

    elif motif == "social":
        # Back-right tinted bubble + front-left bright rounded bubble with uniform azure dots
        dot_blue = _hex_to_rgb01("#1D4ED8")
        d_b2 = _sd_rounded_box(px - 76.0, py - 52.0, 164.0, 124.0, 54.0)
        b2a = 1.0 - _smoothstep(-1.1, 1.1, d_b2)
        if b2a > 0.0:
            col = _blend_rgb(col, mint, b2a * 0.85)
        d_b1 = _sd_rounded_box(px + 48.0, py + 44.0, 186.0, 142.0, 62.0)
        b1a = 1.0 - _smoothstep(-1.1, 1.1, d_b1)
        if b1a > 0.0:
            col = _blend_rgb(col, white, b1a * 0.97)
        d_dots = min(
            _sd_circle(px + 108.0, py + 44.0, 22.0),
            _sd_circle(px + 48.0, py + 44.0, 22.0),
            _sd_circle(px - 12.0, py + 44.0, 22.0),
        )
        da = 1.0 - _smoothstep(-1.1, 1.1, d_dots)
        if da > 0.0:
            col = _blend_rgb(col, dot_blue, da)

    elif motif == "tech":
        # Precision search glass / dev lens with glowing core dot
        d_lens = _sd_ring(px + 38.0, py + 38.0, 164.0, 32.0)
        d_handle = _sd_segment(px, py, 80.0, 80.0, 214.0, 214.0) - 34.0
        ta = 1.0 - _smoothstep(-1.1, 1.1, min(d_lens, d_handle))
        if ta > 0.0:
            col = _blend_rgb(col, white, ta * 0.95)
        da = 1.0 - _smoothstep(-1.1, 1.1, _sd_circle(px + 38.0, py + 38.0, 54.0))
        if da > 0.0:
            col = _blend_rgb(col, mint, da * 0.95)

    elif motif == "apple_badge":
        # Clean minimalist geometric device-cloud / orb + crisp titanium ring
        d_orb = _sd_circle(px, py + 24.0, 184.0)
        d_bite = _sd_circle(px - 178.0, py + 12.0, 82.0)
        d_body = max(d_orb, -d_bite)
        # Angled leaf above
        lx, ly = px - 24.0, py + 224.0
        d_leaf = math.hypot(lx * 0.8 + ly * 0.6, (lx * -0.6 + ly * 0.8) * 1.9) - 62.0
        ba = 1.0 - _smoothstep(-1.1, 1.1, min(d_body, d_leaf))
        if ba > 0.0:
            col = _blend_rgb(col, slate_hi, ba * 0.96)

    elif motif == "adblock":
        d_oct = _sd_octagon(px, py, 248.0)
        d_bar = _sd_rounded_box(px, py, 142.0, 34.0, 18.0)
        aa = 1.0 - _smoothstep(-1.1, 1.1, max(d_oct, -d_bar))
        if aa > 0.0:
            col = _blend_rgb(col, white, aa * 0.96)

    elif motif == "auto":
        d_halo = _sd_ring(px, py, 286.0, 20.0)
        ha = 1.0 - _smoothstep(-1.1, 1.1, d_halo)
        if ha > 0.0:
            col = _blend_rgb(col, gold, ha * 0.72)
        if abs(px) <= 130.0 and abs(py) <= 230.0:
            ba = 1.0 - _smoothstep(-1.1, 1.1, _sd_polygon(px, py, BOLT_POLY) - 8.0)
            if ba > 0.0:
                col = _blend_rgb(col, white, ba * 0.98)

    return col


def _render_icon(
    name: str,
    top_hex: str,
    bot_hex: str,
    motif: str,
    squircle_alpha: bytearray,
    outputs_unmasked: list[Path],
    output_squircle: Path,
) -> None:
    top_rgb = _hex_to_rgb01(top_hex)
    bot_rgb = _hex_to_rgb01(bot_hex)

    unmasked_px = bytearray(SIZE * SIZE * 3)
    squircle_px = bytearray(SIZE * SIZE * 4)

    # Bounding circle for foreground art (every motif sits strictly inside r <= 370 px)
    r_bound = 370
    x_center = SIZE // 2

    for y in range(SIZE):
        py = (y + 0.5) - HALF
        t = y / (SIZE - 1)
        bg_r = top_rgb[0] * (1.0 - t) + bot_rgb[0] * t
        bg_g = top_rgb[1] * (1.0 - t) + bot_rgb[1] * t
        bg_b = top_rgb[2] * (1.0 - t) + bot_rgb[2] * t
        bg_col = (bg_r, bg_g, bg_b)

        br8 = int(round(_clamp(bg_r) * 255))
        bg8 = int(round(_clamp(bg_g) * 255))
        bb8 = int(round(_clamp(bg_b) * 255))

        # Fast row initialization with flat background bytes
        row3_start = y * SIZE * 3
        unmasked_px[row3_start : row3_start + SIZE * 3] = bytes((br8, bg8, bb8)) * SIZE

        row_alpha_start = y * SIZE
        row4_start = y * SIZE * 4
        squircle_px[row4_start : row4_start + SIZE * 4] = bytes((br8, bg8, bb8, 255)) * SIZE
        for x in range(SIZE):
            a8 = squircle_alpha[row_alpha_start + x]
            if a8 != 255:
                squircle_px[row4_start + x * 4 + 3] = a8

        if abs(py) > r_bound:
            continue
        dx_max = int(math.sqrt(r_bound * r_bound - py * py)) + 1
        x_lo = max(0, x_center - dx_max)
        x_hi = min(SIZE, x_center + dx_max + 1)

        for x in range(x_lo, x_hi):
            px = (x + 0.5) - HALF
            col = _motif_pixel(motif, px, py, bg_col)
            if col is bg_col:
                continue
            r8 = int(round(_clamp(col[0]) * 255))
            g8 = int(round(_clamp(col[1]) * 255))
            b8 = int(round(_clamp(col[2]) * 255))
            i3 = row3_start + x * 3
            unmasked_px[i3] = r8
            unmasked_px[i3 + 1] = g8
            unmasked_px[i3 + 2] = b8
            i4 = row4_start + x * 4
            squircle_px[i4] = r8
            squircle_px[i4 + 1] = g8
            squircle_px[i4 + 2] = b8

    for out in outputs_unmasked:
        _write_png(out, SIZE, SIZE, unmasked_px, rgba=False)
    _write_png(output_squircle, SIZE, SIZE, squircle_px, rgba=True)


def _generate_all_svgs() -> None:
    # 1. Myanmar Essential SVG — Tazaungdaing Hot-Air Fire Balloon (Mee Pone Pyan)
    bal_d = _svg_poly_path(BALLOON_POLY)
    fl_d = _svg_poly_path(FLAME_POLY)
    rib_l_d = "M " + " L ".join(f"{x + HALF:.2f} {y + HALF:.2f}" for x, y in BALLOON_LEFT_RIB)
    rib_r_d = "M " + " L ".join(f"{x + HALF:.2f} {y + HALF:.2f}" for x, y in BALLOON_RIGHT_RIB)
    star_pts = _svg_star_points(HALF, HALF - 110.0, 92.0, 38.0)
    bal_defs = [
        '<linearGradient id="balloon-grad" x1="0" y1="0" x2="0" y2="1">',
        '  <stop offset="0%" stop-color="#FFF3D6"/>',
        '  <stop offset="100%" stop-color="#FFD452"/>',
        "</linearGradient>",
        '<mask id="balloon-cut">',
        '  <rect width="1024" height="1024" fill="white"/>',
        f'  <path d="{rib_l_d}" fill="none" stroke="black" stroke-width="20" stroke-linecap="round"/>',
        f'  <path d="{rib_r_d}" fill="none" stroke="black" stroke-width="20" stroke-linecap="round"/>',
        f'  <polygon points="{star_pts}" fill="black" stroke="black" stroke-width="8" stroke-linejoin="round"/>',
        "</mask>",
    ]
    _write_svgs(
        "myanmar-essential", "#0B163D", "#2F235C", defs_extra=bal_defs,
        fg_elements_color=[
            '<circle cx="776" cy="260" r="34" fill="#FDE68A" opacity="0.94"/>',
            f'<path d="{bal_d}" fill="url(#balloon-grad)" mask="url(#balloon-cut)"/>',
            '<rect x="404" y="687" width="216" height="22" rx="10" fill="#FFFFFF" opacity="0.95"/>',
            f'<path d="{fl_d}" fill="#FF9233"/>',
            '<circle cx="512" cy="796" r="18" fill="#FFF3D6"/>',
        ],
        fg_elements_mono=[
            '<circle cx="776" cy="260" r="34" fill="#FFFFFF" opacity="0.75"/>',
            f'<path d="{bal_d}" fill="#FFFFFF" mask="url(#balloon-cut)"/>',
            '<rect x="404" y="687" width="216" height="22" rx="10" fill="#FFFFFF"/>',
            f'<path d="{fl_d}" fill="#FFFFFF"/>',
        ],
    )

    ai_a1 = _svg_arc_path(HALF, HALF, 336.0, -101.0, 11.0)
    ai_a2 = _svg_arc_path(HALF, HALF, 336.0, 79.0, 191.0)
    ast_d = _svg_poly_path(ASTROID_POLY)
    ai_mask = [
        '<mask id="ai-cut">',
        '  <rect width="1024" height="1024" fill="white"/>',
        '  <circle cx="512" cy="512" r="44" fill="black"/>',
        "</mask>",
    ]
    for nm, c_top, c_bot in (
        ("google-ai-auth-proxy", "#183B8C", "#0C707D"),
        ("policy-ai", "#183B8C", "#0C707D"),
    ):
        _write_svgs(
            nm, c_top, c_bot, defs_extra=ai_mask,
            fg_elements_color=[
                f'<path d="{ai_a1}" fill="none" stroke="#FFFFFF" stroke-width="52" stroke-linecap="round" opacity="0.55"/>',
                f'<path d="{ai_a2}" fill="none" stroke="#FFFFFF" stroke-width="52" stroke-linecap="round" opacity="0.55"/>',
                f'<path d="{ast_d}" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="20" stroke-linejoin="round" mask="url(#ai-cut)" opacity="0.98"/>',
                '<circle cx="512" cy="512" r="24" fill="#5CF2D6"/>',
            ],
            fg_elements_mono=[
                f'<path d="{ai_a1}" fill="none" stroke="#FFFFFF" stroke-width="52" stroke-linecap="round" opacity="0.65"/>',
                f'<path d="{ai_a2}" fill="none" stroke="#FFFFFF" stroke-width="52" stroke-linecap="round" opacity="0.65"/>',
                f'<path d="{ast_d}" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="20" stroke-linejoin="round" mask="url(#ai-cut)"/>',
                '<circle cx="512" cy="512" r="24" fill="#FFFFFF"/>',
            ],
        )

    tiles = [
        f'<rect x="{512 + gx - 60}" y="{512 + gy - 60}" width="120" height="120" rx="18" fill="#FFFFFF"/>'
        for gx in (-164, 0, 164)
        for gy in (-164, 0, 164)
    ]
    pixel_mask = [
        '<mask id="pixel-cut">',
        '  <rect width="1024" height="1024" fill="white"/>',
        '  <line x1="248" y1="776" x2="776" y2="248" stroke="black" stroke-width="116" stroke-linecap="round"/>',
        "</mask>",
    ]
    _write_svgs(
        "meta-pixel-mitm", "#2D2166", "#5E1A66", defs_extra=pixel_mask,
        fg_elements_color=[
            f'<g mask="url(#pixel-cut)" opacity="0.92">{"".join(tiles)}</g>',
            '<line x1="248" y1="776" x2="776" y2="248" stroke="#FF5263" stroke-width="60" stroke-linecap="round"/>',
        ],
        fg_elements_mono=[
            f'<g mask="url(#pixel-cut)">{"".join(tiles)}</g>',
            '<line x1="248" y1="776" x2="776" y2="248" stroke="#FFFFFF" stroke-width="60" stroke-linecap="round"/>',
        ],
    )

    sh_d = _svg_poly_path(SHIELD_POLY)
    sh_mask = [
        '<mask id="shield-cut">',
        '  <rect width="1024" height="1024" fill="white"/>',
        '  <path d="M 402 518 L 490 608 L 640 436" fill="none" stroke="black" stroke-width="68" stroke-linecap="round" stroke-linejoin="round"/>',
        "</mask>",
    ]
    _write_svgs(
        "telemetry-shield", "#0B5E58", "#0D2E5C", defs_extra=sh_mask,
        fg_elements_color=[f'<path d="{sh_d}" fill="#FFFFFF" mask="url(#shield-cut)" opacity="0.96"/>'],
        fg_elements_mono=[f'<path d="{sh_d}" fill="#FFFFFF" mask="url(#shield-cut)"/>'],
    )

    play_d = _svg_poly_path(PLAY_TRI_POLY)
    yt_mask = [
        '<mask id="yt-cut">',
        '  <rect width="1024" height="1024" fill="white"/>',
        f'  <path d="{play_d}" fill="black" stroke="black" stroke-width="20" stroke-linejoin="round"/>',
        "</mask>",
    ]
    _write_svgs(
        "youtube-myanmar-enhance", "#9B142C", "#4A0D36", defs_extra=yt_mask,
        fg_elements_color=[
            '<rect x="252" y="314" width="520" height="328" rx="64" fill="#FFFFFF" mask="url(#yt-cut)" opacity="0.96"/>',
            '<rect x="316" y="680" width="392" height="36" rx="16" fill="#FFFFFF" opacity="0.94"/>',
            '<rect x="370" y="740" width="284" height="36" rx="16" fill="#FFD452" opacity="0.98"/>',
        ],
        fg_elements_mono=[
            '<rect x="252" y="314" width="520" height="328" rx="64" fill="#FFFFFF" mask="url(#yt-cut)"/>',
            '<rect x="316" y="680" width="392" height="36" rx="16" fill="#FFFFFF"/>',
            '<rect x="370" y="740" width="284" height="36" rx="16" fill="#FFFFFF" opacity="0.82"/>',
        ],
    )

    cplay_d = _svg_poly_path(CENTER_PLAY_POLY)
    _write_svgs(
        "youtube-music-myanmar", "#B91C1C", "#6D1252",
        fg_elements_color=[
            '<circle cx="512" cy="512" r="246" fill="none" stroke="#FFFFFF" stroke-width="44" opacity="0.95"/>',
            '<circle cx="512" cy="512" r="168" fill="none" stroke="#FFD452" stroke-width="24" opacity="0.96"/>',
            f'<path d="{cplay_d}" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="18" stroke-linejoin="round"/>',
        ],
        fg_elements_mono=[
            '<circle cx="512" cy="512" r="246" fill="none" stroke="#FFFFFF" stroke-width="44"/>',
            '<circle cx="512" cy="512" r="168" fill="none" stroke="#FFFFFF" stroke-width="24" opacity="0.8"/>',
            f'<path d="{cplay_d}" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="18" stroke-linejoin="round"/>',
        ],
    )

    _write_svgs(
        "node-link-check", "#0D4F8B", "#10244E",
        fg_elements_color=[
            '<line x1="302" y1="602" x2="512" y2="372" stroke="#FFFFFF" stroke-width="48" stroke-linecap="round" opacity="0.65"/>',
            '<line x1="512" y1="372" x2="722" y2="602" stroke="#FFFFFF" stroke-width="48" stroke-linecap="round" opacity="0.65"/>',
            '<circle cx="302" cy="602" r="74" fill="#FFFFFF" opacity="0.96"/>',
            '<circle cx="512" cy="372" r="82" fill="#5CF2D6" opacity="0.96"/>',
            '<circle cx="722" cy="602" r="74" fill="#FFFFFF" opacity="0.96"/>',
        ],
        fg_elements_mono=[
            '<line x1="302" y1="602" x2="512" y2="372" stroke="#FFFFFF" stroke-width="48" stroke-linecap="round" opacity="0.7"/>',
            '<line x1="512" y1="372" x2="722" y2="602" stroke="#FFFFFF" stroke-width="48" stroke-linecap="round" opacity="0.7"/>',
            '<circle cx="302" cy="602" r="74" fill="#FFFFFF"/>',
            '<circle cx="512" cy="372" r="82" fill="#FFFFFF"/>',
            '<circle cx="722" cy="602" r="74" fill="#FFFFFF"/>',
        ],
    )

    for nm, t_h, b_h in (("geo-location", "#0F6A52", "#0D2C44"), ("policy-others", "#065F46", "#172554")):
        _write_svgs(
            nm, t_h, b_h,
            fg_elements_color=[
                '<circle cx="512" cy="512" r="240" fill="none" stroke="#FFFFFF" stroke-width="52" opacity="0.92"/>',
                '<rect x="272" y="494" width="480" height="36" rx="10" fill="#FFFFFF" opacity="0.92"/>',
                '<rect x="494" y="272" width="36" height="480" rx="10" fill="#FFFFFF" opacity="0.92"/>',
                '<circle cx="512" cy="512" r="64" fill="#5CF2D6" opacity="0.98"/>',
            ],
            fg_elements_mono=[
                '<circle cx="512" cy="512" r="240" fill="none" stroke="#FFFFFF" stroke-width="52"/>',
                '<rect x="272" y="494" width="480" height="36" rx="10" fill="#FFFFFF"/>',
                '<rect x="494" y="272" width="36" height="480" rx="10" fill="#FFFFFF"/>',
                '<circle cx="512" cy="512" r="64" fill="#FFFFFF"/>',
            ],
        )

    mc_mask = [
        '<mask id="media-cut">',
        '  <rect width="1024" height="1024" fill="white"/>',
        '  <path d="M 402 522 L 488 608 L 640 434" fill="none" stroke="black" stroke-width="60" stroke-linecap="round" stroke-linejoin="round"/>',
        "</mask>",
    ]
    _write_svgs(
        "media-checker", "#5B247A", "#1B1F4F", defs_extra=mc_mask,
        fg_elements_color=['<rect x="252" y="326" width="520" height="372" rx="56" fill="#FFFFFF" mask="url(#media-cut)" opacity="0.96"/>'],
        fg_elements_mono=['<rect x="252" y="326" width="520" height="372" rx="56" fill="#FFFFFF" mask="url(#media-cut)"/>'],
    )

    _write_svgs(
        "policy-shadowshare", "#1B1F6B", "#0D6E6E",
        fg_elements_color=[
            '<circle cx="444" cy="512" r="166" fill="none" stroke="#FFFFFF" stroke-width="56" opacity="0.94"/>',
            '<circle cx="580" cy="512" r="166" fill="none" stroke="#FFFFFF" stroke-width="56" opacity="0.94"/>',
            '<polygon points="512,433 591,512 512,591 433,512" fill="#5CF2D6"/>',
        ],
        fg_elements_mono=[
            '<circle cx="444" cy="512" r="166" fill="none" stroke="#FFFFFF" stroke-width="56"/>',
            '<circle cx="580" cy="512" r="166" fill="none" stroke="#FFFFFF" stroke-width="56"/>',
        ],
    )

    st_mask = [
        '<mask id="st-cut">',
        '  <rect width="1024" height="1024" fill="white"/>',
        f'  <path d="{cplay_d}" fill="black" stroke="black" stroke-width="20" stroke-linejoin="round"/>',
        "</mask>",
    ]
    _write_svgs(
        "policy-streaming", "#9B142C", "#4A0D36", defs_extra=st_mask,
        fg_elements_color=['<rect x="250" y="328" width="524" height="368" rx="58" fill="#FFFFFF" mask="url(#st-cut)" opacity="0.96"/>'],
        fg_elements_mono=['<rect x="250" y="328" width="524" height="368" rx="58" fill="#FFFFFF" mask="url(#st-cut)"/>'],
    )

    _write_svgs(
        "policy-social", "#1D4ED8", "#5B21B6",
        fg_elements_color=[
            '<rect x="424" y="440" width="328" height="248" rx="54" fill="#5CF2D6" opacity="0.85"/>',
            '<rect x="278" y="326" width="372" height="284" rx="62" fill="#FFFFFF" opacity="0.97"/>',
            '<circle cx="404" cy="468" r="22" fill="#1D4ED8"/><circle cx="464" cy="468" r="22" fill="#1D4ED8"/><circle cx="524" cy="468" r="22" fill="#1D4ED8"/>',
        ],
        fg_elements_mono=[
            '<rect x="424" y="440" width="328" height="248" rx="54" fill="#FFFFFF" opacity="0.6"/>',
            '<rect x="278" y="326" width="372" height="284" rx="62" fill="#FFFFFF"/>',
        ],
    )

    _write_svgs(
        "policy-tech", "#1E3A5F", "#0F6A8B",
        fg_elements_color=[
            '<circle cx="474" cy="474" r="164" fill="none" stroke="#FFFFFF" stroke-width="64" opacity="0.95"/>',
            '<line x1="592" y1="592" x2="726" y2="726" stroke="#FFFFFF" stroke-width="68" stroke-linecap="round"/>',
            '<circle cx="474" cy="474" r="54" fill="#5CF2D6" opacity="0.95"/>',
        ],
        fg_elements_mono=[
            '<circle cx="474" cy="474" r="164" fill="none" stroke="#FFFFFF" stroke-width="64"/>',
            '<line x1="592" y1="592" x2="726" y2="726" stroke="#FFFFFF" stroke-width="68" stroke-linecap="round"/>',
        ],
    )

    _write_svgs(
        "policy-apple", "#3A4659", "#0F172A",
        fg_elements_color=[
            '<circle cx="512" cy="488" r="184" fill="#E2E8F0" opacity="0.96"/>',
            '<ellipse cx="536" cy="288" rx="34" ry="58" transform="rotate(-35 536 288)" fill="#E2E8F0"/>',
        ],
        fg_elements_mono=[
            '<circle cx="512" cy="488" r="184" fill="#FFFFFF"/>',
            '<ellipse cx="536" cy="288" rx="34" ry="58" transform="rotate(-35 536 288)" fill="#FFFFFF"/>',
        ],
    )

    oct_pts = " ".join(
        f"{HALF + 268.0 * math.cos(math.pi / 8.0 + i * math.pi / 4.0):.2f},{HALF + 268.0 * math.sin(math.pi / 8.0 + i * math.pi / 4.0):.2f}"
        for i in range(8)
    )
    _write_svgs(
        "policy-adblock", "#991B1B", "#271019",
        defs_extra=['<mask id="ad-cut"><rect width="1024" height="1024" fill="white"/><rect x="370" y="478" width="284" height="68" rx="18" fill="black"/></mask>'],
        fg_elements_color=[f'<polygon points="{oct_pts}" fill="#FFFFFF" mask="url(#ad-cut)" opacity="0.96"/>'],
        fg_elements_mono=[f'<polygon points="{oct_pts}" fill="#FFFFFF" mask="url(#ad-cut)"/>'],
    )

    bolt_d = _svg_poly_path(BOLT_POLY)
    _write_svgs(
        "policy-auto", "#D97706", "#1E1B4B",
        fg_elements_color=[
            '<circle cx="512" cy="512" r="286" fill="none" stroke="#FFD452" stroke-width="40" opacity="0.72"/>',
            f'<path d="{bolt_d}" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="14" stroke-linejoin="round"/>',
        ],
        fg_elements_mono=[
            '<circle cx="512" cy="512" r="286" fill="none" stroke="#FFFFFF" stroke-width="40" opacity="0.72"/>',
            f'<path d="{bolt_d}" fill="#FFFFFF" stroke="#FFFFFF" stroke-width="14" stroke-linejoin="round"/>',
        ],
    )

    for code, acc in (
        ("policy-sg", "#E11D48"),
        ("policy-us", "#1E3A8A"),
        ("policy-jp", "#DC2626"),
        ("policy-hk", "#E11D48"),
        ("policy-kr", "#1D4ED8"),
        ("policy-ca", "#DC2626"),
        ("policy-nl", "#DC2626"),
        ("policy-fr", "#1D4ED8"),
        ("policy-de", "#FACC15"),
        ("policy-uk", "#1E3A8A"),
    ):
        _write_svgs(
            code, "#17223B", "#0B1120",
            fg_elements_color=[
                '<circle cx="512" cy="512" r="256" fill="none" stroke="#CBD5E1" stroke-width="20" opacity="0.75"/>',
                f'<circle cx="512" cy="512" r="244" fill="{acc}" opacity="0.95"/>',
            ],
            fg_elements_mono=['<circle cx="512" cy="512" r="244" fill="#FFFFFF"/>'],
        )


ICON_SPECS = [
    ("myanmar-essential", "#0B163D", "#2F235C", "myanmar", [ROOT / "icon.png", ROOT / "assets/icons/myanmar-essential.png"], ROOT / "assets/icons/squircle/myanmar-essential.png"),
    ("google-ai-auth-proxy", "#183B8C", "#0C707D", "ai", [ROOT / "assets/icons/google-ai-auth-proxy.png"], ROOT / "assets/icons/squircle/google-ai-auth-proxy.png"),
    ("meta-pixel-mitm", "#2D2166", "#5E1A66", "pixel", [ROOT / "assets/icons/meta-pixel-mitm.png"], ROOT / "assets/icons/squircle/meta-pixel-mitm.png"),
    ("telemetry-shield", "#0B5E58", "#0D2E5C", "shield", [ROOT / "assets/icons/telemetry-shield.png"], ROOT / "assets/icons/squircle/telemetry-shield.png"),
    ("youtube-myanmar-enhance", "#9B142C", "#4A0D36", "youtube", [ROOT / "assets/icons/youtube-myanmar-enhance.png"], ROOT / "assets/icons/squircle/youtube-myanmar-enhance.png"),
    ("youtube-music-myanmar", "#B91C1C", "#6D1252", "ytmusic", [ROOT / "assets/icons/youtube-music-myanmar.png"], ROOT / "assets/icons/squircle/youtube-music-myanmar.png"),
    ("node-link-check", "#0D4F8B", "#10244E", "linkcheck", [ROOT / "assets/icons/node-link-check.png"], ROOT / "assets/icons/squircle/node-link-check.png"),
    ("geo-location", "#0F6A52", "#0D2C44", "geo", [ROOT / "assets/icons/geo-location.png"], ROOT / "assets/icons/squircle/geo-location.png"),
    ("media-checker", "#5B247A", "#1B1F4F", "media", [ROOT / "assets/icons/media-checker.png"], ROOT / "assets/icons/squircle/media-checker.png"),
    ("policy-shadowshare", "#1B1F6B", "#0D6E6E", "shadowshare", [ROOT / "assets/icons/policy-shadowshare.png"], ROOT / "assets/icons/squircle/policy-shadowshare.png"),
    ("policy-ai", "#183B8C", "#0C707D", "ai", [ROOT / "assets/icons/policy-ai.png"], ROOT / "assets/icons/squircle/policy-ai.png"),
    ("policy-streaming", "#9B142C", "#4A0D36", "streaming", [ROOT / "assets/icons/policy-streaming.png"], ROOT / "assets/icons/squircle/policy-streaming.png"),
    ("policy-social", "#1D4ED8", "#5B21B6", "social", [ROOT / "assets/icons/policy-social.png"], ROOT / "assets/icons/squircle/policy-social.png"),
    ("policy-tech", "#1E3A5F", "#0F6A8B", "tech", [ROOT / "assets/icons/policy-tech.png"], ROOT / "assets/icons/squircle/policy-tech.png"),
    ("policy-apple", "#3A4659", "#0F172A", "apple_badge", [ROOT / "assets/icons/policy-apple.png"], ROOT / "assets/icons/squircle/policy-apple.png"),
    ("policy-adblock", "#991B1B", "#271019", "adblock", [ROOT / "assets/icons/policy-adblock.png"], ROOT / "assets/icons/squircle/policy-adblock.png"),
    ("policy-auto", "#D97706", "#1E1B4B", "auto", [ROOT / "assets/icons/policy-auto.png"], ROOT / "assets/icons/squircle/policy-auto.png"),
    ("policy-others", "#065F46", "#172554", "geo", [ROOT / "assets/icons/policy-others.png"], ROOT / "assets/icons/squircle/policy-others.png"),
    ("policy-sg", "#17223B", "#0B1120", "flag_sg", [ROOT / "assets/icons/policy-sg.png"], ROOT / "assets/icons/squircle/policy-sg.png"),
    ("policy-us", "#17223B", "#0B1120", "flag_us", [ROOT / "assets/icons/policy-us.png"], ROOT / "assets/icons/squircle/policy-us.png"),
    ("policy-jp", "#17223B", "#0B1120", "flag_jp", [ROOT / "assets/icons/policy-jp.png"], ROOT / "assets/icons/squircle/policy-jp.png"),
    ("policy-hk", "#17223B", "#0B1120", "flag_hk", [ROOT / "assets/icons/policy-hk.png"], ROOT / "assets/icons/squircle/policy-hk.png"),
    ("policy-kr", "#17223B", "#0B1120", "flag_kr", [ROOT / "assets/icons/policy-kr.png"], ROOT / "assets/icons/squircle/policy-kr.png"),
    ("policy-ca", "#17223B", "#0B1120", "flag_ca", [ROOT / "assets/icons/policy-ca.png"], ROOT / "assets/icons/squircle/policy-ca.png"),
    ("policy-nl", "#17223B", "#0B1120", "flag_nl", [ROOT / "assets/icons/policy-nl.png"], ROOT / "assets/icons/squircle/policy-nl.png"),
    ("policy-fr", "#17223B", "#0B1120", "flag_fr", [ROOT / "assets/icons/policy-fr.png"], ROOT / "assets/icons/squircle/policy-fr.png"),
    ("policy-de", "#17223B", "#0B1120", "flag_de", [ROOT / "assets/icons/policy-de.png"], ROOT / "assets/icons/squircle/policy-de.png"),
    ("policy-uk", "#17223B", "#0B1120", "flag_uk", [ROOT / "assets/icons/policy-uk.png"], ROOT / "assets/icons/squircle/policy-uk.png"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Apple HIG plugin & policy icons.")
    parser.add_argument("--only", help="Comma-separated icon names to render.")
    parser.add_argument("--missing-only", action="store_true", help="Only render icons missing on disk.")
    args = parser.parse_args()

    write_grid_overlay_svg()
    _generate_all_svgs()
    squircle_alpha = _precompute_squircle_alpha()

    selected = {x.strip() for x in args.only.split(",")} if args.only else None
    for name, top_hex, bot_hex, motif, unmasked_outs, squircle_out in ICON_SPECS:
        if selected is not None and name not in selected:
            continue
        if args.missing_only and squircle_out.is_file() and all(p.is_file() for p in unmasked_outs):
            continue
        _render_icon(name, top_hex, bot_hex, motif, squircle_alpha, unmasked_outs, squircle_out)
        print(f"Generated 1024px unmasked + G^2 squircle + SVGs for {name}")


if __name__ == "__main__":
    main()
