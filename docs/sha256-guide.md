# `#!source` SHA-256 Verification Guide

Loon verifies plugin download URLs using the `#!source` metadata field.

When installing a `.lpx` plugin from a URL, Loon computes the SHA-256 digest of the **exact URL string** (UTF-8, with **no trailing newline**) and checks whether it matches any comma-separated hash in `#!source`.

## Manual Calculation

```bash
printf '%s' 'https://raw.githubusercontent.com/sithu015/loon-extra/main/plugins/myanmar-essential.lpx' | shasum -a 256
```

If you also distribute via a CDN mirror (such as jsDelivr), compute its SHA-256 too:

```bash
printf '%s' 'https://cdn.jsdelivr.net/gh/sithu015/loon-extra@main/plugins/myanmar-essential.lpx' | shasum -a 256
```

Then combine both hashes with a comma in `#!source`:

```ini
#!source = <raw_sha256>, <cdn_sha256>
```

## Automated Maintenance in This Repo

Run:

```bash
python3 scripts/update_sources.py
```

And verify in CI or locally before pushing:

```bash
python3 scripts/update_sources.py --check
python3 scripts/validate_loon.py --strict
```
