"""Build a real AA-002 roster-import XLSX fixture for the Browser gate."""
from __future__ import annotations

import json
import os
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "backend/tmp/e2e_academic_aa002_state.local.json"
XLSX_PATH = ROOT / "e2e/fixtures/aa002-roster-import.xlsx"
CLASS_NAME = "E2E机器人2401班"


def main() -> int:
    run_id = str(os.getenv("GITHUB_RUN_ID") or "local")[-8:]
    suffix = run_id.replace("-", "")
    rows = [
        {"studentNo": f"D2X{suffix}01", "realName": f"AA002甲{suffix[-4:]}", "gender": "男",
         "idCard": "", "className": CLASS_NAME, "initialStatus": "PENDING_REGISTER"},
        {"studentNo": f"D2X{suffix}02", "realName": f"AA002乙{suffix[-4:]}", "gender": "女",
         "idCard": "", "className": CLASS_NAME, "initialStatus": "PENDING_REGISTER"},
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "导入模板"
    ws.append(["学号 *", "姓名 *", "性别", "身份证号", "班级 *", "初始学籍状态"])
    for row in rows:
        ws.append([row["studentNo"], row["realName"], row["gender"], row["idCard"], row["className"], row["initialStatus"]])
    XLSX_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(XLSX_PATH)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"className": CLASS_NAME, "rows": rows, "xlsxPath": str(XLSX_PATH.relative_to(ROOT))}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"xlsx": str(XLSX_PATH), "studentNos": [r["studentNo"] for r in rows]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
