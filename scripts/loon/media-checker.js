/**
 * Streaming Media Unlock Checker for Loon 3.5.1+ (Myanmar + English)
 * Tests YouTube Premium, Netflix, Disney+, Paramount+, Discovery+, and DAZN through the selected node.
 */

(function () {
  "use strict";

  const NF_BASE_URL = "https://www.netflix.com/title/70143836";
  const DISNEY_LOCATION_BASE_URL = "https://disney.api.edge.bamgrid.com/graph/v1/device/graphql";
  const YTB_BASE_URL = "https://www.youtube.com/premium";
  const DAZN_BASE_URL = "https://startup.core.indazn.com/misl/v5/Startup";
  const PARAM_BASE_URL = "https://www.paramountplus.com/";
  const DISCOVERY_TOKEN_URL =
    "https://us1-prod-direct.discoveryplus.com/token?deviceId=d1a4a5d25212400d1e6985984604d740&realm=go&shortlived=true";
  const DISCOVERY_BASE_URL = "https://us1-prod-direct.discoveryplus.com/users/me";
  const UA =
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

  const nodeName =
    typeof $environment !== "undefined" && $environment && $environment.params
      ? $environment.params.node
      : "";

  const flags = new Map([
    ["AE", "🇦🇪"], ["AR", "🇦🇷"], ["AT", "🇦🇹"], ["AU", "🇦🇺"], ["BD", "🇧🇩"],
    ["BE", "🇧🇪"], ["BG", "🇧🇬"], ["BR", "🇧🇷"], ["CA", "🇨🇦"], ["CH", "🇨🇭"],
    ["CL", "🇨🇱"], ["CN", "🇨🇳"], ["CO", "🇨🇴"], ["CZ", "🇨🇿"], ["DE", "🇩🇪"],
    ["DK", "🇩🇰"], ["EG", "🇪🇬"], ["ES", "🇪🇸"], ["FI", "🇫🇮"], ["FR", "🇫🇷"],
    ["GB", "🇬🇧"], ["GR", "🇬🇷"], ["HK", "🇭🇰"], ["HU", "🇭🇺"], ["ID", "🇮🇩"],
    ["IE", "🇮🇪"], ["IL", "🇮🇱"], ["IN", "🇮🇳"], ["IT", "🇮🇹"], ["JP", "🇯🇵"],
    ["KH", "🇰🇭"], ["KR", "🇰🇷"], ["LA", "🇱🇦"], ["LU", "🇱🇺"], ["MM", "🇲🇲"],
    ["MO", "🇲🇴"], ["MX", "🇲🇽"], ["MY", "🇲🇾"], ["NL", "🇳🇱"], ["NO", "🇳🇴"],
    ["NZ", "🇳🇿"], ["PH", "🇵🇭"], ["PK", "🇵🇰"], ["PL", "🇵🇱"], ["PT", "🇵🇹"],
    ["RO", "🇷🇴"], ["RU", "🇷🇺"], ["SA", "🇸🇦"], ["SE", "🇸🇪"], ["SG", "🇸🇬"],
    ["TH", "🇹🇭"], ["TR", "🇹🇷"], ["TW", "🇹🇼"], ["UA", "🇺🇦"], ["UK", "🇬🇧"],
    ["US", "🇺🇸"], ["VN", "🇻🇳"], ["ZA", "🇿🇦"],
  ]);

  const result = {
    title: "📺 Streaming ဝန်ဆောင်မှု စစ်ဆေးမှု (Media Checker)",
    YouTube: "<b>YouTube Premium:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️",
    Netflix: "<b>Netflix:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️",
    Dazn: "<b>DAZN:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️",
    Disney: "<b>Disney+:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️",
    Paramount: "<b>Paramount+:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️",
    Discovery: "<b>Discovery+:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️",
  };

  function regionBadge(code) {
    const upper = String(code || "").toUpperCase();
    const flag = flags.get(upper) || "";
    return flag ? `⟦${flag} ${upper}⟧` : `⟦${upper}⟧`;
  }

  function disneyLocation() {
    return new Promise((resolve) => {
      $httpClient.post(
        {
          url: DISNEY_LOCATION_BASE_URL,
          node: nodeName,
          timeout: 8000,
          headers: {
            "Accept-Language": "en",
            Authorization: "ZGlzbmV5JmJyb3dzZXImMS4wLjA.Cu56AgSfBTDag5NiRA81oLHkDZfu5L3CKadnefEAY84",
            "Content-Type": "application/json",
            "User-Agent": UA,
          },
          body: JSON.stringify({
            query:
              "mutation registerDevice($input: RegisterDeviceInput!) { registerDevice(registerDevice: $input) { grant { grantType assertion } } }",
            variables: {
              input: {
                applicationRuntime: "chrome",
                attributes: {
                  browserName: "chrome",
                  browserVersion: "126.0.0",
                  manufacturer: "microsoft",
                  model: null,
                  operatingSystem: "windows",
                  operatingSystemVersion: "10.0",
                  osDeviceIds: [],
                },
                deviceFamily: "browser",
                deviceLanguage: "en",
                deviceProfile: "windows",
              },
            },
          }),
        },
        (err, response, data) => {
          if (err || !response || response.status !== 200) {
            result.Disney = "<b>Disney+:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
            resolve();
            return;
          }
          try {
            const resData = JSON.parse(data);
            const session = resData && resData.extensions && resData.extensions.sdk && resData.extensions.sdk.session;
            if (session && session.location && session.location.countryCode) {
              const badge = regionBadge(session.location.countryCode);
              result.Disney = session.inSupportedLocation
                ? `<b>Disney+:</b> ရရှိနိုင်သည် (Supported) ➟ ${badge} 🎉`
                : `<b>Disney+:</b> မကြာမီ ရရှိမည် (Coming Soon) ➟ ${badge} ⚠️`;
            } else {
              result.Disney = "<b>Disney+:</b> မရရှိနိုင်ပါ (Not Supported) 🚫";
            }
          } catch (_e) {
            result.Disney = "<b>Disney+:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
          }
          resolve();
        }
      );
    });
  }

  function ytbTest() {
    return new Promise((resolve) => {
      $httpClient.get({ url: YTB_BASE_URL, node: nodeName, timeout: 10000, headers: { "User-Agent": UA } }, (err, response, data) => {
        if (err || !response || response.status !== 200) {
          result.YouTube = "<b>YouTube Premium:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
          resolve();
          return;
        }
        if (String(data).includes("Premium is not available in your country")) {
          result.YouTube = "<b>YouTube Premium:</b> မရရှိနိုင်ပါ (Not Supported) 🚫";
          resolve();
          return;
        }
        let region = "US";
        const ret = /"GL":"(.*?)"/.exec(data);
        if (ret && ret[1]) region = ret[1];
        else if (String(data).includes("www.google.cn")) region = "CN";
        result.YouTube = `<b>YouTube Premium:</b> ရရှိနိုင်သည် (Supported) ➟ ${regionBadge(region)} 🎉`;
        resolve();
      });
    });
  }

  function daznTest() {
    return new Promise((resolve) => {
      $httpClient.post(
        {
          url: DAZN_BASE_URL,
          node: nodeName,
          timeout: 9000,
          headers: { "User-Agent": UA, "Content-Type": "application/json" },
          body: JSON.stringify({
            LandingPageKey: "generic",
            Platform: "web",
            PlatformAttributes: {},
            Manufacturer: "",
            PromoCode: "",
            Version: "2",
          }),
        },
        (err, response, data) => {
          if (err || !response || response.status !== 200) {
            result.Dazn = "<b>DAZN:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
            resolve();
            return;
          }
          const ret = /"GeolocatedCountry":"(.*?)"/.exec(data);
          result.Dazn =
            ret && ret[1]
              ? `<b>DAZN:</b> ရရှိနိုင်သည် (Supported) ➟ ${regionBadge(ret[1])} 🎉`
              : "<b>DAZN:</b> မရရှိနိုင်ပါ (Not Supported) 🚫";
          resolve();
        }
      );
    });
  }

  function parmTest() {
    return new Promise((resolve) => {
      $httpClient.get({ url: PARAM_BASE_URL, node: nodeName, timeout: 9000, headers: { "User-Agent": UA } }, (err, response) => {
        if (err || !response) {
          result.Paramount = "<b>Paramount+:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
        } else if (response.status === 200) {
          result.Paramount = "<b>Paramount+:</b> ရရှိနိုင်သည် (Supported) 🎉";
        } else if (response.status === 302) {
          result.Paramount = "<b>Paramount+:</b> မရရှိနိုင်ပါ (Not Supported) 🚫";
        } else {
          result.Paramount = "<b>Paramount+:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
        }
        resolve();
      });
    });
  }

  function discoveryTest() {
    return new Promise((resolve) => {
      $httpClient.get({ url: DISCOVERY_TOKEN_URL, node: nodeName, timeout: 8000, headers: { "User-Agent": UA } }, (err, response, data) => {
        if (err || !response || response.status !== 200) {
          result.Discovery = "<b>Discovery+:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
          resolve();
          return;
        }
        try {
          const parsed = JSON.parse(data);
          const token = parsed.data.attributes.token;
          $httpClient.get(
            {
              url: DISCOVERY_BASE_URL,
              node: nodeName,
              timeout: 8000,
              headers: { "User-Agent": UA, Cookie: `st=${token}` },
            },
            (emsg, res, resData) => {
              if (emsg || !res || res.status !== 200) {
                result.Discovery = "<b>Discovery+:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
                resolve();
                return;
              }
              try {
                const resD = JSON.parse(resData);
                const loc = resD && resD.data && resD.data.attributes && resD.data.attributes.currentLocationTerritory;
                result.Discovery =
                  loc === "us"
                    ? "<b>Discovery+:</b> ရရှိနိုင်သည် (Supported) 🎉"
                    : "<b>Discovery+:</b> မရရှိနိုင်ပါ (Not Supported) 🚫";
              } catch (_e) {
                result.Discovery = "<b>Discovery+:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
              }
              resolve();
            }
          );
        } catch (_e) {
          result.Discovery = "<b>Discovery+:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
          resolve();
        }
      });
    });
  }

  function nfTest() {
    return new Promise((resolve) => {
      $httpClient.get({ url: NF_BASE_URL, node: nodeName, timeout: 8000, headers: { "User-Agent": UA } }, (err, response) => {
        if (err || !response) {
          result.Netflix = "<b>Netflix:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
          resolve();
          return;
        }
        if (response.status === 403) {
          result.Netflix = "<b>Netflix:</b> မရရှိနိုင်ပါ (Not Supported) 🚫";
        } else if (response.status === 404) {
          result.Netflix = "<b>Netflix:</b> Originals ဇာတ်ကားများသာ (Originals Only) ⚠️";
        } else if (response.status === 200) {
          const ourl = response.headers["X-Originating-URL"] || response.headers["X-Originating-Url"] || "";
          let region = (ourl.split("/")[3] || "us").split("-")[0];
          if (region === "title" || !region) region = "us";
          result.Netflix = `<b>Netflix:</b> အပြည့်အစုံ ရရှိ (Full Unlock) ➟ ${regionBadge(region)} 🎉`;
        } else {
          result.Netflix = "<b>Netflix:</b> စစ်ဆေးမှု မအောင်မြင်ပါ (Failed) ❗️";
        }
        resolve();
      });
    });
  }

  function renderHtml() {
    const body = [result.Dazn, result.Discovery, result.Paramount, result.Disney, result.Netflix, result.YouTube].join("</br></br>");
    return `<p style="text-align: center; font-family: -apple-system; font-size: large; font-weight: thin">--------------------------------------</br>${body}</br>--------------------------------------</br><font color=#CD5C5C><b>Node အမည် (Node)</b> ➟ ${nodeName || "-"}</font></p>`;
  }

  if (typeof $httpClient !== "undefined" && typeof $done === "function") {
    Promise.all([ytbTest(), disneyLocation(), nfTest(), daznTest(), parmTest(), discoveryTest()]).finally(() => {
      $done({ title: result.title, htmlMessage: renderHtml() });
    });
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { renderHtml, regionBadge, result };
  }
})();
