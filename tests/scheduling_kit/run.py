import sys, pathlib, unittest
root=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'backend/app/modules/academic_affairs'))
sys.path.insert(0,str(pathlib.Path(__file__).parent))
if len(sys.argv)>1: sys.path.insert(0,sys.argv.pop(1))
suite=unittest.defaultTestLoader.discover(str(pathlib.Path(__file__).parent),pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
