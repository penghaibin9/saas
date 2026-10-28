"""Build and package this product without its parent repository or private runtime data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SURFACES = ('admin-web', 'student-web', 'enterprise-web', 'mobile')
SOURCE_DIRS = (*SURFACES, 'backend', 'deploy', 'scripts', 'shared', 'load')
EXCLUDED = {'node_modules', '.venv', '__pycache__', '.pytest_cache', '.git', 'dist', 'unpackage', 'certs', 'backups', 'playwright-report'}
RECEIPT = '.product-build.json'
OUTPUTS = ('admin-web/dist', 'student-web/dist', 'enterprise-web/dist', 'mobile/dist/build/h5')


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def source_files(root: Path) -> list[Path]:
    result = [root / 'README.md']
    result.extend(root / name for name in ('.gitignore', '.gitattributes') if (root / name).is_file())
    for name in ('YIYANG_C09_PRODUCTION_DELIVERY_RUNBOOK_20260929.md', '01-PR275-Standalone-总体任务与施工总控.md'):
        guide = root / 'docs' / name
        if guide.is_file():
            result.append(guide)
    for name in SOURCE_DIRS:
        if (root / name).is_symlink():
            raise ValueError('交付目录不能包含符号链接：' + name)
        for directory, dirs, files in os.walk(root / name, followlinks=False):
            base = Path(directory)
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not d.startswith('test-results')
                and not (base == root / 'backend' and d == 'data'))
            for entry in dirs:
                if (base / entry).is_symlink():
                    raise ValueError('交付目录不能包含符号链接：' + str((base / entry).relative_to(root)))
            for filename in sorted(files):
                path = base / filename
                if filename.startswith('.env') or filename.endswith(('.pyc', '.log', '.key', '.pem', '.pfx', '.p12', '.db', '.sqlite', '.sqlite3')) or '.private.' in filename:
                    continue
                if path.is_symlink():
                    raise ValueError('交付文件不能包含符号链接：' + str(path.relative_to(root)))
                result.append(path)
    for path in result:
        if path.is_symlink() or root.resolve() not in path.resolve().parents:
            raise ValueError('交付文件超出产品目录')
        if path.suffix in {'.sh', '.conf'} and b'\r' in path.read_bytes():
            raise ValueError('服务器维护脚本必须使用Linux换行格式：' + str(path.relative_to(root)))
    return sorted(result)


def hashes(root: Path, files: list[Path]) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): digest(path) for path in files}


def built_files(root: Path) -> list[Path]:
    result = []
    for folder in OUTPUTS:
        target = root / folder
        if not (target / 'index.html').is_file():
            raise ValueError('尚未完成构建：' + folder)
        for path in sorted(target.rglob('*')):
            if path.is_symlink():
                raise ValueError('构建产物不能包含符号链接')
            if path.is_file():
                result.append(path)
    return result


def run(command: list[str], cwd: Path, env=None) -> None:
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    if completed.returncode:
        raise ValueError(f'检查或构建失败，退出码 {completed.returncode}；已停止后续打包。')


def check(root: Path) -> str:
    from check_schema_revision_contract import check_contract
    head, _, errors = check_contract(root)
    if errors:
        raise ValueError('\n'.join(errors))
    for surface in SURFACES:
        if not (root / surface / 'package-lock.json').is_file():
            raise ValueError('缺少固定依赖清单：' + surface)
    for name in ('check_forbidden_imports.py', 'check_admin_import_closure.py', 'check_mobile_import_closure.py'):
        run([sys.executable, str(root / 'scripts' / name)], root)
    print('独立源码入口检查通过；不代表生产部署或业务验收通过。')
    return head


def web_base_path(value: str) -> str:
    if value == '/':
        return ''
    if not re.fullmatch(r'/[a-z0-9_-]+(?:/[a-z0-9_-]+)*/?', value):
        raise ValueError('网页部署路径必须为根路径或小写路径段，例如 /internship/')
    return value.rstrip('/')


def build(root: Path, base_path: str = '/') -> None:
    prefix = web_base_path(base_path)
    head = check(root)
    before = hashes(root, source_files(root))
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        raise ValueError('未找到前端构建工具，请先安装项目要求的运行环境。')
    for surface in SURFACES:
        run([npm, 'ci', '--no-audit', '--no-fund'], root / surface)
    run([npm, 'exec', '--', 'playwright', 'install', 'chromium'], root / 'enterprise-web')
    audits = root / '.product-audits'
    audits.mkdir(exist_ok=True)
    for surface in SURFACES:
        cwd = root / surface
        audited = subprocess.run([npm, 'audit', '--omit=dev', '--json'], cwd=cwd, capture_output=True)
        audit = audits / (surface + '.json')
        audit.write_bytes(audited.stdout)
        if audited.returncode not in (0, 1):
            raise ValueError('生产依赖审计无法完成：' + surface)
        run([shutil.which('node') or 'node', str(root / 'enterprise-web/scripts/check-production-audit-report.mjs'), str(audit)], root)
        run([npm, 'test'], cwd)
        env = dict(os.environ)
        env['VITE_API_BASE_URL'] = prefix or '/'
        env['VITE_BASE'] = prefix + ({'admin-web': '/', 'student-web': '/student/', 'enterprise-web': '/enterprise/', 'mobile': '/mobile/'}[surface])
        env['VITE_STORAGE_SCOPE'] = 'internship' if prefix else ''
        # Packaged H5 uses the same HTTPS gateway; native WeChat is built separately for its explicit domain.
        if surface == 'mobile':
            env['VITE_API_BASE_URL'] = prefix or '/'
        run([npm, 'run', 'build:h5' if surface == 'mobile' else 'build'], cwd, env)
    after = hashes(root, source_files(root))
    if before != after:
        raise ValueError('构建过程中源码发生变化，请核对后重新构建。')
    receipt = {'product': 'internship-standalone', 'schemaRevision': head, 'webBasePath': prefix,
        'createdAtUtc': datetime.now(timezone.utc).isoformat(),
        'sourceFiles': after, 'buildFiles': hashes(root, built_files(root)),
        'auditFiles': hashes(root, sorted(audits.glob('*.json'))),
        'verification': 'local-build-and-frontend-tests', 'productionAccepted': False,
        'wechatHostVerified': False}
    (root / RECEIPT).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print('四个网页工程构建及自动检查通过，可生成独立交付包。')


def package(root: Path, output: Path) -> None:
    receipt = json.loads((root / RECEIPT).read_text(encoding='utf-8'))
    sources, outputs = source_files(root), built_files(root)
    if receipt.get('product') != 'internship-standalone' or receipt.get('sourceFiles') != hashes(root, sources) or receipt.get('buildFiles') != hashes(root, outputs):
        raise ValueError('源码或构建产物已变化，不能复用旧构建回执。')
    audits = [root / '.product-audits' / (surface + '.json') for surface in SURFACES]
    if receipt.get('auditFiles') != hashes(root, audits):
        raise ValueError('依赖审计证据已变化，请重新构建。')
    output = output.resolve()
    if output == root or root in output.parents:
        raise ValueError('交付包请保存到产品目录以外。')
    if output.exists():
        raise ValueError('目标文件已存在，请使用新的交付文件名。')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sources + outputs + audits:
            archive.write(path, path.relative_to(root).as_posix())
        archive.writestr('delivery-manifest.json', json.dumps(receipt, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():
            raise ValueError('交付包完整性检查失败。')
        for name, expected in {**receipt['sourceFiles'], **receipt['buildFiles'], **receipt.get('auditFiles', {})}.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError('交付文件在打包过程中发生变化，不能发布。')
    output.with_suffix(output.suffix + '.sha256').write_text(digest(output) + '  ' + output.name + '\n', encoding='utf-8')
    print('独立交付包已生成：' + str(output))


def main() -> int:
    parser = argparse.ArgumentParser(description='独立岗位实习产品的检查、构建与交付打包')
    parser.add_argument('action', choices=['check', 'build', 'package'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--web-base-path', default='/')
    args = parser.parse_args()
    try:
        if args.action == 'check':
            check(ROOT)
        elif args.action == 'build':
            build(ROOT, args.web_base_path)
        else:
            if not args.output:
                parser.error('打包必须指定 --output')
            package(ROOT, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print('独立产品交付未完成：' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
