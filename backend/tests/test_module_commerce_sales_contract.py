"""M3 sales: real validators/SQL/XLSX/writer; instrumented IO, not a MySQL proof."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import importlib
from io import BytesIO
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

APP = Path(__file__).resolve().parents[1] / "app"


class SalesContractTests(unittest.TestCase):
    def setUp(self):
        saved = {k:v for k,v in sys.modules.items() if k == "app" or k.startswith("app.")}
        def restore():
            for name in list(sys.modules):
                if name == "app" or name.startswith("app."):
                    del sys.modules[name]
            sys.modules.update(saved)
        self.addCleanup(restore)
        for name in saved:
            del sys.modules[name]
        def module(name, **values):
            value = ModuleType(name); value.__dict__.update(values); return value
        self.db = MagicMock()
        self.db.__enter__.return_value = self.db
        self.factory = Mock(return_value=self.db)
        self.audit = Mock()
        for name, sub in (("app", ""), ("app.core","core"), ("app.db","db"),
                          ("app.models","models"), ("app.services","services")):
            sys.modules[name] = module(name, __path__=[str(APP / sub)])
        sys.modules["app.core.config"] = module("app.core.config", settings=SimpleNamespace(TIMEZONE_OFFSET_HOURS=8))
        sys.modules["app.core.context"] = module("app.core.context", get_trace_id=lambda:"sales-contract")
        sys.modules["app.db.session"] = module("app.db.session", db_enabled=lambda:True, get_sessionmaker=lambda:self.factory)
        self.catalog = module("app.services.commercial_catalog_service", get_sku_snapshot=Mock())
        sys.modules[self.catalog.__name__] = self.catalog
        sys.modules["app.services.audit_log"] = module("app.services.audit_log", record_critical_in_session=self.audit)
        self.models = sys.modules["app.models"]
        for name, source in (("Tenant","tenant"), ("PlatformOrder","platform"), ("IdempotencyRecord","idempotency"),
                             ("CommercialSkuVersion","commercial"), ("CommercialOrderItem","commercial"),
                             ("TenantModuleState","commercial"), ("TenantCommercialProfile","commercial"),
                             ("TenantModuleSubscriptionSource","commercial")):
            setattr(self.models, name, getattr(importlib.import_module(f"app.models.{source}"), name))
        self.c = importlib.import_module("app.services.commercial_catalog_contract")
        self.catalog.APPROVED_FEATURE_SCOPES = {k:(v,"studentProfile") for k,v in self.c.MODULE_FEATURES.items()}
        self.s = importlib.import_module("app.services.module_commerce_sales_service")
        self.context = {"tenantId":"42", "tenantStatus":"ACTIVE", "tenantName":"合同测试学校", "readerVersion":"MODULE_V2", "states":{}, "paidThrough":{}}
        self.skus = {k:self.sku(k) for k in self.c.MODULE_FEATURES}
        self.catalog.get_sku_snapshot.side_effect = lambda code, rev, **kw: self.skus[code]
        self.body = {"tenantId":"42", "orderType":"NEW", "remark":"合同编号测试42", "items":[self.line("internship")]}
        self.tenant = SimpleNamespace(id=42, school_name="=HYPERLINK(\"https://invalid.example\")", status="ACTIVE", is_deleted=False)
        self.db.get.return_value = self.tenant

    def sku(self, key, currency="CNY"):
        features = set(self.c.MODULE_FEATURES.values()) | {"studentProfile", "employment", "apiAccess"}
        return self.c.compile_sku({"skuCode":key,"revision":1,"name":key,"productType":"MODULE","moduleKey":key,
            "features":{self.c.MODULE_FEATURES[key]:True,"studentProfile":True},"quotas":{},
            "pricePolicy":{"unitPrice":"100.00","currency":currency,"taxTreatment":"UNSPECIFIED"},
            "lifecyclePolicyVersion":"CONTRACT-42"}, known_features=features,
            approved_features=self.catalog.APPROVED_FEATURE_SCOPES)

    def line(self, key):
        return {"skuCode":key, "skuRevision":1, "skuContentHash":self.skus[key].content_hash,
                "quantity":3, "unitPrice":"0.10", "discountAmount":"0.01",
                "startAt":"2026-09-09T08:00:00+08:00", "endAt":"2027-09-09T08:00:00+08:00"}

    def preview(self):
        return self.s.compile_sales_preview(self.body, self.context,
                                            resolve_sku=lambda code,rev:self.skus[code])

    def assert_failure(self, status):
        with self.assertRaises(self.s.AppException) as caught:
            self.preview()
        self.assertEqual(caught.exception.http_status, status)
        self.db.add.assert_not_called(); self.db.commit.assert_not_called()

    def test_four_modules_exact_money_no_payment_and_no_hidden_addons(self):
        self.body["items"] = [self.line(k) for k in self.skus]
        before = deepcopy(self.body)
        result = self.preview()
        self.assertEqual(result["totalAmount"], "1.16")
        self.assertEqual([i["netAmount"] for i in result["items"]], ["0.29"]*4)
        self.assertTrue(result["validationOnly"])
        self.assertFalse(result["paymentRecorded"] or result["rightsMaterialized"])
        self.assertEqual(self.body, before)
        for item in result["items"]:
            self.assertFalse(item["skuSnapshot"]["features"]["employment"])
            self.assertFalse(item["skuSnapshot"]["features"]["apiAccess"])
        self.factory.assert_not_called()

    def test_invalid_amounts_quantities_and_missing_fields_rejected(self):
        original = deepcopy(self.body)
        for field,value in (("unitPrice",0.1),("unitPrice","1e2"),("unitPrice","0.001"),("unitPrice","NaN"),
                            ("unitPrice","10000000000"),("discountAmount","0.31"),("quantity",True),
                            ("quantity",1.5),("quantity",0),("quantity",1000001)):
            with self.subTest(field=field,value=value):
                self.body=deepcopy(original);self.body["items"][0][field]=value;self.assert_failure(422)
        self.body=deepcopy(original);self.body["items"][0].pop("endAt");self.assert_failure(422)

    def test_total_overflow_never_silently_rounds_or_wraps(self):
        self.body["items"]=[self.line("internship"),self.line("academicAffairs")]
        for item in self.body["items"]:
            item.update(quantity=1,unitPrice="9999999999.99",discountAmount="0.00")
        self.assert_failure(422)

    def test_duplicate_module_and_cross_currency_rejected(self):
        self.body["items"]*=2;self.assert_failure(422)
        self.skus["academicAffairs"]=self.sku("academicAffairs",currency="USD")
        self.body["items"]=[self.line("internship"),self.line("academicAffairs")];self.assert_failure(422)

    def test_bad_sku_fingerprint_and_client_generation_are_rejected(self):
        self.body["items"][0]["skuContentHash"]="a"*64;self.assert_failure(422)
        self.body["items"]=[self.line("internship")];self.body["items"][0]["requestedGeneration"]=77;self.assert_failure(422)

    def test_dates_timezone_and_half_open_boundary(self):
        for start,end in (("2026-02-30T00:00:00Z","2027-09-09T00:00:00Z"),
                          ("2026-09-09T00:00:00","2027-09-09T00:00:00Z"),
                          ("2026-09-09T00:00:00Z","2026-09-09T00:00:00Z"),
                          ("2026-09-09T00:00:01Z","2026-09-09T00:00:00Z")):
            with self.subTest(start=start,end=end):
                self.body["items"][0].update(startAt=start,endAt=end);self.assert_failure(422)

    def test_wrong_tenant_inactive_school_and_unsupported_business_rejected(self):
        self.body["tenantId"]="43";self.assert_failure(409)
        self.body["tenantId"]="42";self.context["tenantStatus"]="SUSPENDED";self.assert_failure(409)
        self.context["tenantStatus"]="ACTIVE";self.body["orderType"]="UPGRADE";self.assert_failure(422)

    def test_frozen_retained_purged_are_not_revived_by_a_new_order(self):
        for state in ("FROZEN","RETAINED","PURGING","PURGED","UNKNOWN"):
            with self.subTest(state=state):
                self.context["states"]={"internship":{"generation":2,"dataState":state}};self.assert_failure(409)

    def test_generation_derived_and_revalidated_under_writer_lock(self):
        self.context["states"]={"internship":{"generation":2,"dataState":"AVAILABLE"}}
        preview=self.preview();self.assertEqual(preview["items"][0]["requestedGeneration"],2)
        self.context["states"]["internship"]["generation"]=3
        with self.assertRaises(self.s.AppException) as caught:
            self.s.validate_sales_context({"tenantId":"42","items":preview["items"]},"NEW",self.context)
        self.assertEqual(caught.exception.http_status,409)

    def test_renewal_requires_paid_boundary_and_preserves_gap_visibility(self):
        self.body["orderType"]="RENEW";self.assert_failure(409)
        self.context["paidThrough"]={"internship":"2026-09-10T00:00:00Z"};self.assert_failure(409)
        self.body["items"][0]["startAt"]="2026-09-10T08:00:00+08:00"
        self.assertEqual(self.preview()["warnings"][0]["code"],"RENEWAL_BOUNDARY")
        self.body["items"][0]["startAt"]="2026-09-11T08:00:00+08:00"
        self.assertIn("空档",self.preview()["warnings"][0]["message"])

    def test_preview_reads_same_session_without_writes(self):
        with patch.object(self.s,"_sales_context",return_value=self.context):
            result=self.s.preview_sales_order(self.body)
        self.assertEqual(result["totalAmount"],"0.29")
        self.catalog.get_sku_snapshot.assert_called_once_with("internship",1,db_session=self.db)
        self.db.commit.assert_not_called();self.db.add.assert_not_called();self.audit.assert_not_called()

    def test_context_sql_joins_paid_owner_and_generation_without_n_plus_one(self):
        self.db.scalars.return_value.all.return_value=[]
        self.db.scalars.return_value.first.return_value=None
        self.db.execute.return_value.all.return_value=[]
        self.s._sales_context(self.db,self.tenant,lock=True)
        self.assertEqual(self.db.execute.call_count,1)
        sql=str(self.db.execute.call_args.args[0]);params=self.db.execute.call_args.args[0].compile().params
        for fragment in ("max(","GROUP BY","t_order.tenant_id", "module_generation", "order_item_id"):
            self.assertIn(fragment,sql)
        self.assertIn("paid",params.values());self.assertIn(42,params.values());self.assertIn("PAID_ORDER_ITEM",params.values())
        state_sql=str(self.db.scalars.call_args_list[0].args[0]);self.assertIn("FOR UPDATE",state_sql)
        self.db.commit.assert_not_called()

    def order(self):
        return SimpleNamespace(id=77,tenant_id=42,order_no="MO-42",order_type="NEW",status="unpaid",amount=Decimal("0.29"),
            paid_amount=Decimal("0.00"),version=1,start_at=None,end_at=None,created_at=datetime(2026,9,9),remark="original")

    def item(self):
        return SimpleNamespace(line_no=1,module_key="internship",sku_code="+SUM(1,2)",sku_revision=1,
            sku_content_hash="a"*64,module_generation=2,quantity=3,unit_price=Decimal("0.10"),discount_amount=Decimal("0.01"),
            net_amount=Decimal("0.29"),currency="CNY",service_start_at=datetime(2026,9,9),service_end_at=datetime(2027,9,9),
            fulfillment_status="PENDING",feature_snapshot_json={"internship":True},quota_snapshot_json={})

    def test_ledger_query_is_paged_and_tenant_scoped_with_batched_counts(self):
        self.db.scalar.return_value=200
        self.db.scalars.return_value.all.return_value=[self.order()]
        self.db.execute.return_value.all.return_value=[(77,1,"CNY","CNY")]
        result=self.s.list_sales_orders("42",status="unpaid",page=2,page_size=7)
        statement=self.db.scalars.call_args.args[0];params=statement.compile().params
        self.assertIn("LIMIT",str(statement));self.assertIn("OFFSET",str(statement))
        self.assertIn(42,params.values());self.assertIn("unpaid",params.values());self.assertIn("MODULE_V2",params.values())
        self.assertEqual(result["items"][0]["itemCount"],1);self.assertEqual(result["total"],200)
        self.assertEqual(self.db.execute.call_count,1);self.db.commit.assert_not_called()

    def test_order_detail_uses_frozen_items_without_catalogue(self):
        self.db.scalars.return_value.first.return_value=self.order()
        self.db.scalars.return_value.all.return_value=[self.item()]
        result=self.s.get_sales_order("42","77")
        self.assertEqual(result["items"][0]["netAmount"],"0.29")
        self.assertEqual(result["snapshotSource"],"ORDER_ITEM_NOT_LIVE_CATALOGUE")
        for call in self.db.scalars.call_args_list:
            self.assertIn(42,call.args[0].compile().params.values())
        self.catalog.get_sku_snapshot.assert_not_called();self.db.commit.assert_not_called()

    def test_foreign_or_missing_detail_returns_404(self):
        self.db.scalars.return_value.first.return_value=None
        with self.assertRaises(self.s.AppException) as caught:self.s.get_sales_order("43","77")
        self.assertEqual(caught.exception.http_status,404)
        self.assertIn(43,self.db.scalars.call_args.args[0].compile().params.values())
        self.db.commit.assert_not_called()

    def test_catalogue_filter_and_corrupt_fingerprint_fail_closed(self):
        sku=self.skus["internship"]
        row=SimpleNamespace(snapshot_json=sku.as_dict(),content_hash="bad",sku_code="internship",sku_revision=1,
                            module_key="internship",publish_status="PUBLISHED")
        self.db.scalar.return_value=1;self.db.scalars.return_value.all.return_value=[row]
        with self.assertRaises(self.s.AppException):self.s.list_sale_skus(module_key="internship",page=2,page_size=7)
        statement=self.db.scalars.call_args.args[0]
        self.assertIn("PUBLISHED",statement.compile().params.values());self.assertIn("LIMIT",str(statement))
        row.content_hash=sku.content_hash
        self.assertEqual(self.s.list_sale_skus()["items"][0]["contentHash"],sku.content_hash)

    def test_export_real_xlsx_preserves_bigint_money_and_formula_literals(self):
        from openpyxl import load_workbook
        self.db.execute.return_value.all.return_value=[(self.order(),self.item())]
        result=self.s.export_sales_orders({"tenantId":"42","reason":"核对合同分项明细"})
        book=load_workbook(BytesIO(base64.b64decode(result["contentBase64"])))
        sheet=book.active
        self.assertEqual(sheet["B2"].data_type,"s");self.assertTrue(sheet["B2"].value.startswith("="))
        self.assertEqual(sheet["J2"].data_type,"s");self.assertEqual(sheet["P2"].value,"0.29")
        self.assertEqual(sheet.freeze_panes,"A2");self.assertEqual(sheet.auto_filter.ref,"A1:U2")
        self.assertIn("勿逐行累加",sheet["F1"].value)
        self.assertEqual(result["rowCount"],1);self.assertFalse(result["truncated"])
        self.assertEqual(self.audit.call_args.kwargs["tenant_id"],42);self.db.commit.assert_called_once()

    def test_export_never_truncates_and_audit_failure_never_returns_bytes(self):
        self.db.execute.return_value.all.return_value=[(self.order(),self.item())]*1001
        with self.assertRaises(self.s.AppException) as caught:self.s.export_sales_orders({"tenantId":"42","reason":"核对合同分项明细"})
        self.assertEqual(caught.exception.http_status,413);self.audit.assert_not_called();self.db.commit.assert_not_called()
        self.db.execute.return_value.all.return_value=[];self.audit.side_effect=RuntimeError("audit down")
        with self.assertRaisesRegex(RuntimeError,"audit down"):self.s.export_sales_orders({"tenantId":"42","reason":"核对合同分项明细"})
        self.db.commit.assert_not_called()

    def test_existing_receipt_replays_before_sales_context_and_catalogue(self):
        writer=importlib.import_module("app.services.commercial_order_item_service")
        contract=self.preview()["order"]
        clean,typ,remark=writer._clean_body(contract)
        receipt={"orderNo":"MO-ORIGINAL","paymentRecorded":False,"rightsMaterialized":False}
        idem=SimpleNamespace(fingerprint=writer._fingerprint(clean,typ,remark),state="COMPLETED",result_json=receipt)
        self.db.scalars.side_effect=[Mock(first=lambda:self.tenant),Mock(first=lambda:idem)]
        self.catalog.get_sku_snapshot.side_effect=RuntimeError("catalogue offline")
        with patch.object(self.s,"_sales_context",side_effect=AssertionError("must replay")):
            result=self.s.create_sales_order(contract,idempotency_key="sales-same-key",actor_id="7")
        self.assertTrue(result["replayed"]);self.catalog.get_sku_snapshot.assert_not_called();self.db.add.assert_not_called()

    def test_new_command_rechecks_frozen_state_before_any_order_insert(self):
        contract=self.preview()["order"]
        self.context["states"]={"internship":{"generation":1,"dataState":"FROZEN"}}
        self.db.scalars.side_effect=[Mock(first=lambda:self.tenant),Mock(first=lambda:None)]
        with patch.object(self.s,"_sales_context",return_value=self.context) as context_read:
            with self.assertRaises(self.s.AppException) as caught:self.s.create_sales_order(contract,idempotency_key="sales-new-key",actor_id="7")
        self.assertEqual(caught.exception.http_status,409)
        self.assertIs(caught.exception.details["salesCommandNotCommitted"],True)
        context_read.assert_called_once_with(self.db,self.tenant,lock=True)
        self.db.add.assert_not_called();self.db.commit.assert_not_called();self.db.rollback.assert_called_once()

    def test_processing_receipt_must_not_release_browser_retry_key(self):
        writer=importlib.import_module("app.services.commercial_order_item_service")
        contract=self.preview()["order"];clean,typ,remark=writer._clean_body(contract)
        idem=SimpleNamespace(fingerprint=writer._fingerprint(clean,typ,remark),state="PROCESSING")
        self.db.scalars.side_effect=[Mock(first=lambda:self.tenant),Mock(first=lambda:idem)]
        with self.assertRaises(self.s.AppException) as caught:self.s.create_sales_order(contract,idempotency_key="sales-same-key",actor_id="7")
        self.assertIsNone(caught.exception.details)
        self.db.add.assert_not_called();self.db.commit.assert_not_called()

    def test_pagination_and_identifiers_never_silently_coerce(self):
        for value in (True,"1",0,10001):
            with self.subTest(page=value),self.assertRaises(self.s.AppException):self.s._page(value,20)
        for value in (True,None,"00042","4e2",str(2**63)):
            with self.subTest(tid=value),self.assertRaises(self.s.AppException):self.s._tid(value)


if __name__ == "__main__":
    unittest.main()
