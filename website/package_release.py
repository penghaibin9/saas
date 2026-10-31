"""Package only the independent website; never discover secrets by a broad glob."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
DIRECTORIES = ('backend/website_app', 'backend/migrations', 'backend/tests', 'frontend/src',
               'frontend/public', 'frontend/scripts', 'frontend/tests', 'frontend/dist', 'deploy', 'materials')
FILES = ('README.md', 'products.json', 'design-qa.md', '.gitignore', 'local.py', 'setup_local.py', 'package_release.py',
         'compose.local.yml', 'backend/alembic.ini', 'backend/requirements.txt',
         'backend/requirements-test.txt', 'backend/requirements-sms.txt',
         'frontend/package.json', 'frontend/package-lock.json', 'frontend/index.html',
         'frontend/vite.config.js')
EXCLUDED = {'.runtime', '.venv', 'node_modules', '__pycache__', '.pytest_cache', '.ssr'}


def release_files(root=ROOT):
    paths = [root / name for name in FILES]
    for directory in DIRECTORIES:
        paths.extend(path for path in (root / directory).rglob('*') if path.is_file())
    for path in sorted(set(paths)):
        relative = path.relative_to(root)
        if EXCLUDED.intersection(relative.parts) or path.suffix in {'.pyc', '.log'}:
            continue
        if path.name == '.env' or path.name.startswith('.env.'):
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise RuntimeError('交付源文件包含外部链接，已停止打包')
        if not path.is_file():
            raise RuntimeError('缺少官网交付文件：' + relative.as_posix())
        yield path, relative.as_posix()


def package(output):
    # This helper writes only to the ignored local release directory.
    release_dir = (ROOT / '.runtime/releases').resolve()
    if output.resolve().parent != release_dir or output.suffix != '.zip':
        raise RuntimeError('交付包只能写入官网 .runtime/releases 目录')
    required = ['index.html', 'manage/index.html', 'sitemap.xml', 'sitemap-pages.xml',
                'products/renshi/index.html', '404.html']
    if any(not (ROOT / 'frontend/dist' / name).is_file() for name in required):
        raise RuntimeError('请先完成独立官网构建，再制作交付包')
    entries = list(release_files())
    manifest = {name: hashlib.sha256(path.read_bytes()).hexdigest() for path, name in entries}
    requirements = ROOT / 'requirements.md'
    if not requirements.exists():
        requirements = ROOT.parent / 'docs/06-开发施工与质量验收/官网多产品与新闻运营-PRD整改方案.md'
    requirement_bytes = requirements.read_bytes()
    manifest['requirements.md'] = hashlib.sha256(requirement_bytes).hexdigest()
    commit = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip()
    release_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path, name in entries:
            archive.write(path, 'website/' + name)
        archive.writestr('website/requirements.md', requirement_bytes)
        archive.writestr('website/release-manifest.json', json.dumps({
            'format': 1, 'files': manifest,
            'sourceCommit': commit or None, 'sourceState': 'local uncommitted candidate',
            'createdAt': datetime.now(timezone.utc).isoformat(),
            'scope': 'independent website only; no credentials or production data'
        }, indent=2))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('交付包完整性检查失败')
        for name, digest in manifest.items():
            if hashlib.sha256(archive.read('website/' + name)).hexdigest() != digest:
                raise RuntimeError('交付包内容校验失败')
    return len(manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='制作独立官网交付包；排除本机凭据和业务数据')
    parser.add_argument('name', help='新的交付包文件名，不含目录')
    args = parser.parse_args()
    if Path(args.name).name != args.name:
        parser.error('只填写文件名')
    try:
        count = package(ROOT / '.runtime/releases' / args.name)
    except FileExistsError:
        raise SystemExit('同名交付包已存在，未覆盖')
    print(f'独立官网交付包已生成并逐文件校验，共 {count} 个文件；未包含本机配置和数据库。')
