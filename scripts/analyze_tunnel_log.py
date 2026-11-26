#!/usr/bin/env python3
"""Analyze Loon macOS tunnelLog files to audit real connected URLs, domains,
rule coverage against sithu015/loon-extra, FINAL fallbacks, and DNS errors.

Default log path on macOS:
  /Library/Application Support/com.loon.Loon/tunnelLog/*.log
"""

from __future__ import annotations

import argparse
import collections
import ipaddress
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_DIR = Path("/Library/Application Support/com.loon.Loon/tunnelLog")

MATCH_RE = re.compile(
    r"\[Info\]\s+\[(\d+)\]\s+(\S+)\s+match policy:(.+?)\s+match rule:(.+?)\s*$"
)
SEARCH_RE = re.compile(
    r"Search rule by host:(\S+)\s+useragent:(.*?)\s+url:(.*?)\s+sni:(\S+)\s+type:(\d+)\s+protocol:(\d+),\s+destPort:(\d+)"
)
DNS_FAIL_SRV_RE = re.compile(
    r"(?:quic://|https://|h3://)[^\s,]+|[a-z0-9.-]+\.(?:nextdns\.io|jupitrdns\.com|surfsharkdns\.com|quad9\.net|cloudflare\.com|cloudflare-dns\.com|adguard-dns\.com|alidns\.com)"
)

MYANMAR_HINTS = (
    ".mm",
    "kbz",
    "aya",
    "wave",
    "yoma",
    "mab",
    "uab",
    "cbbank",
    "mpu",
    "myanmar",
    "irrawaddy",
    "mizzima",
    "dvb.no",
    "khitthit",
    "yktnews",
    "rfa.org",
    "momopaymm",
    "ygn.app",
)
APPLE_HINTS = ("apple", "icloud", "mzstatic", "aaplimg", "digicert.com")
AD_TRACKER_HINTS = (
    "analytics",
    "googletagmanager",
    "doubleclick",
    "adservice",
    "adbutler",
    "ads-img",
    "gvt2.com",
    "gvt3.com",
    "singular.net",
    "posthog",
    "mixpanel",
    "amplitude",
    "hotjar",
    "eppo.cloud",
    "featureassets",
    "cloudflareinsights",
    "data-event-proxy.viber.com",
    "data-events.cdn.viber.com",
    "abtest.api.viber.com",
    "statsigapi",
)
AI_DEV_HINTS = (
    "deepl.com",
    "openai",
    "chatgpt",
    "anthropic",
    "claude",
    "gemini",
    "googleapis.com",
    "antigravity",
    "immersivetranslate",
    "github",
    "npmjs",
    "pypi",
    "pythonhosted",
    "vercel",
    "supabase",
    "neon.tech",
    "context7",
    "mcp",
    "1password",
    "agilebits",
    "wabi.ai",
    "arena.ai",
    "e2llm",
    "perplexity",
    "zed.dev",
)


@dataclass
class RuleMatcher:
    domains: set[str] = field(default_factory=set)
    suffixes: set[str] = field(default_factory=set)
    keywords: list[str] = field(default_factory=list)
    cidrs: list[ipaddress._BaseNetwork] = field(default_factory=list)

    @classmethod
    def from_repo(cls, root: Path, extra_lcf: Path | None = None) -> "RuleMatcher":
        matcher = cls()
        for p in sorted((root / "plugins").glob("*.lpx")):
            matcher._load_file(p, section_filter="[rule]")
        for p in sorted((root / "rules").glob("*.list")):
            matcher._load_file(p, section_filter=None)
        if extra_lcf and extra_lcf.is_file():
            matcher._load_file(extra_lcf, section_filter="[rule]")
        return matcher

    def _load_file(self, path: Path, section_filter: str | None) -> None:
        section = ""
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line.lower()
                continue
            if section_filter and section != section_filter:
                continue
            parts = [x.strip() for x in line.split(",")]
            if len(parts) < 2:
                continue
            rtype, val = parts[0].upper(), parts[1].lower()
            if rtype == "DOMAIN":
                self.domains.add(val)
            elif rtype == "DOMAIN-SUFFIX":
                self.suffixes.add(val)
            elif rtype == "DOMAIN-KEYWORD":
                self.keywords.append(val)
            elif rtype in {"IP-CIDR", "IP-CIDR6"}:
                try:
                    self.cidrs.append(ipaddress.ip_network(val, strict=False))
                except ValueError:
                    pass

    def matches(self, host: str) -> bool:
        h = host.lower().strip("[]")
        try:
            ip = ipaddress.ip_address(h)
            return any(ip in net for net in self.cidrs)
        except ValueError:
            pass
        if h in self.domains:
            return True
        labels = h.split(".")
        for i in range(len(labels)):
            if ".".join(labels[i:]) in self.suffixes:
                return True
        return any(kw in h for kw in self.keywords)


