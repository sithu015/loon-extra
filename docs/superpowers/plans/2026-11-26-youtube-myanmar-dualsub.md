# YouTube Myanmar & DualSub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or strict TDD inline execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and test `plugins/youtube-myanmar-enhance.lpx`, its dual Loon JS modules (`scripts/loon/yt-player-enhance.js` and `scripts/loon/yt-timedtext-dualsub.js`), Apple HIG iconography, validator coverage, and live integration into `FinalV1_cleaned.lcf` + `sithu015/loon-extra`.

**Architecture:** One unified `sithu015/loon-extra` Loon `3.5.1+` plugin replaces `yfamilys/youtube.plugin` + `DualSubs` with zero `/player` conflicts: Rewrite v2 rules strip googlevideo/youtube ad telemetry, `yt-player-enhance.js` patches JSON & binary Protobuf `/player` and `/get_watch` payloads (ad removal, PiP/BG enable, Burmese `my` unlock + optional track injection), and `yt-timedtext-dualsub.js` handles `/api/timedtext` dual-subtitle compositing and Google Translate `tl=my` fallback across XML (`srv3`/`asr`), `json3`, and `WebVTT`.

**Tech Stack:** Loon `3.5.1+` plugin syntax (Rewrite v2 / Script v2), pure zero-dependency JavaScript (Node `v26` `node --test` + Loon JavaScriptCore), Python 3 `unittest` + `validate_loon.py` + `update_sources.py` + `generate_icons.py`.

---

### Task 1: Icon Asset Generation & Validator Support

**Files:**
- Modify: `scripts/generate_icons.py`
- Modify: `tests/test_icons.py`
- Modify: `scripts/validate_loon.py`
- Modify: `tests/test_validate_loon.py`

- [ ] **Step 1: Write failing tests in `tests/test_icons.py` and `tests/test_validate_loon.py`**
  - Add `"youtube-myanmar-enhance"` to `IconDesignSystemTests.NAMES`.
  - Add validator unit test verifying `_validate_script_section` catches missing local `scripts/loon/*.js` paths and undefined `${arg}` references in `[Script]`.
- [ ] **Step 2: Run tests to verify failure (`RED`)**
  - Run: `python3 -m unittest tests/test_icons.py tests/test_validate_loon.py -v`
  - Expected: FAIL (`Missing youtube-myanmar-enhance.png`, missing `_validate_script_section` checks).
- [ ] **Step 3: Implement icon rendering in `scripts/generate_icons.py` and script validation in `scripts/validate_loon.py`**
  - Add `"youtube"` motif (rounded play prism + twin stacked dual-subtitle caption bars inside the 80% primary circle) with `#9B142C` -> `#4A0D36` gradient in `_render_icon` and `_generate_all_svgs`, and add `"youtube-myanmar-enhance"` to `specs`.
  - Add `_validate_script_section` in `scripts/validate_loon.py` to check `REPO_RAW_PREFIX` `.js` paths exist on disk and validate `${var}` placeholders against `[Argument]` (plus built-in `${url}`).
- [ ] **Step 4: Run icon generator + tests to verify pass (`GREEN`)**
  - Run: `python3 scripts/generate_icons.py && python3 -m unittest tests/test_icons.py tests/test_validate_loon.py -v`
  - Expected: All pass cleanly.

---

### Task 2: TDD Core — YouTube Player & Watch Enhancer (`scripts/loon/yt-player-enhance.js`)

**Files:**
- Create: `tests/js/yt_plugin.test.mjs`
- Create: `scripts/loon/yt-player-enhance.js`

- [ ] **Step 1: Write failing Node tests for Protobuf codec & YouTube JSON/Protobuf player enhancer**
  - Test lossless Protobuf wire roundtrip preserving unknown varints, 64-bit ints, nested messages, and packed/unpacked repeated scalar fields byte-for-byte.
  - Test JSON `/player` patching: removes `adPlacements`/`adSlots`, sets `pictureInPictureRender` & `backgroundPlayerRender`, enables `isTranslatable`, inserts/promotes `my` (`မြန်မာ (Burmese)`), injects synthetic `my` track when `autoMyanmar=true`, and avoids duplicates when `my` track already exists or `captionTracks` is empty.
  - Test binary Protobuf `/player` and `/get_watch` patching using real encoded YouTube wire messages (`#7`, `#68`, `#9->#18`, `#2->{#21,#11}`, `#10->#51621377->{#1,#2,#3,#6}`, and `GetWatch #1->#2`), verifying decoded output preserves unknown fields and modifies captions/ads/PiP accurately.
- [ ] **Step 2: Run Node test to verify failure (`RED`)**
  - Run: `node --test tests/js/yt_plugin.test.mjs`
  - Expected: FAIL (`Cannot find module .../scripts/loon/yt-player-enhance.js`).
