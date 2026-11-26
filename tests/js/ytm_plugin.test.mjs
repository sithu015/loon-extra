import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const ytmEnhance = require("../../scripts/loon/ytm-enhance.js");
const ytmLyrics = require("../../scripts/loon/ytm-lyrics-myanmar.js");

function makeMemoryStore(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    read: (k) => (map.has(k) ? map.get(k) : null),
    write: (v, k) => {
      map.set(k, v);
      return true;
    },
  };
}

function encodeString(s) {
  return new TextEncoder().encode(s);
}

function varint(v) {
  let x = BigInt(v);
  const out = [];
  while (x >= 0x80n) {
    out.push(Number((x & 0x7fn) | 0x80n));
    x >>= 7n;
  }
  out.push(Number(x));
  return Uint8Array.from(out);
}

function pbBytes(no, payload) {
  const data = typeof payload === "string" ? encodeString(payload) : payload;
  return ytmEnhance.encodeFields([{ no, wireType: 2, data }]);
}

function pbVarint(no, val) {
  return ytmEnhance.encodeFields([{ no, wireType: 0, data: varint(val) }]);
}

function concat(...arrays) {
  const len = arrays.reduce((s, a) => s + a.length, 0);
  const out = new Uint8Array(len);
  let pos = 0;
  for (const a of arrays) {
    out.set(a, pos);
    pos += a.length;
  }
  return out;
}

test("ytm-enhance strips ads and unlocks background audio & PiP in JSON player", () => {
  const payload = {
    adPlacements: [{ adPlacementRenderer: { id: "ad1" } }],
    adSlots: [{ adSlotRenderer: {} }],
    playerAds: [{}],
    playbackTracking: {
      videostatsPlaybackUrl: { baseUrl: "https://s.youtube.com/api/stats/playback" },
      pageadViewthroughconversion: { baseUrl: "https://www.googleadservices.com/pagead" },
    },
    playabilityStatus: { status: "OK" },
  };
  const res = ytmEnhance.transformJsonResponse(
    "https://music.youtube.com/youtubei/v1/player",
    JSON.stringify(payload),
    { enableAdBlock: true, enableBgPlay: true, removeUpsells: true }
  );
  assert.equal(res.changed, true);
  const out = JSON.parse(res.body);
  assert.deepEqual(out.adPlacements, []);
  assert.deepEqual(out.adSlots, []);
  assert.deepEqual(out.playerAds, []);
  assert.equal(out.playbackTracking.pageadViewthroughconversion, undefined);
  assert.equal(out.playabilityStatus.backgroundPlayerRender.backgroundAbility.active, true);
  assert.equal(out.playabilityStatus.backgroundPlayerRender.backgroundPlayerRenderer.backgroundable, true);
  assert.equal(out.playabilityStatus.audioOnlyPlayability.audioOnlyPlayabilityRenderer.audioOnlyAvailability, "FEATURE_AVAILABILITY_ALLOWED");
  assert.equal(out.playabilityStatus.pictureInPictureRender.pictureInPictureAbility.active, true);
});

test("ytm-enhance unlocks Protobuf player PlayabilityStatus and strips ad fields losslessly", () => {
  const playability = concat(pbVarint(1, 0), pbBytes(99, "keep-unknown-playability"));
  const playbackTracking = concat(pbBytes(1, "keep-stats"), pbBytes(18, "ad-conversion"));
  const proto = concat(
    pbBytes(2, playability),
    pbBytes(7, "ad-placement"),
    pbBytes(9, playbackTracking),
    pbBytes(68, "ad-slot"),
    pbBytes(42, "custom-unknown-field")
  );
  const res = ytmEnhance.transformBytesResponse(
    "https://youtubei.googleapis.com/youtubei/v1/player",
    proto,
    { enableAdBlock: true, enableBgPlay: true }
  );
  assert.equal(res.changed, true);
  const fields = ytmEnhance.decodeFields(res.body);
  assert.equal(fields.some((f) => f.no === 7), false);
  assert.equal(fields.some((f) => f.no === 68), false);
  assert.equal(new TextDecoder().decode(fields.find((f) => f.no === 42).data), "custom-unknown-field");

  const psFields = ytmEnhance.decodeFields(fields.find((f) => f.no === 2).data);
  assert.equal(psFields.some((f) => f.no === 11), true);
  assert.equal(psFields.some((f) => f.no === 21), true);
  assert.equal(new TextDecoder().decode(psFields.find((f) => f.no === 99).data), "keep-unknown-playability");
});

test("ytm-enhance removes SPunlimited Upgrade tab from Guide JSON & Protobuf", () => {
  const guideJson = {
    items: [
      {
        pivotBarRenderer: {
          items: [
            { pivotBarItemRenderer: { navigationEndpoint: { browseEndpoint: { browseId: "FEmusic_home" } } } },
            { pivotBarItemRenderer: { navigationEndpoint: { browseEndpoint: { browseId: "SPunlimited" } } } },
          ],
        },
      },
    ],
  };
  const jRes = ytmEnhance.transformJsonResponse(
    "https://music.youtube.com/youtubei/v1/guide",
    JSON.stringify(guideJson),
    { removeUpsells: true }
  );
  assert.equal(jRes.changed, true);
  const parsed = JSON.parse(jRes.body);
  assert.equal(parsed.items[0].pivotBarRenderer.items.length, 1);

  const iconKeep = pbBytes(1, concat(pbBytes(318370163, pbBytes(1, "FEmusic_home"))));
  const iconDrop = pbBytes(1, concat(pbBytes(318370163, pbBytes(1, "SPunlimited"))));
  const guidePb = pbBytes(4, pbBytes(117866661, concat(iconKeep, iconDrop)));
  const pRes = ytmEnhance.transformBytesResponse(
    "https://youtubei.googleapis.com/youtubei/v1/guide",
    guidePb,
    { removeUpsells: true }
  );
  assert.equal(pRes.changed, true);
  const str = new TextDecoder().decode(pRes.body);
  assert.equal(str.includes("FEmusic_home"), true);
  assert.equal(str.includes("SPunlimited"), false);
});