def strip_host(target: str) -> str:
    if target.startswith("[") and "]" in target:
        return target[1 : target.index("]")]
    if ":" in target:
        head, tail = target.rsplit(":", 1)
        if tail.isdigit() and 0 <= int(tail) <= 65535 and (":" not in head or is_ip(head)):
            return head
    return target


def is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def categorize_host(host: str) -> str:
    h = host.lower()
    if any(k in h for k in MYANMAR_HINTS):
        return "Myanmar / Local"
    if any(k in h for k in APPLE_HINTS):
        return "Apple CDN & Services"
    if any(k in h for k in AD_TRACKER_HINTS):
        return "Ads & Trackers"
    if any(k in h for k in AI_DEV_HINTS):
        return "AI & Developer"
    return "Other"


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def analyze_logs(
    log_files: list[Path],
    matcher: RuleMatcher | None = None,
    redact_query: bool = False,
) -> dict:
    matched_rules: collections.Counter[str] = collections.Counter()
    matched_policies: collections.Counter[str] = collections.Counter()
    connected_hosts: collections.Counter[str] = collections.Counter()
    final_hosts: collections.Counter[str] = collections.Counter()
    urls: collections.Counter[str] = collections.Counter()
    user_agents: collections.Counter[str] = collections.Counter()
    dns_warnings: collections.Counter[str] = collections.Counter()
    dns_proto_counts: collections.Counter[str] = collections.Counter()

    for fp in log_files:
        with fp.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = MATCH_RE.search(line)
                if m:
                    _, target, policy, rule = m.groups()
                    host = strip_host(target)
                    connected_hosts[host] += 1
                    matched_policies[policy.strip()] += 1
                    matched_rules[rule.strip()] += 1
                    if rule.startswith("FINAL"):
                        final_hosts[host] += 1
                    continue

                s = SEARCH_RE.search(line)
                if s:
                    _, ua, url, *_ = s.groups()
                    if url and url != "(null)":
                        urls[redact_url(url) if redact_query else url] += 1
                    if ua and ua != "(null)":
                        user_agents[ua] += 1
                    continue

                if "[Warn]" in line and ("DOQ" in line or "DOH" in line):
                    pm = re.search(r"\[(DOQ/NGQUIC|DOH3/NGHTTP3|DOH|DNS)\]", line)
                    if pm:
                        dns_proto_counts[pm.group(1)] += 1
                    for srv in DNS_FAIL_SRV_RE.findall(line):
                        dns_warnings[srv] += 1

    uncovered_final: dict[str, list[tuple[str, int]]] = collections.defaultdict(list)
    covered_by_repo: list[tuple[str, int]] = []
    for host, count in final_hosts.most_common():
        if matcher and matcher.matches(host):
            covered_by_repo.append((host, count))
        else:
            uncovered_final[categorize_host(host)].append((host, count))

    return {
        "files": [fp.name for fp in log_files],
        "total_connections": sum(connected_hosts.values()),
        "unique_hosts": len(connected_hosts),
        "final_connections": sum(final_hosts.values()),
        "unique_final_hosts": len(final_hosts),
        "top_connected_hosts": connected_hosts.most_common(),
        "top_rules": matched_rules.most_common(),
        "top_policies": matched_policies.most_common(),
        "final_hosts": final_hosts.most_common(),
        "covered_by_repo": covered_by_repo,
        "uncovered_final": dict(uncovered_final),
        "urls": urls.most_common(),
        "user_agents": user_agents.most_common(),
        "dns_proto_counts": dns_proto_counts.most_common(),
        "dns_warnings": dns_warnings.most_common(),
    }


