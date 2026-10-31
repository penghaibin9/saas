"""Repeatable local-only setup. Never resets existing databases or credentials."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / '.runtime'

def run(args, **kwargs):
    subprocess.run(args, check=True, cwd=ROOT, **kwargs)

def require_stopped_services():
    for port in (5210, 8012):
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError(f'本机端口 {port} 正在使用，请先停止对应的官网预览或服务，再重新初始化；未停止任何进程')

def prepare_databases():
    import pymysql
    values = dict(line.split('=',1) for line in (RUNTIME/'database.env').read_text().splitlines())
    with pymysql.connect(host='127.0.0.1',port=3310,user='root',password=values['MYSQL_ROOT_PASSWORD'],autocommit=True) as db:
        with db.cursor() as cursor:
            for name in ('test_website_acceptance','test_website_transfer'):
                cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
                cursor.execute(f"GRANT ALL PRIVILEGES ON `{name}`.* TO 'website'@'%'")

def main():
    parser = argparse.ArgumentParser(description='初始化官网本机独立环境，不读取学生配置，不覆盖现库')
    parser.add_argument('--with-sms',action='store_true',help='安装可选短信供应商依赖；不会发送短信')
    parser.add_argument('--prepare-databases',action='store_true',help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.prepare_databases:
        prepare_databases(); return
    require_stopped_services()
    RUNTIME.mkdir(exist_ok=True)
    if os.name == 'nt':
        who = subprocess.check_output(['whoami'],text=True).strip()
        run(['icacls',str(RUNTIME),'/inheritance:r','/grant:r',f'{who}:(OI)(CI)F','SYSTEM:(OI)(CI)F'],capture_output=True)
    else: RUNTIME.chmod(0o700)
    config, credentials = RUNTIME/'local.json', RUNTIME/'database.env'
    if config.exists() != credentials.exists(): raise RuntimeError('本地私有配置不完整，请核对现有文件；未覆盖凭据')
    if not config.exists():
        password, root_password = secrets.token_hex(24), secrets.token_hex(24)
        credentials.write_text(f'MYSQL_ROOT_PASSWORD={root_password}\nMYSQL_DATABASE=yueke_website_local\nMYSQL_USER=website\nMYSQL_PASSWORD={password}\n',encoding='utf-8')
        config.write_text(json.dumps({'WEBSITE_DATABASE_URL':f'mysql+pymysql://website:{password}@127.0.0.1:3310/yueke_website_local?charset=utf8mb4', 'WEBSITE_TEST_DATABASE_URL':f'mysql+pymysql://website:{password}@127.0.0.1:3310/test_website_acceptance?charset=utf8mb4', 'WEBSITE_ORIGIN':'http://127.0.0.1:5210', 'WEBSITE_LEAD_RATE_SALT':secrets.token_hex(32)},indent=2),encoding='utf-8')
    if os.name != 'nt':
        config.chmod(0o600);credentials.chmod(0o600)
    existing = subprocess.run(['docker','inspect','--format','{{index .Config.Labels "com.docker.compose.project.working_dir"}}','yueke-website-local-database-1'],capture_output=True,text=True,encoding='utf-8')
    if existing.returncode == 0 and Path(existing.stdout.strip()).resolve() != ROOT:
        raise RuntimeError('同名官网容器属于其他目录，未接管或重建')
    run(['docker','compose','-f','compose.local.yml','up','-d','--wait'])
    python = ROOT/'backend/.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.exists(): run([sys.executable,'-m','venv',str(ROOT/'backend/.venv')])
    run([str(python),'-m','pip','install','-r','backend/requirements-test.txt'])
    if args.with_sms: run([str(python),'-m','pip','install','-r','backend/requirements-sms.txt'])
    run([str(python),str(Path(__file__).resolve()),'--prepare-databases'])
    run([str(python),'local.py','migrate'])
    npm = 'npm.cmd' if os.name=='nt' else 'npm'
    run([npm,'--prefix','frontend','ci'])
    run([npm,'--prefix','frontend','run','build'])
    print('官网本机独立环境已准备。未创建默认管理密码，未发送短信或执行生产发布。')

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        raise SystemExit('官网本地初始化未完成：' + (str(exc) if type(exc) is RuntimeError else type(exc).__name__))
