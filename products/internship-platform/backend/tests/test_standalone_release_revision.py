"""Deployment readiness must match the committed standalone migration head."""
import ast
import re
from pathlib import Path

def test_production_expected_revision_matches_standalone_migration_head():
    product=Path(__file__).resolve().parents[2]
    revisions,parents=set(),set()
    for path in (product/'backend/alembic/versions').glob('*.py'):
        tree=ast.parse(path.read_text(encoding='utf-8'))
        values={}
        for node in tree.body:
            if isinstance(node,ast.Assign):
                for target in node.targets:
                    if isinstance(target,ast.Name) and target.id in {'revision','down_revision'}:
                        values[target.id]=ast.literal_eval(node.value)
        if values.get('revision'): revisions.add(values['revision'])
        previous=values.get('down_revision')
        if previous: parents.update(previous if isinstance(previous,(tuple,list)) else [previous])
    expected=re.search(r'EXPECTED_ALEMBIC_REVISION:-([^}]+)',(product/'deploy/docker-compose.production.yml').read_text(encoding='utf-8')).group(1)
    assert revisions-parents=={expected}
