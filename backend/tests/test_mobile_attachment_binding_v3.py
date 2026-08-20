"""V3 §8：移动附件必须走 canonical File Center 绑定，不得由客户端指定归属。

覆盖 §6.1「前端隐藏不等于权限」与 §8.1 的 TEMP_PRIVATE → 安全扫描 → 业务 command
同事务 binding 链路。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import AppException
from app.services import mobile_student_service as stu

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_SOURCE = REPO_ROOT / "backend" / "app" / "services" / "mobile_student_service.py"
ORIENTATION_SOURCE = REPO_ROOT / "backend" / "app" / "services" / "orientation_service.py"
BINDING_SOURCE = REPO_ROOT / "backend" / "app" / "services" / "file_business_binding_service.py"
ATOMIC_SOURCE = REPO_ROOT / "backend" / "app" / "services" / "affairs_student_atomic_service.py"


# ── fileIds 入参校验：客户端限制不作数，服务端必须再判一次 ──

def test_attachment_ids_are_deduped_and_shape_checked():
    assert stu._attachment_ids({}) == []
    assert stu._attachment_ids({"fileIds": []}) == []
    assert stu._attachment_ids({"fileIds": ["1", "2", "1", ""]}) == ["1", "2"]
    assert stu._attachment_ids({"fileIds": [3, 4]}) == ["3", "4"]


@pytest.mark.parametrize("bad", [
    {"fileIds": "1,2"},
    {"fileIds": {"a": 1}},
])
def test_non_array_file_ids_are_rejected(bad):
    with pytest.raises(AppException):
        stu._attachment_ids(bad)


@pytest.mark.parametrize("bad", ["abc", "1 OR 1=1", "../../etc/passwd", "1;DROP"])
def test_non_numeric_file_ids_are_rejected(bad):
    with pytest.raises(AppException):
        stu._attachment_ids({"fileIds": [bad]})


def test_attachment_count_is_bounded_server_side():
    ids = [str(index) for index in range(stu.MAX_ATTACHMENTS_PER_SUBMIT + 1)]
    with pytest.raises(AppException):
        stu._attachment_ids({"fileIds": ids})
    # 恰好在上限内应通过
    ok = [str(index) for index in range(stu.MAX_ATTACHMENTS_PER_SUBMIT)]
    assert len(stu._attachment_ids({"fileIds": ok})) == stu.MAX_ATTACHMENTS_PER_SUBMIT


# ── 绑定必须发生在业务事务里，且由 canonical 服务完成 ──

def test_business_commands_bind_through_the_canonical_service_in_the_same_transaction():
    service = SERVICE_SOURCE.read_text(encoding="utf-8")
    orientation = ORIENTATION_SOURCE.read_text(encoding="utf-8")

    atomic = ATOMIC_SOURCE.read_text(encoding="utf-8")

    for name, source, biz_type in [
        ("campus-service", service, "CAMPUS_SERVICE_WORKORDER"),
        ("green-channel", orientation, "ORIENTATION_GREEN_CHANNEL"),
        ("funding-apply", atomic, "FUNDING"),
    ]:
        assert "bind_file_to_business(" in source, f"{name} 未调用 canonical 绑定服务"
        assert f'biz_type="{biz_type}"' in source, f"{name} 未声明业务类型"
        assert 'subject_type="STUDENT"' in source, f"{name} 未声明归属主体"

    # 绑定必须在 commit 之前——也就是和业务写在同一个事务里
    for name, source in [("campus-service", service), ("green-channel", orientation),
                         ("funding-apply", atomic)]:
        bind_at = source.index("bind_file_to_business(")
        commit_at = source.index("db.commit()", bind_at)
        assert bind_at < commit_at, f"{name} 的绑定必须先于 commit"


def test_client_can_never_choose_the_binding_target():
    """biz_id 只能来自服务端刚写入的业务行，不能来自请求体。"""
    service = SERVICE_SOURCE.read_text(encoding="utf-8")
    orientation = ORIENTATION_SOURCE.read_text(encoding="utf-8")
    assert "biz_id=row.id" in service
    assert "biz_id=g.id" in orientation
    for source in (service, orientation):
        assert "biz_id=body" not in source
        assert 'biz_id=b.get(' not in source


def test_canonical_binding_refuses_unscanned_or_unavailable_files():
    binding = BINDING_SOURCE.read_text(encoding="utf-8")
    assert '_READY_SCAN_STATUS = {"CLEAN", "NOT_REQUIRED"}' in binding
    assert "FILE_NOT_READY" in binding
    assert "禁止绑定正式业务" in binding
    # 绑定服务从不自己 commit：失败必须让业务事务整体回滚
    assert "本模块从不自行 commit" in binding


def test_orientation_green_channel_signature_accepts_attachments_and_actor():
    import inspect
    from app.services.orientation_service import student_submit_green_channel
    params = inspect.signature(student_submit_green_channel).parameters
    assert "file_ids" in params
    assert "actor" in params, "绑定需要 actor 做 owner 校验，不能用空身份"
    # 默认不带附件时行为不变
    assert params["file_ids"].default is None


# ── 资助奖助申请（Real Task 第 4 条） ──
#
# 注意绑定要加在 affairs_student_atomic_service.funding_apply 上，不是
# affairs_funding_service.apply：install() 会把前者 monkey-patch 成学生自助入口的
# 真实实现，学生端小程序和 PC 门户走的都是它。改错地方会写出一段永远不执行的代码
# （这个坑本人踩过，靠 Real Task 真实回放才发现附件根本没绑上）。

def test_student_funding_apply_is_the_atomic_implementation():
    atomic = ATOMIC_SOURCE.read_text(encoding="utf-8")
    assert "portal.funding_apply = funding_apply" in atomic, (
        "学生自助资助申请由 atomic service 覆盖门户实现；绑定必须加在这里"
    )


def test_funding_binding_target_comes_from_the_server_written_row():
    atomic = ATOMIC_SOURCE.read_text(encoding="utf-8")
    assert "biz_id=application.id" in atomic
    assert "biz_id=body" not in atomic
    assert 'biz_id=body.get(' not in atomic


def test_funding_attachments_are_shape_checked_server_side():
    atomic = ATOMIC_SOURCE.read_text(encoding="utf-8")
    assert "_attachment_ids(body)" in atomic, "fileIds 形状必须在服务端再判一次"


def test_funding_biz_type_has_a_real_access_resolver():
    """绑上却没人打得开的附件等于没交——FUNDING 必须有权威 resolver。"""
    from app.services.file_access_service import resolver_registry_snapshot
    assert "FUNDING" in resolver_registry_snapshot()


def test_student_sees_how_many_materials_are_attached():
    """学生交完材料必须看得见它挂在哪一笔申请上，否则提交完像掉进黑洞。"""
    affairs = (REPO_ROOT / "backend" / "app" / "services" / "mobile_affairs_service.py").read_text(
        encoding="utf-8")
    assert '"attachmentCount"' in affairs
    # 一次分组查询取全部条数，不逐行查
    assert "_funding_attachment_counts" in affairs
    assert ".group_by(FileBinding.biz_id)" in affairs
    page = (REPO_ROOT / "miniapp" / "src" / "pages" / "student" / "affairs" / "funding.vue").read_text(
        encoding="utf-8")
    assert "attachmentCount" in page


def test_funding_page_blocks_submit_while_attachments_are_not_ready():
    page = (REPO_ROOT / "miniapp" / "src" / "pages" / "student" / "affairs" / "funding.vue").read_text(
        encoding="utf-8")
    assert "MobileAttachmentPicker" in page
    assert "attachmentsReady" in page
    assert "if (!this.attachmentsReady) return toast" in page
    # 一批临时文件只能绑一次业务，提交成功后必须清空
    assert "this.fileIds = []" in page
