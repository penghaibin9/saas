"""Synthetic user setup only. Actual submissions and reviews are done in the browser."""
import os,sys,json
from pathlib import Path
product=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(product/'backend'));sys.path.insert(0,str(product/'backend/tests'))
from test_yiyang_write_flows_mysql import seed_flow,png_bytes
assert os.environ.get('GAP09_MYSQL_ACCEPTANCE')=='1'
folder=Path(os.environ['WRITE_EVIDENCE_DIR']); folder.mkdir(parents=True,exist_ok=True)
flow=seed_flow()
(folder/'flow.json').write_text(json.dumps(flow,ensure_ascii=False,indent=2),encoding='utf-8')
(folder/'insurance.png').write_bytes(png_bytes());(folder/'report.png').write_bytes(png_bytes())
from PIL import Image
Image.new('RGB',(180,120),(220,250,230)).save(folder/'report-corrected.png',format='PNG')
print('Synthetic accounts and pre-existing assignment created; no insurance or reports submitted.')
