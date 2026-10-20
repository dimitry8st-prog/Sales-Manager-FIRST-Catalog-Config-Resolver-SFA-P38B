"""Qualification gate between trusted discovery research and preparation.

Receives a discovery candidate, a research assessment and a server-side
binding projection; validates that they describe the same fresh scope and
returns one of three verdicts. The module performs no I/O: no network, no
database, no configuration reads and no system clock; time comes only from
the explicit ``now`` argument.
"""

from datetime import datetime, timezone
import re
from urllib.parse import urlsplit
from uuid import UUID

__all__ = ["QualificationError", "qualify_candidate"]

IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
SHA256_RE = re.compile(r"[0-9a-f]{64}")

CANDIDATE_SCHEMA = "FIRST_DISCOVERY_CANDIDATE_V1"
BINDING_SCHEMA = "FIRST_QUALIFICATION_BINDING_V1"
POLICY_SCHEMA = "FIRST_QUALIFICATION_POLICY_V1"
ASSESSMENT_SCHEMA = "FIRST_DISCOVERY_ASSESSMENT_V1"
RESULT_SCHEMA = "FIRST_QUALIFICATION_RESULT_V1"

CANDIDATE_FIELDS = frozenset({
    "schema_version", "candidate_id", "client_id", "runtime_campaign_id",
    "company_name", "contact_email", "source_url",
})
BINDING_FIELDS = frozenset({
    "schema_version", "client_id", "runtime_campaign_id", "offer_id",
    "binding_version",
})
POLICY_FIELDS = frozenset({
    "schema_version", "policy_version", "max_source_age_seconds",
    "max_assessment_age_seconds",
})
ASSESSMENT_FIELDS = frozenset({
    "schema_version", "assessment_id", "assessment_version", "company_name",
    "contact_email", "binding_version", "candidate_id", "client_id",
    "runtime_campaign_id", "offer_id", "source_url", "source_content_sha256",
    "source_observed_at", "checked_at", "source_kind", "source_state",
    "buyer_role", "offer_fit", "contact_association", "evidence_refs",
})

SOURCE_KINDS = frozenset({"PRIMARY", "OTHER"})
SOURCE_STATES = frozenset({"LIVE", "UNAVAILABLE", "UNKNOWN"})
BUYER_ROLES = frozenset({"BUYER", "PROVIDER_ONLY", "UNKNOWN"})
OFFER_FITS = frozenset({"MATCH", "NO_MATCH", "UNKNOWN"})
CONTACT_ASSOCIATIONS = frozenset({"CONFIRMED", "UNCONFIRMED"})


