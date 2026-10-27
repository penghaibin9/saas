import pytest


@pytest.mark.parametrize("surface", ["mobile", "materials", "revoked_write", "raw_reader_write", "stats_reader", "other_biz_psy_metadata"])
def test_normal_mental_operator_reads_masked_scope_without_raw_permission(client, db_mode, surface):
    from affairs_contract_test_support import ensure_role_user
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Permission, PsyReferral, Role, RolePermission, TeacherStudentScope, User
    from sqlalchemy import select
    from app.models.affairs_operations import AffairsMaterialRequirement
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr
    from test_affairs_mental import TID, _seed
    ids = _seed(db_mode)
    uid = ensure_role_user("PSYCHOLOGY_TEACHER", "mental_limited_operator", "心理办理验收人员")
    with get_sessionmaker()() as db:
        account = db.get(User, uid); account.password_hash = hash_password(TEST_LOGIN_PASSWORD); account.must_change_password = False
        role_id = db.scalar(select(Role.id).where(Role.tenant_id == TID, Role.role_code == "PSYCHOLOGY_TEACHER"))
        db.add(TeacherStudentScope(tenant_id=TID, teacher_key=account.login_name,
            role_code="PSYCHOLOGY_TEACHER", scope_type="PSY_STUDENT", ref_value="P001", status="ACTIVE"))
        refs = []
        requirements = []
        for index, sid in enumerate((ids["sa"], ids["sb"])):
            ref = PsyReferral(tenant_id=TID, student_id=sid, level="FOCUS", status="REFERRED",
                reason_summary="必要的客观事由摘要", note="不应免费返回的咨询明细XYZ")
            db.add(ref); db.flush(); refs.append(ref.id)
            requirement = AffairsMaterialRequirement(tenant_id=TID, student_id=sid, biz_type="MENTAL",
                biz_id=ref.id, item_code="MATERIAL_" + str(index), item_name="心理材料",
                material_scope="PSY_STUDENT", sensitivity_level="HIGHLY_SENSITIVE", status="MISSING", review_owner_id=uid)
            db.add(requirement); db.flush(); requirements.append(requirement.id)
        db.commit()
    def login():
        initial = _real_hdr(client, "mental_limited_operator", client_type="TEACHER_MINI")
        response = client.post("/api/v1/auth/switch-role", headers=initial,
            json={"contextId": f"role:{role_id}", "clientType": "TEACHER_MINI"})
        assert response.status_code == 200, response.text
        return {"Authorization": "Bearer " + response.json()["data"]["accessToken"]}
    header = login()
    if surface == "mobile":
        control = client.get("/api/v1/student-affairs/mental/list", headers=header)
        assert control.status_code == 200, control.text
        listed = client.get("/api/v1/mobile/teacher/mental", headers=header)
        assert listed.status_code == 200, listed.text
        detail = client.get(f"/api/v1/mobile/teacher/mental/{refs[0]}", headers=header)
        assert detail.status_code == 200 and detail.json()["data"]["noteMasked"] is True, detail.text
        assert "咨询明细XYZ" not in detail.text
        assert client.get(f"/api/v1/mobile/teacher/mental/{refs[1]}", headers=header).status_code == 403
        with_reason = client.get(f"/api/v1/mobile/teacher/mental/{refs[0]}", headers=header, params={"reason": "办理摘要不能免费取得原文"})
        assert with_reason.status_code == 200 and with_reason.json()["data"]["noteMasked"] is True
        followed = client.post(f"/api/v1/mobile/teacher/mental/{refs[0]}/follow", headers=header,
            json={"version": 0, "content": "正常心理职责可以登记授权个案回访"})
        assert followed.status_code == 200 and followed.json()["data"]["noteMasked"] is True, followed.text
    elif surface == "materials":
        response = client.get("/api/v1/student-affairs/material-requirements", headers=header, params={"bizType": "MENTAL", "pageSize": 1})
        assert response.status_code == 200, response.text
        assert response.json()["data"]["total"] == 1
        assert response.json()["data"]["items"][0]["requirementId"] == str(requirements[0])
        assert "咨询明细XYZ" not in response.text
    elif surface == "other_biz_psy_metadata":
        ensure_role_user("COUNSELOR", "mental_limited_operator", "兼岗心理办理验收人员")
        with get_sessionmaker()() as db:
            role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == "COUNSELOR"))
            co_role_id = role.id
            from app.models import SchoolClass
            # 使用已存在学生的真实班级，不从另一职责的逐生范围拼接。
            from app.models import StudentProfile
            profile_class = db.get(SchoolClass, db.get(StudentProfile, ids["sb"]).class_id)
            db.add(TeacherStudentScope(tenant_id=TID, teacher_key="mental_limited_operator", role_code="COUNSELOR",
                scope_type="CLASS", ref_value=profile_class.class_name, status="ACTIVE"))
            ordinary = AffairsMaterialRequirement(tenant_id=TID, student_id=ids["sb"], biz_type="LEAVE", biz_id=99001,
                item_code="LEAVE_NORMAL", item_name="普通请假说明", material_scope="BUSINESS_SCOPE", status="MISSING")
            private = AffairsMaterialRequirement(tenant_id=TID, student_id=ids["sb"], biz_type="LEAVE", biz_id=99001,
                item_code="LEAVE_PSY", item_name="心理证明材料", material_scope="PSY_STUDENT", status="MISSING")
            db.add_all([ordinary, private]); db.commit(); ordinary_id = ordinary.id
        header = login()
        switched = client.post("/api/v1/auth/switch-role", headers=header,
            json={"contextId": f"role:{co_role_id}", "clientType": "TEACHER_MINI"})
        assert switched.status_code == 200, switched.text
        header = {"Authorization": "Bearer " + switched.json()["data"]["accessToken"]}
        listed = client.get("/api/v1/student-affairs/material-requirements", headers=header, params={"bizType": "LEAVE"})
        assert listed.status_code == 200 and listed.json()["data"]["total"] == 1, listed.text
        assert listed.json()["data"]["items"][0]["requirementId"] == str(ordinary_id)
    else:
        with get_sessionmaker()() as db:
            role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == "PSYCHOLOGY_TEACHER"))
            role.role_type = "CUSTOM"; role.version += 1
            code = {"raw_reader_write": "studentAffairs.risk.psyDetail.view", "stats_reader": "studentAffairs.stats.view"}.get(surface)
            if code:
                permission = db.scalar(select(Permission).where(Permission.permission_code == code))
                if not permission:
                    permission = Permission(permission_code=code, permission_name="隔离测试心理独立能力")
                    db.add(permission); db.flush()
                db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id, status="ACTIVE"))
            db.commit()
        header = login()
        if surface == "stats_reader":
            assert client.get("/api/v1/mobile/teacher/mental-stats", headers=header).status_code == 200
            assert client.get("/api/v1/mobile/teacher/mental", headers=header).status_code == 403
            return
        if surface == "raw_reader_write":
            raw = client.get(f"/api/v1/student-affairs/mental/referrals/{refs[0]}", headers=header, params={"reason": "核验明确授予的原文读取能力"})
            assert raw.status_code == 200 and raw.json()["data"]["noteMasked"] is False, raw.text
            materials = client.get("/api/v1/student-affairs/material-requirements", headers=header, params={"bizType": "MENTAL"})
            assert materials.status_code == 200 and materials.json()["data"]["total"] == 1, materials.text
            assert materials.json()["data"]["items"][0]["allowedActions"] == []
            create = client.post("/api/v1/student-affairs/material-requirements", headers=header,
                json={"bizType": "MENTAL", "bizId": refs[0], "itemCode": "READ_ONLY", "itemName": "只读人员不得创建材料"})
            assert create.status_code == 403, create.text
            waive = client.post(f"/api/v1/student-affairs/material-requirements/{requirements[0]}/review", headers=header,
                json={"action": "WAIVE", "version": 0, "reason": "只读人员不得通过免交改变材料状态"})
            assert waive.status_code == 403, waive.text
        control = client.post(f"/api/v1/student-affairs/mental/referrals/{refs[0]}/follow", headers=header,
            json={"version": 0, "content": "权限已撤销，电脑写入口应被拒绝"})
        assert control.status_code == 403, control.text
        forbidden = client.post(f"/api/v1/mobile/teacher/mental/{refs[0]}/follow", headers=header,
            json={"version": 0, "content": "权限撤销后不能继续写入回访"})
        assert forbidden.status_code == 403, forbidden.text
        with get_sessionmaker()() as db:
            row = db.get(PsyReferral, refs[0])
            assert row.status == "REFERRED" and row.version == 0
