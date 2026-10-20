"""F1-12: pure projection of a validated FIRST campaign binding.

``project_campaign_binding`` takes a raw server-owned F105 config, validates
it with the accepted ``sales_first_binding.validate_first_binding`` and returns
a flat ``FIRST_CAMPAIGN_PROJECTION_V1`` dict (18 fields) for the runtime.

Contract (FIRST_WAVE3_12_V1):

* Error precedence: 1) any ``FirstBindingError`` raised by the F105 validator
  is propagated unchanged (same class, same ``.code``); 2) otherwise
  ``CampaignProjectionError`` with code ``PROJECTION_SCOPE_INVALID`` when the
  validator result does not have the exact validated F105 shape needed to
  build the projection (defensive scope check, never a second validation of
  the caller's input).
* The function is pure: no I/O, no clock (``now`` is passed explicitly), no
  environment, no database. The input ``config`` is never changed and the
  returned containers share no objects with the input.
* ``release_mode`` is always ``NO_OUTBOUND``. No other mode is produced and no
  permission to send is granted. Fact texts, offer name/description are not
  projected; only fact ids are.
* Error messages contain the stable code only, never input data.

Status of a successful call: ``PROJECTED_NO_OUTBOUND`` (a module constant;
it is not an output field).
"""

import copy
from datetime import datetime

from sales_first_binding import validate_first_binding

SCHEMA_VERSION = "FIRST_CAMPAIGN_PROJECTION_V1"
STATUS_PROJECTED_NO_OUTBOUND = "PROJECTED_NO_OUTBOUND"
RELEASE_MODE = "NO_OUTBOUND"
PROJECTION_SCOPE_INVALID = "PROJECTION_SCOPE_INVALID"

PROJECTION_FIELDS = (
    "schema_version",
    "client_id",
    "runtime_campaign_id",
    "make_campaign_id",
    "mailbox_ref",
    "sender_email",
    "offer_id",
    "binding_version",
    "owner_approval_ref",
    "valid_from",
    "expires_at",
    "release_mode",
    "approved_fact_ids",
    "default_locale",
    "allowed_locales",
    "language_pack_versions",
    "daily_send_limit",
    "max_followups",
)

_VALIDATED_SCHEMA_VERSION = "FIRST_BINDING_V1"
_VALIDATED_FIELDS = frozenset(
    {
        "schema_version",
        "client_id",
        "runtime_campaign_id",
        "make_campaign_id",
        "offer",
        "mailbox",
        "owner_approval_ref",
        "binding_version",
        "valid_from",
        "expires_at",
        "release_mode",
        "default_locale",
        "allowed_locales",
        "language_pack_versions",
        "daily_send_limit",
        "max_followups",
        "approved_facts",
        "approved_fact_ids",
    }
)
_OFFER_FIELDS = frozenset({"offer_id", "name", "description"})
_MAILBOX_FIELDS = frozenset({"mailbox_ref", "sender_email"})


class CampaignProjectionError(ValueError):
    """Projection failure with a stable, non-sensitive error code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _scope_invalid() -> None:
    raise CampaignProjectionError(PROJECTION_SCOPE_INVALID)


def _is_str_list(value: object) -> bool:
    return type(value) is list and all(type(item) is str for item in value)


def _is_utc_timestamp(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = datetime.fromisoformat(value)
        offset = parsed.utcoffset()
    except (TypeError, ValueError, OverflowError):
        return False
    return offset is not None and not offset


def _check_validated_shape(validated: object) -> None:
    """Fail with PROJECTION_SCOPE_INVALID unless ``validated`` is F105 output."""

    if type(validated) is not dict or validated.keys() != _VALIDATED_FIELDS:
        _scope_invalid()
    if validated["schema_version"] != _VALIDATED_SCHEMA_VERSION:
        _scope_invalid()
    offer = validated["offer"]
    mailbox = validated["mailbox"]
    if type(offer) is not dict or offer.keys() != _OFFER_FIELDS:
        _scope_invalid()
    if type(mailbox) is not dict or mailbox.keys() != _MAILBOX_FIELDS:
        _scope_invalid()


def _check_projection(projection: dict) -> None:
    """Fail with PROJECTION_SCOPE_INVALID unless the output meets the contract."""

    for field in (
        "client_id",
        "runtime_campaign_id",
        "make_campaign_id",
        "mailbox_ref",
        "sender_email",
        "offer_id",
        "binding_version",
        "owner_approval_ref",
        "default_locale",
    ):
        if type(projection[field]) is not str:
            _scope_invalid()
    if projection["release_mode"] != RELEASE_MODE:
        _scope_invalid()
    if not _is_utc_timestamp(projection["valid_from"]):
        _scope_invalid()
    if not _is_utc_timestamp(projection["expires_at"]):
        _scope_invalid()
    if not _is_str_list(projection["approved_fact_ids"]):
        _scope_invalid()
    allowed_locales = projection["allowed_locales"]
    if not _is_str_list(allowed_locales) or not allowed_locales:
        _scope_invalid()
    if projection["default_locale"] not in allowed_locales:
        _scope_invalid()
    versions = projection["language_pack_versions"]
    if (
        type(versions) is not dict
        or versions.keys() != set(allowed_locales)
        or any(type(version) is not str for version in versions.values())
    ):
        _scope_invalid()
    daily_send_limit = projection["daily_send_limit"]
    max_followups = projection["max_followups"]
    if type(daily_send_limit) is not int or daily_send_limit < 1:
        _scope_invalid()
    if type(max_followups) is not int or max_followups < 0:
        _scope_invalid()


def project_campaign_binding(config: dict, *, now: datetime) -> dict:
    """Validate ``config`` with F105 and return its flat campaign projection.

    ``FirstBindingError`` from the F105 validator is propagated unchanged.
    ``CampaignProjectionError`` (``PROJECTION_SCOPE_INVALID``) is raised when
    the validator result cannot be projected. ``config`` is not modified.
    """

    validated = validate_first_binding(config, now=now)
    _check_validated_shape(validated)
    try:
        projection = {
            "schema_version": SCHEMA_VERSION,
            "client_id": validated["client_id"],
            "runtime_campaign_id": validated["runtime_campaign_id"],
            "make_campaign_id": validated["make_campaign_id"],
            "mailbox_ref": validated["mailbox"]["mailbox_ref"],
            "sender_email": validated["mailbox"]["sender_email"],
            "offer_id": validated["offer"]["offer_id"],
            "binding_version": validated["binding_version"],
            "owner_approval_ref": validated["owner_approval_ref"],
            "valid_from": validated["valid_from"],
            "expires_at": validated["expires_at"],
            "release_mode": validated["release_mode"],
            "approved_fact_ids": copy.deepcopy(validated["approved_fact_ids"]),
            "default_locale": validated["default_locale"],
            "allowed_locales": copy.deepcopy(validated["allowed_locales"]),
            "language_pack_versions": copy.deepcopy(
                validated["language_pack_versions"]
            ),
            "daily_send_limit": validated["daily_send_limit"],
            "max_followups": validated["max_followups"],
        }
    except (KeyError, TypeError, AttributeError):
        raise CampaignProjectionError(PROJECTION_SCOPE_INVALID) from None
    _check_projection(projection)
    return projection
