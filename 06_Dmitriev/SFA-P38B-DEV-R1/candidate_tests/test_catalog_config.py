"""Own checks for the catalog-config resolver.

Positive reads use the real CatalogService, the real consumer and the real
F128 projection. Stubs are used only to count calls or to force one refusal.
"""

import ast
import copy
import contextlib
import sys
import uuid
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "source"), str(ROOT / "checks")]

import unittest

from helpers import CatalogFixturePorts, bundle, now, scope
from first_campaign_catalog import consumer
from first_campaign_catalog.api import create_service, is_id
from first_campaign_catalog.consumer import CatalogPortError
from first_materials_integration import catalog_config
from sales_campaign_projection import project_campaign_binding
from sales_runtime_binding import resolve_campaign_projection

CAMPAIGN_ID = scope()["campaign_id"]
CLIENT_ID = scope()["client_id"]
VERSION = "catalog-v1"
ODD_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class IdText(str):
    """str subclass: is_id and the campaign check both require exact str."""


class SubDateTime(datetime):
    """datetime subclass: the clock result must be an exact datetime."""


class OffsetNone(tzinfo):
    def utcoffset(self, dt):
        return None

    def tzname(self, dt):
        return "NONE"

    def dst(self, dt):
        return None


class RecordingPorts(CatalogFixturePorts):
    """Same in-memory catalog port, without the fixture's single-scope assert.

    The issued fixture refuses every other campaign id before the service can
    answer. This port still stores only the issued row, so another id is a
    real NOT_FOUND from CatalogService.
    """

    def __init__(self):
        super().__init__()
        self.last_scope = None

    @contextlib.contextmanager
    def transaction(self, incoming):
        self.last_scope = copy.deepcopy(incoming)
        self.calls += 1
        yield self