class QualificationError(ValueError):
    """Carries only a stable machine-readable code, never input data."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code

    def __str__(self):
        return self.code


def _check_schema(value, schema_version, fields):
    if set(value) != fields or value.get("schema_version") != schema_version:
        raise QualificationError("INVALID_SCHEMA") from None


def _identifier(value):
    if not isinstance(value, str) or IDENTIFIER_RE.fullmatch(value) is None:
        raise QualificationError("INVALID_IDENTITY") from None
    return value


def _uuid(value):
    if not isinstance(value, str):
        raise QualificationError("INVALID_IDENTITY") from None
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise QualificationError("INVALID_IDENTITY") from None
    if str(parsed) != value:
        raise QualificationError("INVALID_IDENTITY") from None
    return value


def _text(value, code):
    if not isinstance(value, str) or not value.strip():
        raise QualificationError(code) from None
    return value


def _email(value, code):
    if not isinstance(value, str):
        raise QualificationError(code) from None
    normalized = value.strip().lower()
    if EMAIL_RE.fullmatch(normalized) is None:
        raise QualificationError(code) from None
    return normalized


def _url(value, code):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise QualificationError(code) from None
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        username = parsed.username
        password = parsed.password
    except ValueError:
        raise QualificationError(code) from None
    if parsed.scheme != "https" or not hostname:
        raise QualificationError(code) from None
    if username is not None or password is not None:
        raise QualificationError(code) from None
    return value


def _seconds(value):
    if type(value) is not int or value <= 0:
        raise QualificationError("INVALID_POLICY") from None
    return value


def _age_over_limit(age, limit_seconds):
    age_us = (age.days * 86400 + age.seconds) * 1000000 + age.microseconds
    return age_us > limit_seconds * 1000000


def _enum(value, allowed, code):
    if not isinstance(value, str) or value not in allowed:
        raise QualificationError(code) from None
    return value


def _sha256(value):
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise QualificationError("INVALID_ASSESSMENT") from None
    return value


def _timestamp(value):
    if not isinstance(value, str) or not value:
        raise QualificationError("INVALID_TIME") from None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise QualificationError("INVALID_TIME") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise QualificationError("INVALID_TIME") from None
    return parsed


def _evidence_refs(value):
    if not isinstance(value, list) or not value:
        raise QualificationError("INVALID_ASSESSMENT") from None
    seen = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise QualificationError("INVALID_ASSESSMENT") from None
        if item in seen:
            raise QualificationError("INVALID_ASSESSMENT") from None
        seen.add(item)
    return value


def _iso_utc(moment):
    return moment.astimezone(timezone.utc).isoformat()


def qualify_candidate(candidate: dict, assessment: dict, *, binding: dict,
                      policy: dict, now: datetime) -> dict:
    for value in (candidate, binding, policy, assessment):
        if not isinstance(value, dict):
            raise QualificationError("INVALID_INPUT") from None
    if (not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None):
        raise QualificationError("INVALID_INPUT") from None

    _check_schema(candidate, CANDIDATE_SCHEMA, CANDIDATE_FIELDS)
    _check_schema(binding, BINDING_SCHEMA, BINDING_FIELDS)
    _check_schema(policy, POLICY_SCHEMA, POLICY_FIELDS)
    _check_schema(assessment, ASSESSMENT_SCHEMA, ASSESSMENT_FIELDS)

    _identifier(candidate["candidate_id"])
    _identifier(candidate["client_id"])
    _uuid(candidate["runtime_campaign_id"])
    _identifier(binding["client_id"])
    _uuid(binding["runtime_campaign_id"])
    _identifier(binding["offer_id"])
    _identifier(binding["binding_version"])
    _identifier(policy["policy_version"])
    _identifier(assessment["assessment_id"])
    _identifier(assessment["assessment_version"])
    _identifier(assessment["candidate_id"])
    _identifier(assessment["client_id"])
    _uuid(assessment["runtime_campaign_id"])
    _identifier(assessment["offer_id"])
    _identifier(assessment["binding_version"])

    _text(candidate["company_name"], "INVALID_CANDIDATE")
    candidate_email = _email(candidate["contact_email"], "INVALID_CANDIDATE")
    candidate_source_url = _url(candidate["source_url"], "INVALID_CANDIDATE")

    max_source_age = _seconds(policy["max_source_age_seconds"])
    max_assessment_age = _seconds(policy["max_assessment_age_seconds"])

    _text(assessment["company_name"], "INVALID_ASSESSMENT")
    assessment_email = _email(assessment["contact_email"], "INVALID_ASSESSMENT")
    assessment_source_url = _url(assessment["source_url"], "INVALID_ASSESSMENT")
    _sha256(assessment["source_content_sha256"])
    source_kind = _enum(
        assessment["source_kind"], SOURCE_KINDS, "INVALID_ASSESSMENT")
    source_state = _enum(
        assessment["source_state"], SOURCE_STATES, "INVALID_ASSESSMENT")
    buyer_role = _enum(
        assessment["buyer_role"], BUYER_ROLES, "INVALID_ASSESSMENT")
    offer_fit = _enum(
        assessment["offer_fit"], OFFER_FITS, "INVALID_ASSESSMENT")
    contact_association = _enum(
        assessment["contact_association"], CONTACT_ASSOCIATIONS,
        "INVALID_ASSESSMENT")
    _evidence_refs(assessment["evidence_refs"])

    if (candidate["client_id"] != assessment["client_id"]
            or candidate["client_id"] != binding["client_id"]):
        raise QualificationError("SCOPE_MISMATCH") from None
    if (candidate["runtime_campaign_id"] != assessment["runtime_campaign_id"]
            or candidate["runtime_campaign_id"] != binding["runtime_campaign_id"]):
        raise QualificationError("SCOPE_MISMATCH") from None
    if candidate["candidate_id"] != assessment["candidate_id"]:
        raise QualificationError("SCOPE_MISMATCH") from None
    if assessment["offer_id"] != binding["offer_id"]:
        raise QualificationError("SCOPE_MISMATCH") from None

    if assessment["binding_version"] != binding["binding_version"]:
        raise QualificationError("BINDING_VERSION_MISMATCH") from None

    if assessment["company_name"] != candidate["company_name"]:
        raise QualificationError("COMPANY_SCOPE_MISMATCH") from None

    if assessment_email != candidate_email:
        raise QualificationError("CONTACT_SCOPE_MISMATCH") from None

    if assessment_source_url != candidate_source_url:
        raise QualificationError("SOURCE_MISMATCH") from None

    observed_at = _timestamp(assessment["source_observed_at"])
    checked_at = _timestamp(assessment["checked_at"])
    if observed_at > checked_at or checked_at > now:
        raise QualificationError("INVALID_TIME") from None

    basis_reasons = []
    if _age_over_limit(now - observed_at, max_source_age):
        basis_reasons.append("SOURCE_STALE")
    if _age_over_limit(now - checked_at, max_assessment_age):
        basis_reasons.append("ASSESSMENT_STALE")
    if source_kind != "PRIMARY":
        basis_reasons.append("SOURCE_NOT_PRIMARY")
    if source_state != "LIVE":
        basis_reasons.append("SOURCE_NOT_LIVE")
    if basis_reasons:
        verdict = "NEEDS_REVIEW"
        reason_codes = basis_reasons
    else:
        negative_reasons = []
        if buyer_role == "PROVIDER_ONLY":
            negative_reasons.append("PROVIDER_ONLY")
        if offer_fit == "NO_MATCH":
            negative_reasons.append("OFFER_NOT_MATCHED")
        if negative_reasons:
            verdict = "NOT_QUALIFIED"
            reason_codes = negative_reasons
        else:
            unknown_reasons = []
            if buyer_role == "UNKNOWN":
                unknown_reasons.append("BUYER_ROLE_UNKNOWN")
            if offer_fit == "UNKNOWN":
                unknown_reasons.append("OFFER_FIT_UNKNOWN")
            if contact_association == "UNCONFIRMED":
                unknown_reasons.append("CONTACT_UNCONFIRMED")
            if unknown_reasons:
                verdict = "NEEDS_REVIEW"
                reason_codes = unknown_reasons
            else:
                verdict = "QUALIFIED_FOR_PREPARATION"
                reason_codes = ["QUALIFICATION_INPUTS_SUFFICIENT"]

    return {
        "schema_version": RESULT_SCHEMA,
        "verdict": verdict,
        "reason_codes": list(reason_codes),
        "candidate_id": candidate["candidate_id"],
        "client_id": binding["client_id"],
        "runtime_campaign_id": binding["runtime_campaign_id"],
        "offer_id": binding["offer_id"],
        "binding_version": binding["binding_version"],
        "policy_version": policy["policy_version"],
        "assessment_id": assessment["assessment_id"],
        "assessment_version": assessment["assessment_version"],
        "contact_email": candidate_email,
        "source_url": candidate_source_url,
        "source_content_sha256": assessment["source_content_sha256"],
        "source_observed_at": _iso_utc(observed_at),
        "checked_at": _iso_utc(checked_at),
        "evaluated_at": _iso_utc(now),
        "evidence_refs": list(assessment["evidence_refs"]),
    }
