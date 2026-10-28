import pytest
from sqlalchemy.engine import make_url
from test_standalone_browser_auth_mysql import _allowed_auth_test_target


@pytest.mark.parametrize('host,port,database,environment,opted_in,allowed', [
    ('127.0.0.1', 3306, 'internship_employment_test_ci', 'test', True, True),
    ('127.0.0.1', 3306, 'internship_employment_test_ci', 'production', True, False),
    ('127.0.0.1', 3306, 'internship_employment_test_ci', 'test', False, False),
    ('127.0.0.1', 3306, 'internship_independent_test_20261025_v2', 'test', True, False),
    ('remote.invalid', 3306, 'internship_employment_test_ci', 'test', True, False),
    ('127.0.0.1', 3318, 'internship_employment_test_ci', 'test', True, False),
])
def test_auth_fixture_never_accepts_retained_runtime_or_unapproved_target(host, port, database, environment, opted_in, allowed):
    url = make_url(f'mysql+pymysql://fixture@{host}:{port}/{database}')
    assert _allowed_auth_test_target(url, environment, False, opted_in) is allowed


def test_local_release_dashboard_suite_requires_its_explicit_opt_in(monkeypatch):
    import test_student_pc_dashboard_reports_mysql as suite
    monkeypatch.setenv('GAP09_MYSQL_ACCEPTANCE', '1')
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.delenv('RELEASE_MYSQL_ACCEPTANCE', raising=False)
    monkeypatch.setattr(suite.settings, 'APP_ENV', 'test')
    monkeypatch.setattr(suite.settings, 'DATABASE_URL', 'mysql+pymysql://fixture@127.0.0.1:3306/internship_employment_test_ci')
    monkeypatch.setattr(suite, 'seed_flow', lambda: {'seeded': True})
    with pytest.raises(AssertionError):
        suite.story.__wrapped__()
    monkeypatch.setenv('RELEASE_MYSQL_ACCEPTANCE', '1')
    assert suite.story.__wrapped__() == {'seeded': True}
