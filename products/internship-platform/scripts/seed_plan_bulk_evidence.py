"""Create a unique synthetic school for real plan-selection/export browser acceptance."""
import sys, json, os
from pathlib import Path
product = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(product/'backend'))
sys.path.insert(0, str(product/'backend/tests'))
from test_yiyang_plan_export_options_mysql import seed_workspace
out = Path(os.environ['BULK_EVIDENCE_DIR'])
out.mkdir(parents=True, exist_ok=True)
workspace = seed_workspace(23)
(out/'seed.json').write_text(json.dumps(workspace, ensure_ascii=False, indent=2), encoding='utf-8')
print('Unique synthetic school with 23 pre-existing plans created; no existing school data changed.')
