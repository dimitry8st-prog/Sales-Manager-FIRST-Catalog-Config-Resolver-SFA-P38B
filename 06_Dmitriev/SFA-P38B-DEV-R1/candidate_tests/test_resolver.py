"""Contract and real-catalog regression tests for the read-only F128 resolver.

The storage port is synthetic; authentication, bundle validation, consumer,
F105/F106 and F128/F112 all run through the issued public implementations.
"""
import ast
import base64
import copy
import hashlib
import inspect
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
import uuid
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timedelta, timezone, tzinfo
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

import first_campaign_catalog.api as catalog_api
import first_campaign_catalog.consumer as consumer
from first_materials_integration import catalog_config as target
from sales_runtime_binding import resolve_campaign_projection
from sales_campaign_projection import project_campaign_binding


class StrSubclass(str):
    pass


class DateTimeSubclass(datetime):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def encode_config(value):
    raw = canonical(value)
    return {"utf8_b64": base64.b64encode(raw).decode("ascii"),
            "sha256": hashlib.sha256(raw).hexdigest()}


class ReadOnlyPorts:
    """Only read transactions are available, with explicit scoped row keys."""

    def __init__(self, scope, bundle, now):
        self.scope = copy.deepcopy(scope)
        self.now = now
        self.auth = {"authenticated": True, "client_id": scope["client_id"],
                     "capabilities": ["catalog.read"]}
        self.rows = {catalog_api.version_key(scope, "catalog-v1"): {
            "version": "catalog-v1", "revision": 1,
            "bundle": copy.deepcopy(bundle), "revoked": False,
        }}
        self.transaction_scopes = []
        self.reads = []
        self.writes = []

    @contextmanager
    def transaction(self, scope):
        self.transaction_scopes.append(copy.deepcopy(scope))
        yield self

    def get(self, bucket, key):
        self.reads.append((bucket, key))
        return copy.deepcopy(self.rows.get(key))

    def put(self, *args):
        self.writes.append(args)
        raise AssertionError("Resolver must not write storage")


