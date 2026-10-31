"""Read-only check: the independent website must not rejoin the school runtime."""
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def imports_school(source):
    for node in ast.walk(ast.parse(source)):
        names = [item.name for item in node.names] if isinstance(node, ast.Import) else (
            [node.module or ''] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
        )
        if any(name == 'app' or name.startswith('app.') for name in names):
            return True
    return False


def check(root):
    errors = []
    required = ('website/frontend/package-lock.json', 'website/frontend/src/app.js',
                'website/backend/website_app/main.py', 'website/local.py', 'website/package_release.py')
    errors.extend(f'官网源码缺失：{name}' for name in required if not (root / name).is_file())
    forbidden = {
        'frontend/src/main.js': ('installOfficialSeoRuntime', 'installOfficialWechatRuntime', 'OFFICIAL_SALES_PAGES'),
        'frontend/src/router/index.js': ('PortalHomeView',),
        'frontend/src/modules/platform/platform.routes.js': ('PlatformWebsiteNewsView',),
        'frontend/src/modules/platform/platformManagementCatalog.js': ('plt-website-news',),
        'backend/app/main.py': ('from app.api.v1.website_news',),
        'backend/app/api/v1/notification.py': ('@router.post("/website-lead"', '@router.get("/website-wechat-signature"'),
        'frontend/package.json': ('prerender-official-site',),
    }
    for name, tokens in forbidden.items():
        path = root / name
        if not path.is_file():
            errors.append(f'学校入口缺失：{name}')
        elif any(token in path.read_text(encoding='utf-8') for token in tokens):
            errors.append(f'学校仍注册官网功能：{name}')
    for path in (root / 'website/backend/website_app').rglob('*.py'):
        if imports_school(path.read_text(encoding='utf-8')):
            errors.append(f'官网导入学校应用：{path.relative_to(root)}')
    return errors


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        assert imports_school('from app.db.session import get_sessionmaker')
        assert imports_school('import app.services.news')
        assert not imports_school('from website_app.db import get_engine\nfrom . import app')
        print('边界识别自检通过。')
    else:
        errors = check(ROOT)
        print('\n'.join(errors) if errors else '官网与学校运行入口分离检查通过；这不代表业务验收或线上发布通过。')
        raise SystemExit(bool(errors))
