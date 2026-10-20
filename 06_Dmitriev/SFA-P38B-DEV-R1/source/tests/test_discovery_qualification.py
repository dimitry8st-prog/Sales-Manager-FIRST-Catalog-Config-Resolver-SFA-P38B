import copy
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
import unittest

import sales_discovery_qualification as qualification

FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures"
    / "first_discovery_qualification" / "positive_basic.json")

EXPECTED_RESULT_KEYS = {
    "schema_version",
    "verdict",
    "reason_codes",
    "candidate_id",
    "client_id",
    "runtime_campaign_id",
    "offer_id",
    "binding_version",
    "policy_version",
    "assessment_id",
    "assessment_version",
    "contact_email",
    "source_url",
    "source_content_sha256",
    "source_observed_at",
    "checked_at",
    "evaluated_at",
    "evidence_refs",
}


UNSET = object()


def load_fixture():
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


class QualificationTestCase(unittest.TestCase):
    def run_qualification(self, fixture, now=UNSET):
        if now is UNSET:
            now = datetime.fromisoformat(fixture["now"])
        return qualification.qualify_candidate(
            fixture["candidate"],
            fixture["assessment"],
            binding=fixture["binding"],
            policy=fixture["policy"],
            now=now,
        )

    def assert_code(self, fixture, code, now=UNSET):
        with self.assertRaises(qualification.QualificationError) as context:
            self.run_qualification(fixture, now=now)
        self.assertEqual(code, context.exception.code)
        self.assertEqual(code, str(context.exception))
        self.assertIsInstance(context.exception, ValueError)
        return context.exception

    def assert_verdict(self, fixture, verdict, reason_codes, now=UNSET):
        result = self.run_qualification(fixture, now=now)
        self.assertEqual(verdict, result["verdict"])
        self.assertEqual(reason_codes, result["reason_codes"])
        return result


class QualificationPositiveTest(QualificationTestCase):
    def test_positive_fixture_returns_exact_result(self):
        fixture = load_fixture()
        result = self.run_qualification(fixture)
        self.assertEqual(EXPECTED_RESULT_KEYS, set(result.keys()))
        self.assertEqual("FIRST_QUALIFICATION_RESULT_V1",
                         result["schema_version"])
        self.assertEqual("QUALIFIED_FOR_PREPARATION", result["verdict"])
        self.assertEqual(["QUALIFICATION_INPUTS_SUFFICIENT"],
                         result["reason_codes"])
        self.assertEqual("candidate-test", result["candidate_id"])
        self.assertEqual("client-test", result["client_id"])
        self.assertEqual("11111111-1111-4111-8111-111111111111",
                         result["runtime_campaign_id"])
        self.assertEqual("offer-test", result["offer_id"])
        self.assertEqual("binding-v1", result["binding_version"])
        self.assertEqual("qualification-policy-v1", result["policy_version"])
        self.assertEqual("assessment-test", result["assessment_id"])
        self.assertEqual("assessment-v1", result["assessment_version"])
        self.assertEqual("buyer@example.test", result["contact_email"])
        self.assertEqual("https://buyer.example.test/request",
                         result["source_url"])
        self.assertEqual("a" * 64, result["source_content_sha256"])
        self.assertEqual("2026-10-12T10:00:00+00:00",
                         result["source_observed_at"])
        self.assertEqual("2026-10-12T11:30:00+00:00", result["checked_at"])
        self.assertEqual("2026-10-12T12:00:00+00:00", result["evaluated_at"])
        self.assertEqual(["fixture:source-test", "fixture:research-test"],
                         result["evidence_refs"])
        self.assertNotIn("approved", result)
        self.assertNotIn("live_enabled", result)

    def test_email_is_normalized_to_lower_case(self):
        fixture = load_fixture()
        self.assertEqual(" Buyer@Example.Test ",
                         fixture["candidate"]["contact_email"])
        result = self.run_qualification(fixture)
        self.assertEqual("buyer@example.test", result["contact_email"])

    def test_assessment_email_case_and_space_variant_stays_positive(self):
        fixture = load_fixture()
        fixture["assessment"]["contact_email"] = " Buyer@Example.Test "
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_arbitrary_company_and_offer_get_same_algorithm(self):
        fixture = load_fixture()
        fixture["candidate"]["company_name"] = "Zebra Logistics GmbH"
        fixture["assessment"]["company_name"] = "Zebra Logistics GmbH"
        fixture["binding"]["offer_id"] = "offer-zebra-42"
        fixture["assessment"]["offer_id"] = "offer-zebra-42"
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_identical_inputs_and_now_give_identical_result(self):
        first = self.run_qualification(load_fixture())
        second = self.run_qualification(load_fixture())
        self.assertEqual(first, second)
        self.assertIsNot(first["reason_codes"], second["reason_codes"])
        self.assertIsNot(first["evidence_refs"], second["evidence_refs"])

    def test_inputs_are_not_modified_on_success(self):
        fixture = load_fixture()
        snapshot = copy.deepcopy(fixture)
        self.run_qualification(fixture)
        self.assertEqual(snapshot, fixture)

    def test_inputs_are_not_modified_on_error(self):
        fixture = load_fixture()
        fixture["assessment"]["client_id"] = "other-client"
        snapshot = copy.deepcopy(fixture)
        self.assert_code(fixture, "SCOPE_MISMATCH")
        self.assertEqual(snapshot, fixture)

    def test_result_does_not_share_mutable_state_with_inputs(self):
        fixture = load_fixture()
        result = self.run_qualification(fixture)
        self.assertIsNot(result["evidence_refs"],
                         fixture["assessment"]["evidence_refs"])
        result["evidence_refs"].append("injected")
        result["reason_codes"].append("injected")
        self.assertEqual(
            ["fixture:source-test", "fixture:research-test"],
            fixture["assessment"]["evidence_refs"])
        fresh = self.run_qualification(load_fixture())
        self.assertEqual(["QUALIFICATION_INPUTS_SUFFICIENT"],
                         fresh["reason_codes"])

    def test_qualification_error_is_value_error_with_code_only(self):
        self.assertTrue(issubclass(qualification.QualificationError, ValueError))
        error = qualification.QualificationError("SOME_CODE")
        self.assertEqual("SOME_CODE", error.code)
        self.assertEqual("SOME_CODE", str(error))

    def test_binding_and_policy_are_keyword_only(self):
        fixture = load_fixture()
        now = datetime.fromisoformat(fixture["now"])
        with self.assertRaises(TypeError):
            qualification.qualify_candidate(
                fixture["candidate"], fixture["assessment"], fixture["binding"],
                fixture["policy"], now)

    def test_public_surface_is_exact(self):
        self.assertEqual(
            ["QualificationError", "qualify_candidate"],
            qualification.__all__)


