"""Prepare synthetic pre-existing document facts in an explicitly isolated test database."""
import os, sys, json
from pathlib import Path
product = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(product/'backend'))
sys.path.insert(0, str(product/'backend/tests'))
from sqlalchemy.engine import make_url
from sqlalchemy import text
from app.config import settings
from app.db.session import get_sessionmaker
assert settings.APP_ENV == 'test' and os.environ.get('GAP09_MYSQL_ACCEPTANCE') == '1'
assert make_url(settings.DATABASE_URL).get_backend_name() == 'mysql'
assert '_test' in (make_url(settings.DATABASE_URL).database or '')
from test_standalone_browser_auth_mysql import _seed
from test_yiyang_gap09_minimum_age_mysql import scenario
from test_yiyang_sp06_sp07_formal_document_mysql import finished, own_client, generate, pdf
out = Path(os.environ['SP06_EVIDENCE_DIR']).resolve()
out.mkdir(parents=True, exist_ok=True)
_seed()
fixture = finished.__wrapped__(scenario.__wrapped__(None))
with own_client(fixture) as client:
    appraisal = generate(client, fixture)
    certificate = generate(client, fixture, 'INTERNSHIP_CERTIFICATE')
    (out/'enterprise-appraisal.pdf').write_bytes(pdf(client, fixture, appraisal))
    (out/'internship-certificate.pdf').write_bytes(pdf(client, fixture, certificate))
# Browser target has no generated document; UI must create the first version.
fixture = finished.__wrapped__(scenario.__wrapped__(None))
with get_sessionmaker()() as db:
    database = {'mysqlVersion': db.execute(text('select version()')).scalar(),
                'alembic': db.execute(text('select version_num from alembic_version')).scalar()}
(out/'seed.json').write_text(json.dumps({'fixture': fixture, 'database': database}, ensure_ascii=False, indent=2), encoding='utf-8')
print('Synthetic fixture and actual API-generated PDFs saved; credentials not logged.')