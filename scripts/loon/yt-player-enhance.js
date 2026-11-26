/**
 * YouTube Player & Watch Enhancer for Loon 3.5.1+
 * - Strips player adPlacements / adSlots / pagead conversion tracking
 * - Unlocks Picture-in-Picture & Background Playback
 * - Unlocks Burmese (my) translation option and injects/activates Dual/Auto track
 * - Preserves unknown Protobuf wire fields losslessly for forward compatibility
 */

(function (root) {
  "use strict";

  const MY_CODE = "my";
  const MY_LANG_LABEL = "မြန်မာ (Burmese)";
  const MY_TRACK_LABEL = "မြန်မာ (Dual/Auto)";

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
      if ((b & 0x80) === 0) {
        return { val, start, end: pos, bytes: buf.subarray(start, pos) };
      }
      shift += 7n;
      if (shift > 70n) throw new Error("Varint overflow");
    }
    throw new Error("Truncated varint");
  }

  function readVarintVal(bytes) {
    let val = 0n;
    let shift = 0n;
    for (let i = 0; i < bytes.length; i++) {
      val |= BigInt(bytes[i] & 0x7f) << shift;
      shift += 7n;
    }
    return val;
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

  function varintField(no, value) {
    return { no, wireType: 0, data: writeVarint(value) };
  }

  function bytesField(no, payload) {
    const data = typeof payload === "string" ? utf8Encode(payload) : payload;
    return { no, wireType: 2, data };
  }

  function upsertField(fields, newField) {
    const out = [];
    let replaced = false;
    for (let i = 0; i < fields.length; i++) {
      if (fields[i].no === newField.no) {
        if (!replaced) {
          out.push(newField);
          replaced = true;
        }
      } else {
        out.push(fields[i]);
      }
    }
    if (!replaced) out.push(newField);
    return out;
  }

  function appendTlangMy(rawUrl) {
    if (!rawUrl || typeof rawUrl !== "string") return rawUrl;
    const stripped = rawUrl
      .replace(/([?&])tlang=[^&#]*/gi, "$1")
      .replace(/[?&]+$/, "")
      .replace(/\?&+/, "?")
      .replace(/&&+/g, "&");
    const sep = stripped.includes("?") ? "&" : "?";
    return stripped + sep + "tlang=" + MY_CODE;
  }

  function pickBaseTrackIndex(tracks) {
    let enFallback = -1;
    for (let i = 0; i < tracks.length; i++) {
      const code = String(tracks[i].languageCode || "").toLowerCase();
      if (code === "en") return i;
      if (enFallback === -1 && code.startsWith("en")) enFallback = i;
    }
    return enFallback !== -1 ? enFallback : 0;
  }

  function extractHostname(urlStr) {
    const m = /^https?:\/\/([^/:?#]+)/i.exec(String(urlStr || ""));
    return m ? m[1].toLowerCase() : "";
  }

  function buildJsonLabel(text, hostname) {
    const h = String(hostname || "").toLowerCase();
    if (h === "www.youtube.com" || h === "tv.youtube.com") {
      return { simpleText: text };
    }
    return { runs: [{ text }] };
  }

  function buildProtoLabel(text) {
    return encodeFields([bytesField(1, encodeFields([bytesField(1, text)]))]);
  }

  function buildProtoTranslationLang(code, text) {
    return encodeFields([bytesField(1, code), bytesField(2, buildProtoLabel(text))]);
  }

  // --- JSON Enhancement ---

  function patchCaptionsJson(renderer, opts) {
    if (!renderer || typeof renderer !== "object") return false;
    let changed = false;

    if (Array.isArray(renderer.captionTracks) && renderer.captionTracks.length > 0) {
      for (let i = 0; i < renderer.captionTracks.length; i++) {
        if (renderer.captionTracks[i].isTranslatable !== true) {
          renderer.captionTracks[i].isTranslatable = true;
          changed = true;
        }
      }

      if (opts.autoMyanmar) {
        let myIdx = renderer.captionTracks.findIndex(
          (t) => String(t.languageCode || "").toLowerCase() === MY_CODE
        );
        if (myIdx === -1) {
          const baseIdx = pickBaseTrackIndex(renderer.captionTracks);
          const base = renderer.captionTracks[baseIdx];
          if (base && base.baseUrl) {
            renderer.captionTracks.push({
              baseUrl: appendTlangMy(base.baseUrl),
              name: buildJsonLabel(MY_TRACK_LABEL, opts.hostname),
              vssId: "." + MY_CODE,
              languageCode: MY_CODE,
              isTranslatable: true,
            });
            myIdx = renderer.captionTracks.length - 1;
            changed = true;
          }
        }
        if (myIdx !== -1) {
          renderer.defaultCaptionTrackIndex = myIdx;
          if (Array.isArray(renderer.audioTracks)) {
            for (let i = 0; i < renderer.audioTracks.length; i++) {
              const audio = renderer.audioTracks[i];
              if (!Array.isArray(audio.captionTrackIndices)) audio.captionTrackIndices = [];
              if (!audio.captionTrackIndices.includes(myIdx)) audio.captionTrackIndices.push(myIdx);
              audio.defaultCaptionTrackIndex = myIdx;
              audio.visibility = 2;
              audio.hasDefaultTrack = true;
              audio.captionsInitialState = 3;
            }
          }
          changed = true;
        }
      }
    }

    if (Array.isArray(renderer.translationLanguages)) {
      const filtered = renderer.translationLanguages.filter(
        (item) => String(item && item.languageCode || "").toLowerCase() !== MY_CODE
      );
      filtered.unshift({
        languageCode: MY_CODE,
        languageName: buildJsonLabel(MY_LANG_LABEL, opts.hostname),
      });
      renderer.translationLanguages = filtered;
      changed = true;
    }

    return changed;
  }

  function transformPlayerJson(player, rawOpts) {
    if (!player || typeof player !== "object") return player;
    const opts = normalizeOpts(rawOpts);

    if (opts.enableAdBlock) {
      if (Array.isArray(player.adPlacements)) player.adPlacements = [];
      if (Array.isArray(player.adSlots)) player.adSlots = [];
      if (player.playbackTracking && typeof player.playbackTracking === "object") {
        delete player.playbackTracking.pageadViewthroughconversion;
      }
    }

    if (opts.enablePipBg) {
      if (!player.playabilityStatus || typeof player.playabilityStatus !== "object") {
        player.playabilityStatus = {};
      }
      player.playabilityStatus.pictureInPictureRender = {
        pictureInPictureAbility: { active: true, f4: 0, f6: 0, f8: 1 },
      };
      player.playabilityStatus.backgroundPlayerRender = {
        backgroundAbility: { active: true },
      };
    }

    const renderer = player.captions && player.captions.playerCaptionsTracklistRenderer;
    if (renderer) patchCaptionsJson(renderer, opts);
    return player;
  }

  function transformResponseJsonString(url, jsonText, rawOpts) {
    const opts = normalizeOpts(rawOpts, url);
    let data;
    try {
      data = JSON.parse(jsonText);
    } catch (_err) {
      return { changed: false, body: jsonText };
    }
    if (!data || typeof data !== "object") return { changed: false, body: jsonText };

    if (Array.isArray(data.contents)) {
      for (let i = 0; i < data.contents.length; i++) {
        const entry = data.contents[i];
        if (entry && entry.player) transformPlayerJson(entry.player, opts);
        if (entry && entry.playerResponse) transformPlayerJson(entry.playerResponse, opts);
      }
    } else {
      transformPlayerJson(data, opts);
    }

    return { changed: true, body: JSON.stringify(data) };
  }

  // --- Protobuf Enhancement ---

  function patchPlayabilityProto(rawBytes) {
    let fields = decodeFields(rawBytes);
    const pipAbility = encodeFields([varintField(1, 1), varintField(8, 1)]);
    const pipOuter = encodeFields([bytesField(151635310, pipAbility)]);
    const bgAbility = encodeFields([varintField(1, 1)]);
    const bgOuter = encodeFields([bytesField(64657230, bgAbility)]);
    fields = upsertField(fields, bytesField(21, pipOuter));
    fields = upsertField(fields, bytesField(11, bgOuter));
    return encodeFields(fields);
  }

  function patchPlaybackTrackingProto(rawBytes) {
    const fields = decodeFields(rawBytes).filter((f) => f.no !== 18);
    return encodeFields(fields);
  }

  function readCaptionTrackMeta(trackFields) {
    let baseUrl = "";
    let languageCode = "";
    for (let i = 0; i < trackFields.length; i++) {
      const f = trackFields[i];
      if (f.no === 1 && f.wireType === 2) baseUrl = utf8Decode(f.data);
      else if (f.no === 4 && f.wireType === 2) languageCode = utf8Decode(f.data);
    }
    return { baseUrl, languageCode };
  }

  function patchAudioTrackProto(rawBytes, targetIndex) {
    const fields = decodeFields(rawBytes);
    const indices = [];
    const out = [];
    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      if (f.no === 2) {
        if (f.wireType === 2) {
          let p = 0;
          while (p < f.data.length) {
            const v = readVarintSlice(f.data, p);
            indices.push(Number(v.val));
            p = v.end;
          }
        } else if (f.wireType === 0) {
          indices.push(Number(readVarintVal(f.data)));
        }
      } else {
        out.push(f);
      }
    }
    if (!indices.includes(targetIndex)) indices.push(targetIndex);
    for (let i = 0; i < indices.length; i++) {
      out.push(varintField(2, indices[i]));
    }
    let patched = upsertField(out, varintField(3, targetIndex));
    patched = upsertField(patched, varintField(5, 2));
    patched = upsertField(patched, varintField(6, 1));
    patched = upsertField(patched, varintField(11, 3));
    return encodeFields(patched);
  }

  function patchTracklistProto(rawBytes, opts) {
    let fields = decodeFields(rawBytes);
    const tracks = [];
    const nonTrackFields = [];
    const otherLangs = [];

    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      if (f.no === 1 && f.wireType === 2) {
        let tf = decodeFields(f.data);
        tf = upsertField(tf, varintField(7, 1)); // isTranslatable = true
        const meta = readCaptionTrackMeta(tf);
        tracks.push({ meta, data: encodeFields(tf) });
      } else if (f.no === 3 && f.wireType === 2) {
        const lf = decodeFields(f.data);
        const codeField = lf.find((x) => x.no === 1 && x.wireType === 2);
        const code = codeField ? utf8Decode(codeField.data).toLowerCase() : "";
        if (code !== MY_CODE) otherLangs.push(f);
      } else {
        nonTrackFields.push(f);
      }
    }

    let myIdx = -1;
    if (opts.autoMyanmar && tracks.length > 0) {
      myIdx = tracks.findIndex((t) => String(t.meta.languageCode || "").toLowerCase() === MY_CODE);
      if (myIdx === -1) {
        const baseIdx = pickBaseTrackIndex(tracks.map((t) => t.meta));
        const base = tracks[baseIdx];
        if (base && base.meta.baseUrl) {
          const synthetic = encodeFields([
            bytesField(1, appendTlangMy(base.meta.baseUrl)),
            bytesField(2, buildProtoLabel(MY_TRACK_LABEL)),
            bytesField(3, "." + MY_CODE),
            bytesField(4, MY_CODE),
            varintField(7, 1),
          ]);
          tracks.push({ meta: { baseUrl: "", languageCode: MY_CODE }, data: synthetic });
          myIdx = tracks.length - 1;
        }
      }
    }

    let rebuilt = [];
    for (let i = 0; i < tracks.length; i++) rebuilt.push(bytesField(1, tracks[i].data));

    for (let i = 0; i < nonTrackFields.length; i++) {
      const f = nonTrackFields[i];
      if (f.no === 2 && f.wireType === 2 && myIdx !== -1) {
        rebuilt.push(bytesField(2, patchAudioTrackProto(f.data, myIdx)));
      } else {
        rebuilt.push(f);
      }
    }

    rebuilt.push(bytesField(3, buildProtoTranslationLang(MY_CODE, MY_LANG_LABEL)));
    for (let i = 0; i < otherLangs.length; i++) rebuilt.push(otherLangs[i]);

    if (myIdx !== -1) {
      rebuilt = upsertField(rebuilt, varintField(6, myIdx));
    }

    return encodeFields(rebuilt);
  }

  function patchCaptionsProto(rawBytes, opts) {
    const fields = decodeFields(rawBytes);
    let changed = false;
    const out = fields.map((f) => {
      if (f.no === 51621377 && f.wireType === 2) {
        changed = true;
        return bytesField(51621377, patchTracklistProto(f.data, opts));
      }
      return f;
    });
    return changed ? encodeFields(out) : rawBytes;
  }

  function transformPlayerProto(rawBytes, rawOpts) {
    const opts = normalizeOpts(rawOpts);
    let fields = decodeFields(rawBytes);
    const out = [];
    let hasPlayability = false;

    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      if (opts.enableAdBlock && (f.no === 7 || f.no === 68)) continue;
      if (opts.enableAdBlock && f.no === 9 && f.wireType === 2) {
        out.push(bytesField(9, patchPlaybackTrackingProto(f.data)));
        continue;
      }
      if (opts.enablePipBg && f.no === 2 && f.wireType === 2) {
        hasPlayability = true;
        out.push(bytesField(2, patchPlayabilityProto(f.data)));
        continue;
      }
      if (f.no === 10 && f.wireType === 2) {
        out.push(bytesField(10, patchCaptionsProto(f.data, opts)));
        continue;
      }
      out.push(f);
    }

    if (opts.enablePipBg && !hasPlayability) {
      out.push(bytesField(2, patchPlayabilityProto(new Uint8Array(0))));
    }

    return encodeFields(out);
  }

  function patchWatchContentsProto(rawBytes, contentFieldNo, rawOpts) {
    const fields = decodeFields(rawBytes);
    let changed = false;
    const out = fields.map((f) => {
      if (f.no === contentFieldNo && f.wireType === 2) {
        const inner = decodeFields(f.data).map((cf) => {
          if (cf.no === 2 && cf.wireType === 2) {
            changed = true;
            return bytesField(2, transformPlayerProto(cf.data, rawOpts));
          }
          return cf;
        });
        return bytesField(contentFieldNo, encodeFields(inner));
      }
      return f;
    });
    return { changed, body: changed ? encodeFields(out) : rawBytes };
  }

  function transformResponseBytes(url, rawBytes, rawOpts) {
    const opts = normalizeOpts(rawOpts, url);
    if (!rawBytes || rawBytes.length === 0) return { changed: false, body: rawBytes };

    // Defensive UTF-8 JSON handling in case a Web JSON response arrives as bytes
    const firstByte = rawBytes[0];
    if (firstByte === 0x7b || firstByte === 0x5b) {
      const res = transformResponseJsonString(url, utf8Decode(rawBytes), opts);
      return { changed: res.changed, body: res.changed ? utf8Encode(res.body) : rawBytes };
    }

    const u = String(url || "");
    if (u.includes("/youtubei/v1/get_watch")) {
      return patchWatchContentsProto(rawBytes, 1, opts);
    }
    if (u.includes("/youtubei/v1/player")) {
      return { changed: true, body: transformPlayerProto(rawBytes, opts) };
    }
    return { changed: false, body: rawBytes };
  }

  function toBool(v, fallback) {
    if (typeof v === "boolean") return v;
    if (typeof v === "string") {
      const s = v.trim().toLowerCase();
      if (s === "true" || s === "1") return true;
      if (s === "false" || s === "0") return false;
    }
    return fallback;
  }

  function normalizeOpts(rawOpts, url) {
    let parsed = rawOpts;
    if (typeof parsed === "string") {
      try {
        parsed = JSON.parse(parsed);
      } catch (_err) {
        parsed = {};
      }
    }
    const obj = parsed && typeof parsed === "object" ? parsed : {};
    return {
      enableAdBlock: toBool(obj.enableAdBlock, true),
      enablePipBg: toBool(obj.enablePipBg, true),
      autoMyanmar: toBool(obj.autoMyanmar, true),
      hostname: obj.hostname || extractHostname(url),
    };
  }

  function runLoon() {
    if (typeof $request === "undefined" || typeof $response === "undefined" || typeof $done !== "function") {
      return;
    }
    try {
      const arg = typeof $argument !== "undefined" ? $argument : {};
      const opts = normalizeOpts(arg, $request.url);
      const rawBody = $response.bodyBytes || $response.body;
      if (!rawBody) {
        $done({});
        return;
      }
      if (typeof rawBody === "string") {
        const res = transformResponseJsonString($request.url, rawBody, opts);
        $done(res.changed ? { body: res.body } : {});
        return;
      }
      const bytes = rawBody instanceof Uint8Array ? rawBody : new Uint8Array(rawBody);
      const res = transformResponseBytes($request.url, bytes, opts);
      $done(res.changed ? { body: res.body } : {});
    } catch (err) {
      if (typeof console !== "undefined") console.log("[YT-Myanmar] player error: " + err);
      $done({});
    }
  }

  const exported = {
    decodeFields,
    encodeFields,
    readVarintVal,
    writeVarint,
    appendTlangMy,
    transformPlayerJson,
    transformResponseJsonString,
    transformPlayerProto,
    transformResponseBytes,
    normalizeOpts,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = exported;
  }
  if (typeof $request !== "undefined" && typeof $response !== "undefined") {
    runLoon();
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
