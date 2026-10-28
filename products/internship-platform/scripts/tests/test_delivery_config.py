"""Synthetic configuration contracts only; no DNS, network, database or deployment."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_delivery_config import main, public_enterprise_url, read_config, validate_config


class DeliveryConfigTest(unittest.TestCase):
    def valid(self):
        return {'ENTERPRISE_PORTAL_BASE_URL': 'https://internships.school.edu.cn/enterprise',
            'COMPOSE_PROFILES': 'attendance', 'ATTENDANCE_TENANT_ID': '7', 'ATTENDANCE_BATCH_ID': '9007199254741003'}

    def test_complete_synthetic_configuration_and_proxy_path(self):
        self.assertEqual(validate_config(self.valid()), [])
        self.assertTrue(public_enterprise_url('https://internships.school.edu.cn:8443/enterprise/'))
        proxy = Path(__file__).resolve().parents[2] / 'deploy/nginx/internship.conf'
        self.assertIn('location /enterprise/', proxy.read_text(encoding='utf-8'))

    def test_missing_profile_or_explicit_target_never_qualifies(self):
        for key in self.valid():
            with self.subTest(key=key):
                values = self.valid(); del values[key]
                self.assertTrue(validate_config(values))
        for value in ['', '0', '-1', '1.5', '${BATCH_ID}', '9223372036854775808']:
            with self.subTest(value=value):
                self.assertTrue(validate_config({**self.valid(), 'ATTENDANCE_BATCH_ID': value}))
        self.assertTrue(validate_config({**self.valid(), 'COMPOSE_PROFILES': 'backup'}))
        self.assertEqual(validate_config({**self.valid(), 'COMPOSE_PROFILES': 'backup, attendance'}), [])

    def test_url_rejects_insecure_local_placeholder_credentials_or_wrong_proxy_path(self):
        for value in ['http://internships.school.edu.cn/enterprise', 'https://localhost/enterprise',
            'https://127.0.0.1/enterprise', 'https://10.1.2.3/enterprise', 'https://[::1]/enterprise',
            'https://224.0.0.1/enterprise',
            'https://school.internal/enterprise', 'https://school.invalid/enterprise', 'https://example.com/enterprise',
            'https://user:private@internships.school.edu.cn/enterprise', 'https://internships.school.edu.cn/enterprise?token=private',
            'https://internships.school.edu.cn/enterprise#private', 'https://internships.school.edu.cn/',
            'https://internships.school.edu.cn/enterprise/other', 'https://internships.school.edu.cn:bad/enterprise']:
            with self.subTest(url=value):
                self.assertFalse(public_enterprise_url(value))

    def test_explicit_file_parsing_and_output_do_not_expose_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'candidate.env'
            path.write_text('\n'.join(f'{key}="{value}"' for key, value in self.valid().items())
                + '\nDB_PASSWORD=private-not-for-output\n', encoding='utf-8')
            self.assertEqual(read_config(path), self.valid())
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(['--env-file', str(path)]), 0)
            self.assertNotIn('private', output.getvalue())
            self.assertIn('尚未验证', output.getvalue())
            path.write_text('\n'.join(f'export {key}="{value}" # tracked setting' for key, value in self.valid().items()), encoding='utf-8')
            self.assertEqual(read_config(path), self.valid())
            path.write_text(path.read_text() + '\nATTENDANCE_BATCH_ID=9\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                read_config(path)

    def test_empty_school_example_is_installable_but_not_delivery_qualified(self):
        example = Path(__file__).resolve().parents[2] / 'deploy/env.production.example'
        self.assertTrue(validate_config(read_config(example)))


if __name__ == '__main__':
    unittest.main()
