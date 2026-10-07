#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex,CreateTable

from app.models.base import Base
import app.models  # noqa: F401

root=Path(__file__).resolve().parents[1]
sql_out=root/"artifacts"/"0001_internship_standalone_baseline.mysql.sql"
meta_out=root/"artifacts"/"baseline-ddl.json"

forbidden_prefixes=(
    "t_aa_","t_affairs_","t_orientation_","t_graduation_","t_gd_",
    "t_cs_","t_campus_","t_emp_student","t_emp_job","t_emp_material","t_emp_followup",
)
names=sorted(Base.metadata.tables)
bad=[name for name in names if name.startswith(forbidden_prefixes)]
if bad:
    raise SystemExit("forbidden standalone tables: "+", ".join(bad))

dialect=mysql.dialect()
parts=[
    "-- 跃科岗位实习管理平台 Standalone baseline",
    "-- source: main@adea054e2fd59cc0b83bbdb22f10ec98a8e2fd8c",
    "SET NAMES utf8mb4;",
]
for table in Base.metadata.sorted_tables:
    parts.append(str(CreateTable(table).compile(dialect=dialect)).strip()+";")
    for index in sorted(table.indexes,key=lambda i:i.name or ""):
        parts.append(str(CreateIndex(index).compile(dialect=dialect)).strip()+";")
sql="\n\n".join(parts)+"\n"
sql_out.parent.mkdir(parents=True,exist_ok=True)
sql_out.write_text(sql,encoding="utf-8")
payload={
    "schemaVersion":1,
    "tableCount":len(names),
    "tableNames":names,
    "sha256":hashlib.sha256(sql.encode()).hexdigest(),
    "forbiddenTableCount":0,
}
meta_out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"tableCount":len(names),"sha256":payload["sha256"]},ensure_ascii=False))
