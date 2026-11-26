"""Tests for Loon plugin, ruleset, and template validation."""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import update_sources  # noqa: E402
import validate_loon  # noqa: E402


class LoonExtraValidationTests(unittest.TestCase):
    def test_repo_files_pass_strict_validation(self) -> None:
        report = validate_loon.run_validation(ROOT)
        self.assertEqual(report.errors, [], f"Unexpected errors: {report.errors}")
        self.assertEqual(report.warnings, [], f"Unexpected warnings: {report.warnings}")

    def test_plugin_source_hashes_match_expected_urls(self) -> None:
        for plugin in sorted((ROOT / "plugins").glob("*.lpx")):
            rel = plugin.relative_to(ROOT).as_posix()
            changed, expected = update_sources.process_plugin(plugin, check_only=True, date_str=None)
            self.assertFalse(changed, f"{rel} has stale #!source (expected {expected})")
            raw_url, cdn_url = update_sources.expected_urls(rel)
            raw_hash = hashlib.sha256(raw_url.encode("utf-8")).hexdigest()
            cdn_hash = hashlib.sha256(cdn_url.encode("utf-8")).hexdigest()
            self.assertIn(raw_hash, expected)
            self.assertIn(cdn_hash, expected)

    def _copy_plugin_workspace(self, tmp_root: Path) -> None:
        shutil.copytree(ROOT / "plugins", tmp_root / "plugins")
        shutil.copytree(ROOT / "assets", tmp_root / "assets")
        shutil.copy2(ROOT / "icon.png", tmp_root / "icon.png")
        (tmp_root / "rules").mkdir()
        (tmp_root / "templates").mkdir()

    def test_rejects_custom_policy_in_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            self._copy_plugin_workspace(tmp_root)
            p = tmp_root / "plugins" / "myanmar-essential.lpx"
            p.write_text(
                p.read_text(encoding="utf-8") + "\n[Rule]\nDOMAIN,example.com,ShadowShare\n",
                encoding="utf-8",
            )
            report = validate_loon.run_validation(tmp_root)
            self.assertEqual(len(report.errors), 1, report.errors)
            self.assertIn("plugins only support DIRECT, PROXY, or REJECT*", report.errors[0])

    def test_rejects_secret_ca_p12_or_proxy_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "plugins").mkdir()
            (tmp_root / "rules").mkdir()
            (tmp_root / "templates").mkdir()
            t = tmp_root / "templates" / "leak.lcf"
            t.write_text(
                "[Proxy]\nNode = Shadowsocks,1.2.3.4,8388,aes-256-gcm,\"secret\"\n"
                "[Rule]\nFINAL,DIRECT\n[MITM]\nca-p12 = MIIJ\n",
                encoding="utf-8",
            )
            report = validate_loon.run_validation(tmp_root)
            self.assertTrue(any("ca-p12" in e for e in report.errors))
            self.assertTrue(any("proxy node credentials" in e for e in report.errors))

    def test_rejects_rewrite_v2_without_url_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            self._copy_plugin_workspace(tmp_root)
            p = tmp_root / "plugins" / "myanmar-essential.lpx"
            p.write_text(
                p.read_text(encoding="utf-8") + "\n[Rewrite]\nrequest if ${blockMetaPixel} == true then reject_img(200)\n",
                encoding="utf-8",
            )
            report = validate_loon.run_validation(tmp_root)
            self.assertEqual(len(report.errors), 1, report.errors)
            self.assertIn("${url}", report.errors[0])

    def test_rejects_policy_inside_list_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            (tmp_root / "plugins").mkdir()
            (tmp_root / "rules").mkdir()
            (tmp_root / "templates").mkdir()
            r = tmp_root / "rules" / "bad.list"
            r.write_text("DOMAIN-SUFFIX,example.com,DIRECT\n", encoding="utf-8")
            report = validate_loon.run_validation(tmp_root)
            self.assertTrue(any("without policy" in e for e in report.errors), report.errors)


if __name__ == "__main__":
    unittest.main()
