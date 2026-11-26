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
    # Standard sRGB chunk (intent=0 Perceptual) + gAMA (1/2.2 = 45455)
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
    arc_len = par["arc_section_length"]

    # Corner coordinates in [0, size] box (matching figma-squircle top-right -> clockwise)
    # Start on top edge before top-right transition: (size - p, 0)
    w = size
    h = size
    # Precompute points in box [0, w] x [0, h]
    # Top-right corner
    tr_p0 = (w - p, 0.0)
    tr_c1 = (w - (p - a), 0.0)
    tr_c2 = (w - (p - a - b), 0.0)
    tr_p1 = (w - (p - a - b - c), d)
    tr_arc_end = (w - d, p - a - b - c)
    tr_c3 = (w, p - a - b)
    tr_c4 = (w, p - a)
    tr_p2 = (w, p)

    # Bottom-right corner
    br_p0 = (w, h - p)
    br_c1 = (w, h - (p - a))
    br_c2 = (w, h - (p - a - b))
    br_p1 = (w - d, h - (p - a - b - c))
    br_arc_end = (w - (p - a - b - c), h - d)
    br_c3 = (w - (p - a - b), h)
    br_c4 = (w - (p - a), h)
    br_p2 = (w - p, h)

    # Bottom-left corner
    bl_p0 = (p, h)
    bl_c1 = (p - a, h)
    bl_c2 = (p - a - b, h)
    bl_p1 = (p - a - b - c, h - d)
    bl_arc_end = (d, h - (p - a - b - c))
    bl_c3 = (0.0, h - (p - a - b))
    bl_c4 = (0.0, h - (p - a))
    bl_p2 = (0.0, h - p)

    # Top-left corner
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

    _ = arc_len  # validated in corner params
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

    # Convert top-right corner coordinates into centered quadrant coordinates [0, half]^2
    # where x = half - (w - coord_x) -> coord_x - half, y = half - coord_y
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
    # 1. First cubic shoulder
    for i in range(steps):
        pts.append(_eval_cubic(p0, c1, c2, p1, i / steps))
    # 2. Circular arc center is (half - r, half - r)
    cx_arc, cy_arc = half - r, half - r
    ang0 = math.atan2(p1[1] - cy_arc, p1[0] - cx_arc)
    ang1 = math.atan2(arc_end[1] - cy_arc, arc_end[0] - cx_arc)
    for i in range(steps):
        t = i / steps
        ang = ang0 + (ang1 - ang0) * t
        pts.append((cx_arc + r * math.cos(ang), cy_arc + r * math.sin(ang)))
    # 3. Second cubic shoulder
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
    # Precompute segments and angular index around (flat_limit, flat_limit)
    segs: list[tuple[float, float, float, float, float, float]] = []
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        if l2 > 1e-12:
            segs.append((ax, ay, dx, dy, 1.0 / l2, bx))

    # Map theta in [0, pi/2] (measured from (flat_limit, flat_limit)) -> center segment index
    n_segs = len(segs)
    ang_bins = 256
    seg_angles = [
        math.atan2(s[1] - flat_limit + s[3] * 0.5, s[0] - flat_limit + s[2] * 0.5)
        for s in segs
    ]
    lut: list[int] = []
    for k in range(ang_bins + 1):
        th = (math.pi / 2.0) * (1.0 - k / ang_bins)  # decreasing from pi/2 (top) to 0 (right)
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
            ax, ay, dx, dy, inv_l2, _ = segs[i]
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
                # Boundary goes clockwise in top-right (dx > 0, dy < 0):
                # outside is to the left of tangent? Wait: dx>0, dy<0 -> (pax*dy - pay*dx)
                best_cross = pax * dy - pay * dx
        dist = math.sqrt(min_d2)
        return -dist if best_cross > 0.0 else dist

    return sd


def _sd_circle(px: float, py: float, r: float) -> float:
    return math.hypot(px, py) - r


def _sd_ring(px: float, py: float, r_mid: float, half_thick: float) -> float:
    return abs(math.hypot(px, py) - r_mid) - half_thick


def _sd_arc(px: float, py: float, r_mid: float, half_thick: float, center_deg: float, half_span_deg: float) -> float:
    """SDF of a circular arc with round caps centered at `center_deg`."""
    ang = math.atan2(py, px)
    c_rad = math.radians(center_deg)
    span_rad = math.radians(half_span_deg)
    # Signed angular delta in [-pi, pi]
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


