"""教师 PC 就业材料审核权威（V3 施工手册 TP-E04 决断落地）。

历史与本轮决断
────────────────────────────────────────────────────────────
教师 PC 长期存在一条闭环契约：材料审核通过的同时，把学生就业记录置为
「已核验」（`EmpStudent.verify_status = VERIFIED`）。PR #183 明确保留了这条
契约，并用契约测试锁定。

但 #183 同时为教师小程序建立了独立核验命令，要求「已审核通过的材料 +
正式 FileBinding + 安全扫描通过」才允许 VERIFIED。结果是同一个 canonical
状态出现两条门槛不同的到达路径：小程序要正式证据，PC 只要点一下材料通过，
哪怕那份材料只有一个历史 `file_name` 文本。同一所学校、同一名学生，老师用
哪个端操作决定了证据强度——这是端间事实分叉，也正是 TP-E04 关心的
「一份材料通过就完成去向核验，证据要求过弱」。

**本轮决断：不拆闭环，而是把 PC 的证据门槛提到与小程序一致。**

- 材料构成正式证据（正式绑定 + 文件可用 + 扫描放行）→ 保持既有闭环，
  材料 APPROVED 的同时完成 VERIFIED。真实上传过材料的正常流程完全不受影响。
- 材料不构成正式证据（只有历史文件名文本、或文件仍在扫描/未通过）→
  材料照常 APPROVED（材料审核本来就是独立的业务行为，老师看过并认可这件事
  是真的），但 `verify_status` 保持原值，不被隐式推进。老师若确需核验，
  走 PC 新增的独立核验命令（与小程序同一 domain 权威），届时同样要过证据门槛。

这样 PC 与小程序对「什么证据足以支撑 VERIFIED」给出同一答案，而不是各判各的。
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException
from app.modules.employment.services import employment_destination_verification_service as verification
from app.modules.employment.services import employment_service as base
from app.modules.employment.services.employment_runtime_service import _assert_material
from app.services.db_service import session


def approve_material(mid, comment="", *, user: dict) -> dict:
    """审核通过一份 PC 就业材料；证据充分时同时完成去向核验。"""
    with session() as db:
        material, emp = _assert_material(db, mid, user)
        if material.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "该材料已通过")
        before = material.status
        operator, _ = base._op()
        material.status = "APPROVED"
        material.reviewer = operator
        material.review_time = datetime.utcnow()
        material.version = int(material.version or 0) + 1
        emp.material_status = "APPROVED"

        # TP-E04：闭环保留，但门槛与教师小程序拉齐——只有这份材料真的构成正式
        # 证据时才顺带完成核验；否则核验状态保持不变，由独立核验命令处理。
        formal = verification.material_is_formal_evidence(db, material)
        verified_now = False
        verify_before = str(emp.verify_status or "PENDING_VERIFY").upper()
        if formal and verify_before != "VERIFIED":
            emp.verify_status = "VERIFIED"
            emp.version = int(emp.version or 0) + 1
            verified_now = True
            base._audit(db, "VERIFICATION", emp.id, "去向核验通过",
                        "材料审核通过且具备正式证据，闭环完成核验",
                        verify_before, "VERIFIED")

        base._audit(db, "MATERIAL", material.id, "审核通过", comment, before, "APPROVED")
        db.commit()
        return {
            "id": str(material.id),
            "status": "APPROVED",
            # 前端据此如实告诉老师这一步到底做成了什么，不再统一宣称"已核验"。
            "formalEvidence": formal,
            "destinationVerified": verified_now,
            "verifyStatus": str(emp.verify_status or "PENDING_VERIFY"),
        }
