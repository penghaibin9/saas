"""Black-box regression for false procurement qualification, not a load result."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/g20_validate_evidence.py'
spec = importlib.util.spec_from_file_location('g20_validator', SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def evidence():
    return {
        'schemaVersion': 2, 'gate': 'G20', 'generator': 'k6', 'runMode': 'single-generator',
        'requestedVus': 5000, 'realRunAcknowledged': True, 'authConfigured': True,
        'authIdentityCount': 5000, 'businessScenarioConfigured': True,
        'configuredPaths': ['/health', '/api/v1/internship/dashboard?batchId=1'],
        'businessPaths': ['/api/v1/internship/dashboard?batchId=1'],
        'holdSeconds': 60,
        'identityVerification': {'method': 'server-auth-me', 'endpoint': '/api/v1/auth/me',
                                 'verifiedTokenCount': 5000, 'distinctAccountCount': 5000, 'allVerified': True},
        'operationalThresholds': {'p95Ms': 1500, 'p99Ms': 3000, 'maxErrorRate': 0.01},
        'thresholdStatus': {
            'http_req_failed': {'rate<0.01': True},
            'http_req_duration': {'p(95)<1500': True, 'p(99)<3000': True},
            'g20_business_duration': {'avg<=3000': True, 'p(95)<1500': True, 'p(99)<3000': True},
            'g20_business_failure': {'rate<0.01': True},
            'g20_hold_vus': {'min>=5000': True},
        },
        'metrics': {
            'http_reqs': {'values': {'count': 300000, 'rate': 3000}},
            'http_req_failed': {'values': {'rate': 0}},
            'http_req_duration': {'values': {'avg': 100, 'p(95)': 300, 'p(99)': 600}},
            'checks': {'values': {'rate': 1}},
            'g20_business_duration': {'values': {'avg': 100, 'p(95)': 300, 'p(99)': 600}},
            'g20_business_failure': {'values': {'rate': 0}},
            'g20_business_requests': {'values': {'count': 290000}},
            'g20_business_users': {'values': {'count': 5000}},
            'g20_hold_samples': {'values': {'count': 290000}},
            'g20_hold_vus': {'values': {'min': 5000, 'max': 5000, 'value': 5000}},
            'g20_hold_elapsed_seconds': {'values': {'min': 0.01, 'max': 59.99}},
        },
    }


class Qualification(unittest.TestCase):
    def assert_rejected(self, data):
        result = validator.validate(data)
        self.assertFalse(result['g20Qualified'], result)
        self.assertNotEqual(result['verdict'], 'PASS')
        return result

    def test_complete_measured_shape_can_qualify(self):
        self.assertTrue(validator.validate(evidence())['g20Qualified'])

    def test_average_above_three_seconds_is_rejected_despite_green_threshold_flags(self):
        data = evidence(); data['metrics']['http_req_duration']['values']['avg'] = 3000.01
        self.assert_rejected(data)

    def test_fast_health_requests_cannot_hide_slow_business(self):
        data = evidence(); data['metrics']['g20_business_duration']['values']['avg'] = 4000
        self.assert_rejected(data)

    def test_exact_three_seconds_is_allowed(self):
        data = evidence()
        for name in ('http_req_duration', 'g20_business_duration'):
            data['metrics'][name]['values']['avg'] = 3000
        self.assertTrue(validator.validate(data)['g20Qualified'])

    def test_legacy_claimed_vus_and_token_count_do_not_qualify(self):
        data = evidence(); data['schemaVersion'] = 1
        self.assert_rejected(data)

    def test_same_account_with_many_tokens_is_rejected(self):
        data = evidence(); data['identityVerification']['distinctAccountCount'] = 1
        self.assert_rejected(data)

    def test_unverified_accounts_are_rejected(self):
        data = evidence(); data['identityVerification']['allVerified'] = False
        self.assert_rejected(data)

    def test_actual_hold_below_requested_concurrency_is_rejected(self):
        data = evidence(); data['metrics']['g20_hold_vus']['values']['min'] = 4999
        self.assert_rejected(data)

    def test_peak_without_full_observation_window_is_rejected(self):
        data = evidence(); data['metrics']['g20_hold_elapsed_seconds']['values'] = {'min': 30, 'max': 31}
        self.assert_rejected(data)

    def test_not_all_distinct_users_ran_successful_business_is_rejected(self):
        data = evidence(); data['metrics']['g20_business_users']['values']['count'] = 4999
        self.assert_rejected(data)

    def test_missing_business_metrics_is_rejected(self):
        data = evidence(); del data['metrics']['g20_business_duration']
        self.assert_rejected(data)

    def test_numeric_invalid_values_do_not_qualify(self):
        for raw in (True, float('nan'), float('inf'), -1, '100'):
            with self.subTest(raw=raw):
                data = evidence(); data['metrics']['http_req_duration']['values']['avg'] = raw
                self.assert_rejected(data)

    def test_text_false_and_numeric_flags_are_not_true(self):
        for field in ('realRunAcknowledged', 'authConfigured', 'businessScenarioConfigured'):
            for raw in ('false', 1):
                with self.subTest(field=field, raw=raw):
                    data = evidence(); data[field] = raw
                    self.assert_rejected(data)

    def test_threshold_false_as_text_is_rejected(self):
        data = evidence(); data['thresholdStatus']['http_req_failed']['rate<0.01'] = 'false'
        self.assert_rejected(data)

    def test_missing_average_threshold_is_rejected(self):
        data = evidence(); del data['thresholdStatus']['g20_business_duration']['avg<=3000']
        self.assert_rejected(data)

    def test_threshold_flags_cannot_hide_actual_business_failures(self):
        data = evidence(); data['metrics']['g20_business_failure']['values']['rate'] = 0.2
        self.assert_rejected(data)

    def test_health_ready_is_not_business_load(self):
        data = evidence(); data['businessPaths'] = ['/health/ready']
        self.assert_rejected(data)

    def test_smoke_remains_unqualified(self):
        data = evidence(); data['requestedVus'] = 2
        self.assertEqual(self.assert_rejected(data)['verdict'], 'SMOKE_ONLY')

    def test_malformed_containers_are_rejected_without_attribute_errors(self):
        for field in ('metrics', 'thresholdStatus', 'identityVerification', 'operationalThresholds',
                      'configuredPaths', 'businessPaths'):
            with self.subTest(field=field):
                data = evidence(); data[field] = ['invalid']
                self.assert_rejected(data)
        data = evidence(); data['metrics']['http_req_duration']['values'] = ['invalid']
        self.assert_rejected(data)
        data = evidence(); data['thresholdStatus']['http_req_failed'] = ['invalid']
        self.assert_rejected(data)
        with self.assertRaises(validator.EvidenceError):
            validator.validate([])


if __name__ == '__main__':
    unittest.main()
