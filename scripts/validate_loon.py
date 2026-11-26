#!/usr/bin/env python3
"""Static validator & security linter for Loon 3.5.1+ plugins, rulesets, and templates."""

from __future__ import annotations

import argparse
import ipaddress
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from update_sources import expected_urls, sha256_url

ROOT = Path(__file__).resolve().parent.parent
REPO_RAW_PREFIX = "https://raw.githubusercontent.com/sithu015/loon-extra/main/"
REPO_CDN_PREFIX = "https://cdn.jsdelivr.net/gh/sithu015/loon-extra@main/"

REQUIRED_PLUGIN_META = (
    "name",
    "desc",
    "author",
    "homepage",
    "icon",
    "source",
    "loon_version",
    "date",
    "type",
)

PLUGIN_ALLOWED_POLICIES = {
    "DIRECT",
    "PROXY",
    "REJECT",
    "REJECT-IMG",
    "REJECT-DICT",
    "REJECT-ARRAY",
    "REJECT-DROP",
}

KNOWN_RULE_TYPES = {
    "DOMAIN",
    "DOMAIN-SUFFIX",
    "DOMAIN-KEYWORD",
    "DOMAIN-WILDCARD",
    "IP-CIDR",
    "IP-CIDR6",
    "GEOIP",
    "IP-ASN",
    "USER-AGENT",
    "URL-REGEX",
    "PROTOCOL",
    "DEST-PORT",
    "SRC-IP",
    "IN-PORT",
    "AND",
    "OR",
    "NOT",
    "FINAL",
}

ARGUMENT_CONTROLS = {
    "input": {"string", "number"},
    "select": {"string", "number"},
    "switch": {"boolean"},
}

REWRITE_ACTIONS = {
    "url.replace",
    "redirect",
    "reject",
    "reject_img",
    "reject_dict",
    "reject_array",
    "reject_video",
    "request.header.add",
    "request.header.set",
    "request.header.del",
    "request.header.replace",
    "response.header.add",
    "response.header.set",
    "response.header.del",
    "response.header.replace",
    "request.body.replace",
    "response.body.replace",
    "request.json.add",
    "request.json.delete",
    "request.json.replace",
    "request.json.jq",
    "response.json.add",
    "response.json.delete",
    "response.json.replace",
    "response.json.jq",
    "request.body.mock",
    "response.body.mock",
}

SECRET_PATTERNS = [
    (re.compile(r"^\s*ca-p12\s*=\s*\S+", re.I), "Contains private MITM PKCS#12 certificate (`ca-p12`)"),
    (re.compile(r"^\s*ca-passphrase\s*=\s*\S+", re.I), "Contains MITM certificate passphrase (`ca-passphrase`)"),
    (
        re.compile(r"=\s*(Shadowsocks|ShadowsocksR|VMess|VLESS|Trojan|Hysteria2?|TUIC|WireGuard)\s*,", re.I),
        "Contains real proxy node credentials",
    ),
]


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, path: Path | str, line_no: int | None, msg: str) -> None:
        loc = f"{path}:{line_no}" if line_no is not None else str(path)
        self.errors.append(f"{loc}: {msg}")

    def warn(self, path: Path | str, line_no: int | None, msg: str) -> None:
        loc = f"{path}:{line_no}" if line_no is not None else str(path)
        self.warnings.append(f"{loc}: {msg}")


def _check_text_hygiene(path: Path, raw_bytes: bytes, report: ValidationReport) -> list[str]:
    if b"\r\n" in raw_bytes or b"\r" in raw_bytes:
        report.error(path, None, "CRLF or CR line endings detected; must use LF (`\\n`)")
    text = raw_bytes.decode("utf-8")
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        if line.rstrip(" \t") != line:
            report.warn(path, idx, "Trailing whitespace")
        for pat, desc in SECRET_PATTERNS:
            if pat.search(line) and not line.lstrip().startswith("#"):
                report.error(path, idx, f"SECURITY: {desc}")
    return lines


