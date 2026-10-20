import unittest,copy
from helpers import *
from tooling.bundle_codec import validate_bundle
from first_campaign_catalog.api import create_service
from first_campaign_catalog.consumer import trusted_raw_config
from sales_runtime_binding import resolve_campaign_projection
class Baseline(unittest.TestCase):
 def test_exact_bundle_consumer(self):
  view=validate_bundle(bundle(),scope=scope(),now=now());self.assertEqual('FIRST_BINDING_V1',view['normalized_binding']['schema_version'])
 def test_catalog_to_real_F128(self):
  p=CatalogFixturePorts();s=create_service(p)
  def read(campaign_id):return trusted_raw_config(s,scope(),'catalog-v1',now=now())['raw_config']
  result=resolve_campaign_projection({'campaign_id':scope()['campaign_id']},resolve_config=read,now=now());self.assertEqual('NO_OUTBOUND',result['release_mode']);self.assertEqual(1,p.calls)
