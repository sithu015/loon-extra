import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const playerEnhance = require("../../scripts/loon/yt-player-enhance.js");

function concatBytes(...arrays) {
  const total = arrays.reduce((sum, a) => sum + a.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const a of arrays) {
    out.set(a, offset);
    offset += a.length;
  }
  return out;
}

function varint(value) {
  let v = typeof value === "bigint" ? value : BigInt(value);
  if (v < 0n) v = BigInt.asUintN(64, v);
  const bytes = [];
  while (v >= 0x80n) {
    bytes.push(Number((v & 0x7fn) | 0x80n));
    v >>= 7n;
  }
  bytes.push(Number(v));
  return Uint8Array.from(bytes);
}

function fieldVarint(no, value) {
  return concatBytes(varint((BigInt(no) << 3n) | 0n), varint(value));
}

function fieldBytes(no, payload) {
  const bytes = typeof payload === "string" ? new TextEncoder().encode(payload) : payload;
  return concatBytes(varint((BigInt(no) << 3n) | 2n), varint(bytes.length), bytes);
}

function fieldFixed32(no, num) {
  const b = new Uint8Array(4);
  new DataView(b.buffer).setUint32(0, num, true);
  return concatBytes(varint((BigInt(no) << 3n) | 5n), b);
}

function fieldFixed64(no, bigNum) {
  const b = new Uint8Array(8);
  new DataView(b.buffer).setBigUint64(0, BigInt(bigNum), true);
  return concatBytes(varint((BigInt(no) << 3n) | 1n), b);
}

test("protobuf lossless roundtrip preserves large 64-bit varints, fixed32/64, and unknown nested tags", () => {
  const raw = concatBytes(
    fieldVarint(1, 0xffffffffffffffffn),
    fieldFixed64(42, 0x0102030405060708n),
    fieldFixed32(43, 0xdeadbeef),
    fieldBytes(99, fieldBytes(1, "preserve-me"))
  );
  const fields = playerEnhance.decodeFields(raw);
  const reencoded = playerEnhance.encodeFields(fields);
  assert.deepEqual(reencoded, raw);
});

test("JSON /player enhancement removes ads, unlocks PiP/BG, unlocks Burmese translationLanguages, and injects Dual/Auto track", () => {
  const input = {
    adPlacements: [{ adPlacementRenderer: { params: "ad1" } }],
    adSlots: [{ adSlotRenderer: {} }],
    playbackTracking: {
      videostatsPlaybackUrl: { baseUrl: "https://s.youtube.com/api/stats/playback" },
      pageadViewthroughconversion: { baseUrl: "https://www.googleadservices.com/pagead" }
    },
    playabilityStatus: { status: "OK" },
    videoDetails: { videoId: "vid123" },
    captions: {
      playerCaptionsTracklistRenderer: {
        captionTracks: [
          {
            baseUrl: "https://www.youtube.com/api/timedtext?v=vid123&lang=ja",
            name: { simpleText: "Japanese" },
            vssId: ".ja",
            languageCode: "ja",
            isTranslatable: false
          },
          {
            baseUrl: "https://www.youtube.com/api/timedtext?v=vid123&lang=en&tlang=zh-Hans",
            name: { simpleText: "English" },
            vssId: ".en",
            languageCode: "en",
            isTranslatable: false
          }
        ],
        audioTracks: [{ captionTrackIndices: [0, 1], defaultCaptionTrackIndex: 0 }],
        translationLanguages: [
          { languageCode: "ja", languageName: { simpleText: "Japanese" } },
          { languageCode: "en", languageName: { simpleText: "English" } }
        ]
      }
    }
  };

  const out = playerEnhance.transformPlayerJson(structuredClone(input), {
    enableAdBlock: true,
    enablePipBg: true,
    autoMyanmar: true,
    hostname: "www.youtube.com"
  });

  assert.equal(out.adPlacements.length, 0);
  assert.equal(out.adSlots.length, 0);
  assert.equal(out.playbackTracking.pageadViewthroughconversion, undefined);
  assert.ok(out.playbackTracking.videostatsPlaybackUrl);
  assert.equal(out.playabilityStatus.pictureInPictureRender.pictureInPictureAbility.active, true);
  assert.equal(out.playabilityStatus.backgroundPlayerRender.backgroundAbility.active, true);

  const renderer = out.captions.playerCaptionsTracklistRenderer;
  assert.equal(renderer.translationLanguages[0].languageCode, "my");
  assert.equal(renderer.translationLanguages[0].languageName.simpleText, "မြန်မာ (Burmese)");
  assert.equal(renderer.translationLanguages.length, 3);
  assert.ok(renderer.captionTracks.every((t) => t.isTranslatable === true));

  const myTrack = renderer.captionTracks.find((t) => t.languageCode === "my");
  assert.ok(myTrack);
  assert.equal(myTrack.baseUrl, "https://www.youtube.com/api/timedtext?v=vid123&lang=en&tlang=my");
  assert.equal(myTrack.name.simpleText, "မြန်မာ (Dual/Auto)");
  assert.equal(renderer.defaultCaptionTrackIndex, 2);
  assert.deepEqual(renderer.audioTracks[0].captionTrackIndices, [0, 1, 2]);
  assert.equal(renderer.audioTracks[0].defaultCaptionTrackIndex, 2);
  assert.equal(renderer.audioTracks[0].captionsInitialState, 3);
});

