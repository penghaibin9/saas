"""Execute the recovery shell with a refused target; no real database is contacted."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'deploy/backup/restore-drill.sh'


@unittest.skipIf(os.name == 'nt', '部署恢复脚本在Linux容器中验证')
class RestoreGuardTest(unittest.TestCase):
    def test_existing_target_is_never_dropped_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bin').mkdir()
            docker = root / 'bin/docker'
            docker.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
case "$*" in
  *"CREATE DATABASE"*) echo 'target already exists' >&2; exit 1 ;;
esac
exit 0
''')
            docker.chmod(0o755)
            for name in ('database.sql.gz', 'files.tar.gz'):
                (root / name).write_bytes(gzip.compress(b'isolated fixture'))
            manifest = {'schemaVersion': 1, 'product': 'internship-standalone', 'backupSetId': 'test',
                'database': {'file': 'database.sql.gz', 'sha256': hashlib.sha256((root/'database.sql.gz').read_bytes()).hexdigest()},
                'files': {'file': 'files.tar.gz', 'sha256': hashlib.sha256((root/'files.tar.gz').read_bytes()).hexdigest()}}
            path = root / 'manifest.json'; path.write_text(json.dumps(manifest))
            (root / 'manifest.json.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest()+'  manifest.json\n')
            (root / 'local.env').touch()
            log = root / 'commands.log'
            env = {**os.environ, 'PATH': str(root/'bin')+os.pathsep+os.environ['PATH'],
                'FAKE_DOCKER_LOG': str(log), 'ENV_FILE': str(root/'local.env'), 'TMPDIR': str(root),
                'KEEP_DRILL_DB': '0'}
            result = subprocess.run(['bash', str(SCRIPT), str(path), 'already_exists_restore_test'], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('target already exists', result.stderr)
            commands = log.read_text()
            self.assertIn('CREATE DATABASE already_exists_restore_test', commands)
            self.assertNotIn('DROP DATABASE', commands)
            self.assertFalse(list(root.glob('internship-restore.*')))
            self.assertTrue(path.is_file())


if __name__ == '__main__':
    unittest.main()