test("ytm-enhance unlocks BackgroundPlayBackSettingRenderer in Protobuf get_setting idempotently", () => {
  const emptySettings = pbBytes(6, pbBytes(66930374, pbVarint(4, 10135)));
  const r1 = ytmEnhance.transformBytesResponse(
    "https://youtubei.googleapis.com/youtubei/v1/account/get_setting",
    emptySettings,
    { enableBgPlay: true }
  );
  assert.equal(r1.changed, true);
  const f1 = ytmEnhance.decodeFields(r1.body);
  assert.equal(f1.some((f) => f.no === 6 && ytmEnhance.decodeFields(f.data).some((sf) => sf.no === 88478200)), true);
});

test("ytm-lyrics-myanmar translates JSON plain & timed lyrics into Myanmar dual format and caches", async () => {
  const store = makeMemoryStore();
  let calls = 0;
  const fakeGet = async () => {
    calls++;
    return JSON.stringify([
      [["မင်္ဂလာပါ\n", "Hello world\n", null, null, 1], ["မိုးရွာနေသည်", "It is raining", null, null, 1]],
    ]);
  };
  const browseJson = {
    contents: {
      sectionListRenderer: {
        contents: [
          {
            musicDescriptionShelfRenderer: {
              description: { runs: [{ text: "Hello world\nIt is raining" }] },
            },
          },
          { musicMealbarPromoRenderer: { messageTitle: "Get Premium" } },
        ],
      },
    },
  };
  const r1 = await ytmLyrics.transformBrowseJson(
    JSON.stringify(browseJson),
    { lyricsMode: "dual_orig_top", removeUpsells: true },
    { store, httpGet: fakeGet }
  );
  assert.equal(r1.changed, true);
  assert.equal(calls, 1);
  const out = JSON.parse(r1.body);
  assert.equal(out.contents.sectionListRenderer.contents.length, 1);
  const txt = out.contents.sectionListRenderer.contents[0].musicDescriptionShelfRenderer.description.runs[0].text;
  assert.ok(txt.includes("Hello world\n  └ မင်္ဂလာပါ"));
  assert.ok(txt.includes("It is raining\n  └ မိုးရွာနေသည်"));

  // Second call hits bounded cache cleanly
  const r2 = await ytmLyrics.transformBrowseJson(
    JSON.stringify(browseJson),
    { lyricsMode: "my_only", removeUpsells: true },
    { store, httpGet: fakeGet }
  );
  assert.equal(calls, 1);
  const out2 = JSON.parse(r2.body);
  assert.equal(
    out2.contents.sectionListRenderer.contents[0].musicDescriptionShelfRenderer.description.runs[0].text,
    "မင်္ဂလာပါ\nမိုးရွာနေသည်"
  );
});

test("ytm-lyrics-myanmar translates Synced Protobuf TimedLyricsRender (465160965) preserving cue timestamps", async () => {
  const store = makeMemoryStore();
  const fakeGet = async () => JSON.stringify([[["သီချင်းစာသား", "Song line", null, null, 1]]]);

  // Run entry has field 1 (lineText) + field 2 (cueRange/timestamp bytes)
  const runBytes = concat(pbBytes(1, "Song line"), pbBytes(2, "cue-ts-999"));
  const timedContent = concat(pbBytes(1, runBytes), pbBytes(2, "Source: LyricFind"));
  const timedRender = pbBytes(4, timedContent);
  const tree = pbBytes(
    9,
    pbBytes(
      153515154,
      pbBytes(172660663, pbBytes(1, pbBytes(168777401, pbBytes(5, pbBytes(465160965, timedRender)))))
    )
  );

  const res = await ytmLyrics.transformBrowseBytes(
    tree,
    { lyricsMode: "dual_orig_top" },
    { store, httpGet: fakeGet }
  );
  assert.equal(res.changed, true);
  const decodedStr = new TextDecoder().decode(res.body);
  assert.ok(decodedStr.includes("Song line\nသီချင်းစာသား"));
  assert.ok(decodedStr.includes("cue-ts-999"));
  assert.ok(decodedStr.includes("Source: LyricFind"));
});

test("ytm-lyrics-myanmar translates Plain Protobuf MusicDescriptionShelfRenderer (221496734)", async () => {
  const store = makeMemoryStore();
  const fakeGet = async () =>
    JSON.stringify([[["ပထမစာကြောင်း\n", "Line one\n", null, null, 1], ["ဒုတိယစာကြောင်း", "Line two", null, null, 1]]]);

  const desc = pbBytes(1, pbBytes(1, "Line one\nLine two"));
  const shelf = concat(pbBytes(3, desc), pbBytes(10, pbBytes(1, "Source: Musixmatch")));
  const tree = pbBytes(
    9,
    pbBytes(49399797, pbBytes(1, pbBytes(221496734, shelf)))
  );

  const res = await ytmLyrics.transformBrowseBytes(
    tree,
    { lyricsMode: "dual_my_top" },
    { store, httpGet: fakeGet }
  );
  assert.equal(res.changed, true);
  const decodedStr = new TextDecoder().decode(res.body);
  assert.ok(decodedStr.includes("ပထမစာကြောင်း\n  └ Line one"));
  assert.ok(decodedStr.includes("ဒုတိယစာကြောင်း\n  └ Line two"));
  assert.ok(decodedStr.includes("Source: Musixmatch"));
});