test("JSON /player avoids duplicating existing my track or translation language and skips empty captionTracks cleanly", () => {
  const existingMy = {
    playabilityStatus: { status: "OK" },
    captions: {
      playerCaptionsTracklistRenderer: {
        captionTracks: [
          {
            baseUrl: "https://www.youtube.com/api/timedtext?v=x&lang=my",
            name: { runs: [{ text: "Burmese" }] },
            vssId: ".my",
            languageCode: "my",
            isTranslatable: true
          }
        ],
        audioTracks: [{ captionTrackIndices: [0] }],
        translationLanguages: [
          { languageCode: "en", languageName: { runs: [{ text: "English" }] } },
          { languageCode: "my", languageName: { runs: [{ text: "Burmese" }] } }
        ]
      }
    }
  };

  const outExisting = playerEnhance.transformPlayerJson(existingMy, {
    enableAdBlock: false,
    enablePipBg: false,
    autoMyanmar: true,
    hostname: "m.youtube.com"
  });
  const r1 = outExisting.captions.playerCaptionsTracklistRenderer;
  assert.equal(r1.captionTracks.length, 1);
  assert.equal(r1.translationLanguages.filter((x) => x.languageCode === "my").length, 1);
  assert.equal(r1.translationLanguages[0].languageCode, "my");
  assert.equal(r1.defaultCaptionTrackIndex, 0);

  const emptyCaptions = {
    playabilityStatus: { status: "OK" },
    captions: { playerCaptionsTracklistRenderer: { captionTracks: [] } }
  };
  const outEmpty = playerEnhance.transformPlayerJson(emptyCaptions, { autoMyanmar: true });
  assert.equal(outEmpty.captions.playerCaptionsTracklistRenderer.captionTracks.length, 0);
});

