"""Package import aliases must preserve the actual exported-symbol boundary."""
import importlib.util
from pathlib import Path
import pytest


@pytest.mark.parametrize('statement,missing', [
    ('from app.models import KnownModel as LocalModel', []),
    ('from app.models import MissingModel as KnownModel', ['app.models.MissingModel']),
])
def test_alias_does_not_change_the_requested_package_export(tmp_path, monkeypatch, statement, missing):
    script=Path(__file__).resolve().parents[2]/'scripts/check_w2_import_closure.py'
    spec=importlib.util.spec_from_file_location('standalone_import_closure_check',script)
    checker=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    app=tmp_path/'app'
    (app/'api').mkdir(parents=True)
    (app/'models').mkdir()
    (app/'__init__.py').write_text('',encoding='utf-8')
    (app/'api/__init__.py').write_text('',encoding='utf-8')
    (app/'api/router.py').write_text(statement+'\n',encoding='utf-8')
    (app/'models/__init__.py').write_text('class KnownModel:\n    pass\n',encoding='utf-8')
    monkeypatch.setattr(checker,'APP',app)
    _,actual=checker.scan('app.api.router')
    assert actual==missing