class QualificationDecisionTest(QualificationTestCase):
    def test_buyer_role_buyer_is_qualified(self):
        fixture = load_fixture()
        fixture["assessment"]["buyer_role"] = "BUYER"
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_buyer_role_unknown_needs_review(self):
        fixture = load_fixture()
        fixture["assessment"]["buyer_role"] = "UNKNOWN"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["BUYER_ROLE_UNKNOWN"])

    def test_buyer_role_provider_only_not_qualified(self):
        fixture = load_fixture()
        fixture["assessment"]["buyer_role"] = "PROVIDER_ONLY"
        self.assert_verdict(fixture, "NOT_QUALIFIED", ["PROVIDER_ONLY"])

    def test_offer_fit_match_is_qualified(self):
        fixture = load_fixture()
        fixture["assessment"]["offer_fit"] = "MATCH"
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_offer_fit_no_match_not_qualified(self):
        fixture = load_fixture()
        fixture["assessment"]["offer_fit"] = "NO_MATCH"
        self.assert_verdict(fixture, "NOT_QUALIFIED", ["OFFER_NOT_MATCHED"])

    def test_offer_fit_unknown_needs_review(self):
        fixture = load_fixture()
        fixture["assessment"]["offer_fit"] = "UNKNOWN"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["OFFER_FIT_UNKNOWN"])

    def test_contact_confirmed_is_qualified(self):
        fixture = load_fixture()
        fixture["assessment"]["contact_association"] = "CONFIRMED"
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_contact_unconfirmed_needs_review(self):
        fixture = load_fixture()
        fixture["assessment"]["contact_association"] = "UNCONFIRMED"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["CONTACT_UNCONFIRMED"])

    def test_source_kind_primary_is_qualified(self):
        fixture = load_fixture()
        fixture["assessment"]["source_kind"] = "PRIMARY"
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_source_kind_other_needs_review(self):
        fixture = load_fixture()
        fixture["assessment"]["source_kind"] = "OTHER"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["SOURCE_NOT_PRIMARY"])

    def test_source_state_live_is_qualified(self):
        fixture = load_fixture()
        fixture["assessment"]["source_state"] = "LIVE"
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_source_state_unavailable_needs_review(self):
        fixture = load_fixture()
        fixture["assessment"]["source_state"] = "UNAVAILABLE"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["SOURCE_NOT_LIVE"])

    def test_source_state_unknown_needs_review(self):
        fixture = load_fixture()
        fixture["assessment"]["source_state"] = "UNKNOWN"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["SOURCE_NOT_LIVE"])

    def test_all_basis_reasons_keep_declared_order(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = (
            "2026-10-10T10:00:00+00:00")
        fixture["assessment"]["checked_at"] = "2026-10-10T11:00:00+00:00"
        fixture["assessment"]["source_kind"] = "OTHER"
        fixture["assessment"]["source_state"] = "UNKNOWN"
        self.assert_verdict(fixture, "NEEDS_REVIEW", [
            "SOURCE_STALE",
            "ASSESSMENT_STALE",
            "SOURCE_NOT_PRIMARY",
            "SOURCE_NOT_LIVE",
        ])

    def test_stale_source_keeps_order_with_not_live(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = (
            "2026-10-10T10:00:00+00:00")
        fixture["assessment"]["source_state"] = "UNKNOWN"
        self.assert_verdict(
            fixture, "NEEDS_REVIEW", ["SOURCE_STALE", "SOURCE_NOT_LIVE"])

    def test_assessment_stale_keeps_order_with_not_primary(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = "2026-10-12T10:00:00+00:00"
        fixture["assessment"]["source_kind"] = "OTHER"
        self.assert_verdict(
            fixture, "NEEDS_REVIEW",
            ["ASSESSMENT_STALE", "SOURCE_NOT_PRIMARY"])

    def test_source_stale_beats_provider_only(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = (
            "2026-10-10T10:00:00+00:00")
        fixture["assessment"]["buyer_role"] = "PROVIDER_ONLY"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["SOURCE_STALE"])

    def test_source_stale_beats_offer_no_match(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = (
            "2026-10-10T10:00:00+00:00")
        fixture["assessment"]["offer_fit"] = "NO_MATCH"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["SOURCE_STALE"])

    def test_source_not_live_beats_offer_no_match(self):
        fixture = load_fixture()
        fixture["assessment"]["source_state"] = "UNKNOWN"
        fixture["assessment"]["offer_fit"] = "NO_MATCH"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["SOURCE_NOT_LIVE"])

    def test_source_not_live_beats_provider_only(self):
        fixture = load_fixture()
        fixture["assessment"]["source_state"] = "UNKNOWN"
        fixture["assessment"]["buyer_role"] = "PROVIDER_ONLY"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["SOURCE_NOT_LIVE"])

    def test_source_not_primary_beats_provider_only(self):
        fixture = load_fixture()
        fixture["assessment"]["source_kind"] = "OTHER"
        fixture["assessment"]["buyer_role"] = "PROVIDER_ONLY"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["SOURCE_NOT_PRIMARY"])

    def test_source_not_primary_beats_offer_no_match(self):
        fixture = load_fixture()
        fixture["assessment"]["source_kind"] = "OTHER"
        fixture["assessment"]["offer_fit"] = "NO_MATCH"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["SOURCE_NOT_PRIMARY"])

    def test_assessment_stale_example_from_spec(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = "2026-10-12T10:00:00+00:00"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["ASSESSMENT_STALE"])

    def test_assessment_stale_beats_provider_only(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = "2026-10-12T10:00:00+00:00"
        fixture["assessment"]["buyer_role"] = "PROVIDER_ONLY"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["ASSESSMENT_STALE"])

    def test_assessment_stale_beats_offer_no_match(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = "2026-10-12T10:00:00+00:00"
        fixture["assessment"]["offer_fit"] = "NO_MATCH"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["ASSESSMENT_STALE"])

    def test_negative_reasons_keep_declared_order(self):
        fixture = load_fixture()
        fixture["assessment"]["buyer_role"] = "PROVIDER_ONLY"
        fixture["assessment"]["offer_fit"] = "NO_MATCH"
        self.assert_verdict(
            fixture, "NOT_QUALIFIED",
            ["PROVIDER_ONLY", "OFFER_NOT_MATCHED"])

    def test_fresh_no_match_ignores_unconfirmed_contact(self):
        fixture = load_fixture()
        fixture["assessment"]["offer_fit"] = "NO_MATCH"
        fixture["assessment"]["contact_association"] = "UNCONFIRMED"
        self.assert_verdict(fixture, "NOT_QUALIFIED", ["OFFER_NOT_MATCHED"])

    def test_negative_reasons_beat_unknown_reasons(self):
        fixture = load_fixture()
        fixture["assessment"]["buyer_role"] = "PROVIDER_ONLY"
        fixture["assessment"]["offer_fit"] = "UNKNOWN"
        fixture["assessment"]["contact_association"] = "UNCONFIRMED"
        self.assert_verdict(fixture, "NOT_QUALIFIED", ["PROVIDER_ONLY"])

    def test_unknown_reasons_keep_declared_order(self):
        fixture = load_fixture()
        fixture["assessment"]["buyer_role"] = "UNKNOWN"
        fixture["assessment"]["offer_fit"] = "UNKNOWN"
        fixture["assessment"]["contact_association"] = "UNCONFIRMED"
        self.assert_verdict(fixture, "NEEDS_REVIEW", [
            "BUYER_ROLE_UNKNOWN",
            "OFFER_FIT_UNKNOWN",
            "CONTACT_UNCONFIRMED",
        ])

    def test_rejection_of_one_candidate_does_not_exhaust_market(self):
        rejected = load_fixture()
        rejected["assessment"]["offer_fit"] = "NO_MATCH"
        self.assert_verdict(rejected, "NOT_QUALIFIED", ["OFFER_NOT_MATCHED"])
        next_candidate = load_fixture()
        next_candidate["candidate"]["candidate_id"] = "candidate-next"
        next_candidate["assessment"]["candidate_id"] = "candidate-next"
        next_candidate["candidate"]["company_name"] = "Another Buyer Ltd"
        next_candidate["assessment"]["company_name"] = "Another Buyer Ltd"
        self.assert_verdict(
            next_candidate, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_invalid_enum_values_are_rejected(self):
        cases = [
            ("source_kind", "SECONDARY"),
            ("source_state", "DOWN"),
            ("buyer_role", "SELLER"),
            ("offer_fit", "PARTIAL"),
            ("contact_association", "MAYBE"),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                fixture = load_fixture()
                fixture["assessment"][field] = value
                self.assert_code(fixture, "INVALID_ASSESSMENT")


class QualificationTimeTest(QualificationTestCase):
    def test_source_age_exactly_at_limit_stays_fresh(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = (
            "2026-10-11T12:00:00+00:00")
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_source_age_one_second_over_limit_is_stale(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = (
            "2026-10-11T11:59:59+00:00")
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["SOURCE_STALE"])

    def test_assessment_age_exactly_at_limit_stays_fresh(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = "2026-10-12T11:00:00+00:00"
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_assessment_age_one_second_over_limit_is_stale(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = "2026-10-12T10:59:59+00:00"
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["ASSESSMENT_STALE"])

    # F110-RV-01: huge limits are 10**20 / 10**100 (not 1020 / 10100).
    def test_huge_max_source_age_stays_qualified(self):
        fixture = load_fixture()
        fixture["policy"]["max_source_age_seconds"] = 86400000000000
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_huge_max_assessment_age_stays_qualified(self):
        fixture = load_fixture()
        fixture["policy"]["max_assessment_age_seconds"] = 86400000000000
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_max_source_age_10_pow_20_stays_qualified(self):
        fixture = load_fixture()
        fixture["policy"]["max_source_age_seconds"] = 10**20
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_max_assessment_age_10_pow_20_stays_qualified(self):
        fixture = load_fixture()
        fixture["policy"]["max_assessment_age_seconds"] = 10**20
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_max_source_age_10_pow_100_stays_qualified(self):
        fixture = load_fixture()
        fixture["policy"]["max_source_age_seconds"] = 10**100
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_max_assessment_age_10_pow_100_stays_qualified(self):
        fixture = load_fixture()
        fixture["policy"]["max_assessment_age_seconds"] = 10**100
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_source_age_equal_to_limit_stays_qualified(self):
        fixture = load_fixture()
        fixture["policy"]["max_source_age_seconds"] = 7200
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_assessment_age_equal_to_limit_stays_qualified(self):
        fixture = load_fixture()
        fixture["policy"]["max_assessment_age_seconds"] = 1800
        self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])

    def test_source_age_one_microsecond_over_limit_is_stale(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = (
            "2026-10-11T11:59:59.999999+00:00")
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["SOURCE_STALE"])

    def test_assessment_age_one_microsecond_over_limit_is_stale(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = (
            "2026-10-12T10:59:59.999999+00:00")
        self.assert_verdict(fixture, "NEEDS_REVIEW", ["ASSESSMENT_STALE"])

    def test_same_instant_with_different_utc_offsets_is_accepted(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = (
            "2026-10-12T11:00:00+01:00")
        result = self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])
        self.assertEqual("2026-10-12T10:00:00+00:00",
                         result["source_observed_at"])

    def test_equal_instants_with_different_offsets_keep_order(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = (
            "2026-10-12T13:30:00+02:00")
        result = self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])
        self.assertEqual("2026-10-12T11:30:00+00:00",
                         result["source_observed_at"])
        self.assertEqual("2026-10-12T11:30:00+00:00", result["checked_at"])

    def test_now_with_offset_is_reported_as_utc(self):
        fixture = load_fixture()
        now = datetime.fromisoformat("2026-10-12T14:00:00+02:00")
        result = self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"], now=now)
        self.assertEqual("2026-10-12T12:00:00+00:00", result["evaluated_at"])

    def test_z_suffix_timestamp_is_accepted(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = (
            "2026-10-12T10:00:00Z")
        result = self.assert_verdict(
            fixture, "QUALIFIED_FOR_PREPARATION",
            ["QUALIFICATION_INPUTS_SUFFICIENT"])
        self.assertEqual("2026-10-12T10:00:00+00:00",
                         result["source_observed_at"])

    def test_naive_now_is_invalid_input(self):
        fixture = load_fixture()
        self.assert_code(fixture, "INVALID_INPUT",
                         now=datetime(2026, 10, 12, 12, 0, 0))

    def test_non_datetime_now_is_invalid_input(self):
        fixture = load_fixture()
        self.assert_code(fixture, "INVALID_INPUT",
                         now="2026-10-12T12:00:00+00:00")

    def test_none_now_is_invalid_input(self):
        fixture = load_fixture()
        self.assert_code(fixture, "INVALID_INPUT", now=None)

    def test_naive_source_observed_at_is_invalid_time(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = "2026-10-12T10:00:00"
        self.assert_code(fixture, "INVALID_TIME")

    def test_naive_checked_at_is_invalid_time(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = "2026-10-12T11:30:00"
        self.assert_code(fixture, "INVALID_TIME")

    def test_unparseable_timestamp_is_invalid_time(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = "not-a-timestamp"
        self.assert_code(fixture, "INVALID_TIME")

    def test_empty_timestamp_is_invalid_time(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = ""
        self.assert_code(fixture, "INVALID_TIME")

    def test_non_string_timestamp_is_invalid_time(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = 12345
        self.assert_code(fixture, "INVALID_TIME")

    def test_future_checked_at_is_invalid_time(self):
        fixture = load_fixture()
        fixture["assessment"]["checked_at"] = "2026-10-12T12:00:01+00:00"
        self.assert_code(fixture, "INVALID_TIME")

    def test_source_observed_after_checked_is_invalid_time(self):
        fixture = load_fixture()
        fixture["assessment"]["source_observed_at"] = (
            "2026-10-12T12:00:00+00:00")
        self.assert_code(fixture, "INVALID_TIME")

    def test_freshness_follows_passed_now_not_system_clock(self):
        fixture = load_fixture()
        now = datetime(2036, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
        self.assert_verdict(
            fixture, "NEEDS_REVIEW",
            ["SOURCE_STALE", "ASSESSMENT_STALE"], now=now)


class QualificationScopeTest(QualificationTestCase):
    def test_foreign_assessment_client_is_scope_mismatch(self):
        fixture = load_fixture()
        fixture["assessment"]["client_id"] = "other-client"
        self.assert_code(fixture, "SCOPE_MISMATCH")

    def test_foreign_binding_client_is_scope_mismatch(self):
        fixture = load_fixture()
        fixture["binding"]["client_id"] = "other-client"
        self.assert_code(fixture, "SCOPE_MISMATCH")

    def test_foreign_campaign_is_scope_mismatch(self):
        for owner in ("assessment", "binding"):
            with self.subTest(owner=owner):
                fixture = load_fixture()
                fixture[owner]["runtime_campaign_id"] = (
                    "22222222-2222-4222-8222-222222222222")
                self.assert_code(fixture, "SCOPE_MISMATCH")

    def test_foreign_candidate_id_is_scope_mismatch(self):
        fixture = load_fixture()
        fixture["assessment"]["candidate_id"] = "other-candidate"
        self.assert_code(fixture, "SCOPE_MISMATCH")

    def test_foreign_offer_id_is_scope_mismatch(self):
        fixture = load_fixture()
        fixture["assessment"]["offer_id"] = "other-offer"
        self.assert_code(fixture, "SCOPE_MISMATCH")

    def test_changed_candidate_email_is_contact_scope_mismatch(self):
        fixture = load_fixture()
        fixture["candidate"]["contact_email"] = "other-buyer@example.test"
        self.assert_code(fixture, "CONTACT_SCOPE_MISMATCH")

    def test_changed_candidate_company_is_company_scope_mismatch(self):
        fixture = load_fixture()
        fixture["candidate"]["company_name"] = "Other Synthetic Buyer"
        self.assert_code(fixture, "COMPANY_SCOPE_MISMATCH")

    def test_company_name_trailing_space_is_company_scope_mismatch(self):
        fixture = load_fixture()
        fixture["candidate"]["company_name"] = "Synthetic Buyer "
        self.assert_code(fixture, "COMPANY_SCOPE_MISMATCH")

    def test_new_binding_version_is_binding_version_mismatch(self):
        fixture = load_fixture()
        fixture["binding"]["binding_version"] = "binding-v2"
        self.assert_code(fixture, "BINDING_VERSION_MISMATCH")

    def test_changed_assessment_source_url_is_source_mismatch(self):
        fixture = load_fixture()
        fixture["assessment"]["source_url"] = (
            "https://other.example.test/request")
        self.assert_code(fixture, "SOURCE_MISMATCH")

    def test_mismatch_error_precedence_cascade(self):
        scope = {"assessment": {"client_id": "other-client"}}
        version = {"binding": {"binding_version": "binding-v2"}}
        company = {"candidate": {"company_name": "Other Synthetic Buyer"}}
        contact = {"candidate": {"contact_email": "other-buyer@example.test"}}
        source = {"assessment": {"source_url":
                                 "https://other.example.test/request"}}
        cases = [
            ([scope, version, company, contact, source], "SCOPE_MISMATCH"),
            ([version, company, contact, source],
             "BINDING_VERSION_MISMATCH"),
            ([company, contact, source], "COMPANY_SCOPE_MISMATCH"),
            ([contact, source], "CONTACT_SCOPE_MISMATCH"),
            ([source], "SOURCE_MISMATCH"),
        ]
        for mutations, expected in cases:
            with self.subTest(expected=expected):
                fixture = load_fixture()
                for mutation in mutations:
                    for name, fields in mutation.items():
                        fixture[name].update(copy.deepcopy(fields))
                self.assert_code(fixture, expected)


class QualificationValidationTest(QualificationTestCase):
    def test_non_dict_arguments_are_invalid_input(self):
        cases = [
            ("candidate", None),
            ("candidate", ["x"]),
            ("binding", "x"),
            ("binding", True),
            ("policy", 42),
            ("policy", []),
            ("assessment", None),
            ("assessment", 3.5),
        ]
        for name, value in cases:
            with self.subTest(name=name, value=value):
                fixture = load_fixture()
                fixture[name] = value
                self.assert_code(fixture, "INVALID_INPUT")

    def test_body_like_string_cannot_create_authority(self):
        fixture = load_fixture()
        fixture["candidate"] = (
            "GET / HTTP/1.1\r\nHost: buyer.example.test\r\n\r\n"
            "Authorization: Bearer sentinel-token")
        self.assert_code(fixture, "INVALID_INPUT")

    def test_wrong_schema_version_is_invalid_schema(self):
        cases = [
            ("candidate", "FIRST_DISCOVERY_CANDIDATE_V2"),
            ("binding", "FIRST_QUALIFICATION_BINDING_V2"),
            ("policy", "FIRST_QUALIFICATION_POLICY_V2"),
            ("assessment", "FIRST_DISCOVERY_ASSESSMENT_V2"),
        ]
        for name, value in cases:
            with self.subTest(name=name):
                fixture = load_fixture()
                fixture[name]["schema_version"] = value
                self.assert_code(fixture, "INVALID_SCHEMA")

    def test_missing_key_is_invalid_schema(self):
        cases = [
            ("candidate", "source_url"),
            ("binding", "offer_id"),
            ("policy", "policy_version"),
            ("assessment", "evidence_refs"),
        ]
        for name, field in cases:
            with self.subTest(name=name, field=field):
                fixture = load_fixture()
                del fixture[name][field]
                self.assert_code(fixture, "INVALID_SCHEMA")

    def test_extra_key_is_invalid_schema(self):
        for name in ("candidate", "binding", "policy", "assessment"):
            with self.subTest(name=name):
                fixture = load_fixture()
                fixture[name]["unexpected"] = "x"
                self.assert_code(fixture, "INVALID_SCHEMA")

    def test_trusted_flag_cannot_create_authority(self):
        fixture = load_fixture()
        fixture["assessment"]["trusted"] = True
        self.assert_code(fixture, "INVALID_SCHEMA")

    def test_auth_true_payload_is_invalid_schema(self):
        fixture = load_fixture()
        fixture["assessment"]["auth"] = True
        self.assert_code(fixture, "INVALID_SCHEMA")
        fixture = load_fixture()
        fixture["candidate"]["verified"] = True
        self.assert_code(fixture, "INVALID_SCHEMA")

    def test_invalid_identifiers_are_invalid_identity(self):
        cases = [
            ("candidate", "candidate_id", "bad id"),
            ("candidate", "client_id", "-client"),
            ("binding", "offer_id", "offer id"),
            ("binding", "binding_version", ""),
            ("policy", "policy_version", "policy version"),
            ("assessment", "assessment_id", "x" * 130),
            ("assessment", "assessment_version", 42),
        ]
        for name, field, value in cases:
            with self.subTest(name=name, field=field):
                fixture = load_fixture()
                fixture[name][field] = value
                self.assert_code(fixture, "INVALID_IDENTITY")

    def test_invalid_uuids_are_invalid_identity(self):
        cases = [
            ("candidate", "not-a-uuid"),
            ("candidate", "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"),
            ("binding", "11111111-1111-4111-8111-111111111111 "),
            ("assessment", 123),
        ]
        for name, value in cases:
            with self.subTest(name=name, value=value):
                fixture = load_fixture()
                fixture[name]["runtime_campaign_id"] = value
                self.assert_code(fixture, "INVALID_IDENTITY")

    def test_bool_policy_limit_is_invalid_policy(self):
        fixture = load_fixture()
        fixture["policy"]["max_assessment_age_seconds"] = True
        self.assert_code(fixture, "INVALID_POLICY")

    def test_non_positive_policy_limits_are_invalid_policy(self):
        cases = [0, -1, 1.5, "3600", None, False]
        for value in cases:
            with self.subTest(value=value):
                fixture = load_fixture()
                fixture["policy"]["max_source_age_seconds"] = value
                self.assert_code(fixture, "INVALID_POLICY")

    def test_empty_evidence_refs_are_invalid_assessment(self):
        fixture = load_fixture()
        fixture["assessment"]["evidence_refs"] = []
        self.assert_code(fixture, "INVALID_ASSESSMENT")

    def test_duplicate_evidence_refs_are_invalid_assessment(self):
        fixture = load_fixture()
        fixture["assessment"]["evidence_refs"] = [
            "fixture:source-test", "fixture:source-test"]
        self.assert_code(fixture, "INVALID_ASSESSMENT")

    def test_blank_evidence_ref_is_invalid_assessment(self):
        fixture = load_fixture()
        fixture["assessment"]["evidence_refs"] = ["fixture:source-test", "   "]
        self.assert_code(fixture, "INVALID_ASSESSMENT")

    def test_non_list_evidence_refs_are_invalid_assessment(self):
        for value in ("fixture:source-test", {"a": 1}, 5):
            with self.subTest(value=value):
                fixture = load_fixture()
                fixture["assessment"]["evidence_refs"] = value
                self.assert_code(fixture, "INVALID_ASSESSMENT")

    def test_non_string_evidence_ref_is_invalid_assessment(self):
        fixture = load_fixture()
        fixture["assessment"]["evidence_refs"] = ["fixture:source-test", 7]
        self.assert_code(fixture, "INVALID_ASSESSMENT")

    def test_invalid_sha256_is_invalid_assessment(self):
        cases = [
            "A" * 64,
            "a" * 63,
            "a" * 65,
            "z" * 64,
            42,
        ]
        for value in cases:
            with self.subTest(value=value):
                fixture = load_fixture()
                fixture["assessment"]["source_content_sha256"] = value
                self.assert_code(fixture, "INVALID_ASSESSMENT")

    def test_invalid_candidate_email_is_invalid_candidate(self):
        cases = ["nope", "@example.test", "buyer@", "", 42]
        for value in cases:
            with self.subTest(value=value):
                fixture = load_fixture()
                fixture["candidate"]["contact_email"] = value
                self.assert_code(fixture, "INVALID_CANDIDATE")

    def test_invalid_assessment_email_is_invalid_assessment(self):
        cases = ["nope", "buyer@@example.test", ""]
        for value in cases:
            with self.subTest(value=value):
                fixture = load_fixture()
                fixture["assessment"]["contact_email"] = value
                self.assert_code(fixture, "INVALID_ASSESSMENT")

    def test_invalid_candidate_urls_are_invalid_candidate(self):
        cases = [
            "http://buyer.example.test/request",
            "ftp://buyer.example.test/file",
            "https://",
            "https://user:pass@buyer.example.test/request",
            " https://buyer.example.test/request",
            "https://buyer.example.test/request ",
            "https://[bad/request",
            "",
            42,
        ]
        for value in cases:
            with self.subTest(value=value):
                fixture = load_fixture()
                fixture["candidate"]["source_url"] = value
                self.assert_code(fixture, "INVALID_CANDIDATE")

    def test_invalid_assessment_url_is_invalid_assessment(self):
        fixture = load_fixture()
        fixture["assessment"]["source_url"] = "http://buyer.example.test/x"
        self.assert_code(fixture, "INVALID_ASSESSMENT")

    def test_empty_company_name_is_rejected(self):
        fixture = load_fixture()
        fixture["candidate"]["company_name"] = "   "
        self.assert_code(fixture, "INVALID_CANDIDATE")
        fixture = load_fixture()
        fixture["assessment"]["company_name"] = ""
        self.assert_code(fixture, "INVALID_ASSESSMENT")

    def test_non_string_company_name_is_rejected(self):
        fixture = load_fixture()
        fixture["candidate"]["company_name"] = 7
        self.assert_code(fixture, "INVALID_CANDIDATE")
        fixture = load_fixture()
        fixture["assessment"]["company_name"] = ["Synthetic Buyer"]
        self.assert_code(fixture, "INVALID_ASSESSMENT")

    def test_error_message_does_not_leak_sentinel_values(self):
        fixture = load_fixture()
        fixture["candidate"]["company_name"] = "SENTINEL_COMPANY_ABC123"
        fixture["assessment"]["company_name"] = "Different Company"
        error = self.assert_code(fixture, "COMPANY_SCOPE_MISMATCH")
        self.assertNotIn("SENTINEL_COMPANY_ABC123", str(error))
        self.assertNotIn("Different Company", str(error))

        fixture = load_fixture()
        fixture["candidate"]["contact_email"] = "sentinel@@invalid"
        error = self.assert_code(fixture, "INVALID_CANDIDATE")
        self.assertNotIn("sentinel", str(error))

        fixture = load_fixture()
        fixture["candidate"]["source_url"] = (
            "http://sentinel.example.test/secret")
        error = self.assert_code(fixture, "INVALID_CANDIDATE")
        self.assertNotIn("sentinel", str(error))


class QualificationPurityTest(QualificationTestCase):
    def test_module_source_has_no_io_network_clock_or_env(self):
        source = inspect.getsource(qualification)
        forbidden = (
            "psycopg",
            "socket",
            "requests",
            "urlopen",
            "getenv",
            ".environ",
            "os.environ",
            "import os",
            "from os ",
            "datetime.now(",
            "datetime.utcnow(",
            "time.time(",
            "open(",
            "eval(",
            "exec(",
        )
        for token in forbidden:
            self.assertNotIn(token, source, token)

    def test_module_does_not_import_other_project_modules(self):
        source = inspect.getsource(qualification)
        for token in (
            "sales_manager",
            "sales_store",
            "sales_contracts",
            "sales_rules",
            "sales_preparation",
            "sales_mailbox",
            "connectors",
            "import sales",
        ):
            self.assertNotIn(token, source, token)
        for name in ("psycopg", "socket", "requests", "os"):
            self.assertNotIn(name, qualification.__dict__)


if __name__ == "__main__":
    unittest.main()
