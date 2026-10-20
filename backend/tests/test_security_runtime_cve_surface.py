"""Static/runtime contracts for removing known-unneeded CVE trigger CLIs.

This does not waive scanner findings. The Trivy policy remains authoritative; these
checks only prove that reviewed command-line trigger surfaces are absent from the
production security image definition and startup probe.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "backend/Dockerfile.security"
PROBE_PATH = ROOT / "backend/scripts/security_profile_probe.py"


def load_probe():
    spec = importlib.util.spec_from_file_location("security_runtime_cve_probe", PROBE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROBE = load_probe()
CVE_TRIGGER_TOOLS = {
    "gzip", "gunzip", "zcat", "infocmp", "nsenter", "sqlite3",
    "systemd-homed", "getfacl", "setfacl", "pcre2grep", "grep", "egrep", "fgrep",
}
SHELL_TOOLS = {"sh", "dash", "bash"}


class RuntimeCveSurfaceTests(unittest.TestCase):
    def test_reviewed_cve_trigger_clis_and_shells_are_fail_closed(self):
        blocked = set(PROBE.DISALLOWED_RUNTIME_TOOLS)
        self.assertTrue(CVE_TRIGGER_TOOLS.issubset(blocked))
        self.assertTrue(SHELL_TOOLS.issubset(blocked))
        self.assertIn("perl", PROBE.DISALLOWED_RUNTIME_PREFIXES)

    def test_dockerfile_removes_exact_tools_shells_and_all_perl_entrypoints(self):
        text = DOCKERFILE.read_text()
        match = re.search(r"for tool in (.*?); do", text, flags=re.S)
        self.assertIsNotNone(match)
        docker_tools = set(match.group(1).replace("\\\n", " ").split())
        self.assertTrue((CVE_TRIGGER_TOOLS | SHELL_TOOLS).issubset(docker_tools))
        self.assertIn("-name 'perl*'", text)
        self.assertIn("-delete", text)
        self.assertIn("Keep /var/lib/dpkg metadata", text)
        self.assertNotIn("rm -rf /var/lib/dpkg", text)
        self.assertIn('CMD ["python", "scripts/security_runtime_launcher.py", "backend"]', text)

    def test_probe_rejects_versioned_perl_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            executable = folder / "perl5.40.1"
            executable.write_text("fixture")
            executable.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError, "DISALLOWED_RUNTIME_TOOL_PRESENT"):
                PROBE.runtime_surface([folder])

    def test_probe_rejects_exact_trigger_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            executable = folder / "infocmp"
            executable.write_text("fixture")
            executable.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError, "DISALLOWED_RUNTIME_TOOL_PRESENT"):
                PROBE.runtime_surface([folder])

    def test_probe_rejects_shell_reintroduction(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            executable = folder / "sh"
            executable.write_text("fixture")
            executable.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError, "DISALLOWED_RUNTIME_TOOL_PRESENT"):
                PROBE.runtime_surface([folder])

    def test_scanner_policy_is_not_relaxed_by_surface_reduction(self):
        workflow = (ROOT / ".github/workflows/security-image-vulnerability.yml").read_text()
        self.assertIn("--ignore-unfixed=false", workflow)
        self.assertIn("--severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL", workflow)
        self.assertIn("--ignorefile /dev/null", workflow)
        self.assertNotIn("continue-on-error", workflow)


if __name__ == "__main__":
    unittest.main()
