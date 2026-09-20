import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check/module-commercial-stage-gate.py"
spec = importlib.util.spec_from_file_location("m0_stage_gate", SCRIPT)
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
CONTRACT = json.loads((ROOT / "docs/07-部署运维交付与商业化/module-commerce/M0-stage-contract.json").read_text())


class StageGateTests(unittest.TestCase):
    def setUp(self):
        self.source = {"sourceSha": "a"*40, "sourceManifestHash": "b"*64,
                       "moduleMapping": {"canonicalFeatures": copy.deepcopy(CONTRACT["canonicalFeatures"])}}
        self.review = {"sourceSha":"a"*40,"sourceManifestHash":"b"*64,
                       "status":"DISPOSITIONS_VERIFIED_NOT_REMEDIATED","deletionAuthorized":False}
        self.boundary = {"sourceSha":"a"*40,"sourceManifestHash":"b"*64,
                         "status":"STRUCTURAL_BOUNDARY_ASSERTIONS_VERIFIED","deletionAuthorized":False}
        self.contract = copy.deepcopy(CONTRACT)

    def assess(self):
        return G.assess(self.source, self.review, self.boundary, self.contract)

    def test_m0_can_finish_without_authorizing_deletion(self):
        result = self.assess()
        self.assertTrue(result["m0Complete"])
        self.assertTrue(result["m1EntryApproved"])
        self.assertFalse(result["purgeScopeComplete"])
        self.assertFalse(result["deletionAuthorized"])
        self.assertEqual(result["destructiveExitGate"], "M5_M6_REVIEW_REQUIRED")

    def test_module_mapping_or_upstream_deletion_widening_blocks(self):
        self.contract["canonicalFeatures"]["internship"] = "employment"
        with self.assertRaises(ValueError): self.assess()
        self.setUp(); self.boundary["deletionAuthorized"] = True
        with self.assertRaises(ValueError): self.assess()

    def test_no_default_retention_days_may_be_invented(self):
        self.contract["retentionPolicy"]["defaultDays"] = 90
        with self.assertRaises(ValueError): self.assess()

    def test_named_recipient_and_backup_boundary_are_required(self):
        self.contract["schoolRecipientPolicy"]["namedRecipientRequired"] = False
        with self.assertRaises(ValueError): self.assess()
        self.setUp(); self.contract["backupDispositionPolicy"]["onlinePurgeDoesNotClaimBackupErasure"] = False
        with self.assertRaises(ValueError): self.assess()


if __name__ == "__main__":
    unittest.main()
