"""Read-only adapter from an accepted CatalogService to the F128 callback.

The host pins client_id, catalog_version and clock when it builds a resolver.
Each later call checks the campaign id, reads the clock once, and asks the
accepted catalog consumer for that same pin. Nothing is cached, and this
module does not choose a current catalog version or grant any authority.
"""

import copy
import uuid
from datetime import datetime

import first_campaign_catalog.api as catalog_api
import first_campaign_catalog.consumer as catalog_consumer


class CatalogConfigError(ValueError):
    """Failure whose .code and str() are only the contract code."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical_campaign_id(value):
    """True only for an exact str in canonical lowercase UUID form."""
    if type(value) is not str:
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return str(parsed) == value


def make_catalog_config_resolver(service, *, client_id, catalog_version, clock):
    """Return resolver(campaign_id) bound to one client, version and clock.

    The constructor checks the arguments and does not call the service or clock.
    A bad argument raises CatalogConfigError('INVALID_RESOLVER_CONFIGURATION').
    """
    try:
        execute = service.execute
    except Exception:
        execute = None
    if (
        not callable(execute)
        or not callable(clock)
        or not catalog_api.is_id(client_id)
        or not catalog_api.is_id(catalog_version)
    ):
        raise CatalogConfigError("INVALID_RESOLVER_CONFIGURATION")

    def resolver(campaign_id):
        if not _canonical_campaign_id(campaign_id):
            raise CatalogConfigError("INVALID_CAMPAIGN_ID")
        scope = {"client_id": client_id, "campaign_id": campaign_id}
        now = clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise CatalogConfigError("INVALID_CLOCK")
        result = catalog_consumer.trusted_raw_config(
            service,
            scope,
            catalog_version,
            now=now,
        )
        return copy.deepcopy(result["raw_config"])

    return resolver
