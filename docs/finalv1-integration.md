# Integrating `loon-extra` with `FinalV1_cleaned.lcf`

This guide explains how `sithu015/loon-extra` works alongside your local `FinalV1_cleaned.lcf` configuration and lists specific cleanup recommendations observed in `FinalV1_cleaned.lcf`.

## 1. Quick Integration (`[Plugin]` Section)

Add the following entries under `[Plugin]` in your local `.lcf` configuration:

```ini
[Plugin]
https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/myanmar-essential.lpx, enabled=true
https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/google-ai-auth-proxy.lpx, enabled=true
https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/telemetry-shield.lpx, enabled=false
https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/meta-pixel-mitm.lpx, enabled=false
https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/youtube-myanmar-enhance.lpx, enabled=true
```

In Loon's plugin settings UI:
- Map `Myanmar Essential`'s `PROXY` policy to `ShadowShare` (or `🇸🇬 Singapore` / `⚡ Auto (All)`).
- Map `Google AI & Auth Routing`'s `PROXY` policy to `⚡ US Auto` (or `🤖 AI Services`).

## 2. Optional `[Remote Rule]` Mode (Fine-Grained Policy Mapping)

Because Loon plugins only support `DIRECT`, `PROXY`, and `REJECT*`, if you prefer routing each category directly to specific groups in `FinalV1_cleaned.lcf` (`🛑 AdBlock`, `🍎 Apple Services`, `⚡ US Auto`, `ShadowShare`), use `[Remote Rule]` instead of plugins:

```ini
[Remote Rule]
https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/apple-fallback.list, policy=DIRECT, tag=Apple Fallback, enabled=true
https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/myanmar-direct.list, policy=DIRECT, tag=Myanmar Direct, enabled=true
https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/myanmar-media-proxy.list, policy=ShadowShare, tag=Myanmar Media, enabled=true
https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/adblock-extra.list, policy=🛑 AdBlock, tag=AdBlock Extra, enabled=true
https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/google-ai-auth.list, policy=⚡ US Auto, tag=Google AI & Auth, enabled=true
https://raw.githubusercontent.com/sithu015/loon-extra/main/rules/ai-extra.list, policy=🤖 AI Services, tag=AI Extra, enabled=true
```

## 3. Rule Precedence in Loon 3.5.1+

Loon evaluates rules in strict source priority:
1. **Local `[Rule]`** (in your `.lcf` file — highest priority)
2. **`[Plugin]` `[Rule]`** (evaluated in order of `[Plugin]` list)
3. **`[Remote Rule]`** (subscription `.list` files)
4. **`FINAL`** fallback rule (`ShadowShare`)

> **Why `c.apple.news` and `cdn.apple-mapkit.com` work via plugin:** `FinalV1_cleaned.lcf` only matches `apple.com`, `icloud.com`, etc. (`apple.news` and `apple-mapkit.com` are distinct root domains), so they cleanly pass through local rules and match `myanmar-essential.lpx`.

## 4. Recommended Cleanups Observed in `FinalV1_cleaned.lcf`

If you want to tidy up your local `FinalV1_cleaned.lcf` (do **not** commit your local `.lcf` with proxy nodes or `ca-p12` to GitHub!):

1. **Deduplicate `doh-server` (line 11)**: `https://dns.alidns.com/dns-query` appears twice in `doh-server`.
2. **Remove duplicate Google API rules (lines 674–679)**:
   - `reach-pa.googleapis.com` appears 4 times
   - `securitydomain-pa.googleapis.com` appears 2 times
   - These can also be replaced entirely by enabling `google-ai-auth-proxy.lpx` (or `rules/google-ai-auth.list`).
3. **Review accidental log-captured `DIRECT` rules (lines 671–692)**:
   - Duplicate `www.rm98002.com` (3x) and `www.f61pgb.com` (2x)
   - Ad/tracker/gambling domains (`socket.4754848.com`, `gs-ga.praise777.com`, `cdn.praise777.com`, `dlray.3yjt.com`, `socket.18374938.com`, `www.vip7r.com`)
   - `api.github.com,DIRECT` & `cafe.github.com,DIRECT` (note: local `[Rule]` overrides `DOMAIN-SUFFIX,github.com,🔍 Search & Tech`; remove if you want GitHub API routed through `🔍 Search & Tech`).