class ResolverContractTests(unittest.TestCase):
    def setUp(self):
        self.scope = json.loads((ROOT / "fixtures/scope.json").read_text())
        self.bundle = json.loads((ROOT / "fixtures/bundle.json").read_text())
        meta = json.loads((ROOT / "fixtures/meta.json").read_text())
        self.now = datetime.fromisoformat(meta["now"])
        self.config = json.loads(base64.b64decode(
            self.bundle["raw"]["config"]["utf8_b64"]))
        self.ports = ReadOnlyPorts(self.scope, self.bundle, self.now)
        self.service = catalog_api.create_service(self.ports)

    def make(self, **overrides):
        args = {"client_id": self.scope["client_id"],
                "catalog_version": "catalog-v1", "clock": lambda: self.now}
        args.update(overrides)
        return target.make_catalog_config_resolver(self.service, **args)

    def row(self, version="catalog-v1"):
        return self.ports.rows[catalog_api.version_key(self.scope, version)]

    def assert_code(self, code, callable_):
        with self.assertRaises(target.CatalogConfigError) as caught:
            callable_()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code)
        self.assertIsInstance(caught.exception, ValueError)

    def assert_catalog_error(self, status, callable_, code=None):
        with self.assertRaises(consumer.CatalogPortError) as caught:
            callable_()
        self.assertEqual(caught.exception.status, status)
        if code is not None:
            self.assertEqual(caught.exception.data["code"], code)

    def test_public_signature_and_error_abi(self):
        parameters = inspect.signature(
            target.make_catalog_config_resolver).parameters
        self.assertEqual(tuple(parameters),
                         ("service", "client_id", "catalog_version", "clock"))
        self.assertEqual(parameters["service"].kind,
                         inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for name in ("client_id", "catalog_version", "clock"):
            self.assertEqual(parameters[name].kind,
                             inspect.Parameter.KEYWORD_ONLY)
            self.assertIs(parameters[name].default, inspect.Parameter.empty)
        self.assert_code("INVALID_RESOLVER_CONFIGURATION",
                         lambda: self.make(client_id=None))

    def test_constructor_rejects_exact_type_and_identifier_boundaries(self):
        values = (None, True, 1, b"client", StrSubclass("client"), "", " x",
                  "x ", "x\n", "x\x00y", "x\x1fy", "x\x7fy", "x" * 129,
                  "\u2003")
        for field in ("client_id", "catalog_version"):
            for value in values:
                with self.subTest(field=field, value=repr(value)):
                    clock = Mock(return_value=self.now)
                    self.assert_code("INVALID_RESOLVER_CONFIGURATION",
                                     lambda: self.make(**{field: value,
                                                         "clock": clock}))
                    clock.assert_not_called()
        self.assertEqual(self.ports.transaction_scopes, [])

    def test_constructor_uses_existing_unicode_id_policy_without_effects(self):
        values = ("Клиент-А🚀", "e\u0301", "é", "x\u200by", "x\u0080y", "я" * 128)
        clock = Mock(side_effect=AssertionError("constructor clock call"))
        with patch.object(self.service, "execute", side_effect=AssertionError(
                "constructor service call")) as execute:
            for value in values:
                with self.subTest(value=value):
                    self.assertTrue(catalog_api.is_id(value))
                    with patch.object(catalog_api, "is_id", wraps=catalog_api.is_id) as spy:
                        resolver = self.make(client_id=value, catalog_version=value,
                                             clock=clock)
                    self.assertTrue(callable(resolver))
                    self.assertTrue(any(call.args == (value,) for call in spy.call_args_list))
            execute.assert_not_called()
        clock.assert_not_called()
        self.assertEqual(self.ports.transaction_scopes, [])

    def test_constructor_rejects_noncallable_dependencies(self):
        for service in (None, object(), SimpleNamespace(execute=None),
                        SimpleNamespace(execute=True)):
            with self.subTest(service=service):
                clock = Mock(return_value=self.now)
                self.assert_code("INVALID_RESOLVER_CONFIGURATION", lambda:
                    target.make_catalog_config_resolver(
                        service, client_id="client", catalog_version="v1", clock=clock))
                clock.assert_not_called()
        for value in (None, True, 0, "clock", object()):
            with self.subTest(clock=value):
                self.assert_code("INVALID_RESOLVER_CONFIGURATION",
                                 lambda: self.make(clock=value))

    def test_invalid_campaign_precedes_clock_and_consumer(self):
        clock = Mock(side_effect=AssertionError("invalid campaign reached clock"))
        resolver = self.make(clock=clock)
        valid = "abcdefab-cdef-4abc-8def-abcdefabcdef"
        invalid = (None, True, 12, b"uuid", uuid.UUID(valid), StrSubclass(valid),
                   "", valid.upper(), valid.replace("-", ""), "{" + valid + "}",
                   " " + valid, valid + "\n", "urn:uuid:" + valid,
                   valid[:-1] + "g", valid + "x", {"campaign_id": valid})
        with patch.object(consumer, "trusted_raw_config", wraps=consumer.trusted_raw_config) as spy:
            for value in invalid:
                with self.subTest(value=repr(value)):
                    self.assert_code("INVALID_CAMPAIGN_ID", lambda: resolver(value))
            spy.assert_not_called()
        clock.assert_not_called()
        self.assertEqual(self.ports.transaction_scopes, [])

    def test_canonical_uuid_has_no_extra_version_restriction(self):
        clock = Mock(return_value=self.now)
        resolver = self.make(clock=clock)
        for value in ("00000000-0000-0000-0000-000000000000",
                      "abcdefab-cdef-0abc-0def-abcdefabcdef"):
            with self.subTest(campaign_id=value):
                self.assert_catalog_error("NOT_FOUND", lambda: resolver(value))
        self.assertEqual(clock.call_count, 2)
        self.assertEqual([s["campaign_id"] for s in self.ports.transaction_scopes],
                         ["00000000-0000-0000-0000-000000000000",
                          "abcdefab-cdef-0abc-0def-abcdefabcdef"])

    def test_clock_requires_exact_aware_datetime_before_consumer(self):
        invalid = (None, True, 12, self.now.isoformat(), date(2026, 10, 12),
                   datetime(2026, 10, 12),
                   DateTimeSubclass(2026, 10, 12, tzinfo=timezone.utc))
        with patch.object(consumer, "trusted_raw_config", wraps=consumer.trusted_raw_config) as spy:
            for value in invalid:
                with self.subTest(value=repr(value)):
                    clock = Mock(return_value=value)
                    resolver = self.make(clock=clock)
                    self.assert_code("INVALID_CLOCK", lambda: resolver(self.scope["campaign_id"]))
                    clock.assert_called_once_with()
            spy.assert_not_called()
        self.assertEqual(self.ports.transaction_scopes, [])

    def test_aware_non_utc_clock_preserves_object_and_instant(self):
        explicit = self.now.astimezone(timezone(timedelta(hours=5, minutes=30)))
        resolver = self.make(clock=lambda: explicit)
        real = consumer.trusted_raw_config
        with patch.object(consumer, "trusted_raw_config", wraps=real) as spy:
            actual = resolver(self.scope["campaign_id"])
        self.assertEqual(actual, self.config)
        bound = inspect.signature(real).bind(*spy.call_args.args, **spy.call_args.kwargs)
        self.assertIs(bound.arguments["now"], explicit)
        self.assertIs(self.ports.now, self.now)

    def test_malformed_datetime_timezone_is_invalid_clock_before_consumer(self):
        class RaisingTimezone(tzinfo):
            def utcoffset(self, value):
                raise RuntimeError("invalid timezone details")
        class ExcessiveTimezone(tzinfo):
            def utcoffset(self, value):
                return timedelta(days=2)
        class WrongTypeTimezone(tzinfo):
            def utcoffset(self, value):
                return 1
        class NaiveTimezone(tzinfo):
            def utcoffset(self, value):
                return None
        with patch.object(consumer, "trusted_raw_config", wraps=consumer.trusted_raw_config) as spy:
            for zone in (RaisingTimezone(), ExcessiveTimezone(), WrongTypeTimezone(), NaiveTimezone()):
                with self.subTest(zone=type(zone).__name__):
                    value = datetime(2026, 10, 12, tzinfo=zone)
                    clock = Mock(return_value=value)
                    resolver = self.make(clock=clock)
                    self.assert_code("INVALID_CLOCK", lambda: resolver(self.scope["campaign_id"]))
                    clock.assert_called_once_with()
            spy.assert_not_called()

    def test_clock_exception_identity_and_no_retry(self):
        error = RuntimeError("sensitive clock detail")
        clock = Mock(side_effect=error)
        resolver = self.make(clock=clock)
        with patch.object(consumer, "trusted_raw_config", wraps=consumer.trusted_raw_config) as spy:
            with self.assertRaises(RuntimeError) as caught:
                resolver(self.scope["campaign_id"])
            self.assertIs(caught.exception, error)
            clock.assert_called_once_with()
            spy.assert_not_called()

    def test_real_chain_order_exact_scope_pin_and_single_calls(self):
        events = []
        def clock():
            events.append("clock")
            return self.now
        real = consumer.trusted_raw_config
        def observe(*args, **kwargs):
            events.append("consumer")
            return real(*args, **kwargs)
        resolver = self.make(clock=clock)
        with patch.object(consumer, "trusted_raw_config", side_effect=observe) as spy:
            actual = resolver(self.scope["campaign_id"])
        self.assertEqual(events, ["clock", "consumer"])
        spy.assert_called_once()
        bound = inspect.signature(real).bind(*spy.call_args.args, **spy.call_args.kwargs)
        self.assertIs(bound.arguments["service"], self.service)
        self.assertEqual(bound.arguments["scope"], self.scope)
        self.assertEqual(set(bound.arguments["scope"]), {"client_id", "campaign_id"})
        self.assertEqual(bound.arguments["version"], "catalog-v1")
        self.assertIs(bound.arguments["now"], self.now)
        self.assertEqual(actual, self.config)
        self.assertEqual(len(self.ports.reads), 1)
        self.assertEqual(self.ports.writes, [])

    def test_return_is_deepcopy_of_real_consumer_raw_config_only(self):
        real = consumer.trusted_raw_config
        observed = []
        def observe(*args, **kwargs):
            result = real(*args, **kwargs)
            observed.append(result)
            return result
        resolver = self.make()
        with patch.object(consumer, "trusted_raw_config", side_effect=observe):
            result = resolver(self.scope["campaign_id"])
        raw = observed[0]["raw_config"]
        self.assertEqual(result, raw)
        self.assertIsNot(result, raw)
        self.assertIsNot(result["offer"], raw["offer"])
        self.assertIsNot(result["approved_facts"], raw["approved_facts"])
        self.assertIsNot(result["approved_facts"][0], raw["approved_facts"][0])
        raw["offer"]["name"] = "mutated consumer object"
        raw["approved_facts"][0]["text"] = "mutated fact"
        self.assertEqual(result, self.config)
        self.assertEqual(set(result), set(self.config))
        self.assertNotIn("pins", result)
        self.assertNotIn("approved", result)

    def test_mutating_result_does_not_change_later_calls_or_storage(self):
        before = copy.deepcopy(self.ports.rows)
        resolver = self.make()
        first = resolver(self.scope["campaign_id"])
        first["approved_facts"][0]["text"] = "changed"
        first["allowed_locales"].append("de-DE")
        first["language_pack_versions"]["en-GB"] = "changed"
        second = resolver(self.scope["campaign_id"])
        self.assertEqual(second, self.config)
        self.assertEqual(self.ports.rows, before)
        self.assertEqual(len(self.ports.reads), 2)

    def test_authentication_is_rechecked_after_success(self):
        resolver = self.make()
        resolver(self.scope["campaign_id"])
        self.ports.auth["authenticated"] = False
        self.assert_catalog_error("UNAUTHENTICATED", lambda: resolver(self.scope["campaign_id"]))
        self.assertEqual(len(self.ports.reads), 1)
        self.assertFalse(self.ports.auth["authenticated"])

    def test_capability_is_rechecked_after_success(self):
        resolver = self.make()
        resolver(self.scope["campaign_id"])
        self.ports.auth["capabilities"] = []
        self.assert_catalog_error("UNAUTHORIZED", lambda: resolver(self.scope["campaign_id"]))
        self.assertEqual(self.ports.auth["capabilities"], [])
        self.assertEqual(len(self.ports.reads), 1)

    def test_tenant_is_rechecked_after_success_without_auth_repair(self):
        resolver = self.make()
        resolver(self.scope["campaign_id"])
        self.ports.auth["client_id"] = "foreign-client"
        self.assert_catalog_error("UNAUTHORIZED", lambda: resolver(self.scope["campaign_id"]))
        self.assertEqual(self.ports.auth["client_id"], "foreign-client")
        self.assertEqual(len(self.ports.reads), 1)

    def test_revocation_is_rechecked_after_success(self):
        resolver = self.make()
        resolver(self.scope["campaign_id"])
        self.row()["revoked"] = True
        self.assert_catalog_error("BLOCKED", lambda: resolver(self.scope["campaign_id"]), "REVOKED")
        self.assertEqual(len(self.ports.reads), 2)
        self.assertEqual(self.ports.writes, [])

    def test_injected_reader_clock_rechecks_expiry_without_mutating_service_clock(self):
        # Keep F105's config valid beyond the bundle's shorter lifetime, so the
        # consumer's bundle-expiry check is the actual refusal being observed.
        deadline = self.now + timedelta(hours=1)
        self.row()["bundle"]["valid_until"] = deadline.isoformat()
        resolver = self.make()
        resolver(self.scope["campaign_id"])
        old_now = self.ports.now
        self.now = deadline
        self.assert_catalog_error("BLOCKED", lambda: resolver(self.scope["campaign_id"]), "BUNDLE_EXPIRED")
        self.assertIs(self.ports.now, old_now)
        self.assertEqual(len(self.ports.reads), 2)

    def test_resolver_pins_are_fixed_and_new_version_requires_new_resolver(self):
        old = self.make()
        v2 = copy.deepcopy(self.row())
        v2["version"] = "catalog-v2"
        second_config = copy.deepcopy(self.config)
        second_config["binding_version"] = "binding-v2"
        second_config["offer"]["name"] = "Новая версия 🚀"
        v2["bundle"]["raw"]["config"] = encode_config(second_config)
        self.ports.rows[catalog_api.version_key(self.scope, "catalog-v2")] = v2
        new = self.make(catalog_version="catalog-v2")
        self.assertEqual(old(self.scope["campaign_id"]), self.config)
        self.assertEqual(new(self.scope["campaign_id"]), second_config)
        self.assertEqual(old(self.scope["campaign_id"]), self.config)
        self.assertEqual([key for _, key in self.ports.reads], [
            catalog_api.version_key(self.scope, "catalog-v1"),
            catalog_api.version_key(self.scope, "catalog-v2"),
            catalog_api.version_key(self.scope, "catalog-v1"),
        ])

    def test_missing_pin_does_not_fallback_to_existing_version(self):
        resolver = self.make(catalog_version="absent")
        self.assert_catalog_error("NOT_FOUND", lambda: resolver(self.scope["campaign_id"]))
        self.assertEqual(self.ports.reads, [(catalog_api.BUCKET,
                                          catalog_api.version_key(self.scope, "absent"))])

    def test_hash_change_after_success_is_revalidated(self):
        resolver = self.make()
        resolver(self.scope["campaign_id"])
        self.row()["bundle"]["raw"]["config"]["sha256"] = "0" * 64
        self.assert_catalog_error("BLOCKED", lambda: resolver(self.scope["campaign_id"]), "HASH_MISMATCH")
        self.assertEqual(len(self.ports.reads), 2)

    def test_rehashed_foreign_scope_is_rejected_by_real_bundle_validator(self):
        wrong = copy.deepcopy(self.config)
        wrong["client_id"] = "foreign-client"
        self.row()["bundle"]["raw"]["config"] = encode_config(wrong)
        resolver = self.make()
        self.assert_catalog_error("BLOCKED", lambda: resolver(self.scope["campaign_id"]), "FOREIGN_SCOPE")
        self.assertEqual(self.ports.writes, [])

    def test_rehashed_invalid_binding_is_rejected_by_accepted_core(self):
        wrong = copy.deepcopy(self.config)
        wrong["release_mode"] = "SEND_READY"
        self.row()["bundle"]["raw"]["config"] = encode_config(wrong)
        resolver = self.make()
        self.assert_catalog_error("BLOCKED", lambda: resolver(self.scope["campaign_id"]))
        self.assertEqual(self.ports.writes, [])

    def test_consumer_exception_identity_single_call_and_no_retry(self):
        error = LookupError("sensitive consumer detail")
        clock = Mock(return_value=self.now)
        resolver = self.make(clock=clock)
        with patch.object(consumer, "trusted_raw_config", side_effect=error) as spy:
            with self.assertRaises(LookupError) as caught:
                resolver(self.scope["campaign_id"])
            self.assertIs(caught.exception, error)
            spy.assert_called_once()
        clock.assert_called_once_with()

    def test_real_consumer_preserves_service_exception_identity(self):
        error = ConnectionError("sensitive storage detail")
        resolver = self.make()
        with patch.object(self.service, "execute", side_effect=error) as execute:
            with self.assertRaises(ConnectionError) as caught:
                resolver(self.scope["campaign_id"])
            self.assertIs(caught.exception, error)
            execute.assert_called_once()

    def test_F128_ignores_payload_config_and_preserves_inputs(self):
        resolver = self.make()
        campaign = {"campaign_id": self.scope["campaign_id"],
                    "client_id": "foreign-client", "catalog_version": "evil-version",
                    "config": {"release_mode": "SEND_READY", "offer": {"name": "untrusted"}}}
        before = copy.deepcopy(campaign)
        rows_before = copy.deepcopy(self.ports.rows)
        expected = project_campaign_binding(copy.deepcopy(self.config), now=self.now)
        result = resolve_campaign_projection(campaign, resolve_config=resolver, now=self.now)
        self.assertEqual(result, expected)
        self.assertEqual(result["release_mode"], "NO_OUTBOUND")
        self.assertEqual(campaign, before)
        self.assertEqual(self.ports.rows, rows_before)
        self.assertEqual(len(self.ports.reads), 1)
        self.assertEqual(self.ports.writes, [])

    def test_repeated_reads_reenter_clock_service_and_consumer(self):
        clock = Mock(return_value=self.now)
        resolver = self.make(clock=clock)
        with patch.object(consumer, "trusted_raw_config", wraps=consumer.trusted_raw_config) as spy:
            a = resolver(self.scope["campaign_id"])
            b = resolver(self.scope["campaign_id"])
        self.assertEqual(a, b)
        self.assertIsNot(a, b)
        self.assertEqual(clock.call_count, 2)
        self.assertEqual(spy.call_count, 2)
        self.assertEqual(len(self.ports.reads), 2)

    def test_module_initialization_and_real_call_have_no_direct_io(self):
        source_path = ROOT / "source/first_materials_integration/catalog_config.py"
        code = compile(source_path.read_text(encoding="utf-8"), str(source_path), "exec")
        def forbidden(*args, **kwargs):
            raise AssertionError("Unexpected I/O, environment, process or implicit clock")
        class ForbiddenEnvironment(dict):
            def reject(self, *args, **kwargs):
                return forbidden(*args, **kwargs)
            __getitem__ = get = __contains__ = keys = items = values = copy = reject
        patches = [patch("builtins.open", side_effect=forbidden),
                   patch.object(io, "open", side_effect=forbidden),
                   patch.object(os, "getenv", side_effect=forbidden),
                   patch.object(os, "putenv", side_effect=forbidden),
                   patch.object(os, "unsetenv", side_effect=forbidden),
                   patch.object(socket, "create_connection", side_effect=forbidden),
                   patch.object(socket.socket, "connect", side_effect=forbidden),
                   patch.object(urllib.request, "urlopen", side_effect=forbidden),
                   patch.object(subprocess, "Popen", side_effect=forbidden),
                   patch.object(time, "time", side_effect=forbidden)]
        for method in ("open", "read_bytes", "read_text", "write_bytes", "write_text",
                       "stat", "lstat", "resolve", "absolute", "exists", "is_file",
                       "is_dir", "is_symlink", "iterdir", "glob", "rglob", "cwd"):
            patches.append(patch.object(Path, method, side_effect=forbidden))
        namespace = {"__name__": "candidate_import_probe", "__file__": str(source_path)}
        with ExitStack() as stack:
            # Replace the mapping without writing to the actual process
            # environment (putenv/unsetenv themselves are forbidden below).
            stack.enter_context(patch.object(os, "environ", ForbiddenEnvironment()))
            for patcher in patches:
                stack.enter_context(patcher)
            exec(code, namespace)
            resolver = namespace["make_catalog_config_resolver"](
                self.service, client_id=self.scope["client_id"],
                catalog_version="catalog-v1", clock=lambda: self.now)
            result = resolver(self.scope["campaign_id"])
        self.assertEqual(result, self.config)
        self.assertEqual(self.ports.writes, [])

    def test_product_source_has_no_system_clock_or_outbound_entrypoint(self):
        source = (ROOT / "source/first_materials_integration/catalog_config.py").read_text()
        tree = ast.parse(source)
        prohibited = {"open", "eval", "exec", "getenv", "putenv", "urlopen",
                      "connect", "system", "popen", "Popen", "now", "today", "utcnow"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else None)
                self.assertNotIn(name, prohibited)


if __name__ == "__main__":
    unittest.main()
