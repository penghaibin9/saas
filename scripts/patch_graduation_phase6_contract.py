from pathlib import Path

path = Path("backend/tests/test_graduation_material_center_phase6.py")
text = path.read_text(encoding="utf-8")
old = '''    assert "svc.get_proposal_detail" in proposal_detail and "material_records.review" not in proposal_detail
    assert "svc.get_final_detail" in final_detail and "material_records.review" not in final_detail
'''
new = '''    assert "material_queries.proposal_detail" in proposal_detail and "material_records.review" not in proposal_detail
    assert "material_queries.final_detail" in final_detail and "material_records.review" not in final_detail
'''
if text.count(old) != 1:
    raise SystemExit(f"phase6 secure-detail contract replacement count={text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
