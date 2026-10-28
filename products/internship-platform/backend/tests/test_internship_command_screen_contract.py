"""Pure contract checks. These do NOT substitute for the MySQL / permission integration gate."""
import ast
import importlib.util
from datetime import date
from pathlib import Path
import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'app/modules/internship/services'
spec = importlib.util.spec_from_file_location('ix_screen_rules', SOURCE / 'internship_command_screen_rules.py')
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)

@pytest.mark.parametrize('value,code', [
    ('广东省深圳市','440000'), (' 湖南省 ','430000'), ('北京市朝阳区','110000'),
    ('内蒙古自治区','150000'), ('香港特别行政区','810000'), ('台湾省','710000'),
    ('440000','440000'), ('深圳市','UNKNOWN'), ('','UNKNOWN'), (None,'UNKNOWN'),
    ('境外机构','UNKNOWN'), ('上海','310000'), ('陕西省','610000'), ('山西省','140000'),
])
def test_explicit_region_only(value, code):
    assert rules.region_code(value) == code

@pytest.mark.parametrize('day,first,last', [
    (date(2026,9,6),'2026-04','2026-09'), (date(2026,1,1),'2025-08','2026-01'),
    (date(2024,2,29),'2023-09','2024-02'),
])
def test_month_window(day, first, last):
    keys = rules.month_keys(day)
    assert len(keys) == 6 and keys[0] == first and keys[-1] == last

@pytest.mark.parametrize('n', [0,13,-1])
def test_invalid_month_window(n):
    with pytest.raises(ValueError): rules.month_keys(date(2026,9,6), n)

def test_region_codes_are_unique():
    assert len(rules.REGIONS) == 34
    assert len({r[0] for r in rules.REGIONS}) == 34

def test_projection_is_read_only():
    tree = ast.parse((SOURCE / 'internship_command_screen_service.py').read_text(encoding='utf-8'))
    forbidden = {'commit','flush','add','add_all','delete','update','execute_write','bulk_save_objects'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden

def test_no_individual_coordinates_or_identity_returned():
    tree = ast.parse((SOURCE / 'internship_command_screen_service.py').read_text(encoding='utf-8'))
    keys = {k.value for n in ast.walk(tree) if isinstance(n, ast.Dict) for k in n.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert not keys & {'realName','studentNo','phone','lat','lng','latitude','longitude','address'}

def test_scope_and_clock_are_existing_authorities():
    source = (SOURCE / 'internship_command_screen_service.py').read_text(encoding='utf-8')
    assert 'apply_internship_record_scope(query, user)' in source
    assert 'resolve_batch(db, batch_id, for_write=False)' in source
    assert 'local_day_bounds_utc' in source
    assert 'datetime.now(' not in source
