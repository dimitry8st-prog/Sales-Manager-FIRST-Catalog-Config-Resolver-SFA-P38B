import pathlib,sys,subprocess,json,hashlib,unittest,importlib,importlib.util,os
R=pathlib.Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path[:0]=[str(R/'source'),str(R/'checks')]
os.environ['PYTHONDONTWRITEBYTECODE']='1'
mode=sys.argv[1] if len(sys.argv)>1 else 'baseline'
if mode=='integrity':
 errors=[p for p,h in json.loads((R/'PROTECTED_SHA256.json').read_text()).items() if not (R/p).is_file() or hashlib.sha256((R/p).read_bytes()).hexdigest()!=h]
 print(json.dumps({'status':'PASS' if not errors else 'FAIL','changed':errors}));sys.exit(bool(errors))
# Every actual product import is pinned to the extracted source, never global packages.
for row in json.loads((R/'SOURCE_MANIFEST.json').read_text()):
 path=row['path']
 if not path.endswith('.py') or path.startswith('tests/') or path.endswith('__init__.py'):continue
 name=path[:-3].replace('/','.')
 spec=importlib.util.find_spec(name)
 if spec is None or not spec.origin or pathlib.Path(spec.origin).resolve()!=(R/'source'/path).resolve():raise SystemExit('DEPENDENCY_IMPORT_ORIGIN_MISMATCH '+name)
def run_suite(suite):
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 ok=result.wasSuccessful() and result.testsRun>0 and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses
 print(json.dumps({'status':'PASS' if ok else 'FAIL','tests_run':result.testsRun,'skipped':len(result.skipped),'expected_failures':len(result.expectedFailures),'unexpected_successes':len(result.unexpectedSuccesses)}))
 sys.exit(0 if ok else 1)
if mode=='baseline':
 suite=unittest.TestSuite()
 for pattern in ('test_first_binding.py','test_language_registry.py','test_discovery_qualification.py'):
  suite.addTests(unittest.TestLoader().discover(str(R/'source/tests'),pattern=pattern))
 suite.addTests(unittest.TestLoader().discover(str(R/'checks'),pattern='test_baseline*.py'))
 run_suite(suite)
if mode=='acceptance':
 ident=json.loads((R/'TASK_IDENTITY.json').read_text());mod=R/'source'/ident['allowed_product_file']
 if not mod.exists():print('MISSING_IMPLEMENTATION: '+str(mod.relative_to(R)));sys.exit(3)
 name=ident['allowed_product_file'][:-3].replace('/','.')
 imported=importlib.import_module(name)
 if pathlib.Path(imported.__file__).resolve()!=mod.resolve():raise SystemExit('IMPLEMENTATION_IMPORT_ORIGIN_MISMATCH')
 run_suite(unittest.TestLoader().discover(str(R/'checks'),pattern='test_acceptance.py'))
if mode=='candidate':
 files=list((R/'candidate_tests').glob('test*.py'))
 if not files:print('MISSING_CANDIDATE_TESTS');sys.exit(4)
 run_suite(unittest.TestLoader().discover(str(R/'candidate_tests')))
raise SystemExit('Use integrity|baseline|acceptance|candidate')
