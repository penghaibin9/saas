"""Default catalog seed and structural constants.

These definitions are never a runtime policy decision.  Runtime requiredness,
review/archive gates, extensions and sizes come from the enabled batch rule.
"""
from __future__ import annotations

from typing import Any

MODULE_CODE = "GRADUATION"
MANIFEST_ARCHIVE_TYPE = "GRADUATION_FILE_VERSION"
MANIFEST_TARGET_TYPE = "GRADUATION_STUDENT"
MANIFEST_SCHEMA_VERSION = "GRADUATION_MATERIAL_MANIFEST_V2"
SNAPSHOT_SCHEMA_VERSION = "GRADUATION_STRUCTURED_SNAPSHOT_V1"
SNAPSHOT_GENERATOR_VERSION = "graduation-material-closeout/1"

REVIEW_PERMISSION_BY_CODE = {
    "TOPIC_ATTACHMENT": "graduationDesign.topic.review",
    "TASKBOOK": "graduationDesign.taskbook.update",
    "PROPOSAL_REPORT": "graduationDesign.proposal.review",
    "PROPOSAL_DEFENSE": "graduationDesign.proposal.review",
    "MIDTERM_REPORT": "graduationDesign.midterm.review",
    "THESIS_DRAFT": "graduationDesign.final.review",
    "THESIS_FINAL": "graduationDesign.final.review",
    "DESIGN_WORK": "graduationDesign.final.review",
    "SOURCE_CODE": "graduationDesign.final.review",
    "WORK_DESCRIPTION": "graduationDesign.final.review",
    "PLAGIARISM_REPORT": "graduationDesign.plagiarism.result",
    "REVIEW_ATTACHMENT": "graduationDesign.review.submit",
    "DEFENSE_SIGNED_SHEET": "graduationDesign.defense.scoreConfirm",
}


DEFAULT_MATERIAL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {"materialCode": "TOPIC_ATTACHMENT", "materialName": "题目附件", "stage": "TOPIC", "ownerRole": "MENTOR", "required": False, "allowedExtensions": ["pdf", "doc", "docx", "ppt", "pptx"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "TASKBOOK", "materialName": "任务书", "stage": "TASKBOOK", "ownerRole": "MENTOR", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "PROPOSAL_REPORT", "materialName": "开题报告", "stage": "PROPOSAL", "ownerRole": "STUDENT", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "PROPOSAL_DEFENSE", "materialName": "开题答辩材料", "stage": "PROPOSAL", "ownerRole": "STUDENT", "required": False, "allowedExtensions": ["pdf", "ppt", "pptx", "doc", "docx"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "GUIDANCE_RECORD", "materialName": "指导记录附件", "stage": "GUIDANCE", "ownerRole": "MENTOR", "required": True, "allowedExtensions": ["pdf", "doc", "docx", "png", "jpg", "jpeg"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": False, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "MIDTERM_REPORT", "materialName": "中期检查材料", "stage": "MIDTERM", "ownerRole": "MENTOR", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "THESIS_DRAFT", "materialName": "论文初稿", "stage": "FINAL_DRAFT", "ownerRole": "STUDENT", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 100 * 1024**2, "reviewRequired": True, "archiveRequired": False, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "THESIS_FINAL", "materialName": "论文定稿", "stage": "FINAL_APPROVED", "ownerRole": "STUDENT", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 100 * 1024**2, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "DESIGN_WORK", "materialName": "设计作品", "stage": "FINAL_APPROVED", "ownerRole": "STUDENT", "required": False, "allowedExtensions": ["pdf", "zip", "png", "jpg", "jpeg", "mp4"], "maxSizeBytes": 200 * 1024**2, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "SOURCE_CODE", "materialName": "源代码或源代码压缩包", "stage": "FINAL_APPROVED", "ownerRole": "STUDENT", "required": False, "allowedExtensions": ["zip"], "maxSizeBytes": 200 * 1024**2, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "WORK_DESCRIPTION", "materialName": "作品说明书", "stage": "FINAL_APPROVED", "ownerRole": "STUDENT", "required": False, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "SENSITIVE"},
    {"materialCode": "PLAGIARISM_REPORT", "materialName": "查重报告", "stage": "PLAGIARISM", "ownerRole": "MENTOR", "required": True, "allowedExtensions": ["pdf"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "HIGHLY_SENSITIVE"},
    {"materialCode": "REVIEW_ATTACHMENT", "materialName": "评阅意见附件", "stage": "REVIEW", "ownerRole": "REVIEWER", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": False, "archiveRequired": True, "sensitivityLevel": "HIGHLY_SENSITIVE"},
    {"materialCode": "DEFENSE_RECORD", "materialName": "答辩记录", "stage": "DEFENSE", "ownerRole": "DEFENSE_SECRETARY", "required": True, "allowedExtensions": ["pdf", "doc", "docx"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": False, "archiveRequired": True, "sensitivityLevel": "HIGHLY_SENSITIVE"},
    {"materialCode": "DEFENSE_SIGNED_SHEET", "materialName": "答辩签字表", "stage": "DEFENSE", "ownerRole": "DEFENSE_SECRETARY", "required": False, "allowedExtensions": ["pdf", "png", "jpg", "jpeg"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": True, "archiveRequired": True, "sensitivityLevel": "HIGHLY_SENSITIVE"},
    {"materialCode": "GRADE_MATERIAL", "materialName": "成绩评定材料", "stage": "GRADE", "ownerRole": "ADMIN", "required": True, "allowedExtensions": ["pdf", "xlsx"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": False, "archiveRequired": True, "sensitivityLevel": "HIGHLY_SENSITIVE"},
    {"materialCode": "TEMPLATE_REFERENCE", "materialName": "毕业设计模板", "stage": "TEMPLATE", "ownerRole": "ADMIN", "required": False, "allowedExtensions": ["docx", "pdf", "xlsx", "pptx"], "maxSizeBytes": 50 * 1024**2, "reviewRequired": False, "archiveRequired": False, "sensitivityLevel": "NORMAL"},
    {"materialCode": "FINAL_ARCHIVE_PACKAGE", "materialName": "最终归档包", "stage": "ARCHIVE", "ownerRole": "SYSTEM", "required": False, "allowedExtensions": ["zip"], "maxSizeBytes": 1024 * 1024**2, "reviewRequired": False, "archiveRequired": False, "sensitivityLevel": "HIGHLY_SENSITIVE"},
)

DEFAULT_SPEC_BY_CODE = {row["materialCode"]: row for row in DEFAULT_MATERIAL_DEFINITIONS}

STAGE_GROUPS = (
    ("题目与任务书", {"TOPIC", "TASKBOOK"}),
    ("开题材料", {"PROPOSAL"}),
    ("过程指导", {"GUIDANCE"}),
    ("中期检查", {"MIDTERM"}),
    ("论文与成果", {"FINAL_DRAFT", "FINAL_APPROVED"}),
    ("查重与评阅", {"PLAGIARISM", "REVIEW"}),
    ("答辩材料", {"DEFENSE"}),
    ("成绩材料", {"GRADE"}),
    ("归档材料", {"ARCHIVE", "TEMPLATE"}),
)
