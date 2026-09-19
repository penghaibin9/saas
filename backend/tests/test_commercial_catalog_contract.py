"""M1 pure draft contracts; not a substitute for MySQL/API/publication tests."""
import ast
import copy
import json
from decimal import Decimal, localcontext
import importlib.util
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / 'app/services/commercial_catalog_contract.py'
spec = importlib.util.spec_from_file_location('commercial_catalog_contract_tests_subject', PATH)
c = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c
spec.loader.exec_module(c)
DEFAULTS = PATH.parent / 'platform_defaults.py'
FEATURES = ast.literal_eval(next(node.value for node in ast.parse(DEFAULTS.read_text(encoding='utf-8')).body
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FEATURE_KEYS' for t in node.targets)))
SCOPES = {key: (feature, 'studentProfile', 'fileUpload', 'apiAccess') for key, feature in c.MODULE_FEATURES.items()}


def sku_payload(module='internship', revision=1):
    return {'skuCode': module + '-standard', 'revision': revision, 'name': '测试商品，不是实际报价',
            'productType': 'MODULE', 'moduleKey': module,
            'features': {c.MODULE_FEATURES[module]: True, 'studentProfile': True},
            'quotas': {'students': {'limit': 3000, 'unit': 'people', 'aggregation': 'MAX'}},
            'pricePolicy': {'unitPrice': '100.00', 'currency': 'CNY', 'taxTreatment': 'UNSPECIFIED'},
            'lifecyclePolicyVersion': 'TEST-POLICY-1'}


def sku(payload=None):
    return c.compile_sku(payload or sku_payload(), known_features=FEATURES, approved_features=SCOPES)


def order_payload(snapshot):
    item = snapshot.as_dict()
    return {'tenantId': '1000000000000000003', 'currency': 'CNY', 'totalAmount': '100.00', 'items': [
        {'lineNo': 1, 'skuCode': item['skuCode'], 'skuRevision': item['revision'], 'skuContentHash': snapshot.content_hash,
         'quantity': 1, 'unitPrice': '100.00', 'discountAmount': '0.00', 'netAmount': '100.00',
         'startAt': '2026-09-01T08:00:00+08:00', 'endAt': '2027-09-01T08:00:00+08:00', 'requestedGeneration': 1}]}


class CatalogueTests(unittest.TestCase):
    def test_current_module_manifest_matches_the_contract(self):
        path = PATH.parents[3] / 'shared/contracts/module-manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        indexed = {row['moduleKey']: row for row in manifest['modules']}
        for module, feature in c.MODULE_FEATURES.items():
            self.assertEqual(indexed[module]['featureKey'], feature)
        self.assertEqual(indexed['employment']['featureKey'], 'employment')

    def test_new_feature_does_not_implicitly_become_enabled(self):
        compiled = c.compile_sku(sku_payload(), known_features=[*FEATURES, 'futureOptional'], approved_features=SCOPES)
        self.assertFalse(compiled.as_dict()['features']['futureOptional'])

    def test_explicit_features_do_not_inherit_all_true(self):
        result = sku().as_dict()['features']
        self.assertTrue(result['internship'])
        for key in ('graduation', 'academicAffairs', 'studentAffairs', 'employment', 'apiAccess', 'fileUpload'):
            self.assertFalse(result[key])

    def test_snapshot_detaches_all_nested_data(self):
        payload = sku_payload()
        snapshot = sku(payload)
        fingerprint = snapshot.content_hash
        payload['features']['internship'] = False
        readback = snapshot.as_dict()
        readback['quotas']['students']['limit'] = 0
        self.assertEqual(snapshot.content_hash, fingerprint)
        self.assertEqual(snapshot.as_dict()['quotas']['students']['limit'], 3000)
        with self.assertRaises(AttributeError):
            snapshot.canonical_json = '{}'

    def test_new_revision_does_not_modify_old_snapshot(self):
        first = sku()
        payload = sku_payload(revision=2)
        payload['pricePolicy']['unitPrice'] = '200.00'
        second = sku(payload)
        self.assertNotEqual(first.content_hash, second.content_hash)
        self.assertEqual(first.as_dict()['pricePolicy']['unitPrice'], '100.00')

    def test_key_order_has_no_effect_on_fingerprint(self):
        payload = sku_payload()
        self.assertEqual(sku(payload).content_hash, sku(dict(reversed(list(payload.items())))).content_hash)

    def test_invalid_revision_and_unknown_fields_rejected(self):
        for revision in (True, False, '1', 0, -1, 1.5, None):
            with self.subTest(revision=revision), self.assertRaises(c.ContractError):
                sku({**sku_payload(), 'revision': revision})
        with self.assertRaises(c.ContractError):
            sku({**sku_payload(), 'paid': True})

    def test_canonical_module_key_required(self):
        for module in ('graduation', 'academicLegacy', 'employment', 'missing'):
            with self.subTest(module=module), self.assertRaises(c.ContractError):
                sku({**sku_payload(), 'moduleKey': module})
        self.assertEqual(sku(sku_payload('graduationDesign')).as_dict()['features']['graduation'], True)

    def test_other_module_and_implicit_addon_are_rejected(self):
        for key in ('graduation', 'academicAffairs', 'studentAffairs', 'apiAccess', 'employment'):
            payload = sku_payload()
            payload['features'][key] = True
            with self.subTest(key=key), self.assertRaises(c.ContractError):
                sku(payload)

    def test_nonboolean_and_unknown_features_are_rejected(self):
        for value in (1, 0, 'true', None):
            payload = sku_payload()
            payload['features']['internship'] = value
            with self.subTest(value=value), self.assertRaises(c.ContractError):
                sku(payload)
        payload = sku_payload()
        payload['features']['newFeature'] = False
        with self.assertRaises(c.ContractError):
            sku(payload)

    def test_reviewed_scope_is_mandatory(self):
        with self.assertRaises(c.ContractError):
            c.compile_sku(sku_payload(), known_features=FEATURES, approved_features={})
        with self.assertRaises(c.ContractError):
            c.compile_sku(sku_payload(), known_features=FEATURES, approved_features={'internship': ['invented']})

    def test_quota_units_and_aggregation_are_explicit(self):
        for change in ({'aggregation': 'AUTO'}, {'limit': True}, {'limit': -1}, {'unit': ''}):
            payload = sku_payload()
            payload['quotas']['students'].update(change)
            with self.subTest(change=change), self.assertRaises(c.ContractError):
                sku(payload)

    def test_no_unpublished_policy_default_is_invented(self):
        payload = sku_payload()
        del payload['lifecyclePolicyVersion']
        with self.assertRaises(c.ContractError):
            sku(payload)

    def test_addon_is_explicit_and_cannot_grant_base_module(self):
        payload = sku_payload()
        payload.update(productType='ADDON', features={'apiAccess': True})
        self.assertTrue(sku(payload).as_dict()['features']['apiAccess'])
        payload['features']['internship'] = True
        with self.assertRaises(c.ContractError):
            sku(payload)

    def test_bundle_binds_exact_component_versions(self):
        first, second = sku(), sku(sku_payload('graduationDesign'))
        catalogue = {(s.as_dict()['skuCode'], s.as_dict()['revision']): s for s in (first, second)}
        payload = sku_payload()
        payload.update(skuCode='bundle', productType='BUNDLE', moduleKey=None, features={}, quotas={}, components=[
            {'skuCode': s.as_dict()['skuCode'], 'revision': 1, 'contentHash': s.content_hash} for s in (first, second)])
        compiled = c.compile_sku(payload, known_features=FEATURES, approved_features=SCOPES,
                                 resolve_component=lambda code, revision: catalogue[(code, revision)])
        self.assertTrue(compiled.as_dict()['features']['graduation'])
        self.assertFalse(compiled.as_dict()['features']['academicAffairs'])
        self.assertEqual(compiled.as_dict()['components'][0]['snapshot']['pricePolicy']['unitPrice'], '100.00')
        payload['components'][0]['contentHash'] = '0' * 64
        with self.assertRaises(c.ContractError):
            c.compile_sku(payload, known_features=FEATURES, approved_features=SCOPES,
                          resolve_component=lambda code, revision: catalogue[(code, revision)])

    def test_malformed_enum_values_raise_contract_error(self):
        for change in ({'productType': []}, {'moduleKey': {}}, {'productType': None}):
            with self.subTest(change=change), self.assertRaises(c.ContractError):
                sku({**sku_payload(), **change})

    def test_bundle_cannot_override_component_features(self):
        payload = sku_payload()
        payload.update(productType='BUNDLE', moduleKey=None)
        with self.assertRaises(c.ContractError):
            c.compile_sku(payload, known_features=FEATURES, approved_features=SCOPES)


class OrderDraftTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = sku()
        self.payload = order_payload(self.snapshot)

    def compile(self, payload=None):
        return c.compile_order_draft(payload or self.payload, resolve_sku=lambda _code, _revision: self.snapshot)

    def test_exact_money_and_bigint_survive_roundtrip(self):
        result = self.compile().as_dict()
        self.assertEqual(result['tenantId'], '1000000000000000003')
        self.assertEqual(result['totalAmount'], '100.00')
        self.assertTrue(result['validationOnly'])
        self.assertFalse(result['paymentRecorded'])
        self.assertFalse(result['rightsMaterialized'])

    def test_invalid_identifiers_rejected_before_lookup(self):
        for value in (1000000000000000003, True, '0', '01', '-1', '9223372036854775808'):
            with self.subTest(value=value), self.assertRaises(c.ContractError):
                self.compile({**self.payload, 'tenantId': value})

    def test_float_nan_exponent_and_rounding_rejected(self):
        for value in (1.1, True, 'NaN', 'Infinity', '1e2', '-1', '0.001', '10000000000.00', '', ' 1'):
            with self.subTest(value=value), self.assertRaises(c.ContractError):
                c.money(value, 'amount')
        self.assertEqual(c.money(Decimal('0.10'), 'amount'), Decimal('0.10'))

    def test_decimal_tenths_are_exact(self):
        line = self.payload['items'][0]
        line.update(quantity=3, unitPrice='0.10', discountAmount='0.01', netAmount='0.29')
        self.payload['totalAmount'] = '0.29'
        self.assertEqual(self.compile().as_dict()['items'][0]['netAmount'], '0.29')

    def test_header_must_equal_sum(self):
        self.payload['totalAmount'] = '99.99'
        with self.assertRaises(c.ContractError):
            self.compile()

    def test_line_arithmetic_and_quantity_checked(self):
        for change in ({'quantity': True}, {'quantity': 0}, {'discountAmount': '100.01'}, {'netAmount': '90.00'}, {'quantity': 1000001}):
            payload = copy.deepcopy(self.payload)
            payload['items'][0].update(change)
            with self.subTest(change=change), self.assertRaises(c.ContractError):
                self.compile(payload)

    def test_currency_mismatch_rejected(self):
        with self.assertRaises(c.ContractError):
            self.compile({**self.payload, 'currency': 'USD'})

    def test_snapshot_hash_and_identity_must_match(self):
        for change in ({'skuContentHash': 'a'*64}, {'skuCode': 'wrong'}, {'skuRevision': 2}):
            payload = copy.deepcopy(self.payload)
            payload['items'][0].update(change)
            with self.subTest(change=change), self.assertRaises(c.ContractError):
                self.compile(payload)

    def test_naive_time_and_empty_interval_rejected(self):
        for change in ({'startAt': '2026-09-01T00:00:00'}, {'endAt': '2026-09-01T00:00:00Z'}, {'startAt': None}, {'startAt': '2029-01-01T00:00:00Z'}):
            payload = copy.deepcopy(self.payload)
            payload['items'][0].update(change)
            with self.subTest(change=change), self.assertRaises(c.ContractError):
                self.compile(payload)

    def test_timezone_normalization_is_explicit(self):
        line = self.compile().as_dict()['items'][0]
        self.assertEqual(line['startAt'], '2026-09-01T00:00:00Z')
        self.assertEqual(line['endAt'], '2027-09-01T00:00:00Z')

    def test_two_modules_keep_their_own_service_windows(self):
        graduation = sku(sku_payload('graduationDesign'))
        extra = order_payload(graduation)['items'][0]
        extra.update(lineNo=2, startAt='2026-12-01T00:00:00Z', endAt='2027-12-01T00:00:00Z')
        self.payload['items'].append(extra)
        self.payload['totalAmount'] = '200.00'
        catalogue = {s.as_dict()['skuCode']: s for s in (self.snapshot, graduation)}
        result = c.compile_order_draft(self.payload, resolve_sku=lambda code, revision: catalogue[code]).as_dict()
        self.assertEqual(result['items'][0]['endAt'], '2027-09-01T00:00:00Z')
        self.assertEqual(result['items'][1]['endAt'], '2027-12-01T00:00:00Z')

    def test_duplicate_line_and_missing_generation_rejected(self):
        self.payload['items'].append(copy.deepcopy(self.payload['items'][0]))
        with self.assertRaises(c.ContractError):
            self.compile()
        self.payload['items'].pop()
        del self.payload['items'][0]['requestedGeneration']
        with self.assertRaises(c.ContractError):
            self.compile()

    def test_draft_snapshot_is_not_changed_by_caller(self):
        compiled = self.compile()
        before = compiled.content_hash
        self.payload['items'][0]['endAt'] = '2030-01-01T00:00:00Z'
        self.assertEqual(before, compiled.content_hash)

    def test_money_does_not_depend_on_callers_decimal_precision(self):
        self.payload['items'][0].update(unitPrice='123456.78', netAmount='123456.78')
        self.payload['totalAmount'] = '123456.78'
        with localcontext() as context:
            context.prec = 6
            self.assertEqual(self.compile().as_dict()['totalAmount'], '123456.78')

    def test_header_capacity_enforced(self):
        self.payload['items'][0].update(unitPrice='9999999999.99', quantity=2, netAmount='0.00')
        with self.assertRaises(c.ContractError):
            self.compile()


if __name__ == '__main__':
    unittest.main()