def _validate_rule_line(
    path: Path,
    line_no: int,
    line: str,
    mode: str,
    seen_rules: dict[str, int],
    report: ValidationReport,
) -> None:
    parts = [p.strip() for p in line.split(",")]
    if not parts or not parts[0]:
        report.error(path, line_no, "Empty rule entry")
        return

    rtype = parts[0].upper()
    if rtype not in KNOWN_RULE_TYPES:
        report.error(path, line_no, f"Unknown Loon rule type `{parts[0]}`")
        return

    if rtype == "FINAL":
        if mode != "lcf":
            report.error(path, line_no, "`FINAL` is only valid in main `.lcf` configs, not plugins or `.list` files")
        elif len(parts) != 2 or not parts[1]:
            report.error(path, line_no, "`FINAL` must have exactly one policy argument")
        return

    if rtype in {"AND", "OR", "NOT"}:
        return

    if rtype in {"IP-CIDR", "IP-CIDR6"}:
        if len(parts) < 2:
            report.error(path, line_no, f"`{rtype}` requires a CIDR network")
            return
        try:
            net = ipaddress.ip_network(parts[1], strict=False)
            if rtype == "IP-CIDR" and net.version != 4:
                report.error(path, line_no, f"`IP-CIDR` must be IPv4, got `{parts[1]}`")
            if rtype == "IP-CIDR6" and net.version != 6:
                report.error(path, line_no, f"`IP-CIDR6` must be IPv6, got `{parts[1]}`")
        except ValueError as exc:
            report.error(path, line_no, f"Invalid CIDR `{parts[1]}`: {exc}")

    if mode == "list":
        # Remote `.list` files must NOT embed a routing policy (bound via policy= in [Remote Rule]).
        if rtype in {"IP-CIDR", "IP-CIDR6", "IP-ASN"}:
            if len(parts) > 3 or (len(parts) == 3 and parts[2].lower() != "no-resolve"):
                report.error(path, line_no, f"`.list` `{rtype}` rule cannot specify a policy; only optional `no-resolve`")
        elif len(parts) != 2:
            report.error(path, line_no, f"`.list` rule must have format `TYPE,VALUE` without policy (got `{line}`)")
        dedup_key = f"{rtype},{parts[1].lower()}"
    else:
        if len(parts) < 2 or not parts[1]:
            report.error(path, line_no, f"Rule `{rtype}` missing matcher value")
            return
        policy = parts[2] if len(parts) >= 3 else ""
        if rtype in {"IP-CIDR", "IP-CIDR6", "IP-ASN"} and len(parts) >= 4 and parts[3].lower() == "no-resolve":
            pass
        elif rtype in {"IP-CIDR", "IP-CIDR6", "IP-ASN"} and policy.lower() == "no-resolve":
            policy = ""

        if mode == "plugin":
            if policy and policy not in PLUGIN_ALLOWED_POLICIES:
                report.error(
                    path,
                    line_no,
                    f"Plugin rule policy `{policy}` is invalid; plugins only support DIRECT, PROXY, or REJECT*",
                )
        elif mode == "lcf" and not policy:
            report.error(path, line_no, "Main `.lcf` rule must explicitly specify a policy")

        dedup_key = f"{rtype},{parts[1].lower()}"

    if dedup_key in seen_rules:
        report.error(path, line_no, f"Duplicate rule `{dedup_key}` (first seen at line {seen_rules[dedup_key]})")
    else:
        seen_rules[dedup_key] = line_no


def _parse_argument_line(path: Path, line_no: int, line: str, report: ValidationReport) -> tuple[str, str] | None:
    if "=" not in line:
        report.error(path, line_no, f"Malformed `[Argument]` entry `{line}`")
        return None
    name, rhs = [x.strip() for x in line.split("=", 1)]
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        report.error(path, line_no, f"Invalid argument identifier `{name}`")
        return None
    tokens = [t.strip() for t in rhs.split(",")]
    if not tokens:
        report.error(path, line_no, f"Missing control type for argument `{name}`")
        return None
    control = tokens[0].lower()
    if control not in ARGUMENT_CONTROLS:
        report.error(path, line_no, f"Unsupported `[Argument]` control `{control}`")
        return None

    declared_type = None
    for tok in tokens[1:]:
        if tok.startswith("type="):
            declared_type = tok.split("=", 1)[1].strip().lower()
    if declared_type is None:
        declared_type = "boolean" if control == "switch" else "string"

    if declared_type not in ARGUMENT_CONTROLS[control]:
        report.error(
            path,
            line_no,
            f"Argument `{name}` uses control `{control}` incompatible with `type={declared_type}`",
        )
        return None

    if control == "switch" and (len(tokens) < 2 or tokens[1].lower() not in {"true", "false"}):
        report.error(path, line_no, f"Switch argument `{name}` default must be `true` or `false`")
        return None

    return name, declared_type


