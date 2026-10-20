import unittest,copy
from datetime import timedelta,datetime
from unittest.mock import patch
from helpers import *
from first_materials_integration import catalog_config as target
from first_campaign_catalog import consumer
from first_campaign_catalog.api import create_service
from sales_runtime_binding import resolve_campaign_projection
from sales_campaign_projection import project_campaign_binding
class ConfigAcceptance(unittest.TestCase):
 def make(self,p=None,**kw):
  p=p or CatalogFixturePorts();args=dict(client_id=scope()['client_id'],catalog_version='catalog-v1',clock=lambda:p.now);args.update(kw)
  return target.make_catalog_config_resolver(create_service(p),**args),p
 def assert_code(self,code,func):
  with self.assertRaises(target.CatalogConfigError) as e:func()
  self.assertEqual(code,e.exception.code);self.assertEqual(code,str(e.exception))
 def test_real_catalog_consumer_F128_positive(self):
  resolver,p=self.make();c={'campaign_id':scope()['campaign_id'],'config':{'malicious':True}}
  result=resolve_campaign_projection(c,resolve_config=resolver,now=now())
  expected=project_campaign_binding(consumer.trusted_raw_config(create_service(CatalogFixturePorts()),scope(),'catalog-v1',now=now())['raw_config'],now=now())
  self.assertEqual(expected,result);self.assertEqual('NO_OUTBOUND',result['release_mode']);self.assertEqual(1,p.calls);self.assertEqual({'malicious':True},c['config'])
 def test_consumer_called_once_with_pins(self):
  resolver,p=self.make()
  with patch.object(consumer,'trusted_raw_config',wraps=consumer.trusted_raw_config) as spy:resolver(scope()['campaign_id'])
  self.assertEqual(1,spy.call_count);self.assertEqual(scope(),spy.call_args.args[1]);self.assertEqual('catalog-v1',spy.call_args.args[2])
 def test_constructor_has_zero_effect(self):
  calls=[];p=CatalogFixturePorts();resolver,_=self.make(p,clock=lambda:calls.append(1))
  self.assertEqual([],calls);self.assertEqual(0,p.calls);self.assertTrue(callable(resolver))
 def test_wrong_scope_refused_by_real_service(self):
  resolver,p=self.make();p.auth['client_id']='other'
  with self.assertRaises(consumer.CatalogPortError) as e:resolver(scope()['campaign_id'])
  self.assertEqual('UNAUTHORIZED',e.exception.status);self.assertEqual(0,p.calls)
 def test_revocation_after_success_is_not_cached(self):
  resolver,p=self.make();resolver(scope()['campaign_id']);p.row['revoked']=True
  with self.assertRaises(consumer.CatalogPortError) as e:resolver(scope()['campaign_id'])
  self.assertEqual('REVOKED',e.exception.data['code']);self.assertEqual(2,p.calls)
 def test_expiry_clock_changes(self):
  resolver,p=self.make();resolver(scope()['campaign_id']);p.now=datetime.fromisoformat(bundle()['valid_until'].replace('Z','+00:00'))
  with self.assertRaises(consumer.CatalogPortError) as e:resolver(scope()['campaign_id'])
  self.assertEqual('BUNDLE_EXPIRED',e.exception.data['code'])
 def test_missing_version_not_fallback(self):
  resolver,p=self.make(catalog_version='missing-version')
  with self.assertRaises(consumer.CatalogPortError) as e:resolver(scope()['campaign_id'])
  self.assertEqual('NOT_FOUND',e.exception.status)
 def test_invalid_campaign_before_clock_service(self):
  calls=[];resolver,p=self.make(clock=lambda:calls.append(1))
  for x in (None,'INVALID',scope()['campaign_id'].upper(),True):
   if x==scope()['campaign_id']:continue
   self.assert_code('INVALID_CAMPAIGN_ID',lambda:resolver(x))
  self.assertEqual([],calls);self.assertEqual(0,p.calls)
 def test_naive_clock_zero_service(self):
  resolver,p=self.make(clock=lambda:datetime(2026,10,12));self.assert_code('INVALID_CLOCK',lambda:resolver(scope()['campaign_id']));self.assertEqual(0,p.calls)
 def test_exception_object_passes_unchanged(self):
  sentinel=ConnectionError('hidden');resolver,p=self.make()
  with patch.object(consumer,'trusted_raw_config',side_effect=sentinel):
   with self.assertRaises(ConnectionError) as e:resolver(scope()['campaign_id'])
  self.assertIs(sentinel,e.exception)
 def test_return_independent_each_call(self):
  resolver,p=self.make();a=resolver(scope()['campaign_id']);saved=copy.deepcopy(a);a['offer']['name']='changed'
  self.assertEqual(saved,resolver(scope()['campaign_id']));self.assertEqual(2,p.calls)
 def test_missing_capability_not_upgraded(self):
  resolver,p=self.make();p.auth['capabilities']=[]
  with self.assertRaises(consumer.CatalogPortError) as e:resolver(scope()['campaign_id'])
  self.assertEqual('UNAUTHORIZED',e.exception.status)
 def test_invalid_constructor_values(self):
  for kw in ({'client_id':None},{'catalog_version':True},{'clock':None}):self.assert_code('INVALID_RESOLVER_CONFIGURATION',lambda:self.make(**kw))
