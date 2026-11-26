<p align="center">
  <img src="./assets/icons/squircle/myanmar-essential.png" width="108" alt="Myanmar Essential Loon Extra Icon" />
  <img src="./assets/icons/squircle/google-ai-auth-proxy.png" width="108" alt="Google AI & Auth Routing Icon" />
  <img src="./assets/icons/squircle/meta-pixel-mitm.png" width="108" alt="Meta Pixel Shield Icon" />
  <img src="./assets/icons/squircle/telemetry-shield.png" width="108" alt="Telemetry Shield Icon" />
  <img src="./assets/icons/squircle/youtube-myanmar-enhance.png" width="108" alt="YouTube Myanmar & DualSub Icon" />
  <img src="./assets/icons/squircle/node-link-check.png" width="108" alt="Node Link Check Icon" />
  <img src="./assets/icons/squircle/geo-location.png" width="108" alt="GeoLocation Icon" />
  <img src="./assets/icons/squircle/media-checker.png" width="108" alt="Media Checker Icon" />
</p>

# loon-extra

Myanmar-focused **Loon 3.5.1+** plugin suite (`.lpx`), modular remote rulesets (`.list`), sanitized configuration templates, and automated `#!source` SHA-256 verification tooling by [`sithu015`](https://github.com/sithu015).

> Designed to complement [`sithu015/loon-rules`](https://github.com/sithu015/loon-rules) (`AI.list`) and main `.lcf` setups (`ShadowShare`, `🤖 AI Services`, `🍎 Apple Services`, `🛑 AdBlock`).

---

## Plugins (`.lpx`) — Loon `3.5.1(983)+`

All plugins include verified dual `#!source` SHA-256 checksums matching both the **GitHub Raw URL** and the **jsDelivr CDN URL**.

| Plugin | Purpose | Install (Raw GitHub) | Raw / CDN Links |
| :--- | :--- | :--- | :--- |
| **Myanmar Essential**<br>`plugins/myanmar-essential.lpx` | Myanmar Banks/Payments (`DIRECT`), Telecoms & ISPs (`DIRECT`), `.mm` Gov/Edu/Local (`DIRECT`), Blocked Independent Media (`PROXY`), Complementary Ads/Trackers (`REJECT`), Apple Fallback (`DIRECT`), plus optional Meta Pixel Rewrite v2 toggle | [One-Click Install](loon://import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fsithu015%2Floon-extra%2Fmain%2Fplugins%2Fmyanmar-essential.lpx) | [Raw](https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/myanmar-essential.lpx) · [jsDelivr](https://cdn.jsdelivr.net/gh/sithu015/loon-extra@main/plugins/myanmar-essential.lpx) |
| **Google AI & Auth Routing**<br>`plugins/google-ai-auth-proxy.lpx` | Routes log-observed Google Auth/Capability endpoints (`securitydomain-pa`, `reach-pa`, `accountcapabilities-pa`) plus Gemini & Antigravity via selectable `PROXY` group | [One-Click Install](loon://import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fsithu015%2Floon-extra%2Fmain%2Fplugins%2Fgoogle-ai-auth-proxy.lpx) | [Raw](https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/google-ai-auth-proxy.lpx) · [jsDelivr](https://cdn.jsdelivr.net/gh/sithu015/loon-extra@main/plugins/google-ai-auth-proxy.lpx) |
| **Meta Pixel Shield (MitM)**<br>`plugins/meta-pixel-mitm.lpx` | Dedicated MitM plugin (`hostname = www.facebook.com, facebook.com`) for blocking `facebook.com/tr` and `privacy_sandbox/pixel/` without risking cert-pinning issues in `myanmar-essential.lpx` | [One-Click Install](loon://import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fsithu015%2Floon-extra%2Fmain%2Fplugins%2Fmeta-pixel-mitm.lpx) | [Raw](https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/meta-pixel-mitm.lpx) · [jsDelivr](https://cdn.jsdelivr.net/gh/sithu015/loon-extra@main/plugins/meta-pixel-mitm.lpx) |
| **Telemetry & Analytics Shield**<br>`plugins/telemetry-shield.lpx` | Optional cross-app attribution, session replay, and OS telemetry blocker (keeps developer tools like `sentry.io` unblocked) | [One-Click Install](loon://import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fsithu015%2Floon-extra%2Fmain%2Fplugins%2Ftelemetry-shield.lpx) | [Raw](https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/telemetry-shield.lpx) · [jsDelivr](https://cdn.jsdelivr.net/gh/sithu015/loon-extra@main/plugins/telemetry-shield.lpx) |
| **YouTube Myanmar & DualSub**<br>`plugins/youtube-myanmar-enhance.lpx` | Unified YouTube AdBlock, PiP & Background Play, Burmese (`my`) subtitle unlock/injection, and Dual Subtitles (`Original + Myanmar`) across `srv3`/`asr`, `json3`, & `WebVTT` with Google Translate fallback | [One-Click Install](loon://import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fsithu015%2Floon-extra%2Fmain%2Fplugins%2Fyoutube-myanmar-enhance.lpx) | [Raw](https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/youtube-myanmar-enhance.lpx) · [jsDelivr](https://cdn.jsdelivr.net/gh/sithu015/loon-extra@main/plugins/youtube-myanmar-enhance.lpx) |
| **Node Link Check**<br>`plugins/node-link-check.lpx` | Myanmar/English proxy entry-to-exit link & relay checker | [One-Click Install](loon://import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fsithu015%2Floon-extra%2Fmain%2Fplugins%2Fnode-link-check.lpx) | [Raw](https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/node-link-check.lpx) · [jsDelivr](https://cdn.jsdelivr.net/gh/sithu015/loon-extra@main/plugins/node-link-check.lpx) |
| **GeoLocation**<br>`plugins/geo-location.lpx` | Myanmar/English node exit IP, country, city, ISP & ASN inspector | [One-Click Install](loon://import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fsithu015%2Floon-extra%2Fmain%2Fplugins%2Fgeo-location.lpx) | [Raw](https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/geo-location.lpx) · [jsDelivr](https://cdn.jsdelivr.net/gh/sithu015/loon-extra@main/plugins/geo-location.lpx) |
| **Media Checker**<br>`plugins/media-checker.lpx` | Myanmar/English streaming unlock checker (YouTube Premium, Netflix, Disney+, Paramount+, Discovery+, DAZN) | [One-Click Install](loon://import?plugin=https%3A%2F%2Fraw.githubusercontent.com%2Fsithu015%2Floon-extra%2Fmain%2Fplugins%2Fmedia-checker.lpx) | [Raw](https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/media-checker.lpx) · [jsDelivr](https://cdn.jsdelivr.net/gh/sithu015/loon-extra@main/plugins/media-checker.lpx) |

---

## Modular Remote Rulesets (`.list`)

Because Loon plugins only support `DIRECT`, `PROXY`, and `REJECT*`, standalone `.list` rulesets are also provided under `rules/` if you want to bind each category directly to custom `[Proxy Group]` entries in `[Remote Rule]` (e.g., `🛑 AdBlock`, `⚡ US Auto`, `ShadowShare`).

| Ruleset | Recommended Policy | Raw URL |
| :--- | :--- | :--- |
| `rules/myanmar-direct.list` | `DIRECT` | `https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/myanmar-direct.list` |
| `rules/myanmar-media-proxy.list` | `ShadowShare` / `⚡ Auto (All)` | `https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/myanmar-media-proxy.list` |
| `rules/adblock-extra.list` | `🛑 AdBlock` | `https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/adblock-extra.list` |
| `rules/apple-fallback.list` | `DIRECT` / `🍎 Apple Services` | `https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/apple-fallback.list` |
| `rules/google-ai-auth.list` | `⚡ US Auto` / `🤖 AI Services` | `https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/google-ai-auth.list` |
| `rules/ai-extra.list` | `🤖 AI Services` | `https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/ai-extra.list` |
| `rules/telemetry-shield.list` | `🛑 AdBlock` | `https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/telemetry-shield.list` |

---

## `#!source` SHA-256 Checksums

Verified with `printf '%s' '<url>' | shasum -a 256`:

| File | Raw GitHub SHA-256 | jsDelivr CDN SHA-256 |
| :--- | :--- | :--- |
| `plugins/myanmar-essential.lpx` | `2816d0e79e4efc889eb6bb7370a73e174e9295c59eba5c0300cd81e9e2c01194` | `a54424d3f1dd018fe5e1ede23dbf87ec9adc835837c3d36303bbd4d4de4a9bd9` |
| `plugins/google-ai-auth-proxy.lpx` | `4df587ff9d7493b735f0776e6a1f756ce63b10c0121361b65c3309308fd1ea50` | `19eceb8771ecd070e17c63509296f92b805147383e1a803af60a61b8560c54c1` |
| `plugins/meta-pixel-mitm.lpx` | `146d9e0fe8094d4fff8c38815f1f8da9e712c9f094face3d7c54aab5e88a67a5` | `548c6a9234035413550081604d08aab9fb7b447c36480f075635f474b2b8de32` |
| `plugins/telemetry-shield.lpx` | `593553bc6e23c988bb1d064ef89a9f01d1b32fdac5d256ab69c9940528e865dd` | `dbf2179bce8ee57adb41bb1cdf04eddf4ce72e9053fa8e868089b4a569b240b1` |
| `plugins/youtube-myanmar-enhance.lpx` | `2e2fd9acba621fcdb6d3dd116499c6aff1c80619bcd347040fa1acc8f5899ed7` | `4a65ff80413c85e866d2a98a3a63e8e36da77bd010a1a2b8cb0b3317d89514a0` |
| `plugins/node-link-check.lpx` | `f84a7be98c48d06a811c069b287aaf0bea904d4f1f595449961f648b89fb7940` | `da24cdad21be5a67a6e5c15f9fc1c642066dfe7afbeee000c729bd293f25d8d4` |
| `plugins/geo-location.lpx` | `73581bd9e25443865e54324d201c7ef52e124217df0b4403f9a1d78ed144b16b` | `237da941f9e9a8fbd610aa024711c21552a1099c617b217ba720ec25d348c40d` |
| `plugins/media-checker.lpx` | `0a662fd484a727921113c91ff3efc37e674bd8985575ee180923104a64dff549` | `37b96102c7424466693c5b1932245f6785ff75a854d69b18187c780199d60959` |

---

## Documentation & Templates

- **Icon Design System (`G²` Squircle & Liquid Glass SVGs)**: [`docs/icon-design-system.md`](./docs/icon-design-system.md)
- **Integration Guide for `FinalV1_cleaned.lcf`**: [`docs/finalv1-integration.md`](./docs/finalv1-integration.md)
- **SHA-256 `#!source` Guide**: [`docs/sha256-guide.md`](./docs/sha256-guide.md)
- **Sanitized Base Config Template**: [`templates/loon-base.example.lcf`](./templates/loon-base.example.lcf)

---

## မြန်မာဘာသာဖြင့် အကျဉ်းချုပ် (Myanmar Quick Start)

1. Loon App (`3.5.1+`) ရှိ **Plugins** မှတစ်ဆင့် အထက်ပါ **One-Click Install** လင့်ခ် သို့မဟုတ် Raw/jsDelivr URL ကို ထည့်သွင်းပါ။
2. **Myanmar Essential** plugin ထဲတွင် `PROXY` ကို မိမိအသုံးပြုလိုသည့် Proxy Group (`ShadowShare` သို့မဟုတ် `🇸🇬 Singapore`) သို့ ချိတ်ဆက်ပါ။
3. မြန်မာဘဏ်များ၊ Wallet App များ (`KBZPay`, `WavePay`, `AYA Pay`, `CB Pay`, `uabpay`, `Yoma` စသည်) နှင့် `.mm` ဝန်ဆောင်မှုများသည် `DIRECT` ဖြင့် တိုက်ရိုက်အလုပ်လုပ်မည်ဖြစ်ပြီး ပြည်တွင်းပိတ်ဆို့ခံ သတင်းမီဒီယာများသည် `PROXY` မှတစ်ဆင့် ဝင်ရောက်နိုင်မည်ဖြစ်သည်။
4. `Block Meta Pixel (MitM)` သည် HTTPS MitM လိုအပ်သောကြောင့် မူလတွင် `false` ထားရှိထားပါသည်။ လိုအပ်မှသာ ဖွင့်ပါ (သို့မဟုတ် `meta-pixel-mitm.lpx` ကို သီးခြားဖွင့်ပါ)။
5. **YouTube Myanmar & DualSub** ကို အသုံးပြုရန် macOS/iOS တွင် Loon `[MITM]` CA certificate ကို Install & Full Trust ပြုလုပ်ထားရပါမည်။ Plugin Settings ထဲတွင် `Subtitle Display` (`dual_orig_top` / `dual_my_top` / `my_only`) နှင့် `Translation Engine` (`hybrid` / `google_only` / `youtube_only`) တို့ကို တိုက်ရိုက်ရွေးချယ်နိုင်ပါသည်။

---

## Development, Log Auditing & Validation

```bash
# Audit real connected domains/URLs and DNS errors from macOS Loon tunnelLog
python3 scripts/analyze_tunnel_log.py --latest --redact-query

# Re-generate icons (optional)
python3 scripts/generate_icons.py

# Update #!source SHA-256 hashes after editing plugin filenames/URLs
python3 scripts/update_sources.py

# Run strict linter, secret scanner, hash verification, and unit tests
python3 scripts/update_sources.py --check
python3 scripts/validate_loon.py --strict
python3 -m unittest discover -s tests -v
```