def _validate_rewrite_v2(
    path: Path,
    line_no: int,
    line: str,
    arg_types: dict[str, str],
    report: ValidationReport,
) -> None:
    m = re.match(r"^(request|response)\s+if\s+(.+?)\s+then\s+(.+)$", line)
    if not m:
        report.warn(path, line_no, "Rewrite rule is not Loon 3.5.1+ Rewrite v2 (`<phase> if <cond> then <action>`)")
        return

    phase, cond, rhs = m.groups()
    if "${url}" not in cond:
        report.error(path, line_no, "Rewrite v2 condition must contain `${url}` guard")

    # Strip trailing `with ...` clause if present
    actions_part = re.split(r"\s+with\s+", rhs, maxsplit=1)[0]
    for action_call in [a.strip() for a in actions_part.split("|")]:
        am = re.match(r"^([a-z0-9_.]+)\s*\((.*)\)$", action_call)
        if not am:
            report.error(path, line_no, f"Malformed Rewrite v2 action `{action_call}`")
            continue
        aname, aargs = am.groups()
        if aname not in REWRITE_ACTIONS:
            report.error(path, line_no, f"Unknown Rewrite v2 action `{aname}`")
            continue
        if aname.startswith("response.") and phase == "request":
            report.error(path, line_no, f"Action `{aname}` cannot be used in `request` phase")
        if aname.startswith("request.") and phase == "response":
            report.error(path, line_no, f"Action `{aname}` cannot be used in `response` phase")
        if aname in {"reject_img", "reject_dict", "reject_array", "reject_video"}:
            if not re.fullmatch(r"\d{3}", aargs.strip()) or not (100 <= int(aargs.strip()) <= 599):
                report.error(path, line_no, f"`{aname}(...)` status code must be integer 100..599, got `{aargs}`")

    # Validate `${var}` references
    builtin_vars = {"url", "request.method", "response.status"}
    for ref in re.findall(r"\$\{([^}]+)\}", f"{cond} {rhs}"):
        if ref in builtin_vars or ref.startswith("request.header[") or ref.startswith("response.header["):
            if phase == "request" and ref.startswith("response."):
                report.error(path, line_no, f"Request-phase rule cannot reference `${{{ref}}}`")
            continue
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.\d+", ref):
            continue
        if ref not in arg_types:
            report.error(path, line_no, f"Undefined argument `${{{ref}}}` referenced in Rewrite rule")


def _check_repo_script_url(
    path: Path,
    line_no: int,
    script_url: str,
    root: Path,
    report: ValidationReport,
) -> None:
    for prefix in (REPO_RAW_PREFIX, REPO_CDN_PREFIX):
        if script_url.startswith(prefix):
            rel = script_url[len(prefix) :]
            local_script = root / rel
            if not local_script.is_file():
                report.error(path, line_no, f"`[Script]` points to missing repo file `{rel}`")
            break


def _validate_script_section(
    path: Path,
    line_no: int,
    line: str,
    arg_types: dict[str, str],
    root: Path,
    report: ValidationReport,
) -> None:
    v2 = re.match(r"^(request|response)\s+if\s+(.+?)\s+then\s+script\((.+)\)(?:\s+with\s+(.+))?$", line)
    if v2:
        phase, cond, call_args, with_clause = v2.groups()
        if "${url}" not in cond:
            report.error(path, line_no, "Script v2 condition must contain `${url}` guard")
        m_url = re.match(r'^"([^"]+)"', call_args.strip())
        if not m_url:
            report.error(path, line_no, "Script v2 `script(...)` must start with a quoted script URL")
        else:
            _check_repo_script_url(path, line_no, m_url.group(1), root, report)
        builtin_vars = {"url", "request.method", "response.status"}
        for ref in re.findall(r"\$\{([^}]+)\}", line):
            if ref in builtin_vars or ref.startswith("request.header[") or ref.startswith("response.header["):
                if phase == "request" and ref.startswith("response."):
                    report.error(path, line_no, f"Request-phase script cannot reference `${{{ref}}}`")
                continue
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.\d+", ref):
                continue
            if ref not in arg_types:
                report.error(path, line_no, f"Undefined argument `${{{ref}}}` referenced in Script rule")
        if with_clause:
            _ = with_clause
        return

    m_sp = re.search(r"script-path\s*=\s*([^,\s]+)", line)
    if m_sp:
        _check_repo_script_url(path, line_no, m_sp.group(1), root, report)
        return

    report.warn(path, line_no, "Unrecognized `[Script]` entry syntax")


