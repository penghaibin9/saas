"""Run directly with unittest; no database fixture or cleanup is involved."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import SQLAlchemyError
from app.core.exceptions import AppException
from app.modules.internship.services import internship_guidance_service as service


class GuidanceBatchReceiptTest(unittest.TestCase):
    def test_per_student_key_and_uncertain_result_without_database(self):
        body = {
            'batchId': 18, 'guidanceDate': '2026-10-06', 'method': 'PHONE', 'content': '并行A-指导',
            'items': [{'internshipId': str(i), 'requestKey': f'parallel-a-guidance-{i}'} for i in range(1, 5)],
        }
        with patch.object(service, 'create', side_effect=[
            {'id': '901', 'internshipId': '1', 'batchId': '18'},
            AppException('NO_PERMISSION', '指导关系已撤销', http_status=403),
            AppException('AUDIT_UNAVAILABLE', '留痕暂不可用', http_status=503),
            SQLAlchemyError('synthetic database failure'),
        ]) as create:
            result = service.create_batch({'id': '1'}, body)
        self.assertEqual(create.call_count, 4)
        self.assertEqual((result['successCount'], result['failedCount']), (1, 3))
        self.assertEqual([row['requestKey'] for row in result['items']], [row['requestKey'] for row in body['items']])
        self.assertFalse(result['items'][1]['saveUnconfirmed'])
        self.assertTrue(result['items'][2]['saveUnconfirmed'])
        self.assertTrue(result['items'][3]['saveUnconfirmed'])
        self.assertNotIn('synthetic', result['items'][3]['message'])


if __name__ == '__main__':
    unittest.main()