- [ ] **Step 3: Implement `scripts/loon/yt-player-enhance.js`**
  - Implement minimal, readable lossless Protobuf wire reader/writer (`decodeFields`, `encodeFields`, `readVarintRaw`, `writeVarint`, `utf8Decode`, `utf8Encode`).
  - Implement JSON and Protobuf transformation functions for `/player` and `/get_watch`, plus Loon entrypoint guarded by `typeof $request !== "undefined" && typeof $done === "function"` and `module.exports` export for tests.
- [ ] **Step 4: Run Node tests to verify pass (`GREEN`)**
  - Run: `node --test tests/js/yt_plugin.test.mjs`
  - Expected: All Player tests PASS.

---

### Task 3: TDD Core — TimedText Dual Subtitle & Burmese Translator (`scripts/loon/yt-timedtext-dualsub.js`)

**Files:**
- Modify: `tests/js/yt_plugin.test.mjs`
- Create: `scripts/loon/yt-timedtext-dualsub.js`
- Create: `tests/test_yt_myanmar_dualsub.py`

- [ ] **Step 1: Add failing Node tests for XML (`srv3`/`asr`), JSON3, WebVTT compositing, Google Translate batching, and recursion guards**
  - Test `srv3` XML & `asr` karaoke `<s>` flattening, entity unescape/escape (`&#39;`, `&amp;`), empty `a="1"` drop, `<wp rc="1"/>` normalization, and timestamp tolerance matching (`<= 300ms`).
  - Test `json3` (`events[].segs[]`) and `WebVTT` compositing across `dual_orig_top`, `dual_my_top`, and `my_only`.
  - Test request phase rewrite (`!tlang && autoMyanmar -> sets tlang=my`, internal `X-YTMy-Raw` bypass without touching query signatures, `google_only` tlang deferral via cache).
  - Test Google Translate fallback batching (`translate.googleapis.com` mock transport via dependency injection) including per-cue fallback when batched delimiter count mismatches, plus NFC normalization of Burmese strings.
- [ ] **Step 2: Run Node tests to verify failure (`RED`)**
  - Run: `node --test tests/js/yt_plugin.test.mjs`
  - Expected: FAIL on new TimedText tests.
- [ ] **Step 3: Implement `scripts/loon/yt-timedtext-dualsub.js` and `tests/test_yt_myanmar_dualsub.py`**
  - Implement XML parser/serializer, JSON3 parser/serializer, VTT parser/serializer, monotonic overlap cue aligner, batched Google Translate `tl=my` client with fallback, bounded persistent cache helpers, and clean Loon entrypoint (`$httpClient` + `$persistentStore` + `$done`).
  - Create `tests/test_yt_myanmar_dualsub.py` invoking `node --test tests/js/yt_plugin.test.mjs` inside Python `unittest` so `python3 -m unittest discover -s tests -v` verifies everything together.
- [ ] **Step 4: Run all Node and Python tests (`GREEN`)**
  - Run: `node --test tests/js/yt_plugin.test.mjs && python3 -m unittest discover -s tests -v`
  - Expected: 100% PASS.

---

### Task 4: Create Plugin Manifest, Update Hashes/Docs, Publish to GitHub & Integrate into `FinalV1_cleaned.lcf`

**Files:**
- Create: `plugins/youtube-myanmar-enhance.lpx`
- Modify: `README.md`
- Modify: `docs/finalv1-integration.md`
- Modify: `templates/loon-base.example.lcf`
- Modify (local): `/Library/Application Support/com.loon.Loon/config/FinalV1_cleaned.lcf`

- [ ] **Step 1: Write `plugins/youtube-myanmar-enhance.lpx` and sync SHA-256 `#!source`**
  - Write plugin manifest matching Loon `3.5.1+` spec and run `python3 scripts/update_sources.py`.
- [ ] **Step 2: Update `README.md`, `docs/finalv1-integration.md`, and `templates/loon-base.example.lcf`**
  - Add squircle icon preview, install links, `#!source` SHA-256 row, template `[Plugin]` entry (commented/disabled optional or enabled cleanly matching existing entries), and Myanmar/English usage note (reminding MITM CA trust for YouTube).
- [ ] **Step 3: Run full validation & test suite**
  - Run: `python3 scripts/update_sources.py --check && python3 scripts/validate_loon.py --strict && python3 -m unittest discover -s tests -v`
  - Expected: All 5 plugins, 7 rulesets, 1 template, icon tests, and JS/Python tests pass with zero warnings/errors.
- [ ] **Step 4: Commit & push `sithu015/loon-extra` cleanly to `main`**
  - Verify `git status` contains no secrets or `.lcf` leaks; commit and `git push origin main`.
- [ ] **Step 5: Wire `plugins/youtube-myanmar-enhance.lpx` into local `FinalV1_cleaned.lcf` and verify live fetch**
  - Add `https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/youtube-myanmar-enhance.lpx, enabled=true` under `[Plugin]` in `FinalV1_cleaned.lcf`, validate `FinalV1_cleaned.lcf` (`0` non-secret errors, `0` warnings), and confirm Loon fetches & caches the new plugin cleanly in `remotePlugin/`.