def validate_plugin(path: Path, report: ValidationReport, root: Path = ROOT) -> None:
    rel = path.relative_to(root).as_posix()
    lines = _check_text_hygiene(path, path.read_bytes(), report)

    meta: dict[str, str] = {}
    section = ""
    args: dict[str, str] = {}
    seen_rules: dict[str, int] = {}

    for idx, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#!"):
            if "=" not in line:
                report.error(path, idx, f"Malformed metadata header `{line}`")
                continue
            k, v = line[2:].split("=", 1)
            meta[k.strip().lower()] = v.strip()
            continue
        if line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.lower()
            continue

        if section == "[argument]":
            parsed = _parse_argument_line(path, idx, line, report)
            if parsed:
                args[parsed[0]] = parsed[1]
        elif section == "[rule]":
            _validate_rule_line(path, idx, line, "plugin", seen_rules, report)
        elif section == "[rewrite]":
            _validate_rewrite_v2(path, idx, line, args, report)
        elif section == "[script]":
            _validate_script_section(path, idx, line, args, root, report)

    for key in REQUIRED_PLUGIN_META:
        if not meta.get(key):
            report.error(path, None, f"Missing required metadata header `#!{key}`")

    if meta.get("type") and meta["type"] not in {"normal", "parser"}:
        report.error(path, None, f"Invalid `#!type = {meta['type']}` (expected `normal` or `parser`)")

    if meta.get("date") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta["date"]):
        report.error(path, None, f"Invalid `#!date = {meta['date']}` (expected YYYY-MM-DD)")

    icon = meta.get("icon", "")
    if icon.startswith(REPO_RAW_PREFIX):
        local_icon = root / icon[len(REPO_RAW_PREFIX) :]
        if not local_icon.is_file():
            report.error(path, None, f"`#!icon` points to missing file `{local_icon.relative_to(root)}`")

    raw_url, cdn_url = expected_urls(rel)
    expected_hashes = {sha256_url(raw_url), sha256_url(cdn_url)}
    actual_hashes = {h.strip().lower() for h in meta.get("source", "").split(",") if h.strip()}
    if not expected_hashes.issubset(actual_hashes):
        report.error(
            path,
            None,
            f"`#!source` missing expected SHA-256 hash(es) for {rel}; run `python3 scripts/update_sources.py`",
        )


def validate_rules_list(path: Path, report: ValidationReport) -> None:
    lines = _check_text_hygiene(path, path.read_bytes(), report)
    seen_rules: dict[str, int] = {}
    rule_count = 0
    for idx, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rule_count += 1
        _validate_rule_line(path, idx, line, "list", seen_rules, report)
    if rule_count == 0:
        report.error(path, None, "Ruleset file contains zero active rules")


def validate_template_lcf(path: Path, report: ValidationReport) -> None:
    lines = _check_text_hygiene(path, path.read_bytes(), report)
    section = ""
    seen_rules: dict[str, int] = {}
    has_final = False
    for idx, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.lower()
            continue
        if section == "[rule]":
            if line.upper().startswith("FINAL,"):
                has_final = True
            _validate_rule_line(path, idx, line, "lcf", seen_rules, report)
    if not has_final:
        report.error(path, None, "Main config template missing `FINAL,<Policy>` fallback rule")


def run_validation(root: Path = ROOT) -> ValidationReport:
    report = ValidationReport()
    for plugin in sorted((root / "plugins").glob("*.lpx")):
        validate_plugin(plugin, report, root=root)
    for ruleset in sorted((root / "rules").glob("*.list")):
        validate_rules_list(ruleset, report)
    for template in sorted((root / "templates").glob("*.lcf")):
        validate_template_lcf(template, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Loon plugins, rulesets, and templates.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors.")
    args = parser.parse_args()

    report = run_validation(ROOT)
    for w in report.warnings:
        print(f"WARN:  {w}")
    for e in report.errors:
        print(f"ERROR: {e}", file=sys.stderr)

    failed = bool(report.errors) or (args.strict and bool(report.warnings))
    if not failed:
        print(
            f"Validation passed ({len(list((ROOT / 'plugins').glob('*.lpx')))} plugins, "
            f"{len(list((ROOT / 'rules').glob('*.list')))} rulesets, "
            f"{len(list((ROOT / 'templates').glob('*.lcf')))} templates)."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
