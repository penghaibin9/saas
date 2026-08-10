"""学校试点部署合同：静态验证脚本语法和关键生产闸门，防止后续回退。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

SHELL_SCRIPTS = (
    "scripts/check/preflight-school-trial.sh",
    "scripts/deploy/preflight-linux.sh",
    "scripts/deploy/install-systemd-release.sh",
    "scripts/deploy/verify-systemd-release.sh",
)


@pytest.mark.parametrize("relative", SHELL_SCRIPTS)
def test_trial_shell_scripts_parse(relative: str):
    result = subprocess.run(
        ["bash", "-n", str(ROOT / relative)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_release_script_carries_all_three_clients_and_scan_worker():
    text = (ROOT / "scripts/deploy/install-systemd-release.sh").read_text(encoding="utf-8")
    assert 'frontend' in text
    assert 'miniapp' in text
    assert 'student-portal' in text
    assert 'school-lifecycle-file-scan' in text
    assert 'scripts/check_alembic_current.py' in text


def test_deploy_scripts_do_not_pin_an_alembic_revision():
    # 旧事故：部署脚本把 head 写死为 0111，仓库新增迁移后发布验收必然失真。
    for relative in (
        "scripts/deploy/preflight-linux.sh",
        "scripts/deploy/install-systemd-release.sh",
        "scripts/deploy/verify-systemd-release.sh",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "0111_immutable_acceptance_summary" not in text
        assert "Alembic 唯一 head=0111" not in text


def test_systemd_nginx_exposes_portal_but_not_raw_files():
    text = (ROOT / "deploy/nginx/school-lifecycle.systemd.conf.example").read_text(encoding="utf-8")
    assert "location ^~ /portal/" in text
    assert "location /uploads/ { return 404; }" in text
    assert "location /exports/ { return 404; }" in text
    assert "Content-Security-Policy" in text
    assert "school_auth_limit" in text


def test_file_scan_service_is_supervised_and_fail_closed():
    text = (ROOT / "deploy/systemd/school-lifecycle-file-scan.service").read_text(encoding="utf-8")
    assert "ExecStartPre=" in text
    assert "check_production_file_scan.py" in text
    assert "app.workers.file_scan_worker" in text
    assert "Restart=always" in text


def test_systemd_env_example_contains_trial_security_dependencies():
    text = (ROOT / "deploy/env/backend.systemd.env.example").read_text(encoding="utf-8")
    for key in (
        "DEPLOYMENT_MODE=production",
        "APP_ENV=production",
        "DB_ENABLED=true",
        "DB_DRIVER=mysql",
        "REDIS_URL=",
        "FIELD_ENCRYPTION_KEY=",
        "INTERNAL_OPS_TOKEN=",
        "SCHEDULER_MODE=external",
        "CLAMAV_ENABLED=true",
    ):
        assert key in text
