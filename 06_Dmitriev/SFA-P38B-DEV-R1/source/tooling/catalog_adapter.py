"""PROVIDED consumer projection only; service still authenticates each resolve."""
from tooling.bundle_codec import validate_bundle
from sales_first_binding import FirstBindingError
from sales_language_registry import LanguageRegistryError
from tooling.bundle_codec import BundleError

class CatalogPortError(RuntimeError):
    def __init__(self, status, data):
        self.status, self.data = status, data
        super().__init__(status)

def resolve_port(service, request, *, now):
    if type(request) is not dict or set(request) != {'scope','version'}:
        raise CatalogPortError('INVALID', {'code':'INVALID_REQUEST'})
    scope = request['scope']
    catalog = {'client_id','campaign_id'}
    lead = catalog | {'lead_id','mailbox_ref','thread_id'}
    if type(scope) is not dict or set(scope) not in (catalog, lead):
        raise CatalogPortError('INVALID', {'code':'INVALID_REQUEST'})
    for key, value in scope.items():
        if key == 'thread_id' and value is None:
            continue
        if type(value) is not str or not 0 < len(value) <= 128 or value.strip()!=value or any(ord(c)<32 or ord(c)==127 for c in value):
            raise CatalogPortError('INVALID', {'code':'INVALID_REQUEST'})
    result = service.execute('resolve', {'scope':{k:scope[k] for k in ('client_id','campaign_id')},'version':request['version']})
    if type(result) is not dict or set(result) != {'status','data'} or type(result['status']) is not str or type(result['data']) is not dict:
        raise CatalogPortError('DEPENDENCY_UNAVAILABLE', {'code':'INVALID_RESOLVER_RESPONSE'})
    if result['status'] != 'OK':
        raise CatalogPortError(result['status'], result['data'])
    if set(result['data']) != {'version','bundle'} or type(result['data']['version']) is not str or result['data']['version'] != request['version']:
        raise CatalogPortError('DEPENDENCY_UNAVAILABLE', {'code':'INVALID_RESOLVER_RESPONSE'})
    bundle = result['data']['bundle']
    try:
        validate_bundle(bundle, scope={k:scope[k] for k in ('client_id','campaign_id')}, now=now)
    except (BundleError, FirstBindingError, LanguageRegistryError) as error:
        raise CatalogPortError('BLOCKED', {'code':error.code}) from None
    return {'version':result['data']['version'],'bundle_ref':bundle['bundle_ref'],'approved':True}
