from urllib.parse import urlsplit,parse_qs
from app.api.v1.dashboard import _current_workbench_path

def test_old_role_shortcut_projects_to_canonical_workspace_without_losing_object():
    source='/admin/system/roles?roleId=9007199254740993&tab=members&_workspace=old#details'
    target=urlsplit(_current_workbench_path(source));query=parse_qs(target.query)
    assert target.path=='/admin/system/iam' and target.fragment=='details'
    assert query=={'roleId':['9007199254740993'],'tab':['members'],'surface':['roles']}
    assert 'roles?' in source
    templates=urlsplit(_current_workbench_path('/admin/system/roles?tab=templates'))
    assert parse_qs(templates.query)=={'surface':['templates']}

def test_role_shortcut_projection_does_not_touch_other_systems_or_paths():
    for value in [None,'/admin/system/roles-extra','/admin/system/accounts/staff','https://other.example/admin/system/roles']:
        assert _current_workbench_path(value)==value
