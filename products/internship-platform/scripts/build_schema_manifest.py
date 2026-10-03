#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path

from app.models.base import Base
import app.models  # noqa: F401

root=Path(__file__).resolve().parents[1]
out=root/"artifacts"/"schema-manifest.json"
tables=[]
for table in sorted(Base.metadata.tables.values(),key=lambda t:t.name):
    columns=[]
    for col in table.columns:
        columns.append({
            "name":col.name,
            "type":str(col.type),
            "nullable":bool(col.nullable),
            "primaryKey":bool(col.primary_key),
            "unique":bool(col.unique),
        })
    tables.append({"name":table.name,"columns":columns})
canonical=json.dumps(tables,ensure_ascii=False,sort_keys=True,separators=(",",":"))
payload={
    "schemaVersion":1,
    "tableCount":len(tables),
    "tables":tables,
    "fingerprint":"sha256:"+hashlib.sha256(canonical.encode()).hexdigest(),
}
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"tableCount":payload["tableCount"],"fingerprint":payload["fingerprint"]},ensure_ascii=False))
