import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class LocalLauncher(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('website_local_launcher',Path(__file__).resolve().parents[2]/'local.py')
        self.launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.launcher)
        self.temporary=tempfile.TemporaryDirectory(prefix='website-launcher-')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);(self.root/'.runtime').mkdir()
        for name,marker in [('local.json','old-profile'),('delivery.json','connected-profile')]:
            (self.root/'.runtime'/name).write_text(json.dumps({'WEBSITE_PROFILE_TEST_MARKER':marker}),encoding='utf-8')
        self.launcher.ROOT=self.root

    def run_launcher(self,environ=None):
        with patch.dict(os.environ,environ or {},clear=True),patch.object(sys,'argv',['local.py','serve']),patch.object(self.launcher.subprocess,'call',return_value=0) as call:
            with self.assertRaises(SystemExit) as stopped:self.launcher.main()
            self.assertEqual(stopped.exception.code,0)
            return call.call_args.kwargs['env']['WEBSITE_PROFILE_TEST_MARKER']

    def test_connected_default_and_explicit_override_use_one_selected_profile(self):
        (self.root/'.runtime/active-profile.txt').write_text('delivery.json\n',encoding='utf-8')
        self.assertEqual(self.run_launcher(),'connected-profile')
        self.assertEqual(self.run_launcher({'WEBSITE_LOCAL_CONFIG':'local.json'}),'old-profile')
        self.assertEqual(self.run_launcher({'WEBSITE_LOCAL_CONFIG':'delivery.json'}),'connected-profile')
        (self.root/'.runtime/active-profile.txt').write_bytes(b'\xff\xfe')
        self.assertEqual(self.run_launcher({'WEBSITE_LOCAL_CONFIG':'delivery.json'}),'connected-profile')

    def test_missing_pointer_preserves_setup_default_and_invalid_pointer_cannot_escape(self):
        self.assertEqual(self.run_launcher(),'old-profile')
        (self.root/'.runtime/active-profile.txt').write_text('../delivery.json',encoding='utf-8')
        with patch.dict(os.environ,{},clear=True),patch.object(sys,'argv',['local.py','serve']),patch.object(self.launcher.subprocess,'call') as call:
            with self.assertRaises(SystemExit):self.launcher.main()
            call.assert_not_called()

if __name__=='__main__':unittest.main()
