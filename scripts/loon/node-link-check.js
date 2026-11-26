/**
 * Node Proxy Link & Relay Chain Checker for Loon 3.5.1+ (Myanmar + English)
 * Inspects entry server (via Sub-Store RebuildNodeLineJsonByRE cache when present)
 * and exit IP/country/region via ip-api.com.
 */

(function () {
  "use strict";

  const CACHE_KEY = "RebuildNodeLineJsonByRE";
  const TITLE = "🔗 Proxy လမ်းကြောင်း စစ်ဆေးမှု (Node Link Check)";
  const UA =
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

  const nodeName =
    typeof $environment !== "undefined" && $environment && $environment.params
      ? $environment.params.node
      : "";

  function fetchIpInfo(targetIp, node) {
    return new Promise((resolve, reject) => {
      const url = "http://ip-api.com/json/" + encodeURIComponent(targetIp || "") + "?lang=en";
      $httpClient.get({ url, node, headers: { "User-Agent": UA } }, (err, resp, body) => {
        if (err) {
          reject(err);
          return;
        }
        try {
          const parsed = JSON.parse(body);
          if (!parsed || parsed.status !== "success") {
            reject(new Error((parsed && parsed.message) || "IP lookup failed"));
            return;
          }
          resolve(parsed);
        } catch (e) {
          reject(e);
        }
      });
    });
  }

  function formatPlace(info) {
    return [info.country, info.regionName, info.city].filter(Boolean).join(" ").trim() || "-";
  }

  function buildLinkSummaryHtml(opts) {
    const { policy, protoType, inIpInfo, outIpInfo } = opts;
    const inIp = inIpInfo.query || "-";
    const inCC = inIpInfo.countryCode || "";
    const outIp = outIpInfo.query || "-";
    const outCC = outIpInfo.countryCode || "";
    const inPlace = formatPlace(inIpInfo);
    const outPlace = formatPlace(outIpInfo);

    let routeLabel = "Relay / Transit Proxy (ကြားခံလမ်းကြောင်း)";
    let badgeColor = "#0088CC";
    if (outCC === inCC && outCC === "CN") {
      routeLabel = "Domestic Proxy (CN)";
      badgeColor = "#D9534F";
    } else if (outCC === inCC) {
      routeLabel = "Direct Proxy (တိုက်ရိုက်ချိတ်ဆက်မှု)";
      badgeColor = "#2E8B57";
    } else if (/IEPL/i.test(policy)) {
      routeLabel = "IEPL Dedicated (IEPL အထူးလိုင်း)";
      badgeColor = "#00B400";
    } else if (/IPLC/i.test(policy)) {
      routeLabel = "IPLC Dedicated (IPLC အထူးလိုင်း)";
      badgeColor = "#00B400";
    } else if (/专线/.test(policy)) {
      routeLabel = "Private Dedicated Line (အထူးလိုင်း)";
      badgeColor = "#00B400";
    }

    return (
      `<p style="text-align: center; font-family: -apple-system; font-size: large; font-weight: thin">` +
      `<br><b>${inPlace}</b><br><small><small>${inIp}</small></small><br><br>` +
      `<font color=${badgeColor}>-------------------------<br><b>⟦ ${routeLabel} ⟧</b><br>-------------------------</font><br><br>` +
      `<b>${outPlace}</b><br><small><small>${outIp}</small></small><br><br>` +
      `-----------------------------------<br><br>` +
      `<font color=#6959CD><small><b>${protoType}</b> ➟ ${policy}</small></font></p>`
    );
  }

  function buildFallbackHtml(errMsg, outIpInfo) {
    if (outIpInfo && outIpInfo.query) {
      const place = formatPlace(outIpInfo);
      return (
        `<p style="text-align: center; font-family: -apple-system; font-size: large; font-weight: thin">` +
        `<br><font color=#D97706><b>ℹ️ Sub-Store ဝင်ပေါက် (Entry) cache မတွေ့ပါ</b></font><br>` +
        `<small>Exit IP အချက်အလက်ကိုသာ ပြသပေးထားပါသည်</small><br><br>` +
        `<b>${place}</b><br><small>${outIpInfo.query} (${outIpInfo.isp || "-"})</small><br><br>` +
        `-----------------------------------<br>` +
        `<font color=#6959CD><small>Node ➟ ${nodeName || "-"}</small></font></p>`
      );
    }
    return `<p style="text-align: center; font-family: -apple-system; font-size: large;"><br><font color=#D9534F><b>⟦ ${errMsg} ⟧</b></font></p>`;
  }

  async function run() {
    if (typeof $httpClient === "undefined" || typeof $done !== "function") return;
    let outIpInfo = null;
    try {
      outIpInfo = await fetchIpInfo("", nodeName);
      const rawCache = typeof $persistentStore !== "undefined" ? $persistentStore.read(CACHE_KEY) : null;
      const cache = rawCache ? JSON.parse(rawCache) : null;
      const nodeInfo = cache && nodeName ? cache[nodeName] : null;
      if (!nodeInfo || !nodeInfo.server) {
        $done({ title: TITLE, htmlMessage: buildFallbackHtml("Sub-Store cache missing", outIpInfo) });
        return;
      }
      const inIpInfo = await fetchIpInfo(nodeInfo.server, undefined);
      const protoType = String(nodeInfo.type || "PROXY").toUpperCase();
      $done({
        title: TITLE,
        htmlMessage: buildLinkSummaryHtml({ policy: nodeName, protoType, inIpInfo, outIpInfo }),
      });
    } catch (e) {
      $done({
        title: TITLE,
        htmlMessage: buildFallbackHtml((e && e.message) || String(e), outIpInfo),
      });
    }
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { buildLinkSummaryHtml, buildFallbackHtml };
  }
  if (typeof $httpClient !== "undefined") {
    run();
  }
})();
