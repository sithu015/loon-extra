# Icon Design System (Apple HIG & Liquid Glass Architecture)

All plugin icons in `sithu015/loon-extra` are engineered from a single vector specification following Apple's Human Interface Guidelines (App Icons, Continuous Curvature, Icon Grid, and Liquid Glass layered architecture).

## 1. Geometry: `G²` Continuous Curvature vs `G¹` Rounded Rectangles

Standard circular-arc rounded rectangles (`rx`) jump abruptly in curvature from `0` (straight edge) to `1/r` (circular arc) at the seam (`G¹` discontinuity), producing visible corner tension.

For pre-masked web/README showcase assets (`assets/icons/squircle/*.png`) and grid overlays (`assets/icons/svg/apple-icon-grid.svg`), this repository implements the exact Apple/Figma **`G²` Continuous-Curvature Squircle**:
- **Corner Radius Ratio**: `22.37%` of canvas width (`229.07 px` on `1024 px`)
- **Corner Smoothing**: `60%` (`σ = 0.60`), using cubic Bézier shoulder transitions into a `36°` central arc

## 2. Unmasked Square Masters (`#!icon` & Apple HIG)

Per Apple HIG (*Hardware Concentricity*), platforms apply system masking (`Squircle` on iOS/iPadOS/macOS, `Circular` on watchOS/visionOS) automatically:
- **`icon.png` & `assets/icons/*.png`**: Exported as **`1024×1024 px` unmasked opaque sRGB squares** with full-bleed gradients and zero baked drop shadows, bevels, borders, or glow filters. This prevents double-rounding or dark halo artifacts when Loon clips `#!icon` images.
- **`assets/icons/squircle/*.png`**: Exported as **`1024×1024 px` RGBA PNGs** clipped to the exact `G²` Squircle for README and web previews.

## 3. Icon Grid & Liquid Glass Layered SVGs (`iOS 26+`)

- **80% Primary Circle (`d = 819.2 px`, `r = 409.6 px`)**: Every foreground emblem is centered inside the primary circle and safe optical zone so neither `Squircle` nor `Circular` masks clip key geometry.
- **Original Vector Geometry**: Custom geometric emblems only — no raw SF Symbols are embedded as icons.
- **Icon Composer Ready (`assets/icons/svg/`)**:
  - `<name>.svg` separates `<g id="background">` and `<g id="foreground">` on a `1024×1024` vector canvas.
  - `<name>-foreground.svg` provides clean, monochrome-compatible sharp vector silhouettes with negative-space knockouts so all **6 Liquid Glass Appearances** (`Default`, `Dark`, `Clear Light`, `Clear Dark`, `Tinted Light`, `Tinted Dark`) retain high silhouette contrast.
- **Reference Grid**: [`assets/icons/svg/apple-icon-grid.svg`](../assets/icons/svg/apple-icon-grid.svg)

## 4. Tazaungdaing × Loon Motif (`myanmar-essential`)

The flagship `myanmar-essential` icon (`icon.png`) unites **Loon's original hot-air balloon identity** with Myanmar's **Tazaungdaing Fire-Balloon Festival (တန်ဆောင်တိုင် မီးပုံးပျံပွဲ)**:
- Deep Tazaungmon night-sky backdrop (`#0B163D → #2F235C`) with a subtle full moon disc inside the 80% Primary Circle.
- Symmetric cubic-Bézier **Mee Pone Pyan (မီးပုံးပျံ)** lantern envelope with negative-space meridian ribs, a centered 5-pointed star aperture, and a warm flame drop below the rim — retaining crisp contrast even in monochrome Liquid Glass `Tinted` and `Clear` variants.