def resolve_log_files(log_dir: Path, file_path: Path | None, latest_only: bool) -> list[Path]:
    if file_path is not None:
        if not file_path.is_file():
            raise FileNotFoundError(f"Log file not found: {file_path}")
        return [file_path]
    if not log_dir.is_dir():
        raise FileNotFoundError(f"Log directory not found: {log_dir}")
    files = sorted(log_dir.glob("*.log"))
    if not files:
        raise FileNotFoundError(f"No .log files found in: {log_dir}")
    return [files[-1]] if latest_only else files


def format_text(result: dict, top_n: int) -> str:
    out: list[str] = []
    out.append(f"Analyzed {len(result['files'])} log file(s): {', '.join(result['files'])}")
    out.append(
        f"Connections: {result['total_connections']} | Unique hosts: {result['unique_hosts']} | "
        f"FINAL hits: {result['final_connections']} ({result['unique_final_hosts']} unique hosts)"
    )

    out.append(f"\n=== Top {top_n} Connected Hosts ===")
    for host, count in result["top_connected_hosts"][:top_n]:
        out.append(f"  {count:6d}  {host}")

    out.append(f"\n=== Top {top_n} Matched Rules ===")
    for rule, count in result["top_rules"][:top_n]:
        out.append(f"  {count:6d}  {rule}")

    if result["covered_by_repo"]:
        covered_hits = sum(c for _, c in result["covered_by_repo"])
        out.append(
            f"\n=== FINAL Hosts Already Covered by loon-extra ({len(result['covered_by_repo'])} hosts, {covered_hits} hits) ==="
        )
        for host, count in result["covered_by_repo"][:top_n]:
            out.append(f"  {count:6d}  {host}")

    out.append("\n=== Uncovered FINAL Domains by Category ===")
    for cat, items in result["uncovered_final"].items():
        dom_items = [(h, c) for h, c in items if not is_ip(h)]
        if not dom_items:
            continue
        out.append(f"[{cat}] ({len(dom_items)} domains)")
        for host, count in dom_items[:top_n]:
            out.append(f"  {count:6d}  {host}")

    if result["urls"]:
        out.append(f"\n=== Top {min(top_n, len(result['urls']))} Observed HTTP URLs ===")
        for url, count in result["urls"][:top_n]:
            out.append(f"  {count:6d}  {url}")

    if result["dns_proto_counts"]:
        out.append("\n=== DNS Transport Warnings ===")
        for proto, count in result["dns_proto_counts"]:
            out.append(f"  {count:6d}  {proto}")
        for srv, count in result["dns_warnings"][:15]:
            out.append(f"  {count:6d}  {srv}")

    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze Loon tunnelLog files for real connected URLs, rule coverage, and DNS warnings."
    )
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR, help="Path to Loon tunnelLog directory")
    parser.add_argument("--file", type=Path, default=None, help="Analyze a single .log file")
    parser.add_argument("--latest", action="store_true", help="Analyze only the most recent .log file")
    parser.add_argument("--lcf", type=Path, default=None, help="Optional local .lcf file to include in coverage check")
    parser.add_argument("--no-repo-check", action="store_true", help="Skip comparing FINAL hosts against loon-extra rules")
    parser.add_argument("--redact-query", action="store_true", help="Strip query strings from observed HTTP URLs")
    parser.add_argument("--top", type=int, default=30, help="Max items per section in text output")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")
    args = parser.parse_args()

    try:
        files = resolve_log_files(args.log_dir, args.file, args.latest)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    matcher = None if args.no_repo_check else RuleMatcher.from_repo(ROOT, extra_lcf=args.lcf)
    result = analyze_logs(files, matcher=matcher, redact_query=args.redact_query)

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_text(result, top_n=args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
