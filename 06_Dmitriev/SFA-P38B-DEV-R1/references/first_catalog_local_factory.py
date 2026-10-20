"""Protected OS-local DB-role issuer and fail-closed immutable archive.

The bootstrap tenant is newly generated environment identity, explicitly not an
existing business client. No bundle or campaign is approved by this factory.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import psycopg
from first_campaign_catalog.api import create_service, BUCKET, CURRENT_KEY, version_key
from tooling.bundle_codec import validate_bundle, timestamp as bundle_timestamp, BundleError
from sales_first_binding import FirstBindingError
from sales_language_registry import LanguageRegistryError
from first_catalog_integration import CatalogIntegrationPorts
from first_handoff_integration.catalog_owner import D1CatalogOwner

class LocalCatalogPorts(CatalogIntegrationPorts):
    def call_in_transaction(self, name, request, tx):
        # The accepted service captures an early timestamp before lock waits.
        # Revalidate activation at the atomic invalidation boundary with the
        # current host clock; failure rolls catalog+authority back together.
        if name=='authority.invalidate' and request.get('reason')=='CATALOG_ACTIVATE':
            current=tx.get(BUCKET,CURRENT_KEY)
            row=tx.get(BUCKET,version_key(tx.scope,current['version']))
            bundle=row['bundle']
            validate_bundle(bundle,scope=tx.scope,now=self.now,bundle_ref=bundle['bundle_ref'])
        return super().call_in_transaction(name,request,tx)

class FreshClockCatalogService:
    def __init__(self, service):
        self._service=service
        self._ports=service._ports

    def execute(self, operation, request):
        result=self._service.execute(operation,request)
        if operation!='resolve' or result.get('status')!='OK': return result
        try:
            bundle=result['data']['bundle'];now=self._ports.now
            if now>=bundle_timestamp(bundle['valid_until']):
                return {'status':'BLOCKED','data':{'code':'BUNDLE_EXPIRED'}}
            validate_bundle(bundle,scope=dict(request['scope']),now=now)
        except (BundleError,FirstBindingError,LanguageRegistryError) as error:
            return {'status':'BLOCKED','data':{'code':error.code}}
        except Exception:
            return {'status':'DEPENDENCY_UNAVAILABLE','data':{'code':'DEPENDENCY_UNAVAILABLE'}}
        return result

class LocalCatalogFactory:
    def __init__(self, environment_directory):
        raw=Path(environment_directory)
        if not raw.is_absolute(): raise RuntimeError('ABSOLUTE_ENVIRONMENT_PATH_REQUIRED')
        for component in (raw,*raw.parents):
            if component.is_symlink() or (hasattr(component,'is_junction') and component.is_junction()):
                raise RuntimeError('UNSAFE_ENVIRONMENT_PATH')
        self.directory=raw.resolve(strict=True)
        # Host-owned bootstrap wiring supplies the path, never a service request.
        self.config=json.loads((self.directory/'connection.private.json').read_text(encoding='utf-8'))
        binding=json.loads((self.directory/'issuer.private.json').read_text(encoding='utf-8'))
        if binding['identity_kind']!='LOCAL_BOOTSTRAP_NOT_BUSINESS_CLIENT': raise RuntimeError('WRONG_IDENTITY_KIND')
        self.client_id=binding['client_id']
        self.owner_schema=binding['owner_schema']
        self.grants=binding['grants']
        self.policy=binding['policy']
        keys={'connect_timeout_seconds','statement_timeout_seconds','lock_timeout_seconds'}
        if type(self.policy) is not dict or set(self.policy)!=keys or any(type(v) is not int or not 1<=v<=60 for v in self.policy.values()) or self.policy['lock_timeout_seconds']>self.policy['statement_timeout_seconds']:
            raise RuntimeError('EXPLICIT_BOUNDED_LOCAL_POLICY_REQUIRED')
        expected={'sm_runtime':['catalog.read'],'sm_publisher':['catalog.read','catalog.publish']}
        if self.grants!=expected: raise RuntimeError('UNEXPECTED_GRANT_MAPPING')
        if self.config['host']!='127.0.0.1' or self.config['port']!=55484 or self.config['dbname']!='sales_manager_local':
            raise RuntimeError('DATABASE_BINDING_CHANGED')

    def connect(self, role, **kwargs):
        if role not in self.grants: raise PermissionError('LOCAL_SERVICE_ROLE_REQUIRED')
        c=self.config
        conn=psycopg.connect(host=c['host'],port=c['port'],dbname=c['dbname'],user=role,password=c['roles'][role],autocommit=False,connect_timeout=kwargs.get('connect_timeout',self.policy['connect_timeout_seconds']))
        try:
            actual=conn.execute('SELECT session_user,current_user,current_database(),host(inet_server_addr()),inet_server_port()').fetchone()
            if actual!=(role,role,c['dbname'],c['host'],c['port']): raise PermissionError('DATABASE_SESSION_IDENTITY_MISMATCH')
            conn.rollback()
            return conn
        except BaseException:
            conn.close();raise

    def archive(self, scope, ref):
        # No request carries approval or bytes. The OS-protected local manifest
        # starts empty; source approval/import is a separately reviewed operation.
        if scope.get('client_id')!=self.client_id: raise PermissionError('FOREIGN_CLIENT')
        manifest=json.loads((self.directory/'archive_manifest.private.json').read_text(encoding='utf-8'))
        item=manifest.get(json.dumps([scope,ref],ensure_ascii=False,sort_keys=True,separators=(',',':')))
        if item is None: return None
        if type(item) is not dict or set(item)!={'filename','sha256'}: raise RuntimeError('INVALID_ARCHIVE_MANIFEST')
        name=item['filename']
        if type(name) is not str or Path(name).name!=name or not name.endswith('.json'): raise RuntimeError('INVALID_ARCHIVE_PATH')
        parent=self.directory/'immutable_archive'
        path=parent/name
        if parent.is_symlink() or (hasattr(parent,'is_junction') and parent.is_junction()) or path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()): raise RuntimeError('UNSAFE_ARCHIVE_PATH')
        if path.resolve(strict=True).parent!=parent.resolve(strict=True): raise RuntimeError('UNSAFE_ARCHIVE_PATH')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=item['sha256']: raise RuntimeError('ARCHIVE_DIGEST_MISMATCH')
        return json.loads(data)

    def service(self, role):
        # Issuer verifies physical authenticated session before minting context.
        with contextlib.closing(self.connect(role)):
            pass
        owner=D1CatalogOwner(schema=self.owner_schema,catalog_schema=self.config['schema'],client_id=self.client_id)
        ports=LocalCatalogPorts(connect_factory=lambda **kw:self.connect(role,**kw),schema=self.config['schema'],auth={'authenticated':True,'client_id':self.client_id,'capabilities':list(self.grants[role])},clock=lambda:datetime.now(timezone.utc),policy=self.policy,owner=owner,archive=self.archive,mapping_receipt={'owner_identity':'D1_LOCAL_CATALOG_EXTENSION_V1','database_identity':self.config['environment'],'initial_scope_owner_identity':'D1_LOCAL_CATALOG_EXTENSION_V1'})
        return FreshClockCatalogService(create_service(ports))
