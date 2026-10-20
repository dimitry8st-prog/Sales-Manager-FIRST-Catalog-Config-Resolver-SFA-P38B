"""Read the pinned server-owned catalog config through the accepted consumer.

This adapter introduces no authority, cache, storage or implicit clock. The
host supplies the service, version and operation clock. The existing catalog
and consumer continue to own authorization, revocation and bundle validation.
"""

import copy
from datetime import datetime
from uuid import UUID

import first_campaign_catalog.api as catalog_api
import first_campaign_catalog.consumer as catalog_consumer


class CatalogConfigError(ValueError):
    """A resolver validation failure containing only its contract code."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def make_catalog_config_resolver(service, *, client_id, catalog_version, clock):
    """Create a read-only F128 callback with fixed client and version pins.

    Constructing the callback never executes the service or clock. Every use
    reads and validates again; a new version requires a new callback.
    """
    if (
        not callable(getattr(service, "execute", None))
        or not callable(clock)
        or not catalog_api.is_id(client_id)
        or not catalog_api.is_id(catalog_version)
    ):
        raise CatalogConfigError("INVALID_RESOLVER_CONFIGURATION")

    def resolve_config(campaign_id):
        if type(campaign_id) is not str:
            raise CatalogConfigError("INVALID_CAMPAIGN_ID")
        try:
            canonical = str(UUID(campaign_id))
        except ValueError:
            raise CatalogConfigError("INVALID_CAMPAIGN_ID") from None
        if canonical != campaign_id:
            raise CatalogConfigError("INVALID_CAMPAIGN_ID")

        # Keep the clock call outside return-value validation: its exception
        # must pass through as the exact original object, without a retry.
        now = clock()
        if type(now) is not datetime:
            raise CatalogConfigError("INVALID_CLOCK")
        try:
            offset = now.utcoffset()
        except Exception:
            # An exact datetime can still contain an invalid custom tzinfo.
            raise CatalogConfigError("INVALID_CLOCK") from None
        if offset is None:
            raise CatalogConfigError("INVALID_CLOCK")

        scope = {"client_id": client_id, "campaign_id": campaign_id}
        result = catalog_consumer.trusted_raw_config(
            service, scope, catalog_version, now=now
        )
        return copy.deepcopy(result["raw_config"])

    return resolve_config
