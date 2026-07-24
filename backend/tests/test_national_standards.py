"""国家标准库：全文检索、章节、学校专业绑定和权限边界。"""
from datetime import date

from app.db.session import get_sessionmaker
from app.models import (College, Major, NationalMajorCatalog, NationalStandardDocument,
                        NationalStandardSection, NationalStandardSource)
from scripts.sync_moe_professional_standards import extract_sections


def _seed_standard():
    db = get_sessionmaker()()
    source = NationalStandardSource(source_key="MOE_PROFESSIONAL_TEACHING_STANDARD",
        source_type="PROFESSIONAL_TEACHING_STANDARD", title="758项新版职业教育专业教学标准",
        publisher="中华人民共和国教育部", version_label="2025", source_url="https://www.moe.gov.cn/",
        published_date=date(2025, 2, 11), is_official=True,
        copyright_policy="INTERNAL_SEARCH_LINK_SOURCE", retrieval_status="COMPLETE",
        item_count=758, metadata_json={"expected": 758})
    db.add(source); db.flush()
    national_major = NationalMajorCatalog(source_id=source.id, catalog_version="2021",
        education_level="HIGHER_VOCATIONAL_SPECIALIST", category_code="51", category_name="电子与信息大类",
        major_class_code="5102", major_class_name="计算机类", major_code="510203", major_name="软件技术",
        directory_status="ACTIVE", effective_date=date(2021, 3, 12), metadata_json={})
    db.add(national_major); db.flush()
    text = "1 概述\n面向软件开发。\n2 专业名称（专业代码）\n软件技术（510203）\n8 课程设置及学时安排\nJava程序设计。"
    document = NationalStandardDocument(source_id=source.id, major_catalog_id=national_major.id,
        standard_code="MOE-2025-HIGHER_VOCATIONAL_SPECIALIST-510203",
        document_type="PROFESSIONAL_TEACHING_STANDARD", title="软件技术专业教学标准（高等职业教育专科）",
        education_level="HIGHER_VOCATIONAL_SPECIALIST", major_code="510203", major_name="软件技术",
        version_label="2025", published_date=date(2025, 2, 11), source_url="https://www.moe.gov.cn/test.pdf",
        text_status="EXTRACTED", full_text=text, structured_json={"sectionCodes": ["SECTION_01"]},
        char_count=len(text), page_count=9, status="PUBLISHED")
    db.add(document); db.flush()
    db.add(NationalStandardSection(document_id=document.id, section_code="SECTION_01", section_no=1,
        section_title="概述", content_text="面向软件开发。", content_sha256="a" * 64))
    db.add(NationalStandardSection(document_id=document.id, section_code="SECTION_08", section_no=8,
        section_title="课程设置及学时安排", content_text="Java程序设计为专业核心课程。", content_sha256="b" * 64))
    college = College(tenant_id=1000000000000000001, college_name="信息工程学院", code="51")
    db.add(college); db.flush()
    school_major = Major(tenant_id=1000000000000000001, college_id=college.id,
        major_name="软件技术", code="510203")
    db.add(school_major); db.commit()
    ids = {"document": document.id, "schoolMajor": school_major.id}
    db.close(); return ids


def test_national_standard_search_detail_and_binding(client, auth_headers, db_mode):
    ids = _seed_standard()
    stats = client.get("/api/v1/national-standards/stats", headers=auth_headers).json()
    assert stats["code"] == 0
    assert stats["data"]["documents"] == 1 and stats["data"]["fullTextDocuments"] == 1

    searched = client.get("/api/v1/national-standards/documents?keyword=Java",
                          headers=auth_headers).json()
    assert searched["code"] == 0 and searched["data"]["total"] == 1
    assert searched["data"]["list"][0]["majorCode"] == "510203"

    detail = client.get(f"/api/v1/national-standards/documents/{ids['document']}",
                        headers=auth_headers).json()
    assert detail["code"] == 0
    assert detail["data"]["source"]["isOfficial"] is True
    assert detail["data"]["sections"][0]["title"] == "概述"

    bound = client.post("/api/v1/national-standards/bindings", headers=auth_headers,
                        json={"schoolMajorId": ids["schoolMajor"],
                              "documentId": ids["document"]}).json()
    assert bound["code"] == 0 and bound["data"]["isPrimary"] is True
    bindings = client.get("/api/v1/national-standards/bindings", headers=auth_headers).json()
    assert bindings["code"] == 0 and len(bindings["data"]) == 1
    program = client.post("/api/v1/academic-affairs/programs", headers=auth_headers,
                          json={"programName": "国家标准关联培养方案", "majorId": str(ids["schoolMajor"]),
                                "gradeYear": "2026", "totalCredits": 120}).json()
    assert program["code"] == 0
    program_detail = client.get(f"/api/v1/academic-affairs/programs/{program['data']['programId']}",
                                headers=auth_headers).json()
    assert program_detail["code"] == 0 and program_detail["data"]["nationalStandardBound"] is True
    assert program_detail["data"]["nationalStandards"][0]["documentId"] == str(ids["document"])
    relevant = program_detail["data"]["nationalStandards"][0]["relevantSections"]
    assert relevant[0]["no"] == 8
    assert "Java程序设计" in relevant[0]["contentExcerpt"]


def test_national_standard_is_fail_closed_for_student(client, db_mode):
    login = client.post("/api/v1/auth/mock-login",
                        json={"loginName": "student01", "password": "any"}).json()
    response = client.get("/api/v1/national-standards/stats",
                          headers={"Authorization": f"Bearer {login['data']['accessToken']}"})
    assert response.status_code == 403


def test_standard_section_extraction_uses_official_eleven_part_structure():
    text = "\n".join(f"{number} {title}\n第{number}部分正文" for number, title in {
        1: "概述", 2: "专业名称（专业代码）", 3: "入学基本要求", 4: "基本修业年限",
        5: "职业面向", 6: "培养目标", 7: "培养规格", 8: "课程设置及学时安排",
        9: "师资队伍", 10: "教学条件", 11: "质量保障和毕业要求"}.items())
    sections = extract_sections(text)
    assert [item["sectionNo"] for item in sections] == list(range(1, 12))
    assert sections[-1]["sectionTitle"] == "质量保障和毕业要求"