class CatalogConfigCandidateTests(unittest.TestCase):
    def assert_code(self, code, func):
        with self.assertRaises(catalog_config.CatalogConfigError) as caught:
            func()
        self.assertIsInstance(caught.exception, ValueError)
        self.assertEqual(code, caught.exception.code)
        self.assertEqual(code, str(caught.exception))
        self.assertEqual((code,), caught.exception.args)

    def build(self, ports=None, **kwargs):
        ports = ports or CatalogFixturePorts()
        arguments = {
            "client_id": CLIENT_ID,
            "catalog_version": VERSION,
            "clock": lambda: ports.now,
        }
        arguments.update(kwargs)
        service = create_service(ports)
        resolver = catalog_config.make_catalog_config_resolver(service, **arguments)
        return resolver, ports, service

    def test_real_catalog_consumer_f128_positive(self):
        resolver, ports, _service = self.build()
        moment = ports.now
        campaign = {
            "campaign_id": CAMPAIGN_ID,
            "config": {"malicious": True, "release_mode": "SEND"},
            "client_id": "payload-client",
            "catalog_version": "payload-version",
        }
        saved_campaign = copy.deepcopy(campaign)
        result = resolve_campaign_projection(
            campaign, resolve_config=resolver, now=moment
        )
        expected_config = consumer.trusted_raw_config(
            create_service(CatalogFixturePorts()),
            scope(),
            VERSION,
            now=moment,
        )["raw_config"]
        expected = project_campaign_binding(expected_config, now=moment)
        self.assertEqual(expected, result)
        self.assertEqual("NO_OUTBOUND", result["release_mode"])
        self.assertEqual(CLIENT_ID, result["client_id"])
        self.assertEqual(CAMPAIGN_ID, result["runtime_campaign_id"])
        self.assertEqual(1, ports.calls)
        self.assertEqual(saved_campaign, campaign)

    def test_constructor_calls_nothing(self):
        ports = CatalogFixturePorts()
        service = create_service(ports)
        events = []
        original = service.execute

        def execute(operation, request):
            events.append("execute")
            return original(operation, request)

        service.execute = execute

        def clock():
            events.append("clock")
            return ports.now

        with patch.object(consumer, "trusted_raw_config", wraps=consumer.trusted_raw_config) as spy:
            resolver = catalog_config.make_catalog_config_resolver(
                service,
                client_id=CLIENT_ID,
                catalog_version=VERSION,
                clock=clock,
            )
            self.assertEqual([], events)
            self.assertEqual(0, spy.call_count)
        self.assertEqual(0, ports.calls)
        self.assertTrue(callable(resolver))
        self.assertIs(ports.now, service._ports.now)

    def test_invalid_configuration_matrix(self):
        ports = CatalogFixturePorts()
        service = create_service(ports)
        calls = []

        def clock():
            calls.append("clock")
            return ports.now

        class Bare:
            pass

        class ExecuteRaises:
            @property
            def execute(self):
                raise RuntimeError("execute-unavailable")

        class ExecuteNotCallable:
            execute = "not-a-function"

        cases = (
            {"service": None},
            {"service": Bare()},
            {"service": ExecuteRaises()},
            {"service": ExecuteNotCallable()},
            {"client_id": None},
            {"client_id": True},
            {"client_id": 1},
            {"client_id": b"client-test"},
            {"client_id": IdText(CLIENT_ID)},
            {"catalog_version": None},
            {"catalog_version": True},
            {"catalog_version": IdText(VERSION)},
            {"clock": None},
            {"clock": "clock"},
        )
        for case in cases:
            arguments = {
                "service": service,
                "client_id": CLIENT_ID,
                "catalog_version": VERSION,
                "clock": clock,
            }
            arguments.update(case)
            service_arg = arguments.pop("service")
            self.assert_code(
                "INVALID_RESOLVER_CONFIGURATION",
                lambda: catalog_config.make_catalog_config_resolver(service_arg, **arguments),
            )
        self.assertEqual([], calls)
        self.assertEqual(0, ports.calls)

    def test_is_id_boundaries_are_not_tightened(self):
        accepted = (
            "a",
            "a" * 128,
            "я" * 128,
            "a b",
            "клиент-1",
            "версия/1",
            "\u0080",
            VERSION,
        )
        rejected = (
            "",
            "a" * 129,
            "я" * 129,
            " a",
            "a ",
            "a\nb",
            "a\x00b",
            "a\x1fb",
            "a\x7fb",
            "\x7f",
            None,
            True,
            1,
            b"abc",
            IdText("abc"),
        )
        for value in accepted:
            self.assertTrue(is_id(value), repr(value))
            calls = []
            resolver, ports, _service = self.build(
                client_id=value,
                catalog_version=value,
                clock=lambda: calls.append("clock"),
            )
            self.assertEqual([], calls)
            self.assertEqual(0, ports.calls)
            self.assertTrue(callable(resolver))
        for value in rejected:
            self.assertFalse(is_id(value), repr(value))
            calls = []
            self.assert_code(
                "INVALID_RESOLVER_CONFIGURATION",
                lambda: self.build(
                    client_id=value,
                    catalog_version=VERSION,
                    clock=lambda: calls.append("clock"),
                ),
            )
            self.assertEqual([], calls)

    def test_campaign_id_rejected_before_clock_and_service(self):
        events = []
        resolver, ports, service = self.build(clock=lambda: events.append("clock") or now())
        original = service.execute

        def execute(operation, request):
            events.append("execute")
            return original(operation, request)

        service.execute = execute
        samples = (
            None,
            True,
            1,
            b"11111111-1111-4111-8111-111111111111",
            "",
            "INVALID",
            "client-test",
            CAMPAIGN_ID.upper() if CAMPAIGN_ID.upper() != CAMPAIGN_ID else "ABCDEFAB-1234-1234-1234-ABCDEFABCDEF",
            ODD_UUID.upper(),
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeeE",
            "{" + ODD_UUID + "}",
            "urn:uuid:" + ODD_UUID,
            ODD_UUID.replace("-", ""),
            " " + ODD_UUID,
            ODD_UUID + "\n",
            "１１１１１１１１-１１１１-４１１１-８１１１-１１１１１１１１１１１１",
            IdText(ODD_UUID),
            uuid.UUID(ODD_UUID),
        )
        for sample in samples:
            self.assert_code("INVALID_CAMPAIGN_ID", lambda: resolver(sample))
        self.assertEqual([], events)
        self.assertEqual(0, ports.calls)

    def test_canonical_uuid_reaches_real_service_without_version_tightening(self):
        self.assertEqual(ODD_UUID, str(uuid.UUID(ODD_UUID)))
        ports = RecordingPorts()
        resolver, _ports, _service = self.build(ports)
        with self.assertRaises(CatalogPortError) as caught:
            resolver(ODD_UUID)
        self.assertEqual("NOT_FOUND", caught.exception.status)
        self.assertEqual(ODD_UUID, ports.last_scope["campaign_id"])
        self.assertEqual(CLIENT_ID, ports.last_scope["client_id"])
        self.assertEqual({"client_id", "campaign_id"}, set(ports.last_scope))
        self.assertEqual(1, ports.calls)

    def test_call_order_exact_scope_and_single_dependency_calls(self):
        ports = CatalogFixturePorts()
        service = create_service(ports)
        events = []
        original = service.execute

        def execute(operation, request):
            events.append(("execute", operation, copy.deepcopy(request)))
            return original(operation, request)

        service.execute = execute
        moment = now()

        def clock():
            events.append(("clock", moment))
            return moment

        resolver = catalog_config.make_catalog_config_resolver(
            service,
            client_id=CLIENT_ID,
            catalog_version=VERSION,
            clock=clock,
        )
        with patch.object(consumer, "trusted_raw_config", wraps=consumer.trusted_raw_config) as spy:
            resolver(CAMPAIGN_ID)
        self.assertEqual(["clock", "execute"], [name for name, *_rest in events])
        self.assertEqual(1, spy.call_count)
        self.assertIs(service, spy.call_args.args[0])
        self.assertEqual(scope(), spy.call_args.args[1])
        self.assertEqual(VERSION, spy.call_args.args[2])
        self.assertIs(moment, spy.call_args.kwargs["now"])
        self.assertEqual("resolve", events[1][1])
        self.assertEqual(scope(), events[1][2]["scope"])
        self.assertEqual(VERSION, events[1][2]["version"])
        self.assertEqual(1, ports.calls)

    def test_version_is_pinned_and_missing_version_has_no_fallback(self):
        ports = CatalogFixturePorts()
        service = create_service(ports)
        moment = now()
        pinned = catalog_config.make_catalog_config_resolver(
            service,
            client_id=CLIENT_ID,
            catalog_version=VERSION,
            clock=lambda: moment,
        )
        other = catalog_config.make_catalog_config_resolver(
            service,
            client_id=CLIENT_ID,
            catalog_version="missing-version",
            clock=lambda: moment,
        )
        with patch.object(consumer, "trusted_raw_config", wraps=consumer.trusted_raw_config) as spy:
            pinned(CAMPAIGN_ID)
            self.assertEqual(VERSION, spy.call_args.args[2])
            with self.assertRaises(CatalogPortError) as caught:
                other(CAMPAIGN_ID)
            self.assertEqual("missing-version", spy.call_args.args[2])
            pinned(CAMPAIGN_ID)
            self.assertEqual(VERSION, spy.call_args.args[2])
        self.assertEqual("NOT_FOUND", caught.exception.status)
        self.assertEqual(3, ports.calls)

    def test_naive_and_wrong_clock_do_not_call_service(self):
        samples = (
            datetime(2026, 10, 12, 12, 0),
            datetime(2026, 10, 12, 12, 0, tzinfo=OffsetNone()),
            SubDateTime(2026, 10, 12, 12, 0, tzinfo=timezone.utc),
            now().isoformat(),
            None,
            0,
            now().date(),
        )
        for sample in samples:
            calls = []
            resolver, ports, _service = self.build(clock=lambda value=sample: value)
            with patch.object(consumer, "trusted_raw_config", side_effect=AssertionError("consumer")):
                self.assert_code("INVALID_CLOCK", lambda: resolver(CAMPAIGN_ID))
            self.assertEqual([], calls)
            self.assertEqual(0, ports.calls)

    def test_clock_exception_is_the_same_object(self):
        sentinel = TimeoutError("clock-down")

        def clock():
            raise sentinel

        resolver, ports, _service = self.build(clock=clock)
        with patch.object(consumer, "trusted_raw_config", side_effect=AssertionError("consumer")):
            with self.assertRaises(TimeoutError) as caught:
                resolver(CAMPAIGN_ID)
        self.assertIs(sentinel, caught.exception)
        self.assertEqual(0, ports.calls)

    def test_foreign_client_is_refused(self):
        resolver, ports, _service = self.build()
        ports.auth["client_id"] = "other-client"
        with self.assertRaises(CatalogPortError) as caught:
            resolver(CAMPAIGN_ID)
        self.assertEqual("UNAUTHORIZED", caught.exception.status)
        self.assertEqual(0, ports.calls)

    def test_missing_authentication_is_refused(self):
        resolver, ports, _service = self.build()
        ports.auth = {
            "authenticated": False,
            "client_id": CLIENT_ID,
            "capabilities": ["catalog.read"],
        }
        with self.assertRaises(CatalogPortError) as caught:
            resolver(CAMPAIGN_ID)
        self.assertEqual("UNAUTHENTICATED", caught.exception.status)
        self.assertEqual(0, ports.calls)
        ports.auth = None
        with self.assertRaises(CatalogPortError) as caught:
            resolver(CAMPAIGN_ID)
        self.assertEqual("UNAUTHENTICATED", caught.exception.status)

    def test_missing_capability_is_not_added(self):
        resolver, ports, _service = self.build()
        ports.auth["capabilities"] = ["catalog.publish"]
        with self.assertRaises(CatalogPortError) as caught:
            resolver(CAMPAIGN_ID)
        self.assertEqual("UNAUTHORIZED", caught.exception.status)
        self.assertEqual(["catalog.publish"], ports.auth["capabilities"])
        self.assertEqual(0, ports.calls)

    def test_capability_change_after_success_is_visible(self):
        resolver, ports, _service = self.build()
        first = resolver(CAMPAIGN_ID)
        self.assertEqual(CLIENT_ID, first["client_id"])
        ports.auth["capabilities"] = []
        with self.assertRaises(CatalogPortError) as caught:
            resolver(CAMPAIGN_ID)
        self.assertEqual("UNAUTHORIZED", caught.exception.status)
        self.assertEqual(1, ports.calls)

    def test_revoke_after_success_is_not_cached(self):
        resolver, ports, _service = self.build()
        resolver(CAMPAIGN_ID)
        ports.row["revoked"] = True
        with self.assertRaises(CatalogPortError) as caught:
            resolver(CAMPAIGN_ID)
        self.assertEqual("REVOKED", caught.exception.data["code"])
        self.assertEqual(2, ports.calls)

    def test_expiry_after_success_is_not_cached(self):
        resolver, ports, _service = self.build()
        resolver(CAMPAIGN_ID)
        ports.now = datetime.fromisoformat(bundle()["valid_until"].replace("Z", "+00:00"))
        with self.assertRaises(CatalogPortError) as caught:
            resolver(CAMPAIGN_ID)
        self.assertEqual("BUNDLE_EXPIRED", caught.exception.data["code"])
        self.assertEqual(2, ports.calls)

    def test_repeat_read_uses_dependencies_again(self):
        resolver, ports, _service = self.build()
        with patch.object(consumer, "trusted_raw_config", wraps=consumer.trusted_raw_config) as spy:
            first = resolver(CAMPAIGN_ID)
            second = resolver(CAMPAIGN_ID)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first["offer"], second["offer"])
        self.assertEqual(2, spy.call_count)
        self.assertEqual(2, ports.calls)

    def test_consumer_exception_is_the_same_object(self):
        sentinel = ConnectionError("hidden-detail")
        resolver, ports, _service = self.build()
        with patch.object(consumer, "trusted_raw_config", side_effect=sentinel):
            with self.assertRaises(ConnectionError) as caught:
                resolver(CAMPAIGN_ID)
        self.assertIs(sentinel, caught.exception)
        self.assertEqual(0, ports.calls)

    def test_results_are_deep_independent_and_inputs_stay_unchanged(self):
        resolver, ports, service = self.build()
        before_row = copy.deepcopy(ports.row)
        before_auth = copy.deepcopy(ports.auth)
        before_now = ports.now
        holder = {}
        real = consumer.trusted_raw_config

        def observe(service_arg, incoming_scope, version, *, now):
            result = real(service_arg, incoming_scope, version, now=now)
            holder["raw"] = result["raw_config"]
            incoming_scope["client_id"] = "tampered"
            incoming_scope["extra"] = True
            return result

        with patch.object(consumer, "trusted_raw_config", side_effect=observe):
            returned = resolver(CAMPAIGN_ID)
        self.assertEqual(holder["raw"], returned)
        self.assertIsNot(holder["raw"], returned)
        self.assertIsNot(holder["raw"]["offer"], returned["offer"])
        holder["raw"]["offer"]["name"] = "changed-inside"
        self.assertNotEqual("changed-inside", returned["offer"]["name"])
        returned["offer"]["name"] = "changed-outside"
        returned["approved_facts"].append({"injected": True})
        with patch.object(consumer, "trusted_raw_config", wraps=consumer.trusted_raw_config):
            again = resolver(CAMPAIGN_ID)
        self.assertNotEqual("changed-outside", again["offer"]["name"])
        self.assertNotIn({"injected": True}, again["approved_facts"])
        self.assertEqual(before_row, ports.row)
        self.assertEqual(before_auth, ports.auth)
        self.assertIs(before_now, ports.now)
        self.assertIs(before_now, service._ports.now)

    def test_fresh_scope_after_a_consumer_mutates_the_previous_one(self):
        resolver, _ports, _service = self.build()
        seen = []
        real = consumer.trusted_raw_config

        def observe(service_arg, incoming_scope, version, *, now):
            seen.append(copy.deepcopy(incoming_scope))
            result = real(service_arg, incoming_scope, version, now=now)
            incoming_scope["client_id"] = "tampered"
            return result

        with patch.object(consumer, "trusted_raw_config", side_effect=observe):
            resolver(CAMPAIGN_ID)
            resolver(CAMPAIGN_ID)
        self.assertEqual([scope(), scope()], seen)

    def test_no_added_authority_io_or_system_clock(self):
        resolver, ports, _service = self.build()
        before_caps = copy.deepcopy(ports.auth["capabilities"])
        source = Path(catalog_config.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        clock_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"now", "utcnow", "today"}:
                    clock_calls.append(node.func.attr)
        self.assertEqual([], clock_calls)

        def denied(*_args, **_kwargs):
            raise AssertionError("forbidden-effect")

        with patch("builtins.open", denied), patch("socket.socket", denied), patch(
            "time.time", denied
        ):
            result = resolver(CAMPAIGN_ID)
        self.assertEqual(before_caps, ports.auth["capabilities"])
        self.assertEqual("NO_OUTBOUND", result["release_mode"])
        self.assertNotIn("pins", result)
        self.assertNotIn("bundle_ref", result)

    def test_module_stays_on_public_imports_and_namespace_package(self):
        module_path = Path(catalog_config.__file__).resolve()
        self.assertEqual(
            (ROOT / "source" / "first_materials_integration" / "catalog_config.py").resolve(),
            module_path,
        )
        self.assertFalse((module_path.parent / "__init__.py").exists())
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertEqual(
            {
                "copy",
                "uuid",
                "datetime",
                "first_campaign_catalog.api",
                "first_campaign_catalog.consumer",
            },
            imported,
        )


if __name__ == "__main__":
    unittest.main()
