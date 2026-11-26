"""Tests for Loon tunnelLog analyzer."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_tunnel_log  # noqa: E402


SAMPLE_LOG = """\
2026/11/26 05:36:39:133  [Debug]  [17720] Search rule by host:gateway.icloud.com useragent:(null) url:(null) sni:gateway.icloud.com type:0 protocol:3, destPort:443
2026/11/26 05:36:39:135  [Info]  [17720] gateway.icloud.com:443 match policy:DIRECT match rule:DOMAIN-SUFFIX,icloud.com,🍎 Apple Services
2026/11/26 05:36:39:470  [Debug]  [17721] Search rule by host:www.kbzbank.com useragent:(null) url:(null) sni:www.kbzbank.com type:0 protocol:3, destPort:443
2026/11/26 05:36:39:476  [Info]  [17721] www.kbzbank.com:443 match policy:🇸🇬 Singapore 12 match rule:FINAL,ShadowShare
2026/11/26 05:36:40:100  [Debug]  [17722] Search rule by host:example.com useragent:Mozilla/5.0 url:http://example.com/path?token=secret sni:(null) type:0 protocol:1, destPort:80
2026/11/26 05:36:40:102  [Info]  [17722] example.com:80 match policy:🇸🇬 Singapore 12 match rule:FINAL,ShadowShare
2026/11/26 05:36:40:200  [Info]  [17723] 2620:149:af6::10:443 match policy:🇸🇬 Singapore 12 match rule:FINAL,ShadowShare
2026/11/26 05:36:41:000  [Warn]  [DOQ/NGQUIC] Connect quic://dns.jupitrdns.com:853 failed: Error Domain=com.loon.ngquic Code=5
"""


class AnalyzeTunnelLogTests(unittest.TestCase):
    def test_parses_hosts_urls_coverage_and_dns_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "2026-11-26 05:36:39.log"
            log_file.write_text(SAMPLE_LOG, encoding="utf-8")

            matcher = analyze_tunnel_log.RuleMatcher.from_repo(ROOT)
            result = analyze_tunnel_log.analyze_logs([log_file], matcher=matcher, redact_query=True)

            self.assertEqual(result["total_connections"], 4)
            self.assertEqual(result["final_connections"], 3)
            covered_hosts = dict(result["covered_by_repo"])
            self.assertIn("www.kbzbank.com", covered_hosts)
            self.assertIn("2620:149:af6::10", covered_hosts)
            self.assertEqual(result["urls"], [("http://example.com/path", 1)])
            self.assertEqual(result["dns_proto_counts"], [("DOQ/NGQUIC", 1)])
            self.assertIn(("quic://dns.jupitrdns.com:853", 1), result["dns_warnings"])


if __name__ == "__main__":
    unittest.main()