4. **Update `[MITM]` placeholder**:
   - Currently `hostname = *.example.com,-excluded.example.com` and `skip-server-cert-verify = true`.
   - Keep `skip-server-cert-verify = false` in production unless debugging a specific dev host.
   - Keep `facebook.com` out of `[MITM]` unless you intentionally enable `meta-pixel-mitm.lpx` (or `blockMetaPixel = true`), because MitM on Facebook/Messenger can interfere with certificate pinning.
5. **Trim unreachable DoQ / DoH servers observed in `tunnelLog`**:
   - Live testing and `tunnelLog` inspection showed repeated failures on `dns.jupitrdns.com`, `dns.surfsharkdns.com`, `ibksturm.synology.me`, `https://dns.alidns.com/dns-query`, `https://doh.pub/dns-query`, `https://dns.mullvad.net/dns-query`, `https://194.242.2.2/dns-query`, and `https://dns.tatacommunications.com/dns-query`.
   - Keeping only live-verified UDP, DoH (`1.1.1.1`, `1.0.0.1`, `dns.google`, `8.8.8.8`, `8.8.4.4`, `dns.adguard-dns.com`, `doh.opendns.com`, `freedns.controld.com/p0`, `doh.sb`, `dns.quad9.net`), and clean DoQ endpoints gives strong redundancy without DNS handshake timeouts.
6. **Prevent Google / Gemini & Cloudflare Turnstile Split-IP Mismatches**:
   - **Google / Gemini (`IP1 ≠ IP2`)**: Route `google.com`, `google.com.sg`, `gstatic.com`, `googleapis.com`, `googleusercontent.com` under `🤖 AI Services` (`🇺🇸 United States`) alongside `gemini.google.com` so Google web and auth calls always share one unified exit IP.
   - **Cloudflare Turnstile (`challenges.cloudflare.com` stuck on "Verifying...")**: Keep `🔍 Search & Tech` (which contains `cloudflare.com`) aligned with `ShadowShare` (`⚡ Auto (All)`) so `challenges.cloudflare.com` exits from the exact same node IP as general websites hitting `FINAL,ShadowShare` (such as `coolors.co`).
7. **Prevent `"User location is not supported for the API use."` (`FAILED_PRECONDITION`) Leaks**:
   - **Close stale pre-VPN `en0` sockets**: If an IDE or background helper (`language_server`) starts while Loon TUN is stopped or restarting, existing persistent TCP connections on `en0` bypass `utun` and keep sending direct local-ISP traffic even after Loon reconnects; restart the client after Loon connects (and enable Loon System Proxy).
   - **Exclude mislabeled non-US / mixed-GeoIP nodes from AI groups**: Verify proxy exit countries (e.g., `ipinfo.io` + Cloudflare `/cdn-cgi/trace`) rather than trusting subscription labels (`🇺🇸`), keep `🤖 AI Services` on verified native-US endpoints (`⚡ US AI (Clean)`), set `udp-fallback-mode = REJECT`, and include `cloudaicompanion.googleapis.com`, `goog`, `withgoogle.com`, and `google.dev` under `🤖 AI Services`.
8. **YouTube Burmese Dual Subtitles (`youtube-myanmar-enhance.lpx`)**:
   - Do not enable `youtube.plugin` or `DualSubs.YouTube.plugin` alongside `youtube-myanmar-enhance.lpx`, as multiple `http-response` scripts on `/youtubei/v1/player` conflict.
   - Ensure Loon's `[MITM]` CA certificate is installed and trusted on macOS/iOS so YouTube player & `/api/timedtext` rewrites run cleanly (`-redirector*.googlevideo.com` stays excluded from MITM so video streams pass through without decryption overhead).

## 5. Auditing Live Traffic with `tunnelLog`

On macOS, Loon records real connection matches, HTTP URLs, and DNS warnings under `/Library/Application Support/com.loon.Loon/tunnelLog/`. You can audit live traffic coverage against this repository anytime:

```bash
python3 scripts/analyze_tunnel_log.py --latest --redact-query
```

## 6. Security Reminder

Never push your local `.lcf` file containing:
- `[Proxy]` Shadowsocks / VMess / VLESS server passwords or UUIDs
- `[MITM]` `ca-p12` private key blob or `ca-passphrase`

Use `templates/loon-base.example.lcf` as your public reference base instead.