def _build_shield_poly() -> list[tuple[float, float]]:
    """Apple-grid symmetric cubic-bezier shield centered at (0, 0), fitting inside 80% Primary Circle."""
    # Height ~ 672 (-336 to +336), Width ~ 560 (-280 to +280); max corner radius well < 409.6
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
    """4-point smooth cubic-bezier AI spark with softened tips for Liquid Glass legibility."""
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
    """Tazaungdaing hot-air fire balloon (Mee Pone Pyan) envelope inside 80% Primary Circle."""
    segs = [
        ((0.0, -328.0), (148.0, -328.0), (246.0, -230.0), (246.0, -104.0)),
        ((246.0, -104.0), (246.0, 12.0), (166.0, 102.0), (112.0, 154.0)),
        ((112.0, 154.0), (50.0, 164.0), (-50.0, 164.0), (-112.0, 154.0)),
        ((-112.0, 154.0), (-166.0, 102.0), (-246.0, 12.0), (-246.0, -104.0)),
        ((-246.0, -104.0), (-246.0, -230.0), (-148.0, -328.0), (0.0, -328.0)),
    ]
    return _eval_bezier_poly(segs, steps=40)


def _build_flame_poly() -> list[tuple[float, float]]:
    """Crisp hanging flame / fire-pan drop beneath the balloon mouth."""
    segs = [
        ((0.0, 206.0), (38.0, 240.0), (52.0, 274.0), (34.0, 308.0)),
        ((34.0, 308.0), (18.0, 332.0), (-18.0, 332.0), (-34.0, 308.0)),
        ((-34.0, 308.0), (-52.0, 274.0), (-38.0, 240.0), (0.0, 206.0)),
    ]
    return _eval_bezier_poly(segs, steps=24)


