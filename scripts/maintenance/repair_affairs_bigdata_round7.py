from pathlib import Path


def replace_all(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise RuntimeError(f"bigdata repair anchor missing: {path}: {old!r}")
    file.write_text(text.replace(old, new), encoding="utf-8")


def patch_phase2() -> None:
    path = "backend/tests/test_affairs_phase2_bigdata.py"
    replace_all(path, 'status="REVIEW" if i <= half else "APPROVED"',
                'status="COUNSELOR_REVIEW" if i <= half else "APPROVED"')
    replace_all(path, '"REVIEW", COUNT // 2,', '"COUNSELOR_REVIEW", COUNT // 2,')
    replace_all(
        path,
        '''                    statement="二阶段大数据困难认定申请说明不少于十字",
                    status="COUNSELOR_REVIEW" if i <= half else "APPROVED",
''',
        '''                    statement="二阶段大数据困难认定申请说明不少于十字",
                    status="COUNSELOR_REVIEW" if i <= half else "APPROVED",
                    is_deleted=False, version=0,
''',
    )


def patch_round2() -> None:
    path = "backend/tests/test_affairs_round2_bigdata.py"
    replace_all(path, 'status="REVIEW" if index <= 225 else "APPROVED"',
                'status="COUNSELOR_REVIEW" if index <= 225 else "APPROVED"')
    replace_all(path, '"status": "REVIEW",', '"status": "COUNSELOR_REVIEW",')
    replace_all(
        path,
        '''                statement="家庭经济困难，需要学校资助支持完成学业。",
                status="COUNSELOR_REVIEW" if index <= 225 else "APPROVED",
''',
        '''                statement="家庭经济困难，需要学校资助支持完成学业。",
                status="COUNSELOR_REVIEW" if index <= 225 else "APPROVED",
                is_deleted=False, version=0,
''',
    )


def patch_contract() -> None:
    Path("backend/tests/test_affairs_bigdata_status_contract.py").write_text('''from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_bigdata_seeds_only_current_aid_states():
    for name in ("test_affairs_phase2_bigdata.py", "test_affairs_round2_bigdata.py"):
        text = (ROOT / "backend/tests" / name).read_text(encoding="utf-8")
        assert 'status="REVIEW"' not in text
        assert '"status": "REVIEW"' not in text
        assert "COUNSELOR_REVIEW" in text
        assert "is_deleted=False, version=0" in text
''', encoding="utf-8")


if __name__ == "__main__":
    patch_phase2()
    patch_round2()
    patch_contract()
    print("student affairs bigdata round7 passed", flush=True)
