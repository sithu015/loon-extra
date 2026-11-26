/**
 * YouTube Music Enhancer for Loon 3.5.1+
 * - Blocks audio/video adPlacements, adSlots, sponsored feed cards & Premium upsells
 * - Unlocks Background Audio Playback, Audio-Only mode & Picture-in-Picture (PiP)
 * - Removes the bottom "Upgrade" (SPunlimited) tab and enables background playback settings
 * - Self-contained lossless Wire-Type Protobuf + JSON processor (zero external workers)
 */

(function (root) {
  "use strict";

  const CACHE_KEY = "@sithu015.loon_extra.ytm_ad_cache";
  const MAX_CACHE_IDS = 80;
  const BLOCKED_GUIDE_IDS = new Set(["SPunlimited", "FEunlimited", "FEmusic_premium"]);
  const AD_MARKER_EACH = ["pagead", "inline_injection_entrypoint_layout.eml", "ad_slot"];

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

  function bytesContainAscii(haystack, needleStr) {
    if (!haystack || haystack.length < needleStr.length) return false;
    const len = needleStr.length;
    const n0 = needleStr.charCodeAt(0);
    outer: for (let i = 0; i <= haystack.length - len; i++) {
      if (haystack[i] !== n0) continue;
      for (let j = 1; j < len; j++) {
        if (haystack[i + j] !== needleStr.charCodeAt(j)) continue outer;
      }
      return true;
    }
    return false;
  }

  function isSponsoredProtoPayload(bytes) {
    if (!bytes || bytes.length < 32) return false;
    for (let i = 0; i < AD_MARKER_EACH.length; i++) {
      if (bytesContainAscii(bytes, AD_MARKER_EACH[i])) return true;
    }
    return false;
  }

  // --- JSON Transformations ---

  const PROMO_RENDERER_KEYS = new Set([
    "mealbarPromoRenderer",
    "musicMealbarPromoRenderer",
    "interstitialPromoRenderer",
    "statementBannerRenderer",
    "fullWidthPortraitCountdownRenderer",
  ]);
  const AD_RENDERER_KEYS = new Set([
    "adSlotRenderer",
    "compactPromotedItemRenderer",
    "brandVideoSingletonRenderer",
    "promotedSparklesWebRenderer",
  ]);

  function isUnwantedJsonItem(node, opts) {
    if (!node || typeof node !== "object") return false;
    if (opts.enableAdBlock) {
      for (const k of AD_RENDERER_KEYS) {
        if (Object.prototype.hasOwnProperty.call(node, k)) return true;
      }
      if (node.musicResponsiveListItemRenderer) {
        const badges = node.musicResponsiveListItemRenderer.badges;
        if (Array.isArray(badges) && badges.some((b) => b && b.musicInlineBadgeRenderer && b.musicInlineBadgeRenderer.icon && b.musicInlineBadgeRenderer.icon.iconType === "MONEY_FILL")) {
          return true;
        }
      }
    }
    if (opts.removeUpsells) {
      for (const k of PROMO_RENDERER_KEYS) {
        if (Object.prototype.hasOwnProperty.call(node, k)) return true;
      }
    }
    return false;
  }

  function scrubFeedJson(node, opts, depth) {
    if (!node || typeof node !== "object" || depth > 14) return false;
    let changed = false;

    if (Array.isArray(node)) {
      for (let i = node.length - 1; i >= 0; i--) {
        if (isUnwantedJsonItem(node[i], opts)) {
          node.splice(i, 1);
          changed = true;
        } else if (scrubFeedJson(node[i], opts, depth + 1)) {
          changed = true;
        }
      }
      return changed;
    }

    const keys = Object.keys(node);
    for (let i = 0; i < keys.length; i++) {
      const k = keys[i];
      if (opts.removeUpsells && PROMO_RENDERER_KEYS.has(k)) {
        delete node[k];
        changed = true;
        continue;
      }
      if (opts.enableAdBlock && AD_RENDERER_KEYS.has(k)) {
        delete node[k];
        changed = true;
        continue;
      }
      if (scrubFeedJson(node[k], opts, depth + 1)) changed = true;
    }
    return changed;
  }

  function transformPlayerJson(player, opts) {
    if (!player || typeof player !== "object") return false;
    let changed = false;

    if (opts.enableAdBlock) {
      if (Array.isArray(player.adPlacements) && player.adPlacements.length > 0) {
        player.adPlacements = [];
        changed = true;
      }
      if (Array.isArray(player.adSlots) && player.adSlots.length > 0) {
        player.adSlots = [];
        changed = true;
      }
      if (Array.isArray(player.playerAds) && player.playerAds.length > 0) {
        player.playerAds = [];
        changed = true;
      }
      if (player.playbackTracking && player.playbackTracking.pageadViewthroughconversion) {
        delete player.playbackTracking.pageadViewthroughconversion;
        changed = true;
      }
    }

    if (opts.enableBgPlay) {
      if (!player.playabilityStatus || typeof player.playabilityStatus !== "object") {
        player.playabilityStatus = {};
      }
      const ps = player.playabilityStatus;
      ps.pictureInPictureRender = {
        pictureInPictureAbility: { active: true, f4: 0, f6: 0, f8: 1 },
      };
      ps.backgroundPlayerRender = {
        backgroundAbility: { active: true },
        backgroundPlayerRenderer: { backgroundable: true },
      };
      if (ps.audioOnlyPlayability && ps.audioOnlyPlayability.audioOnlyPlayabilityRenderer) {
        ps.audioOnlyPlayability.audioOnlyPlayabilityRenderer.audioOnlyAvailability =
          "FEATURE_AVAILABILITY_ALLOWED";
      } else {
        ps.audioOnlyPlayability = {
          audioOnlyPlayabilityRenderer: {
            audioOnlyAvailability: "FEATURE_AVAILABILITY_ALLOWED",
          },
        };
      }
      changed = true;
    }
    return changed;
  }

  function transformGuideJson(data, opts) {
    if (!opts.removeUpsells || !data || typeof data !== "object") return false;
    let changed = false;

    function walk(obj, depth) {
      if (!obj || typeof obj !== "object" || depth > 10) return;
      if (Array.isArray(obj)) {
        for (let i = obj.length - 1; i >= 0; i--) {
          const item = obj[i];
          const bid =
            item &&
            item.pivotBarItemRenderer &&
            item.pivotBarItemRenderer.navigationEndpoint &&
            item.pivotBarItemRenderer.navigationEndpoint.browseEndpoint &&
            item.pivotBarItemRenderer.navigationEndpoint.browseEndpoint.browseId;
          if (bid && BLOCKED_GUIDE_IDS.has(bid)) {
            obj.splice(i, 1);
            changed = true;
          } else {
            walk(item, depth + 1);
          }
        }
        return;
      }
      for (const k of Object.keys(obj)) walk(obj[k], depth + 1);
    }

    walk(data, 0);
    return changed;
  }

  function transformSettingJson(data, opts) {
    if (!opts.enableBgPlay || !data || typeof data !== "object") return false;
    let changed = false;

    function walk(obj, depth) {
      if (!obj || typeof obj !== "object" || depth > 10) return;
      if (obj.backgroundPlayBackSettingRenderer) {
        const r = obj.backgroundPlayBackSettingRenderer;
        r.backgroundPlayback = true;
        r.download = true;
        r.downloadQualitySelection = true;
        r.smartDownload = true;
        changed = true;
      }
      for (const k of Object.keys(obj)) walk(obj[k], depth + 1);
    }

    walk(data, 0);
    return changed;
  }

  function transformJsonResponse(url, jsonText, rawOpts) {
    const opts = normalizeOpts(rawOpts);
    let data;
    try {
      data = JSON.parse(jsonText);
    } catch (_e) {
      return { changed: false, body: jsonText };
    }
    if (!data || typeof data !== "object") return { changed: false, body: jsonText };

    const u = String(url || "");
    let changed = false;

    if (u.includes("/youtubei/v1/player") || u.includes("/youtubei/v1/get_watch")) {
      if (Array.isArray(data.contents)) {
        for (let i = 0; i < data.contents.length; i++) {
          const entry = data.contents[i];
          if (entry && entry.player && transformPlayerJson(entry.player, opts)) changed = true;
          if (entry && entry.playerResponse && transformPlayerJson(entry.playerResponse, opts)) changed = true;
          if (entry && entry.next && scrubFeedJson(entry.next, opts, 0)) changed = true;
        }
      } else {
        if (transformPlayerJson(data, opts)) changed = true;
      }
    } else if (u.includes("/youtubei/v1/guide")) {
      changed = transformGuideJson(data, opts);
    } else if (u.includes("/youtubei/v1/account/get_setting")) {
      changed = transformSettingJson(data, opts);
    } else if (
      u.includes("/youtubei/v1/browse") ||
      u.includes("/youtubei/v1/next") ||
      u.includes("/youtubei/v1/search")
    ) {
      changed = scrubFeedJson(data, opts, 0);
    }

    return changed ? { changed: true, body: JSON.stringify(data) } : { changed: false, body: jsonText };
  }

  // --- Protobuf Transformations ---

  function patchPlayabilityProto(rawBytes) {
    let fields = decodeFields(rawBytes);
    const pipOuter = encodeFields([bytesField(151635310, encodeFields([varintField(1, 1), varintField(8, 1)]))]);
    const bgOuter = encodeFields([bytesField(64657230, encodeFields([varintField(1, 1)]))]);
    fields = upsertField(fields, bytesField(11, bgOuter));
    fields = upsertField(fields, bytesField(21, pipOuter));
    return encodeFields(fields);
  }

  function transformPlayerProto(rawBytes, opts) {
    const fields = decodeFields(rawBytes);
    const out = [];
    let hasPlayability = false;
    let changed = false;

    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      if (opts.enableAdBlock && (f.no === 7 || f.no === 68)) {
        changed = true;
        continue;
      }
      if (opts.enableAdBlock && f.no === 9 && f.wireType === 2) {
        const inner = decodeFields(f.data);
        const filtered = inner.filter((x) => x.no !== 18);
        if (filtered.length !== inner.length) changed = true;
        out.push(bytesField(9, encodeFields(filtered)));
        continue;
      }
      if (opts.enableBgPlay && f.no === 2 && f.wireType === 2) {
        hasPlayability = true;
        out.push(bytesField(2, patchPlayabilityProto(f.data)));
        changed = true;
        continue;
      }
      out.push(f);
    }

    if (opts.enableBgPlay && !hasPlayability) {
      out.push(bytesField(2, patchPlayabilityProto(new Uint8Array(0))));
      changed = true;
    }

    return { changed, bytes: changed ? encodeFields(out) : rawBytes };
  }

  function scrubItemSectionProto(rawBytes, adCache) {
    const fields = decodeFields(rawBytes);
    let changed = false;
    const out = [];
    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      if (f.no === 1 && f.wireType === 2 && isSponsoredProtoPayload(f.data)) {
        changed = true;
        continue;
      }
      out.push(f);
    }
    return { changed, bytes: changed ? encodeFields(out) : rawBytes };
  }

  function walkAndScrubProto(rawBytes, opts, depth) {
    if (!opts.enableAdBlock || depth > 12) return { changed: false, bytes: rawBytes };
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
        if (f.no === 50195462) {
          const res = scrubItemSectionProto(f.data);
          if (res.changed) {
            changed = true;
            out.push(bytesField(50195462, res.bytes));
            continue;
          }
        } else if (
          f.no === 1 ||
          f.no === 4 ||
          f.no === 7 ||
          f.no === 8 ||
          f.no === 9 ||
          f.no === 10 ||
          f.no === 49399797 ||
          f.no === 58173949 ||
          f.no === 58174010 ||
          f.no === 51779735
        ) {
          const sub = walkAndScrubProto(f.data, opts, depth + 1);
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

  function extractBrowseIdFromRenderer(rawBytes) {
    try {
      const fields = decodeFields(rawBytes);
      for (let i = 0; i < fields.length; i++) {
        if (fields[i].no === 1 && fields[i].wireType === 2) {
          return utf8Decode(fields[i].data);
        }
      }
    } catch (_e) {
      return "";
    }
    return "";
  }

  function transformGuideSectionProto(rawBytes) {
    const fields = decodeFields(rawBytes);
    let changed = false;
    const out = [];
    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      if (f.no === 1 && f.wireType === 2) {
        const inner = decodeFields(f.data);
        let remove = false;
        for (let j = 0; j < inner.length; j++) {
          const rf = inner[j];
          if ((rf.no === 318370163 || rf.no === 117501096) && rf.wireType === 2) {
            const bid = extractBrowseIdFromRenderer(rf.data);
            if (BLOCKED_GUIDE_IDS.has(bid)) {
              remove = true;
              break;
            }
          }
        }
        if (remove) {
          changed = true;
          continue;
        }
      }
      out.push(f);
    }
    return { changed, bytes: changed ? encodeFields(out) : rawBytes };
  }

  function transformGuideProto(rawBytes, opts) {
    if (!opts.removeUpsells) return { changed: false, bytes: rawBytes };
    const fields = decodeFields(rawBytes);
    let changed = false;
    const out = [];
    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      if ((f.no === 4 || f.no === 6) && f.wireType === 2) {
        const itemFields = decodeFields(f.data);
        let itemChanged = false;
        const itemOut = itemFields.map((it) => {
          if (it.no === 117866661 && it.wireType === 2) {
            const sec = transformGuideSectionProto(it.data);
            if (sec.changed) {
              itemChanged = true;
              return bytesField(117866661, sec.bytes);
            }
          }
          return it;
        });
        if (itemChanged) {
          changed = true;
          out.push(bytesField(f.no, encodeFields(itemOut)));
          continue;
        }
      }
      out.push(f);
    }
    return { changed, bytes: changed ? encodeFields(out) : rawBytes };
  }

  function buildBgPlaybackSettingItemProto() {
    const renderer = encodeFields([
      varintField(2, 1), // backgroundPlayback = true
      varintField(3, 1), // download = true
      varintField(9, 1), // downloadQualitySelection = true
      varintField(10, 1), // smartDownload = true
      bytesField(14, encodeFields([varintField(1, 1093)])), // iconType = 1093
    ]);
    return encodeFields([bytesField(88478200, renderer)]);
  }

  function buildClientSettingSubProto(itemEnum) {
    const makeEp = (boolVal) =>
      encodeFields([
        bytesField(
          81212182,
          encodeFields([
            bytesField(
              1,
              encodeFields([bytesField(1, encodeFields([varintField(1, itemEnum)])), varintField(3, boolVal ? 1 : 0)])
            ),
          ])
        ),
      ]);
    const boolRenderer = encodeFields([makeEp(true), makeEp(false)].reduce((acc, ep, idx) => {
      acc.push(bytesField(idx === 0 ? 5 : 6, ep));
      return acc;
    }, [varintField(15, 0)]));
    return encodeFields([bytesField(61331416, boolRenderer)]);
  }

  function transformSettingProto(rawBytes, opts) {
    if (!opts.enableBgPlay) return { changed: false, bytes: rawBytes };
    const fields = decodeFields(rawBytes);
    let hasBgItem = false;
    let changed = false;
    const out = [];

    for (let i = 0; i < fields.length; i++) {
      const f = fields[i];
      if (f.no === 6 && f.wireType === 2) {
        const sFields = decodeFields(f.data);
        let sChanged = false;
        const sOut = sFields.map((sf) => {
          if (sf.no === 88478200 && sf.wireType === 2) {
            hasBgItem = true;
            let bgf = decodeFields(sf.data);
            bgf = upsertField(bgf, varintField(2, 1));
            bgf = upsertField(bgf, varintField(3, 1));
            bgf = upsertField(bgf, varintField(9, 1));
            bgf = upsertField(bgf, varintField(10, 1));
            sChanged = true;
            return bytesField(88478200, encodeFields(bgf));
          }
          if (sf.no === 66930374 && sf.wireType === 2) {
            const cf = decodeFields(sf.data);
            const cat = cf.find((x) => x.no === 4 && x.wireType === 0);
            if (cat && Number(readVarintVal(cat.data)) === 10135 && !bytesContainAscii(sf.data, "\x08\x97\x01")) {
              cf.push(bytesField(3, buildClientSettingSubProto(151)));
              sChanged = true;
              return bytesField(66930374, encodeFields(cf));
            }
          }
          return sf;
        });
        if (sChanged) {
          changed = true;
          out.push(bytesField(6, encodeFields(sOut)));
          continue;
        }
      }
      out.push(f);
    }

    if (!hasBgItem) {
      out.push(bytesField(6, buildBgPlaybackSettingItemProto()));
      changed = true;
    }
    return { changed, bytes: changed ? encodeFields(out) : rawBytes };
  }

  function patchWatchProto(rawBytes, opts) {
    const fields = decodeFields(rawBytes);
    let changed = false;
    const out = fields.map((f) => {
      if (f.no === 1 && f.wireType === 2) {
        const inner = decodeFields(f.data).map((cf) => {
          if (cf.no === 2 && cf.wireType === 2) {
            const pr = transformPlayerProto(cf.data, opts);
            if (pr.changed) {
              changed = true;
              return bytesField(2, pr.bytes);
            }
          } else if (cf.no === 3 && cf.wireType === 2) {
            const nx = walkAndScrubProto(cf.data, opts, 0);
            if (nx.changed) {
              changed = true;
              return bytesField(3, nx.bytes);
            }
          }
          return cf;
        });
        return bytesField(1, encodeFields(inner));
      }
      return f;
    });
    return { changed, bytes: changed ? encodeFields(out) : rawBytes };
  }

  function transformBytesResponse(url, rawBytes, rawOpts) {
    const opts = normalizeOpts(rawOpts);
    if (!rawBytes || rawBytes.length === 0) return { changed: false, body: rawBytes };

    if (rawBytes[0] === 0x7b || rawBytes[0] === 0x5b) {
      const res = transformJsonResponse(url, utf8Decode(rawBytes), opts);
      return { changed: res.changed, body: res.changed ? utf8Encode(res.body) : rawBytes };
    }

    const u = String(url || "");
    if (u.includes("/youtubei/v1/get_watch")) {
      const res = patchWatchProto(rawBytes, opts);
      return { changed: res.changed, body: res.bytes };
    }
    if (u.includes("/youtubei/v1/player")) {
      const res = transformPlayerProto(rawBytes, opts);
      return { changed: res.changed, body: res.bytes };
    }
    if (u.includes("/youtubei/v1/guide")) {
      const res = transformGuideProto(rawBytes, opts);
      return { changed: res.changed, body: res.bytes };
    }
    if (u.includes("/youtubei/v1/account/get_setting")) {
      const res = transformSettingProto(rawBytes, opts);
      return { changed: res.changed, body: res.bytes };
    }
    if (
      u.includes("/youtubei/v1/browse") ||
      u.includes("/youtubei/v1/next") ||
      u.includes("/youtubei/v1/search")
    ) {
      const res = walkAndScrubProto(rawBytes, opts, 0);
      return { changed: res.changed, body: res.bytes };
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
    return {
      enableAdBlock: toBool(obj.enableAdBlock, true),
      enableBgPlay: toBool(obj.enableBgPlay, true),
      removeUpsells: toBool(obj.removeUpsells, true),
    };
  }

  function isMusicAppRequest(url, headers) {
    const u = String(url || "").toLowerCase();
    if (u.includes("//music.youtube.com/")) return true;
    const h = headers || {};
    const ua = String(h["user-agent"] || h["User-Agent"] || "").toLowerCase();
    if (!ua) return true;
    // Allow YouTube Music native clients and non-iOS browsers; skip main YouTube UI-only guide/next quirks if unwanted
    if (u.includes("/youtubei/v1/player") || u.includes("/youtubei/v1/get_watch")) {
      return ua.includes("music") || ua.includes("youtubemusic");
    }
    return true;
  }

  function runLoon() {
    if (typeof $request === "undefined" || typeof $response === "undefined" || typeof $done !== "function") {
      return;
    }
    try {
      const u = $request.url || "";
      if (!isMusicAppRequest(u, $request.headers)) {
        $done({});
        return;
      }
      const arg = typeof $argument !== "undefined" ? $argument : {};
      const rawBody = $response.bodyBytes || $response.body;
      if (!rawBody) {
        $done({});
        return;
      }
      if (typeof rawBody === "string") {
        const res = transformJsonResponse(u, rawBody, arg);
        $done(res.changed ? { body: res.body } : {});
        return;
      }
      const bytes = rawBody instanceof Uint8Array ? rawBody : new Uint8Array(rawBody);
      const res = transformBytesResponse(u, bytes, arg);
      $done(res.changed ? { body: res.body } : {});
    } catch (err) {
      if (typeof console !== "undefined") console.log("[YTM-Myanmar] enhance error: " + err);
      $done({});
    }
  }

  const exported = {
    CACHE_KEY,
    MAX_CACHE_IDS,
    decodeFields,
    encodeFields,
    transformJsonResponse,
    transformBytesResponse,
    normalizeOpts,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = exported;
  }
  if (typeof $request !== "undefined" && typeof $response !== "undefined") {
    runLoon();
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
