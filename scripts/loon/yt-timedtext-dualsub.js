/**
 * YouTube TimedText Dual Subtitle & Burmese Translator for Loon 3.5.1+
 * - Supports srv3/asr XML, json3, and WebVTT subtitles
 * - Combines Original + Myanmar (dual_orig_top / dual_my_top / my_only)
 * - Uses YouTube native tlang=my when available with batched Google Translate fallback
 * - Preserves signed timedtext query parameters verbatim and guards against recursion loops
 */

(function (root) {
  "use strict";

  const MY_CODE = "my";
  const CACHE_KEY = "@sithu015.loon_extra.yt_sub_cache";
  const MAX_CACHE_ENTRIES = 50;
  const MAX_BATCH_ENCODED_LEN = 1400;
  const ALIGN_TOLERANCE_MS = 350;
  const INTERNAL_HEADER = "X-YTMy-Raw";

  // --- Query String Helpers (Preserve Signed Tokens Verbatim) ---

  function getQueryParam(urlStr, key) {
    const qIdx = String(urlStr || "").indexOf("?");
    if (qIdx === -1) return null;
    const hashIdx = urlStr.indexOf("#", qIdx);
    const query = hashIdx === -1 ? urlStr.slice(qIdx + 1) : urlStr.slice(qIdx + 1, hashIdx);
    const pairs = query.split("&");
    for (let i = 0; i < pairs.length; i++) {
      const part = pairs[i];
      if (!part) continue;
      const eq = part.indexOf("=");
      const k = eq === -1 ? part : part.slice(0, eq);
      if (k === key) {
        const val = eq === -1 ? "" : part.slice(eq + 1);
        try {
          return decodeURIComponent(val.replace(/\+/g, " "));
        } catch (_e) {
          return val;
        }
      }
    }
    return null;
  }

  function removeQueryParam(urlStr, key) {
    const qIdx = String(urlStr || "").indexOf("?");
    if (qIdx === -1) return urlStr;
    const base = urlStr.slice(0, qIdx);
    const hashIdx = urlStr.indexOf("#", qIdx);
    const query = hashIdx === -1 ? urlStr.slice(qIdx + 1) : urlStr.slice(qIdx + 1, hashIdx);
    const hash = hashIdx === -1 ? "" : urlStr.slice(hashIdx);
    const kept = [];
    const pairs = query.split("&");
    for (let i = 0; i < pairs.length; i++) {
      const part = pairs[i];
      if (!part) continue;
      const eq = part.indexOf("=");
      const k = eq === -1 ? part : part.slice(0, eq);
      if (k !== key) kept.push(part);
    }
    return kept.length ? base + "?" + kept.join("&") + hash : base + hash;
  }

  function setQueryParam(urlStr, key, value) {
    const cleaned = removeQueryParam(urlStr, key);
    const hashIdx = cleaned.indexOf("#");
    const pre = hashIdx === -1 ? cleaned : cleaned.slice(0, hashIdx);
    const hash = hashIdx === -1 ? "" : cleaned.slice(hashIdx);
    const sep = pre.includes("?") ? "&" : "?";
    return pre + sep + encodeURIComponent(key) + "=" + encodeURIComponent(value) + hash;
  }

  function isBurmeseCode(code) {
    if (!code) return false;
    return String(code).trim().toLowerCase().split(/[-_]/)[0] === MY_CODE;
  }

  // --- Bounded Store Helpers ---

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

  function saveVideoMeta(store, videoId, patch) {
    if (!videoId) return;
    const cache = loadCache(store);
    const prev = cache[videoId] && typeof cache[videoId] === "object" ? cache[videoId] : {};
    delete cache[videoId];
    cache[videoId] = Object.assign({}, prev, patch, { ts: Date.now() });
    const keys = Object.keys(cache);
    if (keys.length > MAX_CACHE_ENTRIES) {
      for (let i = 0; i < keys.length - MAX_CACHE_ENTRIES; i++) {
        delete cache[keys[i]];
      }
    }
    try {
      store.write(JSON.stringify(cache), CACHE_KEY);
    } catch (_e) {
      // Ignore storage write quota errors cleanly
    }
  }

  function getVideoMeta(store, videoId) {
    if (!videoId) return null;
    const cache = loadCache(store);
    return cache[videoId] || null;
  }

  // --- XML / Entity Helpers ---

  function decodeXmlEntities(str) {
    if (!str) return "";
    return String(str)
      .replace(/&#x([0-9a-fA-F]+);/g, (_m, hex) => String.fromCodePoint(parseInt(hex, 16)))
      .replace(/&#(\d+);/g, (_m, dec) => String.fromCodePoint(parseInt(dec, 10)))
      .replace(/&apos;/g, "'")
      .replace(/&quot;/g, '"')
      .replace(/&gt;/g, ">")
      .replace(/&lt;/g, "<")
      .replace(/&amp;/g, "&");
  }

  function escapeXmlText(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function getAttr(attrStr, name) {
    const re = new RegExp("(?:^|\\s)" + name + "\\s*=\\s*([\"'])([\\s\\S]*?)\\1");
    const m = re.exec(attrStr || "");
    return m ? decodeXmlEntities(m[2]) : null;
  }

  function detectFormat(urlStr, headers, body) {
    const fmt = (getQueryParam(urlStr, "fmt") || "").toLowerCase();
    if (fmt === "json3" || fmt === "srv3" || fmt === "vtt" || fmt === "srv1") return fmt;

    const ct = getHeaderCI(headers, "content-type") || "";
    const lowerCt = ct.toLowerCase();
    if (lowerCt.includes("json")) return "json3";
    if (lowerCt.includes("vtt")) return "vtt";
    if (lowerCt.includes("xml")) {
      return String(body || "").includes("<transcript") ? "srv1" : "srv3";
    }

    const trimmed = String(body || "").trimStart();
    if (trimmed.startsWith("{")) return "json3";
    if (trimmed.startsWith("WEBVTT")) return "vtt";
    if (trimmed.includes("<transcript")) return "srv1";
    if (trimmed.startsWith("<")) return "srv3";
    return "unknown";
  }

  function getHeaderCI(headers, name) {
    if (!headers || typeof headers !== "object") return undefined;
    const target = name.toLowerCase();
    for (const k of Object.keys(headers)) {
      if (k.toLowerCase() === target) return headers[k];
    }
    return undefined;
  }

  function stripHeaderCI(headers, name) {
    const out = {};
    if (!headers || typeof headers !== "object") return out;
    const target = name.toLowerCase();
    for (const k of Object.keys(headers)) {
      if (k.toLowerCase() !== target) out[k] = headers[k];
    }
    return out;
  }

  // --- Format Parsers & Serializers ---

  function normalizeInlineText(text) {
    return String(text || "")
      .replace(/<[^>]+>/g, "")
      .replace(/\u200b/g, "")
      .trim();
  }

  function parseSrv3Xml(xmlStr) {
    const headMatch = /<head\b[^>]*>([\s\S]*?)<\/head>/i.exec(xmlStr);
    let head = headMatch ? headMatch[0] : "";
    if (head) {
      // Prevent 2-row rolling window overlap with tall Myanmar stacked diacritics
      head = head.replace(/(<wp\b[^>]*\brc=)(["'])[^"']*\2/gi, '$1"1"');
    }

    const cues = [];
    const pRe = /<p\b([^>]*?)(?:\/>|>([\s\S]*?)<\/p>)/gi;
    let m;
    while ((m = pRe.exec(xmlStr)) !== null) {
      const attrs = m[1] || "";
      const inner = m[2] || "";
      if (getAttr(attrs, "a") === "1") continue; // drop empty rolling scroll spacer

      const tStr = getAttr(attrs, "t");
      const dStr = getAttr(attrs, "d");
      const startMs = tStr !== null ? parseInt(tStr, 10) : 0;
      const durMs = dStr !== null ? parseInt(dStr, 10) : 0;

      let text = "";
      const segs = [];
      const sRe = /<s\b[^>]*>([\s\S]*?)<\/s>/gi;
      let sm;
      while ((sm = sRe.exec(inner)) !== null) {
        segs.push(decodeXmlEntities(sm[1]));
      }
      if (segs.length > 0) {
        text = segs.join("");
      } else {
        text = decodeXmlEntities(inner.replace(/<br\s*\/?>/gi, "\n").replace(/<[^>]+>/g, ""));
      }
      text = text.replace(/\r\n/g, "\n").trim();
      if (!text) continue;

      cues.push({
        startMs: Number.isFinite(startMs) ? startMs : 0,
        endMs: (Number.isFinite(startMs) ? startMs : 0) + (Number.isFinite(durMs) ? durMs : 0),
        durMs: Number.isFinite(durMs) ? durMs : 0,
        w: getAttr(attrs, "w"),
        text,
      });
    }

    return { format: "srv3", head, cues };
  }

  function serializeSrv3Xml(parsed, cues) {
    const lines = ['<?xml version="1.0" encoding="utf-8" ?>', '<timedtext format="3">'];
    if (parsed.head) lines.push("  " + parsed.head.trim());
    lines.push("  <body>");
    for (let i = 0; i < cues.length; i++) {
      const c = cues[i];
      let attrStr = `t="${c.startMs}" d="${Math.max(0, c.durMs)}"`;
      if (c.w !== null && c.w !== undefined && c.w !== "") attrStr += ` w="${escapeXmlText(c.w)}"`;
      lines.push(`    <p ${attrStr}>${escapeXmlText(c.text)}</p>`);
    }
    lines.push("  </body>");
    lines.push("</timedtext>");
    return lines.join("\n");
  }

  function parseSrv1Xml(xmlStr) {
    const cues = [];
    const tRe = /<text\b([^>]*)>([\s\S]*?)<\/text>/gi;
    let m;
    while ((m = tRe.exec(xmlStr)) !== null) {
      const attrs = m[1] || "";
      const startSec = parseFloat(getAttr(attrs, "start") || "0");
      const durSec = parseFloat(getAttr(attrs, "dur") || "0");
      const text = decodeXmlEntities(m[2] || "").replace(/\r\n/g, "\n").trim();
      if (!text) continue;
      const startMs = Math.round((Number.isFinite(startSec) ? startSec : 0) * 1000);
      const durMs = Math.round((Number.isFinite(durSec) ? durSec : 0) * 1000);
      cues.push({ startMs, durMs, endMs: startMs + durMs, text });
    }
    return { format: "srv1", cues };
  }

  function serializeSrv1Xml(cues) {
    const lines = ['<?xml version="1.0" encoding="utf-8" ?>', "<transcript>"];
    for (let i = 0; i < cues.length; i++) {
      const c = cues[i];
      const start = (c.startMs / 1000).toFixed(3).replace(/\.?0+$/, "");
      const dur = (c.durMs / 1000).toFixed(3).replace(/\.?0+$/, "");
      lines.push(`  <text start="${start}" dur="${dur}">${escapeXmlText(c.text)}</text>`);
    }
    lines.push("</transcript>");
    return lines.join("\n");
  }

  function parseJson3(jsonStr) {
    const doc = JSON.parse(jsonStr);
    if (Array.isArray(doc.wpWinPositions)) {
      for (let i = 0; i < doc.wpWinPositions.length; i++) {
        const wp = doc.wpWinPositions[i];
        if (wp && typeof wp === "object" && wp.rc !== undefined) wp.rc = 1;
      }
    }
    const cues = [];
    const events = Array.isArray(doc.events) ? doc.events : [];
    for (let i = 0; i < events.length; i++) {
      const ev = events[i];
      if (!ev || ev.aAppend === 1 || !Array.isArray(ev.segs)) continue;
      const text = ev.segs.map((s) => (s && typeof s.utf8 === "string" ? s.utf8 : "")).join("").replace(/\r\n/g, "\n").trim();
      if (!text) continue;
      const startMs = Number(ev.tStartMs) || 0;
      const durMs = Number(ev.dDurationMs) || 0;
      const cleanedEvent = Object.assign({}, ev);
      delete cleanedEvent.wWinId;
      cleanedEvent.segs = [{ utf8: text }];
      cues.push({
        startMs,
        durMs,
        endMs: startMs + durMs,
        text,
        rawEvent: cleanedEvent,
      });
    }
    return { format: "json3", doc, cues };
  }

  function serializeJson3(parsed, cues) {
    const outDoc = Object.assign({}, parsed.doc);
    outDoc.events = cues.map((c) => {
      const ev = c.rawEvent ? Object.assign({}, c.rawEvent) : { tStartMs: c.startMs, dDurationMs: c.durMs };
      delete ev.wWinId;
      ev.segs = [{ utf8: c.text }];
      return ev;
    });
    return JSON.stringify(outDoc);
  }

  function parseVttTimeMs(ts) {
    const m = /^(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})$/.exec(String(ts || "").trim());
    if (!m) return 0;
    const h = parseInt(m[1] || "0", 10);
    const min = parseInt(m[2], 10);
    const sec = parseInt(m[3], 10);
    const ms = parseInt(m[4], 10);
    return ((h * 60 + min) * 60 + sec) * 1000 + ms;
  }

  function parseVtt(vttStr) {
    const blocks = String(vttStr || "").replace(/\r\n/g, "\n").split(/\n{2,}/);
    const header = blocks.length > 0 && blocks[0].startsWith("WEBVTT") ? blocks[0] : "WEBVTT";
    const cues = [];
    for (let i = 0; i < blocks.length; i++) {
      const block = blocks[i].trim();
      if (!block || block.startsWith("WEBVTT") || block.startsWith("NOTE") || block.startsWith("STYLE") || block.startsWith("REGION")) {
        continue;
      }
      const lines = block.split("\n");
      let timeIdx = -1;
      for (let k = 0; k < lines.length; k++) {
        if (lines[k].includes("-->")) {
          timeIdx = k;
          break;
        }
      }
      if (timeIdx === -1) continue;
      const cueId = timeIdx > 0 ? lines.slice(0, timeIdx).join("\n") : null;
      const timingLine = lines[timeIdx];
      const tm = /^(\S+)\s+-->\s+(\S+)(.*)$/.exec(timingLine);
      if (!tm) continue;
      const startMs = parseVttTimeMs(tm[1]);
      const endMs = parseVttTimeMs(tm[2]);
      const text = normalizeInlineText(lines.slice(timeIdx + 1).join("\n"));
      if (!text) continue;
      cues.push({
        startMs,
        endMs,
        durMs: Math.max(0, endMs - startMs),
        cueId,
        timingLine,
        text,
      });
    }
    return { format: "vtt", header, cues };
  }

  function serializeVtt(parsed, cues) {
    const out = [parsed.header];
    for (let i = 0; i < cues.length; i++) {
      const c = cues[i];
      const part = [];
      if (c.cueId) part.push(c.cueId);
      part.push(c.timingLine);
      part.push(c.text);
      out.push(part.join("\n"));
    }
    return out.join("\n\n") + "\n";
  }

  function parseSubtitle(format, body) {
    if (format === "json3") return parseJson3(body);
    if (format === "vtt") return parseVtt(body);
    if (format === "srv1") return parseSrv1Xml(body);
    if (format === "srv3") return parseSrv3Xml(body);
    return { format: "unknown", cues: [] };
  }

  function serializeSubtitle(parsed, cues) {
    if (parsed.format === "json3") return serializeJson3(parsed, cues);
    if (parsed.format === "vtt") return serializeVtt(parsed, cues);
    if (parsed.format === "srv1") return serializeSrv1Xml(cues);
    if (parsed.format === "srv3") return serializeSrv3Xml(parsed, cues);
    return null;
  }

  // --- Cue Alignment & Dual Combining ---

  function overlapDuration(a, b) {
    const start = Math.max(a.startMs, b.startMs);
    const end = Math.min(a.endMs || a.startMs, b.endMs || b.startMs);
    return Math.max(0, end - start);
  }

  function findMatchingCueIndex(targetCue, candidates, hintIdx, toleranceMs) {
    if (!candidates || candidates.length === 0) return -1;
    let bestIdx = -1;
    let bestScore = -1;
    let bestDiff = Infinity;

    const startSearch = Math.max(0, hintIdx - 1);
    const endSearch = Math.min(candidates.length - 1, hintIdx + 4);
    for (let j = startSearch; j <= endSearch; j++) {
      const cand = candidates[j];
      const diff = Math.abs(targetCue.startMs - cand.startMs);
      const ov = overlapDuration(targetCue, cand);
      if (diff <= toleranceMs || ov > 0) {
        const score = ov > 0 ? 100000 + ov - diff : 1000 - diff;
        if (score > bestScore || (score === bestScore && diff < bestDiff)) {
          bestScore = score;
          bestDiff = diff;
          bestIdx = j;
        }
      }
    }
    return bestIdx;
  }

  function formatDualText(origText, myText, subtitleMode) {
    const origNorm = String(origText || "").trim().normalize("NFC");
    const myNorm = String(myText || "").trim().normalize("NFC");
    if (!myNorm) return origNorm;
    if (!origNorm || subtitleMode === "my_only") return myNorm;
    if (origNorm === myNorm) return myNorm;
    if (subtitleMode === "dual_my_top") return myNorm + "\n" + origNorm;
    return origNorm + "\n" + myNorm;
  }

  function alignAndMergeCues(baseCues, secondaryCues, opts) {
    const mode = opts.subtitleMode || "dual_orig_top";
    const isSecondaryMyanmar = Boolean(opts.secondaryIsMyanmar);
    let hint = 0;

    return baseCues.map((baseCue, idx) => {
      const matchIdx = secondaryCues
        ? findMatchingCueIndex(baseCue, secondaryCues, hint, ALIGN_TOLERANCE_MS)
        : -1;
      if (matchIdx !== -1) hint = matchIdx;
      const otherText = matchIdx !== -1 ? secondaryCues[matchIdx].text : "";
      const origText = isSecondaryMyanmar ? baseCue.text : otherText;
      const myText = isSecondaryMyanmar ? (otherText || baseCue.text) : baseCue.text;
      return Object.assign({}, baseCue, {
        text: formatDualText(origText, myText, mode),
      });
    });
  }

  // --- Google Translate (Myanmar Unicode NFC) ---

  function parseGoogleTranslateResponse(bodyStr) {
    const data = JSON.parse(bodyStr);
    if (Array.isArray(data) && Array.isArray(data[0])) {
      return data[0].map((seg) => (Array.isArray(seg) && typeof seg[0] === "string" ? seg[0] : "")).join("");
    }
    if (data && Array.isArray(data.sentences)) {
      return data.sentences.map((s) => (s && typeof s.trans === "string" ? s.trans : "")).join("");
    }
    throw new Error("Unexpected Google Translate payload");
  }

  async function translateBatchExact(lines, sourceLang, httpGet) {
    if (lines.length === 0) return [];
    const sl = sourceLang && !isBurmeseCode(sourceLang) ? String(sourceLang).split(/[-_]/)[0] : "auto";
    const q = lines.join("\n");
    const reqUrl =
      "https://translate.googleapis.com/translate_a/single?client=gtx&dt=t&sl=" +
      encodeURIComponent(sl) +
      "&tl=" +
      MY_CODE +
      "&q=" +
      encodeURIComponent(q);

    const res = await httpGet({
      url: reqUrl,
      headers: {
        Accept: "*/*",
        Referer: "https://translate.google.com/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      },
    });
    if (!res || (res.status && res.status >= 400) || !res.body) {
      throw new Error("Translate HTTP error: " + (res ? res.status : "empty"));
    }

    const translated = parseGoogleTranslateResponse(res.body);
    if (lines.length === 1) {
      return [translated.replace(/[\r\n]+/g, " ").trim().normalize("NFC")];
    }

    const splitLines = translated.split(/\r?\n/);
    if (splitLines.length === lines.length) {
      return splitLines.map((s) => s.trim().normalize("NFC"));
    }

    // Binary split recovery ensures 1:1 cue mapping if Google collapsed/split a delimiter
    const mid = Math.ceil(lines.length / 2);
    const left = await translateBatchExact(lines.slice(0, mid), sourceLang, httpGet);
    const right = await translateBatchExact(lines.slice(mid), sourceLang, httpGet);
    return left.concat(right);
  }

  async function translateCueTextsToMyanmar(rawTexts, sourceLang, httpGet) {
    const uniqueMap = new Map();
    const uniqueOrder = [];
    for (let i = 0; i < rawTexts.length; i++) {
      const normalized = String(rawTexts[i] || "").replace(/[\r\n]+/g, " ").trim();
      if (!normalized) continue;
      if (!uniqueMap.has(normalized)) {
        uniqueMap.set(normalized, "");
        uniqueOrder.push(normalized);
      }
    }

    const batches = [];
    let current = [];
    let currentLen = 0;
    for (let i = 0; i < uniqueOrder.length; i++) {
      const item = uniqueOrder[i];
      const encLen = encodeURIComponent(item + "\n").length;
      if (current.length > 0 && (currentLen + encLen > MAX_BATCH_ENCODED_LEN || current.length >= 25)) {
        batches.push(current);
        current = [];
        currentLen = 0;
      }
      current.push(item);
      currentLen += encLen;
    }
    if (current.length > 0) batches.push(current);

    for (let b = 0; b < batches.length; b++) {
      const batch = batches[b];
      try {
        const out = await translateBatchExact(batch, sourceLang, httpGet);
        for (let k = 0; k < batch.length; k++) {
          uniqueMap.set(batch[k], out[k] || batch[k]);
        }
      } catch (_err) {
        // Leave source text unchanged for failed batch so captions remain usable
        for (let k = 0; k < batch.length; k++) {
          uniqueMap.set(batch[k], batch[k]);
        }
      }
    }

    return rawTexts.map((raw) => {
      const normalized = String(raw || "").replace(/[\r\n]+/g, " ").trim();
      if (!normalized) return "";
      return uniqueMap.get(normalized) || raw;
    });
  }

  // --- Request & Response Handlers ---

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
    const subMode = ["dual_orig_top", "dual_my_top", "my_only"].includes(obj.subtitleMode)
      ? obj.subtitleMode
      : "dual_orig_top";
    const transMode = ["hybrid", "google_only", "youtube_only"].includes(obj.translationMode)
      ? obj.translationMode
      : "hybrid";
    const autoMyanmar =
      typeof obj.autoMyanmar === "boolean"
        ? obj.autoMyanmar
        : String(obj.autoMyanmar || "true").toLowerCase() !== "false";
    return {
      subtitleMode: subMode,
      translationMode: transMode,
      autoMyanmar,
    };
  }

  function handleRequest(req, rawOpts, rawStore) {
    if (!req || !req.url) return {};
    const opts = normalizeOpts(rawOpts);
    const store = makeStore(rawStore);

    if (getHeaderCI(req.headers, INTERNAL_HEADER)) {
      return { headers: stripHeaderCI(req.headers, INTERNAL_HEADER) };
    }

    const videoId = getQueryParam(req.url, "v");
    const lang = getQueryParam(req.url, "lang");
    const tlang = getQueryParam(req.url, "tlang");

    if (videoId && lang) {
      saveVideoMeta(store, videoId, { lang });
    }

    if (isBurmeseCode(lang)) return {};

    if (opts.translationMode === "google_only") {
      if (tlang && isBurmeseCode(tlang)) {
        if (videoId) saveVideoMeta(store, videoId, { lang: lang || "", forceGoogle: true });
        return { url: removeQueryParam(req.url, "tlang") };
      }
      if (!tlang && opts.autoMyanmar && lang && videoId) {
        saveVideoMeta(store, videoId, { lang, forceGoogle: true });
      }
      return {};
    }

    if (!tlang && opts.autoMyanmar && lang) {
      return { url: setQueryParam(req.url, "tlang", MY_CODE) };
    }

    return {};
  }

  function defaultHttpGet(req) {
    return new Promise((resolve, reject) => {
      if (typeof $httpClient === "undefined") {
        reject(new Error("$httpClient unavailable"));
        return;
      }
      $httpClient.get(req, (err, resp, data) => {
        if (err) {
          reject(err);
          return;
        }
        resolve({
          status: resp ? resp.status ?? resp.statusCode ?? 200 : 200,
          headers: (resp && resp.headers) || {},
          body: data,
        });
      });
    });
  }

  async function fetchOriginalTimedText(reqUrl, reqHeaders, httpGet) {
    const origUrl = removeQueryParam(reqUrl, "tlang");
    const headers = Object.assign({}, stripHeaderCI(reqHeaders, "accept-encoding"), {
      [INTERNAL_HEADER]: "1",
    });
    const resp = await httpGet({ url: origUrl, headers });
    if (!resp || (resp.status && resp.status >= 400) || !resp.body) return null;
    return resp;
  }

  async function handleResponse(req, res, rawOpts, deps) {
    if (!req || !req.url || !res) return {};
    const opts = normalizeOpts(rawOpts);
    const store = makeStore(deps && deps.store);
    const httpGet = (deps && deps.httpGet) || defaultHttpGet;

    if (getHeaderCI(req.headers, INTERNAL_HEADER)) return {};

    const videoId = getQueryParam(req.url, "v");
    const lang = getQueryParam(req.url, "lang");
    const tlang = getQueryParam(req.url, "tlang");
    const cachedMeta = getVideoMeta(store, videoId);
    const sourceLang = lang || (cachedMeta && cachedMeta.lang) || "auto";

    // Native Burmese captions need only normalization (scroll window/entity hygiene)
    if (isBurmeseCode(lang) && !tlang) {
      const parsed = parseSubtitle(detectFormat(req.url, res.headers, res.body), res.body);
      if (parsed.cues.length === 0) return {};
      const out = serializeSubtitle(parsed, parsed.cues);
      return out ? { body: out } : {};
    }

    const requestedMyanmar = isBurmeseCode(tlang);
    const wantsGoogleForOrig =
      !tlang &&
      !isBurmeseCode(lang) &&
      ((opts.translationMode === "google_only" && (opts.autoMyanmar || (cachedMeta && cachedMeta.forceGoogle))) ||
        false);

    if (!requestedMyanmar && !wantsGoogleForOrig) {
      return {};
    }

    // Direct translation path when response is already the original track (google_only mode)
    if (!requestedMyanmar && wantsGoogleForOrig) {
      if ((res.status && res.status >= 400) || !res.body) return {};
      const parsedOrig = parseSubtitle(detectFormat(req.url, res.headers, res.body), res.body);
      if (parsedOrig.cues.length === 0) return {};
      const translated = await translateCueTextsToMyanmar(
        parsedOrig.cues.map((c) => c.text),
        sourceLang,
        httpGet
      );
      const merged = parsedOrig.cues.map((c, idx) =>
        Object.assign({}, c, {
          text: formatDualText(c.text, translated[idx], opts.subtitleMode),
        })
      );
      const serialized = serializeSubtitle(parsedOrig, merged);
      return serialized ? { body: serialized } : {};
    }

    // Requested tlang=my path
    let myParsed =
      (!res.status || res.status < 400) && res.body
        ? parseSubtitle(detectFormat(req.url, res.headers, res.body), res.body)
        : { format: "unknown", cues: [] };

    if (opts.translationMode !== "google_only" && myParsed.cues.length > 0) {
      if (opts.subtitleMode === "my_only") {
        const cleaned = myParsed.cues.map((c) =>
          Object.assign({}, c, { text: String(c.text || "").trim().normalize("NFC") })
        );
        const serialized = serializeSubtitle(myParsed, cleaned);
        return serialized ? { body: serialized } : {};
      }
      const origResp = await fetchOriginalTimedText(req.url, req.headers, httpGet);
      if (!origResp) {
        const serialized = serializeSubtitle(myParsed, myParsed.cues);
        return serialized ? { body: serialized } : {};
      }
      const origParsed = parseSubtitle(
        detectFormat(removeQueryParam(req.url, "tlang"), origResp.headers, origResp.body),
        origResp.body
      );
      if (origParsed.cues.length === 0) {
        const serialized = serializeSubtitle(myParsed, myParsed.cues);
        return serialized ? { body: serialized } : {};
      }
      const merged = alignAndMergeCues(origParsed.cues, myParsed.cues, {
        subtitleMode: opts.subtitleMode,
        secondaryIsMyanmar: true,
      });
      const serialized = serializeSubtitle(origParsed, merged);
      return serialized ? { body: serialized } : {};
    }

    // Fallback to Google Translate (when YouTube tlang=my fails/empty or google_only)
    if (opts.translationMode === "youtube_only") return {};

    const origResp = await fetchOriginalTimedText(req.url, req.headers, httpGet);
    if (!origResp) return {};
    const origParsed = parseSubtitle(
      detectFormat(removeQueryParam(req.url, "tlang"), origResp.headers, origResp.body),
      origResp.body
    );
    if (origParsed.cues.length === 0) return {};

    const translated = await translateCueTextsToMyanmar(
      origParsed.cues.map((c) => c.text),
      sourceLang,
      httpGet
    );
    const merged = origParsed.cues.map((c, idx) =>
      Object.assign({}, c, {
        text: formatDualText(c.text, translated[idx], opts.subtitleMode),
      })
    );
    const serialized = serializeSubtitle(origParsed, merged);
    return serialized ? { body: serialized } : {};
  }

  function runLoon() {
    if (typeof $request === "undefined" || typeof $done !== "function") return;
    const arg = typeof $argument !== "undefined" ? $argument : {};
    if (typeof $response === "undefined") {
      try {
        $done(handleRequest($request, arg));
      } catch (err) {
        if (typeof console !== "undefined") console.log("[YT-Myanmar] timedtext req error: " + err);
        $done({});
      }
      return;
    }

    handleResponse($request, $response, arg)
      .then((result) => $done(result || {}))
      .catch((err) => {
        if (typeof console !== "undefined") console.log("[YT-Myanmar] timedtext res error: " + err);
        $done({});
      });
  }

  const exported = {
    getQueryParam,
    removeQueryParam,
    setQueryParam,
    parseSubtitle,
    serializeSubtitle,
    alignAndMergeCues,
    translateCueTextsToMyanmar,
    handleRequest,
    handleResponse,
    normalizeOpts,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = exported;
  }
  if (typeof $request !== "undefined") {
    runLoon();
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
