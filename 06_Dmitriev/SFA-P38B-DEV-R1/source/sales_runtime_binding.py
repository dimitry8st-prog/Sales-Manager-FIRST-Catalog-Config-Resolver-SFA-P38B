"""F1-28: implement only this bounded adapter; see CONTRACT.json.

``resolve_campaign_projection`` is the pluggable boundary between a runtime
campaign row and the accepted F112 projection of its server-owned F105 binding.

* The binding config comes only from the explicitly injected, server-owned
  ``resolve_config(campaign_id)``; ``campaign["config"]`` and task payloads are
  never read for binding.
* The resolver result is passed unchanged to the accepted
  ``project_campaign_binding(config, now=now)``; F105/F112 validation is not
  repeated here and their exceptions (and resolver exceptions) propagate
  unchanged.
* The result is the exact F112 projection, deep-copied, with no added fields
  and no merge with the runtime campaign. ``release_mode`` stays as F112 sets
  it (``NO_OUTBOUND``).
* Pure: no I/O, no clock (``now`` is passed explicitly), no environment.
  Integration status: NOT_CONNECTED.
"""

import copy

from sales_campaign_projection import project_campaign_binding

INVALID_RUNTIME_CAMPAIGN = "INVALID_RUNTIME_CAMPAIGN"
TRUSTED_RESOLVER_REQUIRED = "TRUSTED_RESOLVER_REQUIRED"
RUNTIME_SCOPE_MISMATCH = "RUNTIME_SCOPE_MISMATCH"


class RuntimeBindingError(ValueError):
    """Runtime binding failure with a stable, non-sensitive error code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def resolve_campaign_projection(campaign, *, resolve_config, now):
    """Return the F112 projection of the trusted binding for ``campaign``.

    Check order: runtime campaign shape, resolver callable, one resolver call,
    accepted F112 projection, runtime scope.
    """

    if type(campaign) is not dict:
        raise RuntimeBindingError(INVALID_RUNTIME_CAMPAIGN)
    campaign_id = campaign.get("campaign_id")
    if type(campaign_id) is not str or not campaign_id:
        raise RuntimeBindingError(INVALID_RUNTIME_CAMPAIGN)
    if not callable(resolve_config):
        raise RuntimeBindingError(TRUSTED_RESOLVER_REQUIRED)

    config = resolve_config(campaign_id)
    projection = project_campaign_binding(config, now=now)

    if projection["runtime_campaign_id"] != campaign_id:
        raise RuntimeBindingError(RUNTIME_SCOPE_MISMATCH)
    return copy.deepcopy(projection)
