"""PROVIDED R3 pure transport codec. No auth, storage, files, network or service."""
import base64
import binascii
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from sales_first_binding import validate_first_binding
from sales_language_registry import load_language_registry

class BundleError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def require(value, code):
    if not value:
        raise BundleError(code)

def timestamp(value):
    require(type(value) is str, 'INVALID_VALIDITY')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(result.utcoffset() is not None, 'INVALID_VALIDITY')
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        raise BundleError('INVALID_VALIDITY') from None

def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'INVALID_JSON')
        result[key] = value
    return result

def _constant(value):
    raise BundleError('INVALID_JSON')

def decode_blob(blob):
    require(type(blob) is dict and set(blob) == {'utf8_b64', 'sha256'}, 'INVALID_BUNDLE')
    require(type(blob['sha256']) is str and re.fullmatch('[0-9a-f]{64}', blob['sha256']), 'INVALID_HASH')
    require(type(blob['utf8_b64']) is str, 'INVALID_BASE64')
    try:
        raw = base64.b64decode(blob['utf8_b64'], validate=True)
    except (ValueError, binascii.Error):
        raise BundleError('INVALID_BASE64') from None
    require(base64.b64encode(raw).decode('ascii') == blob['utf8_b64'], 'INVALID_BASE64')
    require(hashlib.sha256(raw).hexdigest() == blob['sha256'], 'HASH_MISMATCH')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_constant)
    except (UnicodeError, ValueError):
        raise BundleError('INVALID_JSON') from None
    require(type(value) is dict, 'INVALID_JSON')
    return value

def validate_bundle(bundle, *, scope, now, bundle_ref=None):
    require(type(bundle) is dict and set(bundle) == {'schema_version','bundle_ref','raw','valid_until'}, 'INVALID_BUNDLE')
    require(bundle['schema_version'] == 'B8_APPROVED_BUNDLE_R3', 'INVALID_BUNDLE')
    ref = bundle['bundle_ref']
    require(type(ref) is str and 0 < len(ref) <= 128 and ref.strip() == ref and not any(ord(c)<32 or ord(c)==127 for c in ref), 'INVALID_BUNDLE_REF')
    require(bundle_ref is None or ref == bundle_ref, 'BUNDLE_REF_MISMATCH')
    require(type(scope) is dict and set(scope) == {'client_id','campaign_id'}, 'INVALID_SCOPE')
    require(isinstance(now, datetime) and now.utcoffset() is not None, 'INVALID_VALIDITY')
    raw = bundle['raw']
    require(type(raw) is dict and set(raw) == {'config','registry','packs'} and type(raw['packs']) is list, 'INVALID_BUNDLE')
    config = decode_blob(raw['config'])
    registry = decode_blob(raw['registry'])
    packs = [decode_blob(x) for x in raw['packs']]
    # Scope/hash must fail before validation or consumption of foreign materials.
    require(config.get('client_id') == scope['client_id'] and config.get('runtime_campaign_id') == scope['campaign_id'], 'FOREIGN_SCOPE')
    binding = validate_first_binding(config, now=now)
    loaded = load_language_registry(registry, packs, approved_fact_ids=binding['approved_fact_ids'])
    require(registry['default_locale'] == config['default_locale'] and set(registry['active_locales']) == set(config['allowed_locales']) and registry['language_pack_versions'] == config['language_pack_versions'], 'BINDING_REGISTRY_MISMATCH')
    deadline = timestamp(bundle['valid_until'])
    require(timestamp(config['valid_from']) < deadline <= timestamp(config['expires_at']), 'INVALID_VALIDITY')
    require(now.astimezone(timezone.utc) < deadline, 'BUNDLE_EXPIRED')
    return {'raw_config':copy.deepcopy(config),'registry':copy.deepcopy(registry),'packs':copy.deepcopy(packs),'normalized_binding':binding,'loaded_registry':loaded,'pins':{'config_sha256':raw['config']['sha256'],'registry_sha256':raw['registry']['sha256'],'pack_sha256':{p['locale']:b['sha256'] for p,b in zip(packs,raw['packs'])}},'valid_until':deadline.isoformat()}
