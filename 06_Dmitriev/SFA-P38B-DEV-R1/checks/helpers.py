from pathlib import Path
import json,base64,hashlib,copy,contextlib
from datetime import datetime
R=Path(__file__).resolve().parents[1]
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
def bundle():return json.loads((R/'fixtures/bundle.json').read_text())
def scope():return json.loads((R/'fixtures/scope.json').read_text())
def now():return datetime.fromisoformat(json.loads((R/'fixtures/meta.json').read_text())['now'])
def qualification():return json.loads((R/'source/tests/fixtures/first_discovery_qualification/positive_basic.json').read_text())
class CatalogFixturePorts:
 def __init__(self):
  self.auth={'authenticated':True,'client_id':scope()['client_id'],'capabilities':['catalog.read']};self.now=now();self.row={'version':'catalog-v1','revision':1,'bundle':bundle(),'revoked':False};self.calls=0
 @contextlib.contextmanager
 def transaction(self,s):
  assert s==scope();self.calls+=1;yield self
 def get(self,bucket,key):
  from first_campaign_catalog.api import version_key
  return copy.deepcopy(self.row) if key==version_key(scope(),'catalog-v1') else None
 def put(self,*args):raise AssertionError('READ_ONLY_PORT_MUST_NOT_WRITE')
