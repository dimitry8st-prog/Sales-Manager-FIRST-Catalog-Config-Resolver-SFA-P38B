"""Consumer-side wiring of the catalog (integration hooks, not wired into shared runtime).

* resolve_consumer: unchanged consumer catalog.resolve port {version,bundle_ref,approved}
  through the PROVIDED tooling.catalog_adapter.resolve_port. Any refusal raises
  CatalogPortError and must stop the consumer before materialization/send.
* trusted_raw_config: input for the trusted F105 resolve_config adapter, i.e. the
  decoded raw_config of the validated stored bundle, never the consumer wrapper.
* ImmutableBundleSource: production catalog.bundle source adapter that returns the
  exact stored DTO from the scoped immutable ref index, or from an injected
  authenticated immutable archive which must equal the index when both exist.
"""
import copy

from tooling.bundle_codec import BundleError, validate_bundle
from tooling.catalog_adapter import CatalogPortError, resolve_port
from sales_first_binding import FirstBindingError
from sales_language_registry import LanguageRegistryError

from first_campaign_catalog.api import BUCKET, bundle_ref_key, canonical_bytes, is_id

__all__ = ['CatalogPortError', 'resolve_consumer', 'trusted_raw_config', 'ImmutableBundleSource',
           'BundleSourceUnavailable', 'BundleSourceConflict']


def resolve_consumer(service, request, *, now):
    return resolve_port(service, request, now=now)


def trusted_raw_config(service, scope, version, *, now):
    """Return {version,bundle_ref,raw_config,pins} only after an OK resolve and re-validation."""
    catalog_scope = {'client_id': scope.get('client_id'), 'campaign_id': scope.get('campaign_id')} if type(scope) is dict else scope
    result = service.execute('resolve', {'scope': catalog_scope, 'version': version})
    if type(result) is not dict or set(result) != {'status', 'data'} or type(result['data']) is not dict:
        raise CatalogPortError('DEPENDENCY_UNAVAILABLE', {'code': 'INVALID_RESOLVER_RESPONSE'})
    if result['status'] != 'OK':
        raise CatalogPortError(result['status'], result['data'])
    data = result['data']
    if set(data) != {'version', 'bundle'} or data['version'] != version:
        raise CatalogPortError('DEPENDENCY_UNAVAILABLE', {'code': 'INVALID_RESOLVER_RESPONSE'})
    try:
        view = validate_bundle(data['bundle'], scope=catalog_scope, now=now)
    except (BundleError, FirstBindingError, LanguageRegistryError) as error:
        raise CatalogPortError('BLOCKED', {'code': error.code}) from None
    return {'version': version, 'bundle_ref': data['bundle']['bundle_ref'],
            'raw_config': copy.deepcopy(view['raw_config']), 'pins': copy.deepcopy(view['pins'])}


class BundleSourceUnavailable(LookupError):
    pass


class BundleSourceConflict(RuntimeError):
    pass


class ImmutableBundleSource:
    """catalog.bundle({scope,bundle_ref}) adapter over the module-owned ref index.

    transaction: callable(scope) -> context manager with get(bucket,key) (ports.transaction).
    archive: optional callable(scope, bundle_ref) -> DTO|None supplied by the integrator for
    not-yet-indexed approved bundles; it is an UNVERIFIED integration hook in this return.
    """

    def __init__(self, transaction, archive=None):
        self._transaction = transaction
        self._archive = archive

    def __call__(self, request):
        if type(request) is not dict or set(request) != {'scope', 'bundle_ref'}:
            raise BundleSourceUnavailable('INVALID_REQUEST')
        scope, ref = request['scope'], request['bundle_ref']
        if type(scope) is not dict or set(scope) != {'client_id', 'campaign_id'} or not all(is_id(v) for v in scope.values()) or not is_id(ref):
            raise BundleSourceUnavailable('INVALID_REQUEST')
        with self._transaction(dict(scope)) as tx:
            indexed = tx.get(BUCKET, bundle_ref_key(scope, ref))
        archived = self._archive(dict(scope), ref) if self._archive is not None else None
        if indexed is not None and archived is not None and canonical_bytes(indexed) != canonical_bytes(archived):
            raise BundleSourceConflict('ARCHIVE_INDEX_MISMATCH')
        found = indexed if indexed is not None else archived
        if found is None:
            raise BundleSourceUnavailable('UNKNOWN_BUNDLE_REF')
        return copy.deepcopy(found)
