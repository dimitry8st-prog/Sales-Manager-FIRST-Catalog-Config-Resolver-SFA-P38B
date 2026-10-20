"""B8-01 R3 catalog service: publish / resolve / revoke of approved immutable bundles.

Normative sources: CATALOG_R3_SPEC.md, SHARED_CONTRACT_R3.md, PORT_CONTRACTS.json.
Bundle validation is delegated to the PROVIDED tooling.bundle_codec.validate_bundle,
which in turn calls the unchanged F105/F106 validators. This module owns request
validation, authentication/capability checks, immutable storage, catalog CAS,
replay, revocation and orchestration of the atomic invalidation facade.
"""
import copy
import json
import re
from datetime import datetime

from tooling.bundle_codec import BundleError, timestamp as bundle_timestamp, validate_bundle
from sales_first_binding import FirstBindingError
from sales_language_registry import LanguageRegistryError

BUCKET = 'catalog'
CURRENT_KEY = 'current'
OPERATIONS = {
    'publish': frozenset({'scope', 'version', 'expected_revision', 'bundle_ref'}),
    'resolve': frozenset({'scope', 'version'}),
    'revoke': frozenset({'scope', 'version', 'expected_revision'}),
}
CAPABILITIES = {'publish': 'catalog.publish', 'resolve': 'catalog.read', 'revoke': 'catalog.publish'}
REASON_ACTIVATE = 'CATALOG_ACTIVATE'
REASON_REVOKE = 'CATALOG_REVOKED'
SCOPE_KEYS = frozenset({'client_id', 'campaign_id'})
LEAD_SCOPE_KEYS = frozenset({'client_id', 'campaign_id', 'lead_id', 'mailbox_ref', 'thread_id'})
ROW_KEYS = frozenset({'version', 'revision', 'bundle', 'revoked'})
CURRENT_KEYS = frozenset({'version', 'revision'})
# Harness convention (SHARED_CONTRACT_R3): '*' grants every enumerated capability
# to the synthetic offline principal; production auth adapters enumerate exact caps.
WILDCARD_CAPABILITY = '*'
VALIDATOR_ERRORS = (BundleError, FirstBindingError, LanguageRegistryError)
CORRUPT_RECORD = 'CORRUPT_CATALOG_RECORD'
_UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z')


# ---------------------------------------------------------------- codecs

