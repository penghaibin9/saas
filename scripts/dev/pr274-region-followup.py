from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

HEAD = '32e0a8deb86ca23e3575b73e500ba0b166f14c5e'
BASE = '86f1e64abcd1261e9ed3437720c299f8cbb5ee56'
TREE = 'e23c589ccaeca444b3c580d9d3f587fbbef03be5'
REPO = 'penghaibin9/saas'
REGION = 'miniapp/src/components/MobileRegionPicker.vue'
TEST = 'miniapp/tests/orientation-region-picker.test.mjs'
FILES = [REGION, TEST]
TESTS = '''
test('external form clear removes the previous region from every selector', () => {
  const vm = view('浙江省 杭州市 西湖区')
  assert.equal(vm.countyCode, '330106')
  vm.modelValue = ''
  component.watch.modelValue.handler.call(vm, '')
  assert.equal(vm.provinceCode, '')
  assert.equal(vm.cityCode, '')
  assert.equal(vm.countyCode, '')
  assert.deepEqual(vm.events, [])
})

test('a completed selection can be cleared externally without preserving an internal draft', () => {
  const vm = view('湖南省 长沙市 岳麓区')
  vm.chooseProvince('330000'); vm.chooseCity('330100'); vm.chooseCounty('330106')
  assert.equal(vm.modelValue, '浙江省 杭州市 西湖区')
  vm.modelValue = ''
  component.watch.modelValue.handler.call(vm, '')
  assert.equal(vm.provinceCode + vm.cityCode + vm.countyCode, '')
})

test('disabled region selection never changes a value or emits a native confirmation', () => {
  const vm = view('浙江省 杭州市 西湖区')
  vm.disabled = true
  vm.chooseProvince('430000'); vm.chooseCity('430100'); vm.chooseCounty('430104')
  vm.onConfirm({ detail: { value: ['湖南省', '长沙市', '岳麓区'], code: ['430000', '430100', '430104'] } })
  assert.equal(vm.modelValue, '浙江省 杭州市 西湖区')
  assert.equal(vm.countyCode, '330106')
  assert.deepEqual(vm.events, [])
})

import { createRenderer, h, nextTick, ref } from 'vue'

test('Vue prop updates distinguish internal cascading edits from an external clear', async () => {
  const renderer = createRenderer({
    createElement: tag => ({ tag, children: [] }), createText: text => ({ text }), createComment: text => ({ text }),
    insert(child, parent) { child.parent = parent; (parent.children ||= []).push(child) }, remove() {},
    parentNode: node => node.parent, nextSibling: () => null, patchProp() {},
    setText(node, text) { node.text = text }, setElementText(node, text) { node.text = text }
  })
  const model = ref('浙江省 杭州市 西湖区')
  const definition = { ...component, render: () => null }
  let region
  const app = renderer.createApp({ setup: () => () => h(definition, {
    modelValue: model.value, 'onUpdate:modelValue': value => { model.value = value }, ref: value => { region = value }
  }) })
  app.mount({ children: [] })
  try {
    region.chooseProvince('430000'); await nextTick()
    assert.equal(model.value, ''); assert.equal(region.provinceCode, '430000')
    region.chooseCity('430100'); await nextTick()
    assert.equal(region.cityCode, '430100')
    region.chooseCounty('430104'); await nextTick()
    assert.equal(region.countyCode, '430104'); assert.notEqual(model.value, '')
    model.value = ''; await nextTick()
    assert.equal(region.provinceCode + region.cityCode + region.countyCode, '')
  } finally { app.unmount() }
})
'''

def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args]).decode('utf-8')

def replace(path, old, new, count=1):
    p = Path(path); value = p.read_text(encoding='utf-8')
    if value.count(old) != count: raise RuntimeError(f'Changed anchor: {path}: {old!r}')
    p.write_text(value.replace(old, new), encoding='utf-8', newline='\n')

