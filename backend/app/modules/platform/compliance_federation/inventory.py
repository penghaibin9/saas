"""Machine-readable source-authority inventory for PLAT-B-C0.

Every writer listed here remains owned by its domain.  Federation code may
import evaluators/read models only; boundary tests enforce the writer ban.
"""
from __future__ import annotations

DOMAIN_COMPLIANCE_INVENTORY = (
    {
        "domain": "INTERNSHIP",
        "providerCode": "INTERNSHIP_NATIVE",
        "mode": "NATIVE_ENGINE",
        "nativeEvaluator": "app.modules.internship.services.internship_compliance_authoritative_service.evaluate_internship_compliance",
        "ruleSource": "internship_compliance_rules.get_batch_compliance_rules",
        "actualSource": "InternshipRecord plus domain evidence models",
        "writerSource": "internship domain services",
        "operationCodes": ("ONBOARD", "CONTINUE", "ASSESS", "ARCHIVE", "BATCH_CLOSE"),
        "severityStates": ("BLOCK", "WARN"),
        "evidenceRef": "evidenceId/evidenceVersion",
        "fourClientConsumers": ("STAFF_PC", "STUDENT_PC", "TEACHER_MINIAPP", "STUDENT_MINIAPP"),
    },
    {
        "domain": "GRADUATION",
        "providerCode": "GRADUATION_MATERIAL",
        "mode": "MATERIAL_POLICY",
        "nativeEvaluator": None,
        "ruleSource": "graduation.materials.rule_service.active_rule/rule_items",
        "actualSource": "GraduationStudentMaterial/FileVersion/FileObject",
        "writerSource": "graduation.materials.command_service",
        "operationCodes": ("SUBMIT", "REVIEW", "ARCHIVE"),
        "severityStates": ("BLOCK", "WARN"),
        "evidenceRef": "current FileVersion/FileObject",
        "fourClientConsumers": ("STAFF_PC", "STUDENT_PC"),
    },
    {
        "domain": "STUDENT_AFFAIRS",
        "providerCode": "AFFAIRS_EVIDENCE",
        "mode": "EVIDENCE_ONLY",
        "nativeEvaluator": None,
        "ruleSource": "AffairsMaterialRequirement",
        "actualSource": "FileAsset/FileVersion/FileObject/FileBinding",
        "writerSource": "affairs_material_center_service",
        "operationCodes": (),
        "severityStates": (),
        "evidenceRef": "current FileVersion/FileBinding",
        "fourClientConsumers": ("STAFF_PC", "STUDENT_PC"),
    },
    {
        "domain": "ACADEMIC",
        "providerCode": "ACADEMIC_EVIDENCE",
        "mode": "EVIDENCE_ONLY",
        "nativeEvaluator": None,
        "ruleSource": "status-change state/material contract",
        "actualSource": "AA_STATUS_CHANGE FileBinding",
        "writerSource": "status_change_material_service",
        "operationCodes": (),
        "severityStates": (),
        "evidenceRef": "active FileBinding",
        "fourClientConsumers": ("STAFF_PC", "STUDENT_PC", "TEACHER_MINIAPP", "STUDENT_MINIAPP"),
    },
)
