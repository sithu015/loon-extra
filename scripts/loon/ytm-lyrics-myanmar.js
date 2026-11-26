/**
 * YouTube Music Bilingual Myanmar Lyrics & Browse Filter for Loon 3.5.1+
 * - Translates both Timed/Synced Lyrics (timedLyricsRender 465160965) and
 *   Plain Lyrics (musicDescriptionShelfRenderer 221496734) into Burmese (my)
 * - Supports Web/PWA JSON (`music.youtube.com`) and iOS/macOS App Protobuf (`youtubei.googleapis.com`)
 * - Preserves cue-time/sync fields and unknown Protobuf fields losslessly
 * - Caches translations in a bounded store (@sithu015.loon_extra.ytm_lyrics_cache, max 40 songs)
 * - Strips sponsored/Premium upsell shelves on regular `browse` feeds
 */

(function (root) {
  "use strict";

  const MY_CODE = "my";
  const CACHE_KEY = "@sithu015.loon_extra.ytm_lyrics_cache";
  const MAX_CACHE_SONGS = 40;
  const MAX_BATCH_ENCODED_LEN = 1200;
  const MYANMAR_CHAR_RE = /[\u1000-\u109f\uaa60-\uaa7f]/;
  const PUNCT_ONLY_RE = /^[\s♪♫•·.,!?;:'"()[\]{}\-–—*/\\~`]+$/;

  const _decoder = typeof TextDecoder !== "undefined" ? new TextDecoder("utf-8") : null;
  const _encoder = typeof TextEncoder !== "undefined" ? new TextEncoder() : null;

  function utf8Decode(bytes) {
    if (_decoder) return _decoder.decode(bytes);
    let str = "";
    for (let i = 0; i < bytes.length; ) {
      const b = bytes[i++];
      if (b < 0x80) str += String.fromCharCode(b);
      else if ((b & 0xe0) === 0xc0) str += String.fromCharCode(((b & 0x1f) << 6) | (bytes[i++] & 0x3f));
      else if ((b & 0xf0) === 0xe0) {
        const b2 = bytes[i++];
        const b3 = bytes[i++];
        str += String.fromCharCode(((b & 0x0f) << 12) | ((b2 & 0x3f) << 6) | (b3 & 0x3f));
      } else {
        const b2 = bytes[i++];
        const b3 = bytes[i++];
        const b4 = bytes[i++];
        let cp = ((b & 0x07) << 18) | ((b2 & 0x3f) << 12) | ((b3 & 0x3f) << 6) | (b4 & 0x3f);
        cp -= 0x10000;
        str += String.fromCharCode(0xd800 + (cp >> 10), 0xdc00 + (cp & 0x3ff));
      }
    }
    return str;
  }

  function utf8Encode(str) {
    if (_encoder) return _encoder.encode(str);
    const out = [];
    for (let i = 0; i < str.length; i++) {
      let cp = str.charCodeAt(i);
      if (cp >= 0xd800 && cp <= 0xdbff && i + 1 < str.length) {
        const lo = str.charCodeAt(++i);
        cp = 0x10000 + ((cp - 0xd800) << 10) + (lo - 0xdc00);
      }
      if (cp < 0x80) out.push(cp);
      else if (cp < 0x800) out.push(0xc0 | (cp >> 6), 0x80 | (cp & 0x3f));
      else if (cp < 0x10000) out.push(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
      else out.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3f), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
    }
    return Uint8Array.from(out);
  }

  function concatBytes(arrays) {
    let total = 0;
    for (let i = 0; i < arrays.length; i++) total += arrays[i].length;
    const out = new Uint8Array(total);
    let pos = 0;
    for (let i = 0; i < arrays.length; i++) {
      out.set(arrays[i], pos);
      pos += arrays[i].length;
    }
    return out;
  }

  function readVarintSlice(buf, pos) {
    const start = pos;
    let shift = 0n;
    let val = 0n;
    while (pos < buf.length) {
      const b = buf[pos++];
      val |= BigInt(b & 0x7f) << shift;
      if ((b & 0x80) === 0) return { val, start, end: pos, bytes: buf.subarray(start, pos) };
      shift += 7n;
      if (shift > 70n) throw new Error("Varint overflow");
    }
    throw new Error("Truncated varint");
  }

  function writeVarint(value) {
    let v = typeof value === "bigint" ? value : BigInt(value);
    if (v < 0n) v = BigInt.asUintN(64, v);
    const out = [];
    while (v >= 0x80n) {
      out.push(Number((v & 0x7fn) | 0x80n));
      v >>= 7n;
    }
    out.push(Number(v));
    return Uint8Array.from(out);
  }

  function decodeFields(buf) {
    const fields = [];
    let pos = 0;
    while (pos < buf.length) {
      const tagInfo = readVarintSlice(buf, pos);
      pos = tagInfo.end;
      const no = Number(tagInfo.val >> 3n);
      const wireType = Number(tagInfo.val & 7n);
      let data;
      if (wireType === 0) {
        const vInfo = readVarintSlice(buf, pos);
        pos = vInfo.end;
        data = vInfo.bytes;
      } else if (wireType === 1) {
        if (pos + 8 > buf.length) throw new Error("Truncated fixed64");
        data = buf.subarray(pos, pos + 8);
        pos += 8;
      } else if (wireType === 2) {
        const lenInfo = readVarintSlice(buf, pos);
        pos = lenInfo.end;
        const len = Number(lenInfo.val);
        if (pos + len > buf.length) throw new Error("Truncated length-delimited field");
        data = buf.subarray(pos, pos + len);
        pos += len;
      } else if (wireType === 3) {
        const groupStart = pos;
        let depth = 1;
        while (depth > 0) {
          const innerTag = readVarintSlice(buf, pos);
          pos = innerTag.end;
          const wt = Number(innerTag.val & 7n);
          if (wt === 0) pos = readVarintSlice(buf, pos).end;
          else if (wt === 1) pos += 8;
          else if (wt === 2) {
            const li = readVarintSlice(buf, pos);
            pos = li.end + Number(li.val);
          } else if (wt === 3) depth++;
          else if (wt === 4) depth--;
          else if (wt === 5) pos += 4;
          else throw new Error("Unsupported wireType inside group: " + wt);
          if (pos > buf.length) throw new Error("Truncated group");
        }
        data = buf.subarray(groupStart, pos);
      } else if (wireType === 5) {
        if (pos + 4 > buf.length) throw new Error("Truncated fixed32");
        data = buf.subarray(pos, pos + 4);
        pos += 4;
      } else {
        throw new Error("Unsupported wireType: " + wireType);
      }
      fields.push({ no, wireType, tagBytes: tagInfo.bytes, data });
    }
    return fields;
  }

  function encodeFields(fields) {
    const parts = [];
    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      parts.push(f.tagBytes || writeVarint((BigInt(f.no) << 3n) | BigInt(f.wireType)));
      if (f.wireType === 2) parts.push(writeVarint(f.data.length));
      parts.push(f.data);
    }
    return concatBytes(parts);
  }

  function bytesField(no, payload) {
    return { no, wireType: 2, data: typeof payload === "string" ? utf8Encode(payload) : payload };
  }

  // --- Cache & Translation Helpers ---

  function makeStore(rawStore) {
    if (rawStore && typeof rawStore.read === "function" && typeof rawStore.write === "function") {
      return rawStore;
    }
    if (typeof $persistentStore !== "undefined") {
      return {
        read: (k) => $persistentStore.read(k),
        write: (v, k) => $persistentStore.write(v, k),
      };
    }
    return { read: () => null, write: () => false };
  }

  function hashKey(lines) {
    let h = 2166136261;
    const str = lines.join("\n");
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return "ytm_" + (h >>> 0).toString(36) + "_" + lines.length;
  }

  function loadCache(store) {
    try {
      const raw = store.read(CACHE_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch (_e) {
      return {};
    }
  }

  function saveCache(store, cacheObj, key, lines) {
    try {
      const out = { ...cacheObj };
      delete out[key];
      out[key] = lines;
      const keys = Object.keys(out);
      while (keys.length > MAX_CACHE_SONGS) {
        delete out[keys.shift()];
      }
      store.write(JSON.stringify(out), CACHE_KEY);
    } catch (_e) {
      // Ignore persistence write failures
    }
  }

  function shouldSkipTranslation(line) {
    const t = String(line || "").trim();
    if (!t || MYANMAR_CHAR_RE.test(t) || PUNCT_ONLY_RE.test(t)) return true;
    return false;
  }

  function parseGoogleTranslateResponse(bodyStr, expectedCount) {
    try {
      const data = JSON.parse(bodyStr);
      if (!Array.isArray(data) || !Array.isArray(data[0])) return [];
      const joined = data[0].map((seg) => (Array.isArray(seg) ? seg[0] || "" : "")).join("");
      const splitLines = joined.split("\n");
      if (splitLines.length === expectedCount) return splitLines;
      // Fallback: align or trim if trailing empty newline present
      while (splitLines.length > expectedCount && splitLines[splitLines.length - 1] === "") {
        splitLines.pop();
      }
      return splitLines;
    } catch (_e) {
      return [];
    }
  }

  function defaultHttpGet(url) {
    return new Promise((resolve) => {
      if (typeof $httpClient === "undefined" || typeof $httpClient.get !== "function") {
        resolve(null);
        return;
      }
      $httpClient.get({ url, timeout: 8 }, (err, resp, body) => {
        if (err || !resp || (resp.status !== 200 && resp.statusCode !== 200)) {
          resolve(null);
          return;
        }
        resolve(body);
      });
    });
  }

  async function batchTranslateLines(lines, httpGet) {
    const results = new Array(lines.length).fill("");
    const needIdx = [];
    for (let i = 0; i < lines.length; i++) {
      if (!shouldSkipTranslation(lines[i])) needIdx.push(i);
    }
    if (needIdx.length === 0) return results;

    let pos = 0;
    while (pos < needIdx.length) {
      const chunkIndices = [];
      let encodedLen = 0;
      while (pos < needIdx.length) {
        const idx = needIdx[pos];
        const clean = String(lines[idx]).replace(/\r?\n/g, " ").trim();
        const addLen = encodeURIComponent(clean + "\n").length;
        if (chunkIndices.length > 0 && encodedLen + addLen > MAX_BATCH_ENCODED_LEN) break;
        chunkIndices.push({ idx, text: clean });
        encodedLen += addLen;
        pos++;
      }

      const payload = chunkIndices.map((c) => c.text).join("\n");
      const url =
        "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=" +
        MY_CODE +
        "&dt=t&q=" +
        encodeURIComponent(payload);
      const body = await httpGet(url);
      if (body) {
        const translated = parseGoogleTranslateResponse(body, chunkIndices.length);
        for (let k = 0; k < chunkIndices.length; k++) {
          const val = translated[k] ? String(translated[k]).trim() : "";
          if (val) results[chunkIndices[k].idx] = val;
        }
      }
    }
    return results;
  }

  function formatLyricLine(orig, trans, mode, indentPrefix) {
    const o = String(orig || "");
    const tr = String(trans || "").trim();
    if (!tr || tr === o.trim()) return o;
    const prefix = indentPrefix || "\n";
    if (mode === "my_only") return tr;
    if (mode === "dual_my_top") return tr + prefix + o;
    return o + prefix + tr;
  }

  async function translateWithCache(lines, store, httpGet) {
    if (!lines.length) return [];
    const key = hashKey(lines);
    const cache = loadCache(store);
    if (Array.isArray(cache[key]) && cache[key].length === lines.length) {
      return cache[key];
    }
    const translated = await batchTranslateLines(lines, httpGet);
    if (translated.some(Boolean)) {
      saveCache(store, cache, key, translated);
    }
    return translated;
  }

  // --- JSON Lyrics & Upsell Handlers ---

  function stripBrowseAdsUpsellsJson(node, opts, depth) {
    if (!node || typeof node !== "object" || depth > 14) return false;
    let changed = false;
    const promoKeys = new Set(["mealbarPromoRenderer", "musicMealbarPromoRenderer", "interstitialPromoRenderer", "statementBannerRenderer"]);
    const adKeys = new Set(["adSlotRenderer", "compactPromotedItemRenderer", "brandVideoSingletonRenderer"]);

    if (Array.isArray(node)) {
      for (let i = node.length - 1; i >= 0; i--) {
        const el = node[i];
        let drop = false;
        if (el && typeof el === "object") {
          if (opts.enableAdBlock) {
            for (const k of adKeys) if (Object.prototype.hasOwnProperty.call(el, k)) drop = true;
          }
          if (opts.removeUpsells) {
            for (const k of promoKeys) if (Object.prototype.hasOwnProperty.call(el, k)) drop = true;
          }
        }
        if (drop) {
          node.splice(i, 1);
          changed = true;
        } else if (stripBrowseAdsUpsellsJson(el, opts, depth + 1)) {
          changed = true;
        }
      }
      return changed;
    }

    for (const k of Object.keys(node)) {
      if ((opts.enableAdBlock && adKeys.has(k)) || (opts.removeUpsells && promoKeys.has(k))) {
        delete node[k];
        changed = true;
      } else if (stripBrowseAdsUpsellsJson(node[k], opts, depth + 1)) {
        changed = true;
      }
    }
    return changed;
  }

  function collectJsonLyricTargets(node, plainRuns, timedRuns, depth) {
    if (!node || typeof node !== "object" || depth > 14) return;
    if (Array.isArray(node)) {
      for (let i = 0; i < node.length; i++) collectJsonLyricTargets(node[i], plainRuns, timedRuns, depth + 1);
      return;
    }
    if (
      node.musicDescriptionShelfRenderer &&
      node.musicDescriptionShelfRenderer.description &&
      Array.isArray(node.musicDescriptionShelfRenderer.description.runs)
    ) {
      for (const r of node.musicDescriptionShelfRenderer.description.runs) {
        if (r && typeof r.text === "string" && r.text.trim()) plainRuns.push(r);
      }
    }
    if (
      node.timedLyricsRenderer &&
      node.timedLyricsRenderer.timedLyricsContent &&
      Array.isArray(node.timedLyricsRenderer.timedLyricsContent.runs)
    ) {
      for (const r of node.timedLyricsRenderer.timedLyricsContent.runs) {
        if (r && typeof r.text === "string") timedRuns.push(r);
      }
    }
    for (const k of Object.keys(node)) {
      if (k === "musicDescriptionShelfRenderer" || k === "timedLyricsRenderer") continue;
      collectJsonLyricTargets(node[k], plainRuns, timedRuns, depth + 1);
    }
  }

  async function transformBrowseJson(jsonText, rawOpts, deps) {
    const opts = normalizeOpts(rawOpts);
    const store = makeStore(deps && deps.store);
    const httpGet = (deps && deps.httpGet) || defaultHttpGet;

    let data;
    try {
      data = JSON.parse(jsonText);
    } catch (_e) {
      return { changed: false, body: jsonText };
    }
    if (!data || typeof data !== "object") return { changed: false, body: jsonText };

    let changed = stripBrowseAdsUpsellsJson(data, opts, 0);

    if (opts.lyricsMode !== "off") {
      const plainRuns = [];
      const timedRuns = [];
      collectJsonLyricTargets(data, plainRuns, timedRuns, 0);

      for (let i = 0; i < plainRuns.length; i++) {
        const lines = plainRuns[i].text.split("\n");
        const translated = await translateWithCache(lines, store, httpGet);
        if (translated.some(Boolean)) {
          plainRuns[i].text = lines
            .map((line, idx) => (line.trim() ? formatLyricLine(line, translated[idx], opts.lyricsMode, "\n  └ ") : line))
            .join("\n");
          changed = true;
        }
      }

      if (timedRuns.length > 0) {
        const lines = timedRuns.map((r) => r.text);
        const translated = await translateWithCache(lines, store, httpGet);
        if (translated.some(Boolean)) {
          for (let i = 0; i < timedRuns.length; i++) {
            if (timedRuns[i].text.trim()) {
              timedRuns[i].text = formatLyricLine(timedRuns[i].text, translated[i], opts.lyricsMode, "\n");
            }
          }
          changed = true;
        }
      }
    }

    return changed ? { changed: true, body: JSON.stringify(data) } : { changed: false, body: jsonText };
  }

  // --- Protobuf Lyrics & Browse Handlers ---

  function extractRunStrings(runListBytes) {
    const items = [];
    for (let i = 0; i < runListBytes.length; i++) {
      const rf = decodeFields(runListBytes[i]);
      const tf = rf.find((x) => x.no === 1 && x.wireType === 2);
      items.push({ fields: rf, text: tf ? utf8Decode(tf.data) : "" });
    }
    return items;
  }

  function rebuildRunBytes(item, newText) {
    let found = false;
    const out = item.fields.map((f) => {
      if (f.no === 1 && f.wireType === 2 && !found) {
        found = true;
        return bytesField(1, newText);
      }
      return f;
    });
    if (!found) out.unshift(bytesField(1, newText));
    return encodeFields(out);
  }

  async function patchTimedLyricsNode(rawBytes, opts, store, httpGet) {
    // TimedLyricsRender (465160965) -> field 4 (TimedLyricsContent) -> repeated field 1 (runs) -> field 1 (lineText)
    const fields = decodeFields(rawBytes);
    let changed = false;
    const out = [];
    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      if (f.no === 4 && f.wireType === 2) {
        const cFields = decodeFields(f.data);
        const runEntries = cFields.filter((x) => x.no === 1 && x.wireType === 2).map((x) => x.data);
        if (runEntries.length > 0) {
          const parsedRuns = extractRunStrings(runEntries);
          const lines = parsedRuns.map((r) => r.text);
          const translated = await translateWithCache(lines, store, httpGet);
          if (translated.some(Boolean)) {
            let runIdx = 0;
            const rebuiltContent = cFields.map((cf) => {
              if (cf.no === 1 && cf.wireType === 2) {
                const pr = parsedRuns[runIdx];
                const tr = translated[runIdx];
                runIdx++;
                if (pr.text.trim()) {
                  return bytesField(1, rebuildRunBytes(pr, formatLyricLine(pr.text, tr, opts.lyricsMode, "\n")));
                }
              }
              return cf;
            });
            changed = true;
            out.push(bytesField(4, encodeFields(rebuiltContent)));
            continue;
          }
        }
      }
      out.push(f);
    }
    return { changed, bytes: changed ? encodeFields(out) : rawBytes };
  }

  async function patchMusicDescLyricsNode(rawBytes, opts, store, httpGet) {
    // MusicDescriptionShelfRenderer (221496734) -> field 3 (description) -> repeated field 1 (runs) -> field 1 (text)
    const fields = decodeFields(rawBytes);
    let changed = false;
    const out = [];
    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      if (f.no === 3 && f.wireType === 2) {
        const dFields = decodeFields(f.data);
        const newDFields = [];
        let descChanged = false;
        for (let j = 0; j < dFields.length; j++) {
          const df = dFields[j];
          if (df.no === 1 && df.wireType === 2) {
            const rf = decodeFields(df.data);
            const tf = rf.find((x) => x.no === 1 && x.wireType === 2);
            if (tf) {
              const rawText = utf8Decode(tf.data);
              const lines = rawText.split("\n");
              const translated = await translateWithCache(lines, store, httpGet);
              if (translated.some(Boolean)) {
                const updated = lines
                  .map((line, idx) =>
                    line.trim() ? formatLyricLine(line, translated[idx], opts.lyricsMode, "\n  └ ") : line
                  )
                  .join("\n");
                descChanged = true;
                newDFields.push(bytesField(1, rebuildRunBytes({ fields: rf }, updated)));
                continue;
              }
            }
          }
          newDFields.push(df);
        }
        if (descChanged) {
          changed = true;
          out.push(bytesField(3, encodeFields(newDFields)));
          continue;
        }
      }
      out.push(f);
    }
    return { changed, bytes: changed ? encodeFields(out) : rawBytes };
  }

  const BROWSE_WALK_TAGS = new Set([
    1, 4, 5, 9, 10,
    49399797, 50195462, 58173949, 58174010,
    153515154, 172660663, 168777401,
  ]);

  async function walkBrowseProtoLyrics(rawBytes, opts, store, httpGet, depth) {
    if (depth > 14) return { changed: false, bytes: rawBytes };
    let fields;
    try {
      fields = decodeFields(rawBytes);
    } catch (_e) {
      return { changed: false, bytes: rawBytes };
    }
    let changed = false;
    const out = [];
    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      if (f.wireType === 2) {
        if (f.no === 465160965) {
          const res = await patchTimedLyricsNode(f.data, opts, store, httpGet);
          if (res.changed) {
            changed = true;
            out.push(bytesField(465160965, res.bytes));
            continue;
          }
        } else if (f.no === 221496734) {
          const res = await patchMusicDescLyricsNode(f.data, opts, store, httpGet);
          if (res.changed) {
            changed = true;
            out.push(bytesField(221496734, res.bytes));
            continue;
          }
        } else if (BROWSE_WALK_TAGS.has(f.no)) {
          const sub = await walkBrowseProtoLyrics(f.data, opts, store, httpGet, depth + 1);
          if (sub.changed) {
            changed = true;
            out.push(bytesField(f.no, sub.bytes));
            continue;
          }
        }
      }
      out.push(f);
    }
    return { changed, bytes: changed ? encodeFields(out) : rawBytes };
  }

  async function transformBrowseBytes(rawBytes, rawOpts, deps) {
    const opts = normalizeOpts(rawOpts);
    if (!rawBytes || rawBytes.length === 0) return { changed: false, body: rawBytes };
    if (rawBytes[0] === 0x7b || rawBytes[0] === 0x5b) {
      const res = await transformBrowseJson(utf8Decode(rawBytes), opts, deps);
      return { changed: res.changed, body: res.changed ? utf8Encode(res.body) : rawBytes };
    }
    if (opts.lyricsMode === "off") return { changed: false, body: rawBytes };

    const store = makeStore(deps && deps.store);
    const httpGet = (deps && deps.httpGet) || defaultHttpGet;
    const res = await walkBrowseProtoLyrics(rawBytes, opts, store, httpGet, 0);
    return { changed: res.changed, body: res.bytes };
  }

  function normalizeOpts(rawOpts) {
    let parsed = rawOpts;
    if (typeof parsed === "string") {
      try {
        parsed = JSON.parse(parsed);
      } catch (_e) {
        parsed = {};
      }
    }
    const obj = parsed && typeof parsed === "object" ? parsed : {};
    const validModes = new Set(["dual_orig_top", "dual_my_top", "my_only", "off"]);
    const rawMode = String(obj.lyricsMode || "dual_orig_top").trim();
    const toBool = (v, fb) =>
      typeof v === "boolean"
        ? v
        : typeof v === "string"
        ? v.trim().toLowerCase() === "true" || v.trim() === "1"
          ? true
          : v.trim().toLowerCase() === "false" || v.trim() === "0"
          ? false
          : fb
        : fb;
    return {
      lyricsMode: validModes.has(rawMode) ? rawMode : "dual_orig_top",
      enableAdBlock: toBool(obj.enableAdBlock, true),
      removeUpsells: toBool(obj.removeUpsells, true),
    };
  }

  async function runLoon() {
    if (typeof $request === "undefined" || typeof $response === "undefined" || typeof $done !== "function") {
      return;
    }
    try {
      const arg = typeof $argument !== "undefined" ? $argument : {};
      const rawBody = $response.bodyBytes || $response.body;
      if (!rawBody) {
        $done({});
        return;
      }
      if (typeof rawBody === "string") {
        const res = await transformBrowseJson(rawBody, arg);
        $done(res.changed ? { body: res.body } : {});
        return;
      }
      const bytes = rawBody instanceof Uint8Array ? rawBody : new Uint8Array(rawBody);
      const res = await transformBrowseBytes(bytes, arg);
      $done(res.changed ? { body: res.body } : {});
    } catch (err) {
      if (typeof console !== "undefined") console.log("[YTM-Myanmar] lyrics error: " + err);
      $done({});
    }
  }

  const exported = {
    CACHE_KEY,
    MAX_CACHE_SONGS,
    parseGoogleTranslateResponse,
    batchTranslateLines,
    formatLyricLine,
    transformBrowseJson,
    transformBrowseBytes,
    normalizeOpts,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = exported;
  }
  if (typeof $request !== "undefined" && typeof $response !== "undefined") {
    runLoon();
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
