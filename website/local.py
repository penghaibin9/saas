"""Local website launcher; reads ignored, private configuration without printing it."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
def main():
    active_profile = ROOT / '.runtime/active-profile.txt'
    profile = os.environ.get('WEBSITE_LOCAL_CONFIG')
    if profile is None:
        profile = active_profile.read_text(encoding='utf-8').strip() if active_profile.exists() else 'local.json'
    import re
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.json', profile):
        raise SystemExit('官网本机配置必须位于自己的私有运行目录')
    config = ROOT / '.runtime' / profile
    if not config.exists():
        raise SystemExit('请先配置官网本机独立环境，详见 website/README.md')
    env = {**os.environ, **json.loads(config.read_text(encoding='utf-8'))}
    # Use an independently installed interpreter if available, else current one.
    python = ROOT / 'backend/.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    python = str(python) if python.exists() else sys.executable
    commands = {
        'migrate': [python, '-m', 'alembic', 'upgrade', 'head'],
        'serve': [python, '-m', 'uvicorn', 'website_app.main:app', '--host', '127.0.0.1', '--port', '8012'],
        'worker': [python, '-m', 'website_app.worker'],
        'consultation-worker': [python, '-m', 'website_app.retention_worker'],
        'test': [python, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
        'manage': [python, '-m', 'website_app.manage', *sys.argv[2:]],
        'transfer': [python, '-m', 'website_app.news.transfer', *sys.argv[2:]],
    }
    action = sys.argv[1] if len(sys.argv) > 1 else ''
    if action not in commands:
        raise SystemExit('用法：local.py migrate | serve | worker | consultation-worker | test | manage ...')
    if action == 'worker':
        env['WEBSITE_NEWS_WORKER_ENABLED'] = 'true'
    if action == 'test':
        env['WEBSITE_DATABASE_URL'] = env.pop('WEBSITE_TEST_DATABASE_URL')
        env['WEBSITE_TEST_REQUIRED'] = 'true'
    raise SystemExit(subprocess.call(commands[action], cwd=ROOT/'backend', env=env))
if __name__ == '__main__':
    main()
