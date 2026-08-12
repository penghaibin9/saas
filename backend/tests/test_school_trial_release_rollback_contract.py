"""学校试点发布回滚合同：最终生产验收成功前必须保持 rollback armed。"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = ROOT / "scripts/deploy/install-systemd-release.sh"


def test_release_keeps_rollback_armed_until_final_acceptance():
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")

    quiesce_pos = text.index("QUIESCED=1")
    verify_pos = text.index('bash "$RELEASE_DIR/scripts/deploy/verify-systemd-release.sh"')
    acceptance_pos = text.index('bash "$RELEASE_DIR/scripts/deploy/accept-production-release.sh"')
    disarm_pos = text.rindex("QUIESCED=0")
    trap_clear_pos = text.index("trap - EXIT", disarm_pos)

    # 初始值 + 最终 acceptance 成功后的解除；中途不得提前解除回滚保护。
    assert text.count("QUIESCED=0") == 2
    assert quiesce_pos < verify_pos < acceptance_pos < disarm_pos < trap_clear_pos

    # 候选版本已启动后失败时必须先停止所有新写入者；首次安装无 previous 也不能留失败版本在线。
    assert (
        "systemctl stop school-lifecycle-backend school-lifecycle-scheduler "
        "school-lifecycle-file-scan"
    ) in text
    assert 'rm -f "$APP_ROOT/current"' in text
