"""Trace source provenance to the actual Nhóm 07 report attached to this handoff.

Does not assume a prior hash recorded in legacy matrix represents same bytes.
"""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/source_materials/Report_DATN_CNTT_Nhom07_v1.0.docx'
EXPECTED_SHA256 = 'afa6de52170d73eb41a39f93a5d5b5a8a513d8b5cfac101f3f47b8091186c50a'


class SourceProvenanceTests(unittest.TestCase):
    def test_authoritative_report_is_present_and_unmodified(self):
        self.assertTrue(REPORT.is_file())
        hasher = hashlib.sha256()
        with REPORT.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                hasher.update(chunk)
        self.assertEqual(hasher.hexdigest(), EXPECTED_SHA256)

    def test_historical_matrix_is_not_misrepresented_as_same_document(self):
        matrix = json.loads((ROOT / 'docs/REPORT_V1_SOURCE_MATRIX.json').read_text(encoding='utf-8'))
        self.assertEqual(len(matrix['use_cases']), 16)
        self.assertEqual(len(matrix['business_rules']), 7)
        # Do not silently rewrite an older report's fingerprint.
        self.assertNotEqual(matrix['source']['sha256'], EXPECTED_SHA256)
        analysis = (ROOT / 'docs/PHAN_TICH_NGHIEP_VU_VA_KET_QUA_CODE_20261027.md').read_text(encoding='utf-8')
        self.assertIn(EXPECTED_SHA256, analysis)


if __name__ == '__main__':
    unittest.main()
