from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
errors = []

for rel in (
    "student-portal/src/services/internshipCoreApi.js",
    "miniapp/src/services/internshipApi.js",
    "frontend/src/modules/internship/api/internship.api.js",
):
    text = (ROOT / rel).read_text(encoding="utf-8")
    if "/files/upload" in text:
        errors.append(f"{rel}: references removed /files/upload endpoint")

models = (ROOT / "backend/app/models/internship.py").read_text(encoding="utf-8")
for token in (
    "complainant_contact_hash", "source_type", "source_id",
    "uk_risk_source", "uk_internship_final_score_record",
    "uk_internship_archive_record",
):
    if token not in models:
        errors.append(f"internship model missing invariant: {token}")

complaints = (ROOT / "backend/app/modules/internship/services/internship_complaint_service.py").read_text(encoding="utf-8")
for token in (
    "encrypt_sensitive", "decrypt_sensitive", "complainant_contact_hash",
    "投诉未精确关联实习记录", 'source_type="COMPLAINT"',
):
    if token not in complaints:
        errors.append(f"complaint hardening missing: {token}")

students = (ROOT / "backend/app/modules/internship/services/internship_student_service.py").read_text(encoding="utf-8")
if "在岗或考核中的学生禁止直接换岗/退岗" not in students:
    errors.append("direct active-position mutation is not blocked")

positions = (ROOT / "backend/app/modules/internship/services/internship_position_service.py").read_text(encoding="utf-8")
if "请先完成正式调岗/退岗" not in positions:
    errors.append("occupied positions can still be archived")

if errors:
    raise SystemExit("\n".join(f"ERROR: {item}" for item in errors))
print("internship production contracts: OK")
