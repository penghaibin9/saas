from pathlib import Path

path = Path("backend/tests/test_portal_graduation.py")
text = path.read_text(encoding="utf-8")

admin = '''def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


'''
helper = admin + '''def _running_batch(client, suffix: str) -> int:
    """Create and activate a real batch so material rules are bootstrapped explicitly."""
    headers = _admin(client)
    created = client.post("/api/v1/graduation/batches", headers=headers, json={
        "batchName": f"门户毕业设计测试-{suffix}",
        "batchNo": f"PORTAL-{suffix}",
        "gradeYear": "2026届",
        "plannedCount": 10,
    }).json()
    assert created["code"] == 0, created
    batch_id = int(created["data"]["id"])
    activated = client.post(
        f"/api/v1/graduation/batches/{batch_id}/activate", headers=headers
    ).json()
    assert activated["code"] == 0, activated
    return batch_id


'''
if "def _running_batch(" not in text:
    assert admin in text
    text = text.replace(admin, helper, 1)

text = text.replace("def _seed_gd_ready_for_proposal(no, name):", "def _seed_gd_ready_for_proposal(no, name, batch_id):")
text = text.replace(
    'g = GraduationStudent(tenant_id=TID, student_no=no, name=name, advisor_name="王导师",\n                             topic_id=1, topic_title="XX系统的设计与实现", stage="GUIDING",',
    'g = GraduationStudent(tenant_id=TID, batch_id=batch_id, student_no=no, name=name, advisor_name="王导师",\n                             topic_id=1, topic_title="XX系统的设计与实现", stage="GUIDING",',
    1,
)
text = text.replace("def _seed_gd_for_final(no, name):", "def _seed_gd_for_final(no, name, batch_id):")
text = text.replace(
    'g = GraduationStudent(tenant_id=TID, student_no=no, name=name, advisor_name="王导师",\n                             topic_id=1, topic_title="XX系统的设计与实现", stage="FINAL_CHECK",',
    'g = GraduationStudent(tenant_id=TID, batch_id=batch_id, student_no=no, name=name, advisor_name="王导师",\n                             topic_id=1, topic_title="XX系统的设计与实现", stage="FINAL_CHECK",',
    1,
)

start = text.index("def _seed_pdf_file(student_no):")
end = text.index("\n\ndef test_view_and_submit_final", start)
text = text[:start] + '''def _seed_pdf_file(client, headers):
    """Upload through the public file API so ownership, SHA-256 and scan state are real."""
    response = client.post(
        "/api/v1/files", headers=headers,
        files={"file": ("毕业论文.pdf", b"%PDF-1.4 portal graduation test", "application/pdf")},
        params={"bizType": "GRADUATION_MATERIAL"},
    ).json()
    assert response["code"] == 0, response
    return str(response["data"]["fileId"])
''' + text[end:]

replacements = {
    '_seed_student("GD-P-101", "开题一")\n    _seed_gd_ready_for_proposal("GD-P-101", "开题一")': '_seed_student("GD-P-101", "开题一")\n    batch_id = _running_batch(client, "P101")\n    _seed_gd_ready_for_proposal("GD-P-101", "开题一", batch_id)',
    '_seed_student("GD-P-102", "开题二")\n    _seed_gd_ready_for_proposal("GD-P-102", "开题二")': '_seed_student("GD-P-102", "开题二")\n    batch_id = _running_batch(client, "P102")\n    _seed_gd_ready_for_proposal("GD-P-102", "开题二", batch_id)',
    '_seed_student("GD-P-301", "成果一")\n    _seed_gd_for_final("GD-P-301", "成果一")\n    fid = _seed_pdf_file("GD-P-301")\n    h = _stu_token("成果一", "GD-P-301")': '_seed_student("GD-P-301", "成果一")\n    batch_id = _running_batch(client, "P301")\n    _seed_gd_for_final("GD-P-301", "成果一", batch_id)\n    h = _stu_token("成果一", "GD-P-301")\n    fid = _seed_pdf_file(client, h)',
    '_seed_student("GD-P-302", "成果二")\n    _seed_gd_for_final("GD-P-302", "成果二")': '_seed_student("GD-P-302", "成果二")\n    batch_id = _running_batch(client, "P302")\n    _seed_gd_for_final("GD-P-302", "成果二", batch_id)',
    '_seed_student("GD-P-401", "答辩一")\n    _seed_gd_ready_for_proposal("GD-P-401", "答辩一")': '_seed_student("GD-P-401", "答辩一")\n    batch_id = _running_batch(client, "P401")\n    _seed_gd_ready_for_proposal("GD-P-401", "答辩一", batch_id)',
    '_seed_student("GD-P-403", "答辩三")\n    _seed_gd_ready_for_proposal("GD-P-403", "答辩三")': '_seed_student("GD-P-403", "答辩三")\n    batch_id = _running_batch(client, "P403")\n    _seed_gd_ready_for_proposal("GD-P-403", "答辩三", batch_id)',
}
for old, new in replacements.items():
    if old in text:
        text = text.replace(old, new, 1)

# Keep the optimistic-lock contract explicit in every submit path.
text = text.replace('"attachments": []}).json()', '"attachments": [], "expectedVersion": 0}).json()', 1)
text = text.replace('json={"background": "", "plan": "", "outcome": ""})', 'json={"background": "", "plan": "", "outcome": "", "expectedVersion": 0})')
text = text.replace('json={"background": "x内容"})', 'json={"background": "x内容", "expectedVersion": 0})')
text = text.replace('json={"finalType": "初稿", "attachments": [fid]}).json()', 'json={"finalType": "初稿", "attachments": [fid], "expectedVersion": 0}).json()', 1)
text = text.replace('json={"finalType": "初稿", "attachments": []})', 'json={"finalType": "初稿", "attachments": [], "expectedVersion": 0})')
text = text.replace('json={"finalType": "xyz", "attachments": ["f1"]})', 'json={"finalType": "xyz", "attachments": ["f1"], "expectedVersion": 0})')

path.write_text(text, encoding="utf-8")