def canonical(value):
    """Shared R3 canonical JSON: UTF8, sort_keys, compact separators, no NaN/Infinity."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def canonical_bytes(value):
    return canonical(value).encode('utf-8')


def version_key(scope, version):
    return canonical([scope['client_id'], scope['campaign_id'], version])


def bundle_ref_key(scope, bundle_ref):
    return canonical(['bundle_ref', scope['client_id'], scope['campaign_id'], bundle_ref])


def revoke_replay_key(scope, version):
    return canonical(['replay', 'revoke', scope['client_id'], scope['campaign_id'], version])


def is_id(value):
    return (type(value) is str and 0 < len(value) <= 128 and value.strip() == value
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def is_rev(value):
    return type(value) is int and value >= 0


def _response(status, data=None):
    return {'status': status, 'data': dict(data) if data else {}}


def _invalid_request():
    return _response('INVALID', {'code': 'INVALID_REQUEST'})


def _dependency(code):
    return _response('DEPENDENCY_UNAVAILABLE', {'code': code})


def _blocked(code):
    return _response('BLOCKED', {'code': code})


class _Abort(Exception):
    """Carries a domain response out of a transaction and forces its rollback."""

    def __init__(self, response):
        super().__init__(response['status'])
        self.response = response


class _InvalidationFailed(Exception):
    """authority.invalidate raised or returned a response violating its contract."""


# ---------------------------------------------------------------- validation

def _parse_request(operation, request):
    """Exact root keys and strict scalar types; returns an independent copy or None."""
    if type(operation) is not str or operation not in OPERATIONS:
        return None
    if type(request) is not dict or set(request) != OPERATIONS[operation]:
        return None
    scope = request['scope']
    if type(scope) is not dict or set(scope) != SCOPE_KEYS:
        return None
    if not is_id(scope['client_id']) or not is_id(scope['campaign_id']) or not _UUID.match(scope['campaign_id']):
        return None
    if not is_id(request['version']):
        return None
    parsed = {'scope': {'client_id': scope['client_id'], 'campaign_id': scope['campaign_id']},
              'version': request['version']}
    if 'expected_revision' in request:
        if not is_rev(request['expected_revision']):
            return None
        parsed['expected_revision'] = request['expected_revision']
    if 'bundle_ref' in request:
        if not is_id(request['bundle_ref']):
            return None
        parsed['bundle_ref'] = request['bundle_ref']
    return parsed


def _valid_row(row, version):
    return (type(row) is dict and set(row) == ROW_KEYS and row['version'] == version
            and is_rev(row['revision']) and row['revision'] > 0 and type(row['revoked']) is bool
            and type(row['bundle']) is dict)


def _current_revision(current):
    """Missing current means revision 0; malformed current is corruption (None)."""
    if current is None:
        return 0
    if type(current) is dict and set(current) == CURRENT_KEYS and is_id(current['version']) and is_rev(current['revision']):
        return current['revision']
    return None


def _same_bytes(left, right):
    try:
        return canonical_bytes(left) == canonical_bytes(right)
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------- service

class CatalogService:
    def __init__(self, ports):
        self._ports = ports

    def execute(self, operation, request):
        parsed = _parse_request(operation, request)
        if parsed is None:
            return _invalid_request()
        denied = self._authorize(operation, parsed['scope'])
        if denied is not None:
            return denied
        return getattr(self, '_' + operation)(parsed)

    # -- trust context ---------------------------------------------------
    def _authorize(self, operation, scope):
        auth = getattr(self._ports, 'auth', None)
        if type(auth) is not dict or auth.get('authenticated') is not True:
            return _response('UNAUTHENTICATED')
        capabilities = auth.get('capabilities')
        if type(capabilities) is not list or not all(type(c) is str for c in capabilities) or not is_id(auth.get('client_id')):
            return _response('UNAUTHENTICATED')
        if auth['client_id'] != scope['client_id']:
            return _response('UNAUTHORIZED')
        if CAPABILITIES[operation] not in capabilities and WILDCARD_CAPABILITY not in capabilities:
            return _response('UNAUTHORIZED')
        return None

    def _now(self):
        now = getattr(self._ports, 'now', None)
        if isinstance(now, datetime) and now.utcoffset() is not None:
            return now
        return None

    # -- publish ---------------------------------------------------------
    def _publish(self, request):
        scope, version = request['scope'], request['version']
        expected, ref = request['expected_revision'], request['bundle_ref']
        now = self._now()
        if now is None:
            return _dependency('DEPENDENCY_UNAVAILABLE')
        try:
            fetched = self._ports.call('catalog.bundle', {'scope': dict(scope), 'bundle_ref': ref})
        except Exception:
            return _dependency('DEPENDENCY_UNAVAILABLE')
        bundle = copy.deepcopy(fetched)
        if type(bundle) is not dict or 'bundle_ref' not in bundle:
            return _response('INVALID', {'code': 'INVALID_BUNDLE'})
        if bundle['bundle_ref'] != ref:
            return _response('INVALID', {'code': 'BUNDLE_REF_MISMATCH'})
        try:
            canonical_bytes(bundle)
        except (TypeError, ValueError):
            return _response('INVALID', {'code': 'INVALID_BUNDLE'})

        vkey, rkey = version_key(scope, version), bundle_ref_key(scope, ref)
        progress = {}
        try:
            with self._ports.transaction(dict(scope)) as tx:
                row = tx.get(BUCKET, vkey)
                if row is not None:
                    if not _valid_row(row, version):
                        return _blocked(CORRUPT_RECORD)
                    if not _same_bytes(row['bundle'], bundle):
                        return _response('CONFLICT')
                    if row['revoked']:
                        return _blocked('REVOKED')
                    return _response('REPLAY', {'version': version, 'revision': row['revision']})
                indexed = tx.get(BUCKET, rkey)
                if indexed is not None and not _same_bytes(indexed, bundle):
                    return _response('CONFLICT')
                current = tx.get(BUCKET, CURRENT_KEY)
                current_rev = _current_revision(current)
                if current_rev is None:
                    return _blocked(CORRUPT_RECORD)
                if expected != current_rev:
                    return _response('STALE')
                try:
                    validate_bundle(bundle, scope=dict(scope), now=now, bundle_ref=ref)
                except VALIDATOR_ERRORS as error:
                    return _response('INVALID', {'code': error.code})
                scopes = self._enumerate(scope, current_rev)
                new_rev = current_rev + 1
                record = {'version': version, 'revision': new_rev, 'bundle': bundle, 'revoked': False}
                progress['record'] = record

                def activate(itx):
                    progress['callback_entered'] = True
                    self._recheck(itx, current_rev)
                    if itx.get(BUCKET, vkey) is not None:
                        raise _Abort(_response('STALE'))
                    itx.put(BUCKET, vkey, copy.deepcopy(record))
                    itx.put(BUCKET, rkey, copy.deepcopy(bundle))
                    itx.put(BUCKET, CURRENT_KEY, {'version': version, 'revision': new_rev})
                    self._invalidate(itx, scope, current_rev, scopes, REASON_ACTIVATE)
                    progress['callback_done'] = True

                self._run_facade(scopes, activate, progress)
        except _Abort as abort:
            return abort.response
        except _InvalidationFailed:
            return _dependency('INVALIDATION_FAILED')
        except Exception:
            if progress.get('callback_done'):
                return self._reread(scope, vkey, progress['record'],
                                    {'version': version, 'revision': progress['record']['revision']})
            raise
        return _response('OK', {'version': version, 'revision': progress['record']['revision']})

    # -- revoke ----------------------------------------------------------
    def _revoke(self, request):
        scope, version, expected = request['scope'], request['version'], request['expected_revision']
        vkey, replay_key = version_key(scope, version), revoke_replay_key(scope, version)
        progress = {}
        try:
            with self._ports.transaction(dict(scope)) as tx:
                row = tx.get(BUCKET, vkey)
                if row is None:
                    return _response('NOT_FOUND')
                if not _valid_row(row, version):
                    return _blocked(CORRUPT_RECORD)
                if row['revoked']:
                    replay = tx.get(BUCKET, replay_key)
                    data = replay.get('response') if type(replay) is dict and replay.get('operation') == 'revoke' else None
                    if (type(data) is dict and set(data) == {'version', 'revision', 'revoked'}
                            and data['version'] == version and data['revoked'] is True and is_rev(data['revision'])):
                        return _response('REPLAY', data)
                    # Revoked outside this module's replay index: never invent a revision.
                    return _blocked('REVOKED')
                current = tx.get(BUCKET, CURRENT_KEY)
                current_rev = _current_revision(current)
                if current is None or current_rev is None:
                    return _blocked(CORRUPT_RECORD)
                if expected != current_rev:
                    return _response('STALE')
                scopes = self._enumerate(scope, current_rev)
                new_rev = current_rev + 1
                active_version = current['version']
                revoked_row = dict(copy.deepcopy(row), revoked=True)
                data = {'version': version, 'revision': new_rev, 'revoked': True}
                progress['replay'] = {'operation': 'revoke', 'version': version, 'response': data}

                def revoke(itx):
                    progress['callback_entered'] = True
                    self._recheck(itx, current_rev)
                    still = itx.get(BUCKET, vkey)
                    if not _valid_row(still, version) or still['revoked']:
                        raise _Abort(_response('STALE'))
                    itx.put(BUCKET, vkey, revoked_row)
                    # Active pointer keeps the previously active version; only the revision moves.
                    itx.put(BUCKET, CURRENT_KEY, {'version': active_version, 'revision': new_rev})
                    itx.put(BUCKET, replay_key, copy.deepcopy(progress['replay']))
                    self._invalidate(itx, scope, current_rev, scopes, REASON_REVOKE)
                    progress['callback_done'] = True

                self._run_facade(scopes, revoke, progress)
        except _Abort as abort:
            return abort.response
        except _InvalidationFailed:
            return _dependency('INVALIDATION_FAILED')
        except Exception:
            if progress.get('callback_done'):
                return self._reread(scope, replay_key, progress['replay'], progress['replay']['response'])
            raise
        return _response('OK', progress['replay']['response'])

    # -- resolve ---------------------------------------------------------
    def _resolve(self, request):
        scope, version = request['scope'], request['version']
        now = self._now()
        if now is None:
            return _dependency('DEPENDENCY_UNAVAILABLE')
        with self._ports.transaction(dict(scope)) as tx:
            row = tx.get(BUCKET, version_key(scope, version))
        if row is None:
            return _response('NOT_FOUND')
        if not _valid_row(row, version):
            return _blocked(CORRUPT_RECORD)
        if row['revoked']:
            return _blocked('REVOKED')
        bundle = copy.deepcopy(row['bundle'])
        # Expiry is decided before F105 time validation so that it has a stable code.
        if 'valid_until' in bundle:
            try:
                deadline = bundle_timestamp(bundle['valid_until'])
            except BundleError as error:
                return _blocked(error.code)
            if now >= deadline:
                return _blocked('BUNDLE_EXPIRED')
        try:
            validate_bundle(bundle, scope=dict(scope), now=now)
        except VALIDATOR_ERRORS as error:
            return _blocked(error.code)
        return _response('OK', {'version': version, 'bundle': copy.deepcopy(row['bundle'])})

    # -- shared orchestration -------------------------------------------
    def _enumerate(self, scope, current_rev):
        """authority.enumerate under the catalog lock; returns UTF8-canonically sorted scopes."""
        try:
            result = self._ports.call('authority.enumerate', {'scope': dict(scope)})
        except Exception:
            raise _Abort(_dependency('DEPENDENCY_UNAVAILABLE')) from None
        if (type(result) is not dict or set(result) != {'complete', 'scopes', 'catalog_revision'}
                or type(result['complete']) is not bool or type(result['scopes']) is not list
                or not is_rev(result['catalog_revision'])):
            raise _Abort(_dependency('INVALID_ENUMERATION'))
        if not result['complete']:
            raise _Abort(_dependency('INCOMPLETE_ENUMERATION'))
        seen, scopes = set(), []
        for item in result['scopes']:
            if type(item) is not dict or set(item) != LEAD_SCOPE_KEYS:
                raise _Abort(_dependency('INVALID_ENUMERATION'))
            if not all(is_id(item[k]) for k in ('client_id', 'campaign_id', 'lead_id', 'mailbox_ref')):
                raise _Abort(_dependency('INVALID_ENUMERATION'))
            if item['thread_id'] is not None and not is_id(item['thread_id']):
                raise _Abort(_dependency('INVALID_ENUMERATION'))
            if item['client_id'] != scope['client_id'] or item['campaign_id'] != scope['campaign_id']:
                raise _Abort(_dependency('INVALID_ENUMERATION'))
            identity = canonical_bytes(item)
            if identity in seen:
                raise _Abort(_dependency('INVALID_ENUMERATION'))
            seen.add(identity)
            scopes.append(dict(item))
        if result['catalog_revision'] != current_rev:
            raise _Abort(_response('STALE'))
        # Lexical UTF8 canonical JSON order; never native tuple ordering of None/str.
        scopes.sort(key=canonical_bytes)
        return scopes

    def _run_facade(self, scopes, callback, progress):
        """Invoke ports.invalidate, attributing failures to their origin.

        Raised inside the catalog transaction, so every path below propagates through it
        and rolls back before the caller maps the error to a response:
        * facade failure before/around the callback (callback not entered) -> INVALIDATION_FAILED;
        * error raised inside the callback (storage) -> propagated unchanged;
        * failure after the callback completed -> unchanged, handled as uncertain commit (reread).
        """
        try:
            self._ports.invalidate(scopes, callback)
        except (_Abort, _InvalidationFailed):
            raise
        except Exception as error:
            if progress.get('callback_entered'):
                raise
            raise _InvalidationFailed('FACADE_' + type(error).__name__) from error

    @staticmethod
    def _recheck(itx, current_rev):
        if _current_revision(itx.get(BUCKET, CURRENT_KEY)) != current_rev:
            raise _Abort(_response('STALE'))

    def _invalidate(self, itx, scope, current_rev, scopes, reason):
        # A participating transaction exposing call() keeps the authority write in the same tx.
        caller = getattr(itx, 'call', None)
        if not callable(caller):
            caller = self._ports.call
        request = {'scope': dict(scope), 'expected_revision': current_rev,
                   'scopes': copy.deepcopy(scopes), 'reason': reason}
        try:
            result = caller('authority.invalidate', request)
        except Exception as error:
            raise _InvalidationFailed(type(error).__name__) from error
        if (type(result) is not dict or set(result) != {'revision', 'invalidated'}
                or not is_rev(result['revision']) or not is_rev(result['invalidated'])
                or result['revision'] != current_rev + 1 or result['invalidated'] != len(scopes)):
            raise _InvalidationFailed('INVALID_INVALIDATE_RESPONSE')

    def _reread(self, scope, key, expected_value, data):
        """Uncertain commit: scoped reread of the stable identity, never re-running effects."""
        try:
            with self._ports.transaction(dict(scope)) as tx:
                stored = tx.get(BUCKET, key)
        except Exception:
            return _response('UNKNOWN', {'code': 'COMMIT_UNKNOWN'})
        if stored is not None and _same_bytes(stored, expected_value):
            return _response('OK', data)
        return _response('UNKNOWN', {'code': 'COMMIT_UNKNOWN'})


def create_service(ports):
    return CatalogService(ports)
