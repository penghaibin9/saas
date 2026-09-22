from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/security-image-vulnerability.yml'
DOCKERFILE = ROOT / 'backend/Dockerfile.security'
PROBE_PATH = ROOT / 'backend/scripts/security_profile_probe.py'
EXPECTED_RUNTIME_SCRIPTS = {
    'check_crypto_compatibility.py',
    'check_production_file_scan.py',
    'check_production_redis.py',
    'cleanup_shared_import_batches.py',
    'run_scheduled_jobs.py',
    'security_profile_probe.py',
    'security_runtime_launcher.py',
}


def load_probe():
    spec = importlib.util.spec_from_file_location('security_profile_surface_probe', PROBE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PROBE = load_probe()


class SecurityProductionImageSurfaceContracts(unittest.TestCase):
    def test_production_scan_uses_reviewed_ubi_python_and_micro_runtime(self):
        text = WORKFLOW.read_text()
        self.assertIn('export PYTHON_BASE_TAG="registry.access.redhat.com/ubi9/python-312-minimal:9.8"', text)
        self.assertIn('export RUNTIME_BASE_TAG="registry.access.redhat.com/ubi9/ubi-micro:9.8"', text)
        self.assertNotIn('python:3.12-slim-bookworm', text)
        self.assertNotIn('python:3.12-alpine', text)

    def test_both_bases_are_resolved_to_digest_before_build(self):
        text = WORKFLOW.read_text()
        python_pull = text.index('docker pull "$PYTHON_BASE_TAG"')
        runtime_pull = text.index('docker pull "$RUNTIME_BASE_TAG"')
        python_inspect = text.index('export PYTHON_BASE_DIGEST=')
        runtime_inspect = text.index('export RUNTIME_BASE_DIGEST=')
        build = text.index('docker build -f backend/Dockerfile.security')
        self.assertLess(python_pull, python_inspect)
        self.assertLess(runtime_pull, runtime_inspect)
        self.assertLess(python_inspect, build)
        self.assertLess(runtime_inspect, build)
        self.assertIn('--build-arg "SECURITY_PYTHON_BASE_IMAGE=$PYTHON_BASE_DIGEST"', text)
        self.assertIn('--build-arg "RUNTIME_BASE_IMAGE=$RUNTIME_BASE_DIGEST"', text)
        self.assertIn("'runtimeBaseDigest': os.environ['RUNTIME_BASE_DIGEST']", text)

    def test_runtime_is_built_from_micro_installroot_not_python_base(self):
        text = DOCKERFILE.read_text()
        self.assertIn('FROM ${RUNTIME_BASE_IMAGE} AS micro-root', text)
        self.assertIn('dnf install', text)
        self.assertIn('--installroot "$INSTALL_ROOT"', text)
        self.assertIn('python3.12 ca-certificates tzdata', text)
        self.assertIn('dnf clean all --installroot "$INSTALL_ROOT"', text)
        self.assertIn('FROM scratch', text)
        self.assertIn('COPY --from=rootfs /runtime-root/ /', text)
        self.assertNotIn('rpm -e --nodeps', text)
        self.assertNotIn('rm -rf /usr/lib/sysimage/rpm', text)
        self.assertIn('unexpected runtime package: $pkg', text)
        self.assertIn('curl-minimal libcurl-minimal', text)

    def test_runtime_does_not_copy_entire_backend_scripts_tree(self):
        text = DOCKERFILE.read_text()
        self.assertNotIn('COPY backend/scripts ./scripts', text)
        copy_block = text[text.index('RUN mkdir -p /runtime-root/app/backend/scripts'):text.index('COPY shared /runtime-root/app/shared')]
        copied = set(re.findall(r'backend/scripts/([A-Za-z0-9_.-]+\.py)', copy_block))
        self.assertEqual(copied, EXPECTED_RUNTIME_SCRIPTS)
        self.assertNotIn('seed_demo_data.py', copy_block)
        self.assertNotIn('bootstrap_', copy_block)

    def test_scheduler_dependency_is_in_runtime_allowlist(self):
        scheduler = (ROOT / 'backend/scripts/run_scheduled_jobs.py').read_text()
        self.assertIn('from scripts.cleanup_shared_import_batches import run', scheduler)
        self.assertIn('cleanup_shared_import_batches.py', EXPECTED_RUNTIME_SCRIPTS)

    def test_setuid_and_setgid_bits_are_stripped_before_nonroot_user(self):
        text = DOCKERFILE.read_text()
        find = 'find "$INSTALL_ROOT/usr/bin" "$INSTALL_ROOT/usr/sbin" "$INSTALL_ROOT/bin" "$INSTALL_ROOT/sbin"'
        self.assertIn(find, text)
        self.assertIn('-perm -4000 -o -perm -2000', text)
        self.assertIn('-exec chmod a-s {} +', text)
        self.assertLess(text.index(find), text.index('USER 10001:10001'))

    def test_final_image_keeps_native_inventory_but_removes_admin_tools(self):
        text = DOCKERFILE.read_text()
        self.assertNotIn('rm -rf /var/lib/dpkg', text)
        self.assertNotIn('rm -rf /usr/lib/sysimage/rpm', text)
        match = re.search(r'for tool in (.*?); do', text, flags=re.S)
        self.assertIsNotNone(match)
        docker_tools = set(match.group(1).replace('\\\n', ' ').split())
        self.assertEqual(docker_tools, set(PROBE.DISALLOWED_RUNTIME_TOOLS))
        for required in ('python', 'uvicorn', 'alembic'):
            self.assertNotIn(required, docker_tools)
        for tool in ('sh', 'dash', 'bash', 'microdnf', 'rpm', 'apt-get', 'dpkg'):
            self.assertIn(tool, docker_tools)

    def test_native_runtime_surface_check_is_mandatory_before_scan(self):
        text = WORKFLOW.read_text()
        surface = text.index('- name: Verify shell-free runtime and production entrypoint families')
        scan = text.index('- name: Scan OS and language packages')
        self.assertLess(surface, scan)
        block = text[surface:scan]
        self.assertIn('python scripts/security_profile_probe.py image', block)
        self.assertIn('import app.main', block)
        for name in EXPECTED_RUNTIME_SCRIPTS:
            self.assertIn(name, block)
        self.assertIn('/bin/sh', block)
        self.assertNotIn('continue-on-error', block)
        self.assertNotIn('|| true', block)

    def test_vulnerability_policy_is_not_relaxed_to_make_unfixed_findings_green(self):
        text = WORKFLOW.read_text()
        self.assertIn('--severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL --ignore-unfixed=false', text)
        self.assertIn('--ignorefile /dev/null', text)
        self.assertIn("--ignore-policy ''", text)
        self.assertIn("--vex ''", text)
        self.assertIn('Require fresh matching image evidence and zero blocking findings', text)

    def test_pr_scan_separates_runtime_smoke_from_vulnerability_drift(self):
        text = WORKFLOW.read_text()
        self.assertIn('schedule:', text)
        self.assertIn('Classify immutable vulnerability surface', text)
        self.assertIn('if [ "$GITHUB_EVENT_NAME" != "pull_request" ]; then', text)
        self.assertIn(
            "backend/Dockerfile\\.security|backend/requirements\\.txt|scripts/check/check-security-image-audit\\.py",
            text,
        )
        self.assertIn("PYTHON_BASE_TAG|RUNTIME_BASE_TAG|trivy image", text)
        self.assertIn("steps.vulnerability_surface.outputs.scan_required == 'true'", text)
        self.assertIn("NO_PACKAGE_OR_IMAGE_SURFACE_CHANGE", text)
        self.assertIn("SCHEDULED_DAILY", text)

    def test_probe_rejects_disallowed_regular_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            path = folder / 'microdnf'
            path.write_text('fixture')
            path.chmod(0o755)
            with self.assertRaisesRegex(RuntimeError, 'DISALLOWED_RUNTIME_TOOL_PRESENT'):
                PROBE.runtime_surface([folder])

    def test_runtime_probe_rejects_disallowed_symlink_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            target = folder / 'target'
            target.write_text('fixture')
            (folder / 'ssh').symlink_to(target)
            with self.assertRaisesRegex(RuntimeError, 'DISALLOWED_RUNTIME_TOOL_PRESENT'):
                PROBE.runtime_surface([folder])

    def test_runtime_probe_rejects_setuid_and_setgid_drift(self):
        for mode in (0o4755, 0o2755):
            with self.subTest(mode=oct(mode)), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                path = folder / 'fixture-bin'
                path.write_text('fixture')
                path.chmod(mode)
                with self.assertRaisesRegex(RuntimeError, 'PRIVILEGED_EXECUTABLE_PRESENT'):
                    PROBE.runtime_surface([folder])

    def test_runtime_probe_accepts_reviewed_empty_surface(self):
        with tempfile.TemporaryDirectory() as directory:
            PROBE.runtime_surface([Path(directory)])

    def test_real_image_smokes_all_production_entrypoint_families_before_scan(self):
        text = WORKFLOW.read_text()
        surface = text.index('- name: Verify shell-free runtime and production entrypoint families')
        scan = text.index('- name: Scan OS and language packages')
        block = text[surface:scan]
        for evidence in ('uvicorn --help', 'alembic --help', 'import app.main',
                         'security_runtime_launcher.py', 'scripts/run_scheduled_jobs.py',
                         'app/workers/file_scan_worker.py'):
            self.assertIn(evidence, block)
        self.assertLess(text.index('uvicorn --help'), scan)
        self.assertLess(text.index('alembic --help'), scan)


if __name__ == '__main__':
    unittest.main()
