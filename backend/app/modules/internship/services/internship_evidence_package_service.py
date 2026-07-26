from __future__ import annotations
import io, json, zipfile
from datetime import datetime
from openpyxl import Workbook
from sqlalchemy import func, select
from app.core.exceptions import AppException
from app.models import InternshipEvidencePackage, InternshipRecord
from app.services import file_service
from app.services.db_service import _as_id, _tid, session
from app.modules.internship.services.internship_compliance_service import evaluate_internship_compliance

MAX_STUDENTS = 500
def generate(package_type, target_id, user=None):
    typ=package_type.upper()
    with session() as db:
        if typ=="BATCH":
            records=db.scalars(select(InternshipRecord).where(InternshipRecord.tenant_id==_tid(),InternshipRecord.batch_id==_as_id(target_id),InternshipRecord.is_deleted.is_(False))).all();batch_id=_as_id(target_id)
        elif typ=="STUDENT":
            records=[db.get(InternshipRecord,_as_id(target_id))];records=[x for x in records if x and x.tenant_id==_tid()];batch_id=records[0].batch_id if records else None
        elif typ=="ENTERPRISE":
            records=db.scalars(select(InternshipRecord).where(InternshipRecord.tenant_id==_tid(),InternshipRecord.enterprise_id==_as_id(target_id),InternshipRecord.is_deleted.is_(False))).all();batch_id=None
        else:raise AppException("VALIDATION_ERROR","packageType 必须为 STUDENT/BATCH/ENTERPRISE")
        from app.modules.internship.services.internship_student_service import _current_scope, _rec_in_scope
        from app.models import StudentProfile
        scope = _current_scope(user)
        records = [rec for rec in records if _rec_in_scope(
            scope, db, rec, db.get(StudentProfile, rec.student_id))]
        if len(records)>MAX_STUDENTS:raise AppException("VALIDATION_ERROR",f"单次证据包最多 {MAX_STUDENTS} 名学生")
        results=[evaluate_internship_compliance(x.id,"ARCHIVE",user) for x in records]
        missing=[{"internshipId":str(x.id),"items":[i["code"] for i in r["blockers"]]} for x,r in zip(records,results) if r["blockers"]]
        wb=Workbook();ws=wb.active;ws.title="合规汇总";ws.append(["实习记录ID","学生ID","是否通过","阻断项"])
        for rec,r in zip(records,results):ws.append([rec.id,rec.student_id,"是" if r["passed"] else "否","、".join(i["code"] for i in r["blockers"])])
        xlsx=io.BytesIO();wb.save(xlsx)
        manifest={"packageId": None, "packageType": typ, "tenantId": str(_tid()), "targetId": str(target_id),
                  "batchId": str(batch_id or ""), "generatedAt": datetime.utcnow().isoformat() + "Z",
                  "generatedBy": (user or {}).get("realName") or "系统",
                  "studentCount": len(records), "missingItems": missing,
                  "ruleVersion": (results[0]["ruleVersion"] if results else None),
                  "metricVersion": "internship-stats-v1",
                  "includedItems": ["manifest.json", "summary.xlsx"],
                  "sourceVersions": [
                      {"internshipId": str(x.id), "ruleVersion": r["ruleVersion"]}
                      for x, r in list(zip(records, results))[:50]
                  ]}
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2));z.writestr("summary.xlsx",xlsx.getvalue())
        meta=file_service.store_bytes(
            out.getvalue(),
            f"internship_compliance_{typ}_{target_id}.zip",
            biz_type="COMPLIANCE_EVIDENCE",
            mime_type="application/zip",
            user=user,
        )
        latest=db.scalar(select(func.max(InternshipEvidencePackage.package_version)).where(InternshipEvidencePackage.tenant_id==_tid(),InternshipEvidencePackage.package_type==typ,InternshipEvidencePackage.target_id==_as_id(target_id))) or 0
        p=InternshipEvidencePackage(tenant_id=_tid(),package_type=typ,batch_id=batch_id,target_id=_as_id(target_id),package_version=latest+1,package_file_id=str(meta.get("id") or meta.get("fileId") or ""),manifest_json=manifest,included_items=["manifest.json","summary.xlsx"],missing_items=missing,rule_version=manifest.get("ruleVersion"),metric_version="internship-stats-v1",generated_by_name=(user or {}).get("realName") or "系统",generated_at=datetime.utcnow(),row_count=len(records),file_count=2)
        db.add(p);db.flush();manifest["packageId"]=str(p.id);manifest["packageVersion"]=p.package_version;p.manifest_json=manifest
        from app.models import InternshipAuditTrail
        db.add(InternshipAuditTrail(tenant_id=_tid(),target_id=p.id,target_type="EVIDENCE_PACKAGE",action="GENERATE",operator_name=(user or {}).get("realName") or "系统",detail_json={"type":typ,"targetId":str(target_id),"version":p.package_version},occurred_at=datetime.utcnow()))
        db.commit();return {"id":str(p.id),"fileId":p.package_file_id,"version":p.package_version,"missingItems":missing,"manifest":manifest}
