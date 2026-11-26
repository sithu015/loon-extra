# YouTube AdBlock, PiP & Burmese Dual Subtitle Plugin (`youtube-myanmar-enhance`) Design Spec

**Date:** 2026-11-26
**Target Repository:** `sithu015/loon-extra` (`/Users/sithuaung/.gemini/antigravity/scratch/loon-extra`)
**Target Loon Version:** Loon `3.5.1(983)+` (iOS, iPadOS, macOS)
**Local Integration Target:** `/Library/Application Support/com.loon.Loon/config/FinalV1_cleaned.lcf`

---

## 1. Problem & Goal

Existing community YouTube plugins on `yfamilys.com/loon` and GitHub have two incompatible gaps for Myanmar users:
1. `yfamilys.com/plugin/youtube.plugin` (`Maasea`) provides player AdBlock, Picture-in-Picture (PiP), and Background Play, but restricts `translationLanguages` to 11 languages without Burmese (`my`) and renders at most a single translated caption track.
2. `DualSubs.YouTube.plugin` (`DualSubs`) provides dual-subtitle compositing across `timedtext` formats, but provides no in-player ad removal or PiP/Background Play, defaults to Chinese presets via external web panels, and collides with `Maasea` because both attach `http-response` (`binary-body-mode=1`) scripts to `youtubei.googleapis.com/youtubei/v1/player` and `/get_watch`.

**Goal:** Build a self-contained, auditable, zero-conflict Loon `3.5.1+` plugin suite inside `sithu015/loon-extra` (`plugins/youtube-myanmar-enhance.lpx`) unifying:
- YouTube AdBlock (URL rewrites + `/player` & `/get_watch` `adPlacements`/`adSlots` removal)
- Picture-in-Picture & Background Playback unlock
- Burmese (`my` — `မြန်မာ (Burmese)`) caption unlock, promotion, and optional auto-enablement
- Dual Subtitle (`Original + Myanmar`, `Myanmar + Original`, or `Myanmar Only`) across `srv3` XML (including `asr` auto-captions), `json3`, and `WebVTT`, using YouTube native `tlang=my` with automatic Google Translate fallback (`sl=auto&tl=my`).

---

## 2. Architecture & Component Boundaries

### 2.1 Plugin Manifest (`plugins/youtube-myanmar-enhance.lpx`)
- Uses `sithu015/loon-extra` required `#!` headers (`name`, `desc`, `author`, `homepage`, `icon`, dual `#!source` SHA-256 checksums, `system`, `system_version`, `loon_version = 3.5.1(983)`, `date`, `tag`, `type = normal`).
- Declares native Loon UI `[Argument]` controls:
  - `subtitleMode` (`select`: `"dual_orig_top"`, `"dual_my_top"`, `"my_only"`)
  - `translationMode` (`select`: `"hybrid"`, `"google_only"`, `"youtube_only"`)
  - `autoMyanmar` (`switch`: `true`)
  - `enableAdBlock` (`switch`: `true`)
  - `enablePipBg` (`switch`: `true`)
- Uses Loon `3.5.1+` Rewrite v2 (`request if ${enableAdBlock} == true && ${url} ~= ... then ...`) for `googlevideo.com` (`&ctier=L`, `&oad`) and YouTube ad stat endpoints (`api/stats/ads`, `pagead`, `ptracking`, `api/stats/qoe?adcontext`).
- Separates Web JSON and App Binary Protobuf `[Script]` rules so `$response.body` types match cleanly:
  1. Web JSON (`/player` on `(www|m|tv).youtube.com`): `requires_body=true` (string JSON).
  2. App Protobuf (`/player` and `/get_watch` on `youtubei.googleapis.com`): `requires_body=true, binary_body_mode=true` (`Uint8Array`).
  3. TimedText Request (`/api/timedtext` on `(www|m).youtube.com`): `request` phase.
  4. TimedText Response (`/api/timedtext` on `(www|m).youtube.com`): `response` phase with `requires_body=true`.
- `[Mitm]`: `hostname = -redirector*.googlevideo.com, *.googlevideo.com, www.youtube.com, m.youtube.com, tv.youtube.com, youtubei.googleapis.com, s.youtube.com` (excludes `-redirector*.googlevideo.com` to avoid decrypting raw video CDN streams).

### 2.2 Player & Watch Enhancer (`scripts/loon/yt-player-enhance.js`)
- Supports both UTF-8 JSON (and defensive `Uint8Array` JSON decode) and binary Protobuf via a lossless raw-wire Protobuf scanner/serializer (`decodeFields` / `encodeFields`) that preserves every unmodified field verbatim.
- Verified YouTube Protobuf field numbers patched:
  - `Player`: `#7 adPlacements` (remove), `#68 adSlots` (remove), `#9 playbackTracking` -> `#18 pageadViewthroughconversion` (remove), `#2 playabilityStatus` -> `#21 pictureInPictureRender` (`#151635310` -> `#1 active=true`) & `#11 backgroundPlayerRender` (`#64657230` -> `#1 active=true`), `#10 captions` -> `#51621377 playerCaptionsTracklistRenderer`.
  - `GetWatch`: `#1 contents` -> `#2 player`.
  - `PlayerCaptionsTracklistRenderer`: `#1 captionTracks` (`#1 baseUrl`, `#2 name` Label `{#1 runs: [{#1 text}]}`, `#3 vssId`, `#4 languageCode`, `#7 isTranslatable`), `#2 audioTracks` (`#2 captionTrackIndices`, `#3 defaultCaptionTrackIndex`, `#5 visibility`, `#6 hasDefaultTrack`, `#11 captionsInitialState`), `#3 translationLanguages` (`#1 languageCode`, `#2 languageName` Label), `#6 defaultCaptionTrackIndex`.
