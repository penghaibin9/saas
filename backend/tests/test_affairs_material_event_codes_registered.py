"""学工材料消息事件码必须真实登记（回归守卫）。

发现经过：做 C8「从业务详情发起补材料」时，登记材料缺项恒返回
    422 / VALIDATION_ERROR / 未登记的消息事件码：MATERIAL.REQUIRED

根因不是缺模板定义，而是**注册代码从来没被执行**：
    affairs_operations_service._register_message_templates()
        只被 affairs_operations_service.install() 调用
    而 install() 全仓无任何调用方
于是 MATERIAL.* 五个事件码从未进入 message_event_outbox_service._EVENT_TEMPLATES，
「登记缺项并通知学生」这个功能在生产上完全不可用。

已在 clean origin/main（post-PR100 d57774c67）上复现确认，非本轮改动引入。

本文件守住：材料链路用到的事件码必须存在于权威模板表，且不依赖任何
「必须先调用某个 install()」的隐式前提。
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MATERIAL_EVENT_CODES = (
    "MATERIAL.REQUIRED",
    "MATERIAL.REMINDED",
    "MATERIAL.ACCEPTED",
    "MATERIAL.RETURNED",
    "MATERIAL.WAIVED",
)


def test_material_event_codes_exist_in_the_canonical_template_table():
    """权威来源是 _EVENT_TEMPLATES 本身，导入即可用，不需要先跑 install()。"""
    from app.services.message_event_outbox_service import _EVENT_TEMPLATES

    missing = [code for code in MATERIAL_EVENT_CODES if code not in _EVENT_TEMPLATES]
    assert not missing, f"材料事件码未登记，登记/审核材料会 422：{missing}"


def test_material_templates_carry_usable_delivery_metadata():
    """模板必须能真正投递：缺 message_type / title 会在 outbox 组装时炸掉。"""
    from app.services.message_event_outbox_service import _EVENT_TEMPLATES

    for code in MATERIAL_EVENT_CODES:
        tpl = _EVENT_TEMPLATES[code]
        assert tpl.get("message_type"), code
        assert tpl.get("title"), code
        assert tpl.get("source_module") == "student-affairs", code


def test_every_event_code_emitted_by_material_service_is_registered():
    """静态扫描材料服务里实际 emit 的事件码，全部必须已登记。

    比只检查上面五个更稳：以后新增事件码但忘了登记，这里会直接红。
    """
    from app.services.message_event_outbox_service import _EVENT_TEMPLATES

    source = (ROOT / "app/modules/student_affairs/services"
              / "affairs_material_center_service.py").read_text(encoding="utf-8")
    emitted = {
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value.startswith("MATERIAL.")
    }
    assert emitted, "未扫描到任何 MATERIAL.* 事件码，扫描逻辑可能失效"
    unregistered = sorted(emitted - set(_EVENT_TEMPLATES))
    assert not unregistered, f"材料服务 emit 了未登记的事件码：{unregistered}"
