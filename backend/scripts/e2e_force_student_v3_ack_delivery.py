"""把 S9-RT 的回执消息推进到真实可收件状态（仅隔离 E2E 库）。

消息中心的正式治理会在 UTC+8 22:00–07:00 把普通 IMMEDIATE 发布改成 SCHEDULED。
Playwright 若恰在静默时段运行，seed 已成功创建/受理 campaign，但学生收件箱在 07:00
前本来就看不到，于是“确认回执”浏览器回放会被墙钟时间随机击穿。

这里不绕开消息写入：草稿、预览、发布仍全部由正式 HTTP API 完成；本脚本只在安全的
本地 E2E 数据库中把该夹具 campaign 的 scheduled_at 推到已到期，然后调用正式 scheduler
与 delivery worker，最后验证目标学生确实收到 UnifiedMessage。生产/预发库一律拒绝运行。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select

from e2e_seed_student_v3_realtask import (
    STATE_PATH,
    TENANT_CODE,
    assert_safe_target,
)
from app.core.context import set_tenant
from app.db.session import get_sessionmaker
from app.services import message_campaign_service as campaign_svc


def _session():
    return get_sessionmaker()()


def _delivered(campaign_id: int, tenant_id: int, user_id: int) -> bool:
    from app.models import UnifiedMessage

    db = _session()
    try:
        row = db.scalar(select(UnifiedMessage.id).where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.campaign_id == campaign_id,
            UnifiedMessage.receiver_user_id == user_id,
            UnifiedMessage.is_deleted.is_(False),
        ))
        return row is not None
    finally:
        db.close()


def main() -> int:
    assert_safe_target()
    if not STATE_PATH.exists():
        raise SystemExit("S9-RT state missing — run seed first")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    campaign_id = int((state.get("ackMessage") or {}).get("campaignId") or 0)
    student_login = str((state.get("student") or {}).get("loginName") or "")
    if not campaign_id or not student_login:
        raise SystemExit("S9-RT ack campaign/student identity missing")

    from app.models import MessageCampaign, Tenant, User

    db = _session()
    try:
        tenant = db.scalar(select(Tenant).where(
            Tenant.tenant_code == TENANT_CODE,
            Tenant.is_deleted.is_(False),
        ))
        if tenant is None:
            raise SystemExit(f"tenant {TENANT_CODE} missing")
        tenant_id = int(tenant.id)
        # context.py 的 canonical tenant context 是 dict；传裸 int 会让 current_tenant_id()
        # 在 scheduler 内按 .get("tenantId") 读取时崩溃。这里与真实 HTTP 中间件保持同形。
        set_tenant({"tenantId": str(tenant_id)})
        student_user = db.scalar(select(User).where(
            User.tenant_id == tenant_id,
            User.login_name == student_login,
            User.user_type == "STUDENT",
            User.is_deleted.is_(False),
        ))
        if student_user is None:
            raise SystemExit(f"student user {student_login} missing")
        student_user_id = int(student_user.id)

        camp = db.scalar(select(MessageCampaign).where(
            MessageCampaign.id == campaign_id,
            MessageCampaign.tenant_id == tenant_id,
            MessageCampaign.is_deleted.is_(False),
        ))
        if camp is None:
            raise SystemExit(f"ack campaign {campaign_id} missing")

        if camp.status == "SCHEDULED":
            # 只改该 E2E campaign 的时钟前置事实；真正的受众重算、作业入队、投递、收口
            # 仍由 process_scheduled_campaigns / delivery worker 完成。
            camp.scheduled_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
    finally:
        db.close()

    try:
        # process_scheduled_campaigns 会对到期单重算受众并落 DeliveryJob；publish 的正常即时
        # 路径若已经 PUBLISHING，则只需 drain worker。重复调用均幂等。
        campaign_svc.process_scheduled_campaigns(limit=200)
        for _ in range(5):
            campaign_svc.process_pending_deliveries(limit=200)
            if _delivered(campaign_id, tenant_id, student_user_id):
                print(f"[s9-rt] ack campaign delivered campaign={campaign_id} user={student_user_id}")
                return 0

        raise SystemExit(
            f"ack campaign not delivered after scheduler drain: campaign={campaign_id} user={student_user_id}"
        )
    finally:
        set_tenant(None)


if __name__ == "__main__":
    raise SystemExit(main())