- Caption logic:
  - Marks all existing `captionTracks` `isTranslatable = true`.
  - Inserts or promotes `{ languageCode: "my", languageName: "မြန်မာ (Burmese)" }` at index `0` of `translationLanguages` (using desktop `simpleText` or mobile/app `runs` structure appropriately).
  - When `autoMyanmar == true` and no native `my` track exists in non-empty `captionTracks`, picks base track (`en` first, else `en-*`, else `captionTracks[0]`), strips any existing `tlang` param safely, appends `tlang=my`, injects `"မြန်မာ (Dual/Auto)"` track, and registers its index in `audioTracks` + `defaultCaptionTrackIndex`.

### 2.3 TimedText Dual Subtitle & Burmese Translator (`scripts/loon/yt-timedtext-dualsub.js`)
- **Recursion Guard:** Internal fetches of original caption tracks attach HTTP header `X-YTMy-Raw: 1` (never mutating signed URL query parameters other than removing `tlang`). Request hook removes `X-YTMy-Raw` and passes through unmodified; Response hook exits immediately when internal fetch marker matches active URL cache or header.
- **Request Phase:**
  - Caches original `lang` per video `v` in `$persistentStore` (bounded LRU, max 50 entries).
  - If `!tlang && autoMyanmar && lang && !isBurmese(lang)`: adds `tlang=my`.
  - If `translationMode === "google_only"` and `tlang === "my"`: removes `tlang` before forwarding upstream, stores target metadata keyed cleanly so response phase translates original directly via Google Translate without wasting a YouTube `tlang` fetch, OR forwards normally and translates response fallback cleanly. (Design choice: keep `tlang` stripped only when `translationMode === "google_only"` by encoding state in short-lived per-video cache so `sparams` HMAC is never corrupted by custom query params!)
- **Response Phase:**
  - Parses XML (`srv3` / `<timedtext>`), JSON3 (`events[]`), or WebVTT cleanly without external runtime dependencies.
  - Normalizes YouTube `asr` rolling `<s ...>` karaoke tags into clean text paragraphs, removes empty `a="1"` spacer nodes and `wWinId` overlap attributes, and clamps `<wp rc="1">` to avoid Myanmar stacked-diacritic line clipping.
  - **Hybrid Translation & Composition:**
    1. If source track is already Burmese (`my`), normalize and return unmodified.
    2. In `hybrid` or `youtube_only`: if YouTube response contains valid cues, fetch original track (`tlang` removed), align cues by timestamp tolerance (`<= 300ms` monotonic overlap window), and format per `subtitleMode` (`dual_orig_top`, `dual_my_top`, `my_only`).
    3. If YouTube `tlang=my` returns empty/non-200 or `translationMode === "google_only"`: translate original cues via batched `translate.googleapis.com/translate_a/single?client=gtx&dt=t&sl=auto&tl=my` requests with sentinel/count validation and single-cue retry fallback, normalize output with Unicode `NFC`, and merge per `subtitleMode`.
- Fails open (`$done({})`) on unexpected parse/network exceptions so captions never break completely.

### 2.4 Validation, Iconography & Tests
- Add `youtube-myanmar-enhance` icon rendering in `scripts/generate_icons.py` (`1024x1024` unmasked RGB master + `G²` squircle RGBA export + layered Liquid Glass SVGs).
- Extend `scripts/validate_loon.py` to validate `[Script]` entries referencing `sithu015/loon-extra` local `.js` files and `${arg}` parameter references against `[Argument]`.
- Add `tests/js/yt_plugin.test.mjs` (`node --test`) + `tests/test_yt_myanmar_dualsub.py` unittest bridge covering protobuf roundtrips, ad/PiP patching, Burmese track injection, XML/`asr`/JSON3/VTT dual alignment, translator batching fallback, and error isolation.

---

## 3. Security & Policy Constraints

- Zero third-party runtime JavaScript dependencies: both JS files live in `sithu015/loon-extra/scripts/loon/` and are directly auditable.
- Plugin `[Rule]` contains no custom `.lcf` group names (if any rules needed, only `DIRECT`, `PROXY`, `REJECT*`).
- `FinalV1_cleaned.lcf` `[MITM]` and `[Proxy]` secrets remain excluded from `sithu015/loon-extra`.
- Dual `#!source` SHA-256 hashes synced via `scripts/update_sources.py` before pushing.
