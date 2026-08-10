"""学校试点部署合同：静态验证脚本语法和关键生产闸门，防止后续回退。"""
from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENV_RUNNER = ROOT / "scripts/deploy/run-with-envfile.py"

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


def test_environment_file_loader_does_not_shell_evaluate_secrets(tmp_path: Path):
    special = "A&b$ c#d!@%=:+-_(trial)"
    env_file = tmp_path / "backend.env"
    env_file.write_text(
        "APP_ENV=production\n"
        f"DB_PASSWORD={special}\n"
        "QUOTED_VALUE='value with spaces & $ signs'\n",
        encoding="utf-8",
    )

    get_result = subprocess.run(
        [sys.executable, str(ENV_RUNNER), "--get", str(env_file), "DB_PASSWORD"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert get_result.returncode == 0, get_result.stderr
    assert get_result.stdout == special

    exec_result = subprocess.run(
        [
            sys.executable,
            str(ENV_RUNNER),
            str(env_file),
            "--",
            sys.executable,
            "-c",
            "import os; print(os.environ['DB_PASSWORD']); print(os.environ['QUOTED_VALUE'])",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert exec_result.returncode == 0, exec_result.stderr
    assert exec_result.stdout.splitlines() == [special, "value with spaces & $ signs"]


def test_release_scripts_never_source_environment_file():
    for relative in (
        "scripts/deploy/install-systemd-release.sh",
        "scripts/deploy/verify-systemd-release.sh",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert '. "$ENV_FILE"' not in text
        assert "source $ENV_FILE" not in text
        assert "run-with-envfile.py" in text


def test_release_script_carries_all_three_clients_and_scan_worker():
    text = (ROOT / "scripts/deploy/install-systemd-release.sh").read_text(encoding="utf-8")
    assert "frontend" in text
    assert "miniapp" in text
    assert "student-portal" in text
    assert "school-lifecycle-file-scan" in text
    assert "scripts/check_alembic_current.py" in text


def test_release_serializes_apply_and_injects_public_origin_into_h5():
    text = (ROOT / "scripts/deploy/install-systemd-release.sh").read_text(encoding="utf-8")
    assert "flock -n 9" in text
    assert 'PUBLIC_BASE_URL_VALUE="$(env_value PUBLIC_BASE_URL)"' in text
    assert 'VITE_API_BASE_URL="$PUBLIC_BASE_URL_VALUE" VITE_USE_MOCK=false npm run build:h5' in text
    assert "miniapp H5 contains a localhost API origin" in text


def test_release_builds_before_quiesce_then_backs_up_before_migration():
    text = (ROOT / "scripts/deploy/install-systemd-release.sh").read_text(encoding="utf-8")
    # 耗时构建必须发生在停服务之前；静默窗口内先 stop，再取最后一致备份，再迁移。
    build_pos = text.index("npm run build:h5")
    stop_pos = text.index('systemctl stop "${ACTIVE_OLD_SERVICES[@]}"')
    backup_pos = text.index("mysqldump")
    migrate_pos = text.index("-m alembic upgrade head")
    switch_pos = text.index('mv -Tf "$APP_ROOT/current.next" "$APP_ROOT/current"')
    assert build_pos < stop_pos < backup_pos < migrate_pos < switch_pos
    assert "release_failure_guard" in text
    assert "ACTIVE_OLD_SERVICES" in text


def test_release_verification_probes_scan_and_storage():
    text = (ROOT / "scripts/deploy/verify-systemd-release.sh").read_text(encoding="utf-8")
    assert "scripts/check_production_file_scan.py" in text
    assert "scripts/check_production_storage.py" in text
    assert (ROOT / "backend/scripts/check_production_storage.py").is_file()


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
    # Nginx 的 add_header 默认是“子级一旦声明就不继承父级”。SPA index/assets
    # 不能为了 Cache-Control 再写 add_header，否则会丢 HSTS/CSP/X-Frame 等安全头。
    assert "add_header Cache-Control" not in text
    assert "expires -1;" in text


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
        "PUBLIC_BASE_URL=https://",
        "REDIS_URL=",
        "FIELD_ENCRYPTION_KEY=",
        "INTERNAL_OPS_TOKEN=",
        "SCHEDULER_MODE=external",
        "CLAMAV_ENABLED=true",
    ):
        assert key in text


def test_documented_field_key_shape_matches_fernet_contract():
    # Fernet key 的真实合同是“32 raw bytes 经 urlsafe-base64 编码”，不是任意长度字符串。
    sample = base64.urlsafe_b64encode(b"x" * 32).decode()
    raw = base64.urlsafe_b64decode(sample.encode())
    assert len(raw) == 32
    for relative in (
        "scripts/check/preflight-school-trial.sh",
        "scripts/deploy/preflight-linux.sh",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "urlsafe_b64decode" in text
        assert "len(raw) == 32" in text
