/**
 * Node IP & GeoLocation Checker for Loon 3.5.1+ (Myanmar + English)
 * Queries ip-api.com through the selected Loon node and renders HTML info.
 */

(function () {
  "use strict";

  const API_URL = "http://ip-api.com/json/?fields=8450015&lang=en";
  const nodeName =
    typeof $environment !== "undefined" && $environment && $environment.params
      ? $environment.params.node
      : "";

  const FIELDS = ["query", "isp", "as", "country", "city", "timezone", "lon", "lat", "currency"];
  const LABELS = [
    "🗺️ IP လိပ်စာ (IP)",
    "🖥️ ISP",
    "#️⃣ ASN",
    "🌍 နိုင်ငံ / ဒေသ (Country)",
    "🏙 မြို့ (City)",
    "🕗 အချိန်ဇုန် (Timezone)",
    "📍 လောင်ဂျီကျု (Lon)",
    "📍 လတ္တီကျု (Lat)",
    "🪙 ငွေကြေး (Currency)",
  ];

  const flags = new Map([
    ["AC", "🇦🇨"], ["AD", "🇦🇩"], ["AE", "🇦🇪"], ["AF", "🇦🇫"], ["AG", "🇦🇬"],
    ["AI", "🇦🇮"], ["AL", "🇦🇱"], ["AM", "🇦🇲"], ["AO", "🇦🇴"], ["AQ", "🇦🇶"],
    ["AR", "🇦🇷"], ["AS", "🇦🇸"], ["AT", "🇦🇹"], ["AU", "🇦🇺"], ["AW", "🇦🇼"],
    ["AX", "🇦🇽"], ["AZ", "🇦🇿"], ["BA", "🇧🇦"], ["BB", "🇧🇧"], ["BD", "🇧🇩"],
    ["BE", "🇧🇪"], ["BF", "🇧🇫"], ["BG", "🇧🇬"], ["BH", "🇧🇭"], ["BI", "🇧🇮"],
    ["BJ", "🇧🇯"], ["BM", "🇧🇲"], ["BN", "🇧🇳"], ["BO", "🇧🇴"], ["BR", "🇧🇷"],
    ["BS", "🇧🇸"], ["BT", "🇧🇹"], ["BW", "🇧🇼"], ["BY", "🇧🇾"], ["BZ", "🇧🇿"],
    ["CA", "🇨🇦"], ["CD", "🇨🇩"], ["CF", "🇨🇫"], ["CG", "🇨🇬"], ["CH", "🇨🇭"],
    ["CI", "🇨🇮"], ["CL", "🇨🇱"], ["CM", "🇨🇲"], ["CN", "🇨🇳"], ["CO", "🇨🇴"],
    ["CR", "🇨🇷"], ["CU", "🇨🇺"], ["CV", "🇨🇻"], ["CY", "🇨🇾"], ["CZ", "🇨🇿"],
    ["DE", "🇩🇪"], ["DK", "🇩🇰"], ["DO", "🇩🇴"], ["DZ", "🇩🇿"], ["EC", "🇪🇨"],
    ["EE", "🇪🇪"], ["EG", "🇪🇬"], ["ES", "🇪🇸"], ["ET", "🇪🇹"], ["EU", "🇪🇺"],
    ["FI", "🇫🇮"], ["FJ", "🇫🇯"], ["FR", "🇫🇷"], ["GB", "🇬🇧"], ["GE", "🇬🇪"],
    ["GH", "🇬🇭"], ["GR", "🇬🇷"], ["GT", "🇬🇹"], ["HK", "🇭🇰"], ["HR", "🇭🇷"],
    ["HU", "🇭🇺"], ["ID", "🇮🇩"], ["IE", "🇮🇪"], ["IL", "🇮🇱"], ["IM", "🇮🇲"],
    ["IN", "🇮🇳"], ["IQ", "🇮🇶"], ["IR", "🇮🇷"], ["IS", "🇮🇸"], ["IT", "🇮🇹"],
    ["JM", "🇯🇲"], ["JO", "🇯🇴"], ["JP", "🇯🇵"], ["KE", "🇰🇪"], ["KG", "🇰🇬"],
    ["KH", "🇰🇭"], ["KR", "🇰🇷"], ["KW", "🇰🇼"], ["KZ", "🇰🇿"], ["LA", "🇱🇦"],
    ["LB", "🇱🇧"], ["LK", "🇱🇰"], ["LT", "🇱🇹"], ["LU", "🇱🇺"], ["LV", "🇱🇻"],
    ["MA", "🇲🇦"], ["MD", "🇲🇩"], ["MM", "🇲🇲"], ["MN", "🇲🇳"], ["MO", "🇲🇴"],
    ["MX", "🇲🇽"], ["MY", "🇲🇾"], ["NG", "🇳🇬"], ["NL", "🇳🇱"], ["NO", "🇳🇴"],
    ["NP", "🇳🇵"], ["NZ", "🇳🇿"], ["OM", "🇴🇲"], ["PA", "🇵🇦"], ["PE", "🇵🇪"],
    ["PH", "🇵🇭"], ["PK", "🇵🇰"], ["PL", "🇵🇱"], ["PR", "🇵🇷"], ["PT", "🇵🇹"],
    ["PY", "🇵🇾"], ["QA", "🇶🇦"], ["RO", "🇷🇴"], ["RS", "🇷🇸"], ["RU", "🇷🇺"],
    ["SA", "🇸🇦"], ["SE", "🇸🇪"], ["SG", "🇸🇬"], ["SI", "🇸🇮"], ["SK", "🇸🇰"],
    ["TH", "🇹🇭"], ["TN", "🇹🇳"], ["TR", "🇹🇷"], ["TW", "🇹🇼"], ["TZ", "🇹🇿"],
    ["UA", "🇺🇦"], ["UG", "🇺🇬"], ["UK", "🇬🇧"], ["US", "🇺🇸"], ["UY", "🇺🇾"],
    ["UZ", "🇺🇿"], ["VN", "🇻🇳"], ["ZA", "🇿🇦"],
    ["USD", "🇺🇸"], ["EUR", "🇪🇺"], ["GBP", "🇬🇧"], ["JPY", "🇯🇵"], ["SGD", "🇸🇬"],
    ["MMK", "🇲🇲"], ["THB", "🇹🇭"], ["CNY", "🇨🇳"], ["HKD", "🇭🇰"], ["TWD", "🇹🇼"],
    ["KRW", "🇰🇷"], ["INR", "🇮🇳"], ["MYR", "🇲🇾"], ["VND", "🇻🇳"], ["AUD", "🇦🇺"],
    ["CAD", "🇨🇦"], ["CHF", "🇨🇭"], ["RUB", "🇷🇺"],
  ]);

  function formatInfoHtml(rawData) {
    let cnt;
    try {
      cnt = JSON.parse(rawData);
    } catch (_e) {
      return '<p style="text-align: center; font-family: -apple-system; font-size: large;">❌ အချက်အလက် ဖတ်ရှု၍မရပါ (Invalid Response)</p>';
    }
    if (!cnt || cnt.status !== "success") {
      const msg = (cnt && cnt.message) || "Unknown error";
      return `<p style="text-align: center; font-family: -apple-system; font-size: large;">❌ စစ်ဆေးမှု မအောင်မြင်ပါ (${msg})</p>`;
    }

    let res = "------------------------------";
    for (let i = 0; i < FIELDS.length; i++) {
      const key = FIELDS[i];
      let val = cnt[key];
      if (key === "country" && val && cnt.countryCode) {
        const flag = flags.get(String(cnt.countryCode).toUpperCase()) || "";
        val = val + (flag ? " · " + flag : "");
      } else if (key === "currency" && val) {
        const cFlag = flags.get(String(val).toUpperCase()) || "";
        val = val + (cFlag ? " " + cFlag : "");
      }
      if (val !== undefined && val !== null && val !== "") {
        res += `</br><b>${LABELS[i]}:</b> ${val}</br>`;
      }
    }
    res += `------------------------------</br><font color=#6959CD><b>Node အမည် (Node):</b> ${nodeName || "-"}</font>`;
    return `<p style="text-align: center; font-family: -apple-system; font-size: large; font-weight: thin">${res}</p>`;
  }

  function run() {
    if (typeof $httpClient === "undefined" || typeof $done !== "function") return;
    $httpClient.get({ url: API_URL, node: nodeName }, (error, _response, data) => {
      if (error) {
        const html =
          '<p style="text-align: center; font-family: -apple-system; font-size: large; font-weight: bold;"></br></br>🛑 စစ်ဆေးမှု အချိန်ကုန်သွားပါသည် (Timeout)</p>';
        $done({ title: "🔎 Node IP စစ်ဆေးမှု ရလဒ်", htmlMessage: html });
        return;
      }
      const html = data
        ? formatInfoHtml(data)
        : '<p style="text-align: center; font-family: -apple-system; font-size: large;">❌ ရလဒ် ဗလာဖြစ်နေပါသည် (Empty)</p>';
      $done({ title: "🔎 Node IP စစ်ဆေးမှု ရလဒ် (GeoLocation)", htmlMessage: html });
    });
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { formatInfoHtml };
  }
  if (typeof $httpClient !== "undefined") {
    run();
  }
})();