test("Protobuf /player and /get_watch patch ads, PiP/BG, Burmese unlock & track injection losslessly", () => {
  const captionJa = concatBytes(
    fieldBytes(1, "https://www.youtube.com/api/timedtext?v=p1&lang=ja"),
    fieldBytes(2, fieldBytes(1, fieldBytes(1, "Japanese"))),
    fieldBytes(3, ".ja"),
    fieldBytes(4, "ja"),
    fieldVarint(7, 0)
  );
  const captionEn = concatBytes(
    fieldBytes(1, "https://www.youtube.com/api/timedtext?v=p1&lang=en"),
    fieldBytes(2, fieldBytes(1, fieldBytes(1, "English"))),
    fieldBytes(3, ".en"),
    fieldBytes(4, "en"),
    fieldVarint(7, 0)
  );
  const audioTrack = concatBytes(
    fieldBytes(2, concatBytes(varint(0), varint(1))), // packed captionTrackIndices
    fieldVarint(5, 1)
  );
  const langEn = concatBytes(
    fieldBytes(1, "en"),
    fieldBytes(2, fieldBytes(1, fieldBytes(1, "English")))
  );
  const tracklist = concatBytes(
    fieldBytes(1, captionJa),
    fieldBytes(1, captionEn),
    fieldBytes(2, audioTrack),
    fieldBytes(3, langEn)
  );
  const captions = fieldBytes(51621377, tracklist);
  const playbackTracking = concatBytes(
    fieldBytes(1, fieldBytes(1, "https://s.youtube.com/api/stats/playback")),
    fieldBytes(18, fieldBytes(1, "https://googleadservices.com/pagead"))
  );
  const playabilityStatus = fieldVarint(1, 0);
  const unknownPlayerField = fieldBytes(120, "untouched-player-blob");

  const rawPlayer = concatBytes(
    fieldBytes(7, "ad-placement-payload"),
    fieldBytes(68, "ad-slot-payload"),
    fieldBytes(2, playabilityStatus),
    fieldBytes(9, playbackTracking),
    fieldBytes(10, captions),
    unknownPlayerField
  );

  // Wrap inside GetWatchResponse (#1 contents -> #2 player)
  const rawGetWatch = fieldBytes(1, concatBytes(fieldBytes(2, rawPlayer), fieldBytes(3, "next-blob")));

  const patchedGetWatch = playerEnhance.transformResponseBytes(
    "https://youtubei.googleapis.com/youtubei/v1/get_watch?prettyPrint=false",
    rawGetWatch,
    { enableAdBlock: true, enablePipBg: true, autoMyanmar: true }
  );

  assert.ok(patchedGetWatch.changed);
  const watchFields = playerEnhance.decodeFields(patchedGetWatch.body);
  const contentFields = playerEnhance.decodeFields(watchFields.find((f) => f.no === 1).data);
  // Unknown field #3 next-blob kept intact
  assert.equal(new TextDecoder().decode(contentFields.find((f) => f.no === 3).data), "next-blob");

  const playerFields = playerEnhance.decodeFields(contentFields.find((f) => f.no === 2).data);
  assert.equal(playerFields.some((f) => f.no === 7), false);
  assert.equal(playerFields.some((f) => f.no === 68), false);
  assert.equal(new TextDecoder().decode(playerFields.find((f) => f.no === 120).data), "untouched-player-blob");

  // PlaybackTracking keeps #1 and removes #18
  const trackingFields = playerEnhance.decodeFields(playerFields.find((f) => f.no === 9).data);
  assert.equal(trackingFields.some((f) => f.no === 1), true);
  assert.equal(trackingFields.some((f) => f.no === 18), false);

  // PlayabilityStatus enables #21 PiP and #11 Background
  const playabilityFields = playerEnhance.decodeFields(playerFields.find((f) => f.no === 2).data);
  assert.equal(Number(playerEnhance.readVarintVal(playabilityFields.find((f) => f.no === 1).data)), 0);
  const pipOuter = playerEnhance.decodeFields(playabilityFields.find((f) => f.no === 21).data);
  const pipAbility = playerEnhance.decodeFields(pipOuter.find((f) => f.no === 151635310).data);
  assert.equal(Number(playerEnhance.readVarintVal(pipAbility.find((f) => f.no === 1).data)), 1);
  const bgOuter = playerEnhance.decodeFields(playabilityFields.find((f) => f.no === 11).data);
  const bgAbility = playerEnhance.decodeFields(bgOuter.find((f) => f.no === 64657230).data);
  assert.equal(Number(playerEnhance.readVarintVal(bgAbility.find((f) => f.no === 1).data)), 1);

  // Captions tracklist has my promoted to #3 index 0, all tracks translatable, and injected &tlang=my track
  const capFields = playerEnhance.decodeFields(playerFields.find((f) => f.no === 10).data);
  const tlFields = playerEnhance.decodeFields(capFields.find((f) => f.no === 51621377).data);
  const tracks = tlFields.filter((f) => f.no === 1).map((f) => playerEnhance.decodeFields(f.data));
  assert.equal(tracks.length, 3);
  for (const tr of tracks) {
    assert.equal(Number(playerEnhance.readVarintVal(tr.find((x) => x.no === 7).data)), 1);
  }
  const myProtoTrack = tracks[2];
  assert.equal(
    new TextDecoder().decode(myProtoTrack.find((x) => x.no === 1).data),
    "https://www.youtube.com/api/timedtext?v=p1&lang=en&tlang=my"
  );
  assert.equal(new TextDecoder().decode(myProtoTrack.find((x) => x.no === 4).data), "my");

  const langs = tlFields.filter((f) => f.no === 3).map((f) => playerEnhance.decodeFields(f.data));
  assert.equal(new TextDecoder().decode(langs[0].find((x) => x.no === 1).data), "my");
  assert.equal(langs.length, 2);
});