def reproduce():
    if git('rev-parse', 'HEAD').strip() != HEAD or git('status', '--porcelain').strip():
        raise RuntimeError('Require untouched current repair head')
    p = Path(TEST); p.write_text(p.read_text(encoding='utf-8').rstrip() + '\n\n' + TESTS.strip() + '\n', encoding='utf-8', newline='\n')
    result = subprocess.run(['node', '--test', '--test-reporter=tap', 'tests/orientation-region-picker.test.mjs'], cwd='miniapp', text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    Path('../region-before-repair.log').write_text(result.stdout, encoding='utf-8')
    failures = [line for line in result.stdout.splitlines() if line.startswith('not ok')]
    if result.returncode != 1 or len(failures) != 3 or not all(('external' in line) for line in failures):
        raise RuntimeError('Expected external-reset regression was not reproduced exactly: ' + result.stdout)
    print('Reproduced three external-reset regressions on unchanged component:', *failures, sep='\n')

def apply():
    replace(REGION, "data() { return { provinceCode: '', cityCode: '', countyCode: '' } }", "data() { return { provinceCode: '', cityCode: '', countyCode: '', pendingSelectionClear: false } }")
    replace(REGION, "    if (!value) return\n    const names = String(value).trim().split(/\\s+/)", """    if (!value) {
      if (this.pendingSelectionClear) { this.pendingSelectionClear = false; return }
      this.provinceCode = ''; this.cityCode = ''; this.countyCode = ''
      return
    }
    this.pendingSelectionClear = false
    const names = String(value).trim().split(/\\s+/)""")
    replace(REGION, "  methods: {\n    // #ifdef H5\n", """  methods: {
    // #ifdef H5
    clearModelForSelection() {
      // Internal cascade edits clear the submitted value, not the new selection.
      // The marker lasts through Vue's prop update, never through a later reset.
      this.pendingSelectionClear = true
      this.$emit('update:modelValue', '')
      this.$nextTick?.(() => { this.pendingSelectionClear = false })
    },
""")
    replace(REGION, "this.countyCode = ''; this.$emit('update:modelValue', '')", "this.countyCode = ''; this.clearModelForSelection()", count=2)
    replace(REGION, "if (!code) { this.$emit('update:modelValue', ''); return }", "if (!code) { this.clearModelForSelection(); return }")
    subprocess.run(['git', 'diff', '--check'], check=True)
    changed = set(git('diff', '--name-only').splitlines())
    if changed != set(FILES): raise RuntimeError('Unexpected follow-up scope')
    subprocess.run(['git', 'add', '--', *FILES], check=True)
    Path('region-reviewed.diff').write_text(git('diff', '--cached', '--'), encoding='utf-8')
    print(git('diff', '--cached', '--stat'))

def api(method, path, value=None):
    data = json.dumps(value).encode() if value is not None else None
    request = urllib.request.Request('https://api.github.com/repos/' + REPO + path, data=data, method=method, headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=45) as response: return json.load(response)

def publish():
    pr = api('GET', '/pulls/274')
    if pr['head']['sha'] != HEAD or pr['base']['sha'] != BASE or pr['state'] != 'open': raise RuntimeError('PR changed; refuse stale candidate')
    if set(git('diff', '--cached', '--name-only').splitlines()) != set(FILES): raise RuntimeError('Unexpected staged files')
    entries=[]
    for path in FILES:
        content = subprocess.check_output(['git', 'show', ':' + path])
        blob = api('POST', '/git/blobs', {'content': base64.b64encode(content).decode(), 'encoding': 'base64'})
        if blob['sha'] != hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest(): raise RuntimeError('Blob mismatch')
        entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    tree = api('POST', '/git/trees', {'base_tree': TREE, 'tree': entries})
    commit = api('POST', '/git/commits', {'message': 'fix(orientation): clear stale H5 region state on external form reset', 'tree': tree['sha'], 'parents': [HEAD]})
    evidence={'candidate':commit['sha'],'parent':HEAD,'tree':tree['sha'],'files':FILES,'branchUpdated':False,'merged':False}
    Path('region-candidate.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CANDIDATE_READY '+json.dumps(evidence,ensure_ascii=False))

if __name__ == '__main__':
    {'reproduce':reproduce,'apply':apply,'publish':publish}[sys.argv[1]]()