def _build_balloon_ribs() -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Symmetric meridian curve guides for the fire-balloon panel cutouts."""
    left_rib = _eval_bezier_poly(
        [
            ((-16.0, -312.0), (-118.0, -242.0), (-146.0, -112.0), (-78.0, 144.0)),
        ],
        steps=48,
    )
    right_rib = _eval_bezier_poly(
        [
            ((16.0, -312.0), (118.0, -242.0), (146.0, -112.0), (78.0, 144.0)),
        ],
        steps=48,
    )
    return left_rib, right_rib


BALLOON_STAR_POLY = _build_star_poly(0.0, -110.0, 92.0, 38.0)
BALLOON_POLY = _build_balloon_poly()
FLAME_POLY = _build_flame_poly()
BALLOON_LEFT_RIB, BALLOON_RIGHT_RIB = _build_balloon_ribs()
SHIELD_POLY = _build_shield_poly()
ASTROID_POLY = _build_astroid_poly()


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
  <!-- Outer G^2 Continuous Curvature Squircle (r=22.37%, smoothing=60%) -->
  <path d="{sq_path}" fill="#1E293B" stroke="#38BDF8" stroke-width="4"/>
  <!-- 80% Primary Circle (d = 819.2 px, r = 409.6 px) -->
  <circle cx="512" cy="512" r="{PRIMARY_CIRCLE_R:.2f}" fill="none" stroke="#FBBF24" stroke-width="3" stroke-dasharray="12 10"/>
  <!-- 72% Safe Inner Squircle -->
  <path d="{inner_sq_path}" fill="none" stroke="#94A3B8" stroke-width="2" stroke-dasharray="8 8"/>
  <!-- 52% Core Keyline Circle -->
  <circle cx="512" cy="512" r="{SIZE * 0.26:.2f}" fill="none" stroke="#94A3B8" stroke-width="2" stroke-dasharray="8 8"/>
  <!-- Orthogonals & Diagonals -->
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


def _render_icon(
    name: str,
    top_hex: str,
    bot_hex: str,
    motif: str,
    squircle_sd,
    outputs_unmasked: list[Path],
    output_squircle: Path,
) -> None:
    top_rgb = _hex_to_rgb01(top_hex)
    bot_rgb = _hex_to_rgb01(bot_hex)
    white = (1.0, 1.0, 1.0)
    gold = _hex_to_rgb01("#FFD452")
    amber = _hex_to_rgb01("#FF9233")
    lantern_warm = _hex_to_rgb01("#FFF3D6")
    moon_silver = _hex_to_rgb01("#FDE68A")
    mint = _hex_to_rgb01("#5CF2D6")
    coral = _hex_to_rgb01("#FF5263")

    unmasked_px = bytearray(SIZE * SIZE * 3)
    squircle_px = bytearray(SIZE * SIZE * 4)

    for y in range(SIZE):
        py = (y + 0.5) - HALF
        t = y / (SIZE - 1)
        bg_r = top_rgb[0] * (1.0 - t) + bot_rgb[0] * t
        bg_g = top_rgb[1] * (1.0 - t) + bot_rgb[1] * t
        bg_b = top_rgb[2] * (1.0 - t) + bot_rgb[2] * t

        for x in range(SIZE):
            px = (x + 0.5) - HALF
            col = (bg_r, bg_g, bg_b)

            # Fast outer bounding check: all foreground artwork sits inside Primary Circle (r<=410)
            r2 = px * px + py * py
            if r2 <= 460.0 * 460.0:
                if motif == "myanmar":
                    # Tazaungmon Full Moon disc in upper-right sky (100% inside 80% Primary Circle, clear of balloon)
                    d_moon = math.hypot(px - 264.0, py + 252.0) - 34.0
                    moon_a = 1.0 - _smoothstep(-1.1, 1.1, d_moon)
                    if moon_a > 0.0:
                        col = _blend_rgb(col, moon_silver, moon_a * 0.94)

                    # Tazaungdaing Hot-Air Fire Balloon (Mee Pone Pyan) envelope with curved rib & clean star knockout
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

                    # Hanging burner rim bar & glowing flame drop
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
                    # Dual diagonal orbital arcs + smooth 4-point astroid spark with core aperture
                    d_arc1 = _sd_arc(px, py, 336.0, 26.0, -45.0, 56.0)
                    d_arc2 = _sd_arc(px, py, 336.0, 26.0, 135.0, 56.0)
                    arc_a = 1.0 - _smoothstep(-1.1, 1.1, min(d_arc1, d_arc2))
                    if arc_a > 0.0:
                        col = _blend_rgb(col, white, arc_a * 0.55)
                    if abs(px) <= 245.0 and abs(py) <= 245.0:
                        d_ast = _sd_polygon(px, py, ASTROID_POLY) - 10.0
                        d_hole = _sd_circle(px, py, 44.0)
                        d_shape = max(d_ast, -d_hole)
                        sp_a = 1.0 - _smoothstep(-1.1, 1.1, d_shape)
                        if sp_a > 0.0:
                            col = _blend_rgb(col, white, sp_a * 0.98)
                        core_a = 1.0 - _smoothstep(-1.1, 1.1, _sd_circle(px, py, 24.0))
                        if core_a > 0.0:
                            col = _blend_rgb(col, mint, core_a)

                elif motif == "pixel":
                    # 3x3 grid of rounded tiles with clean knockout channel around diagonal block slash
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
                        d_tiles_cut = max(d_tiles, -d_slash_gap)
                        tile_a = 1.0 - _smoothstep(-1.1, 1.1, d_tiles_cut)
                        if tile_a > 0.0:
                            col = _blend_rgb(col, white, tile_a * 0.92)
                    slash_a = 1.0 - _smoothstep(-1.1, 1.1, d_slash_core)
                    if slash_a > 0.0:
                        col = _blend_rgb(col, coral, slash_a)

                elif motif == "shield":
                    # Apple-grid symmetric cubic-bezier shield with knockout checkmark
                    if abs(px) <= 295.0 and abs(py) <= 355.0:
                        d_sh = _sd_polygon(px, py, SHIELD_POLY)
                        d_c1 = _sd_segment(px, py, -110.0, 6.0, -22.0, 96.0) - 34.0
                        d_c2 = _sd_segment(px, py, -22.0, 96.0, 128.0, -76.0) - 34.0
                        d_chk = min(d_c1, d_c2)
                        d_final = max(d_sh, -d_chk)
                        sh_a = 1.0 - _smoothstep(-1.1, 1.1, d_final)
                        if sh_a > 0.0:
                            col = _blend_rgb(col, white, sh_a * 0.96)

            r8 = int(round(_clamp(col[0]) * 255))
            g8 = int(round(_clamp(col[1]) * 255))
            b8 = int(round(_clamp(col[2]) * 255))

            idx3 = (y * SIZE + x) * 3
            unmasked_px[idx3] = r8
            unmasked_px[idx3 + 1] = g8
            unmasked_px[idx3 + 2] = b8

            # Apple G^2 Continuous-Curvature Squircle mask
            d_sq = squircle_sd(px, py)
            sq_a = 1.0 - _smoothstep(-1.1, 1.1, d_sq)
            idx4 = (y * SIZE + x) * 4
            squircle_px[idx4] = r8
            squircle_px[idx4 + 1] = g8
            squircle_px[idx4 + 2] = b8
            squircle_px[idx4 + 3] = int(round(sq_a * 255))

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
        "myanmar-essential",
        "#0B163D",
        "#2F235C",
        defs_extra=bal_defs,
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

    # 2. Google AI & Auth Routing SVG
    ai_a1 = _svg_arc_path(HALF, HALF, 336.0, -101.0, 11.0)
    ai_a2 = _svg_arc_path(HALF, HALF, 336.0, 79.0, 191.0)
    ast_d = _svg_poly_path(ASTROID_POLY)
    ai_mask = [
        '<mask id="ai-cut">',
        '  <rect width="1024" height="1024" fill="white"/>',
        '  <circle cx="512" cy="512" r="44" fill="black"/>',
        '</mask>',
    ]
    _write_svgs(
        "google-ai-auth-proxy",
        "#183B8C",
        "#0C707D",
        defs_extra=ai_mask,
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

    # 3. Meta Pixel MitM SVG
    tiles = []
    for gx in (-164, 0, 164):
        for gy in (-164, 0, 164):
            x0 = 512 + gx - 60
            y0 = 512 + gy - 60
            tiles.append(f'<rect x="{x0}" y="{y0}" width="120" height="120" rx="18" fill="#FFFFFF"/>')
    pixel_mask = [
        '<mask id="pixel-cut">',
        '  <rect width="1024" height="1024" fill="white"/>',
        '  <line x1="248" y1="776" x2="776" y2="248" stroke="black" stroke-width="116" stroke-linecap="round"/>',
        '</mask>',
    ]
    _write_svgs(
        "meta-pixel-mitm",
        "#2D2166",
        "#5E1A66",
        defs_extra=pixel_mask,
        fg_elements_color=[
            f'<g mask="url(#pixel-cut)" opacity="0.92">{"".join(tiles)}</g>',
            '<line x1="248" y1="776" x2="776" y2="248" stroke="#FF5263" stroke-width="60" stroke-linecap="round"/>',
        ],
        fg_elements_mono=[
            f'<g mask="url(#pixel-cut)">{"".join(tiles)}</g>',
            '<line x1="248" y1="776" x2="776" y2="248" stroke="#FFFFFF" stroke-width="60" stroke-linecap="round"/>',
        ],
    )

    # 4. Telemetry Shield SVG
    sh_d = _svg_poly_path(SHIELD_POLY)
    sh_mask = [
        '<mask id="shield-cut">',
        '  <rect width="1024" height="1024" fill="white"/>',
        '  <path d="M 402 518 L 490 608 L 640 436" fill="none" stroke="black" stroke-width="68" stroke-linecap="round" stroke-linejoin="round"/>',
        '</mask>',
    ]
    _write_svgs(
        "telemetry-shield",
        "#0B5E58",
        "#0D2E5C",
        defs_extra=sh_mask,
        fg_elements_color=[f'<path d="{sh_d}" fill="#FFFFFF" mask="url(#shield-cut)" opacity="0.96"/>'],
        fg_elements_mono=[f'<path d="{sh_d}" fill="#FFFFFF" mask="url(#shield-cut)"/>'],
    )


def main() -> None:
    write_grid_overlay_svg()
    _generate_all_svgs()
    squircle_sd = _build_squircle_sd()

    specs = [
        (
            "myanmar-essential",
            "#0B163D",
            "#2F235C",
            "myanmar",
            [ROOT / "icon.png", ROOT / "assets/icons/myanmar-essential.png"],
            ROOT / "assets/icons/squircle/myanmar-essential.png",
        ),
        (
            "google-ai-auth-proxy",
            "#183B8C",
            "#0C707D",
            "ai",
            [ROOT / "assets/icons/google-ai-auth-proxy.png"],
            ROOT / "assets/icons/squircle/google-ai-auth-proxy.png",
        ),
        (
            "meta-pixel-mitm",
            "#2D2166",
            "#5E1A66",
            "pixel",
            [ROOT / "assets/icons/meta-pixel-mitm.png"],
            ROOT / "assets/icons/squircle/meta-pixel-mitm.png",
        ),
        (
            "telemetry-shield",
            "#0B5E58",
            "#0D2E5C",
            "shield",
            [ROOT / "assets/icons/telemetry-shield.png"],
            ROOT / "assets/icons/squircle/telemetry-shield.png",
        ),
    ]

    for name, top_hex, bot_hex, motif, unmasked_outs, squircle_out in specs:
        _render_icon(name, top_hex, bot_hex, motif, squircle_sd, unmasked_outs, squircle_out)
        print(f"Generated 1024px unmasked + G^2 squircle + SVGs for {name}")


if __name__ == "__main__":
    main()