const timedtextDual = require("../../scripts/loon/yt-timedtext-dualsub.js");

function makeMemoryStore() {
  const map = new Map();
  return {
    read: (k) => map.get(k) ?? null,
    write: (v, k) => {
      map.set(k, v);
      return true;
    },
  };
}

test("srv3 XML and asr karaoke captions flatten <s> segments, drop a=1 spacers, set rc=1, and align Dual/Burmese", async () => {
  const origXml = `<?xml version="1.0" encoding="utf-8" ?>
<timedtext format="3">
  <head>
    <ws id="0"/>
    <wp id="1" ap="6" ah="20" av="100" rc="2" cc="40"/>
  </head>
  <body>
    <p t="1000" d="2000" w="1"><s>Hello</s><s> world &amp; friends</s></p>
    <p t="3100" d="500" w="1" a="1"> </p>
    <p t="4000" d="2500" w="1">How&#39;s it going?</p>
  </body>
</timedtext>`;

  const myXml = `<?xml version="1.0" encoding="utf-8" ?>
<timedtext format="3">
  <head>
    <wp id="1" ap="6" ah="20" av="100" rc="2" cc="40"/>
  </head>
  <body>
    <p t="1120" d="2000" w="1">မင်္ဂလာပါ သူငယ်ချင်းများ</p>
    <p t="4050" d="2500" w="1">အဆင်ပြေရဲ့လား။</p>
  </body>
</timedtext>`;

  let fetchedUrl = "";
  let fetchedHeaders = null;
  const out = await timedtextDual.handleResponse(
    {
      url: "https://www.youtube.com/api/timedtext?v=abc&lang=en&tlang=my&fmt=srv3",
      headers: { "User-Agent": "YouTube" },
    },
    { status: 200, headers: { "Content-Type": "text/xml; charset=UTF-8" }, body: myXml },
    { subtitleMode: "dual_orig_top", translationMode: "hybrid", autoMyanmar: true },
    {
      store: makeMemoryStore(),
      httpGet: async (req) => {
        fetchedUrl = req.url;
        fetchedHeaders = req.headers;
        return { status: 200, headers: { "Content-Type": "text/xml" }, body: origXml };
      },
    }
  );

  assert.equal(fetchedUrl, "https://www.youtube.com/api/timedtext?v=abc&lang=en&fmt=srv3");
  assert.equal(fetchedHeaders["X-YTMy-Raw"], "1");
  assert.ok(out.body);
  assert.match(out.body, /rc="1"/);
  assert.doesNotMatch(out.body, /a="1"/);
  assert.match(out.body, /Hello world &amp; friends\nမင်္ဂလာပါ သူငယ်ချင်းများ/);
  assert.match(out.body, /How&#39;s it going\?\nအဆင်ပြေရဲ့လား။/);
});

test("json3 and WebVTT support dual_my_top and my_only modes", async () => {
  const origJson = JSON.stringify({
    events: [
      { tStartMs: 500, dDurationMs: 1200, wWinId: 1, segs: [{ utf8: "Good " }, { utf8: "morning" }] },
      { tStartMs: 1800, dDurationMs: 300, aAppend: 1, segs: [{ utf8: "\n" }] },
    ],
  });
  const myJson = JSON.stringify({
    events: [{ tStartMs: 550, dDurationMs: 1200, wWinId: 1, segs: [{ utf8: "မင်္ဂလာနံနက်ခင်းပါ" }] }],
  });

  const outDual = await timedtextDual.handleResponse(
    { url: "https://m.youtube.com/api/timedtext?v=j1&lang=en&tlang=my&fmt=json3", headers: {} },
    { status: 200, headers: { "Content-Type": "application/json" }, body: myJson },
    { subtitleMode: "dual_my_top", translationMode: "hybrid", autoMyanmar: true },
    {
      store: makeMemoryStore(),
      httpGet: async () => ({ status: 200, headers: { "Content-Type": "application/json" }, body: origJson }),
    }
  );
  const parsedDual = JSON.parse(outDual.body);
  assert.equal(parsedDual.events.length, 1);
  assert.equal(parsedDual.events[0].wWinId, undefined);
  assert.equal(parsedDual.events[0].segs[0].utf8, "မင်္ဂလာနံနက်ခင်းပါ\nGood morning");

  const origVtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nLine one\n";
  const myVtt = "WEBVTT\n\n00:00:01.050 --> 00:00:03.000\nပထမစာကြောင်း\n";
  const outVttMyOnly = await timedtextDual.handleResponse(
    { url: "https://www.youtube.com/api/timedtext?v=vtt1&lang=en&tlang=my&fmt=vtt", headers: {} },
    { status: 200, headers: { "Content-Type": "text/vtt" }, body: myVtt },
    { subtitleMode: "my_only", translationMode: "hybrid", autoMyanmar: true },
    {
      store: makeMemoryStore(),
      httpGet: async () => ({ status: 200, headers: { "Content-Type": "text/vtt" }, body: origVtt }),
    }
  );
  assert.match(outVttMyOnly.body, /00:00:01\.050 --> 00:00:03\.000\nပထမစာကြောင်း/);
  assert.doesNotMatch(outVttMyOnly.body, /Line one/);
});

test("Google Translate fallback works when YouTube native tlang=my fails or google_only is chosen, with batch split-half recovery", async () => {
  const origXml = `<?xml version="1.0" encoding="utf-8" ?>
<timedtext format="3"><body>
  <p t="100" d="1000">First line</p>
  <p t="1200" d="1000">Second line</p>
  <p t="2400" d="1000">First line</p>
</body></timedtext>`;

  const store = makeMemoryStore();
  // Request hook caches language cleanly and skips X-YTMy-Raw internal requests without touching sparams
  const reqBypass = timedtextDual.handleRequest(
    { url: "https://www.youtube.com/api/timedtext?v=fb1&lang=en&sparams=v", headers: { "X-YTMy-Raw": "1" } },
    { autoMyanmar: true, translationMode: "hybrid" },
    store
  );
  assert.equal(reqBypass.headers["X-YTMy-Raw"], undefined);
  assert.equal(reqBypass.url, undefined);

  const reqAuto = timedtextDual.handleRequest(
    { url: "https://www.youtube.com/api/timedtext?v=fb1&lang=en", headers: {} },
    { autoMyanmar: true, translationMode: "hybrid" },
    store
  );
  assert.equal(reqAuto.url, "https://www.youtube.com/api/timedtext?v=fb1&lang=en&tlang=my");

  // Simulate YouTube tlang=my returning empty 200 -> fallback fetches orig + calls Google Translate;
  // first batch simulates merged newline mismatch so recursive split-half recovers 1:1 translations
  let translateCalls = 0;
  const out = await timedtextDual.handleResponse(
    { url: "https://www.youtube.com/api/timedtext?v=fb1&lang=en&tlang=my", headers: {} },
    { status: 200, headers: { "Content-Type": "text/xml" }, body: '<?xml version="1.0"?><timedtext format="3"><body></body></timedtext>' },
    { subtitleMode: "dual_orig_top", translationMode: "hybrid", autoMyanmar: true },
    {
      store,
      httpGet: async (req) => {
        if (req.url.includes("www.youtube.com/api/timedtext")) {
          return { status: 200, headers: { "Content-Type": "text/xml" }, body: origXml };
        }
        if (req.url.includes("translate.googleapis.com")) {
          translateCalls++;
          const q = decodeURIComponent(req.url.split("&q=")[1] || "");
          if (q.includes("\n")) {
            // Simulate mismatched newline count on multi-line batch
            return { status: 200, body: JSON.stringify([[["ပထမနှင့်ဒုတိယပေါင်း", q, null, null, 1]]]) };
          }
          const map = {
            "First line": "ပထမစာကြောင်း",
            "Second line": "ဒုတိယစာကြောင်း",
          };
          return { status: 200, body: JSON.stringify([[[map[q] || q, q, null, null, 1]]]) };
        }
        throw new Error("Unexpected URL: " + req.url);
      },
    }
  );

  assert.ok(translateCalls >= 3); // initial mismatched batch + 2 unique single-cue fallbacks (deduped "First line")
  assert.match(out.body, /First line\nပထမစာကြောင်း/);
  assert.match(out.body, /Second line\nဒုတိယစာကြောင်း/);
});

