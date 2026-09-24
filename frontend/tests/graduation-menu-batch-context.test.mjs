import test from 'node:test'
import assert from 'node:assert/strict'
import { workspaceRouteOwner, activeWorkspacePage } from '../src/components/workspace/workspaceRouting.js'
import { GRADUATION_WORKSPACES } from '../src/modules/graduation/config/graduationWorkspaces.js'

test('graduation menu ownership survives batch context and additional filters', () => {
  for (const mod of GRADUATION_WORKSPACES) for (const leaf of mod.children) {
    const url = new URL(leaf.path, 'http://test.local')
    url.searchParams.set('batchId', '51')
    url.searchParams.set('page', '2')
    const fullPath = url.pathname + url.search
    const owner = workspaceRouteOwner(url.pathname, fullPath)
    assert.equal(owner.modKey, mod.key, fullPath)
    assert.equal(owner.leafKey, leaf.label, fullPath)
    const pages = GRADUATION_WORKSPACES.flatMap(m => m.children.map(l => ({ ...l, id: l.path, moduleKey: m.key })))
    assert.equal(activeWorkspacePage(pages, {fullPath, query:{}}, owner.modKey)?.label, leaf.label, fullPath)
  }
})

test('batch create edit and detail never belong to overview', () => {
 for(const path of ['/admin/graduation/batches/create','/admin/graduation/batches/51/edit','/admin/graduation/batches/51']){
  const fullPath=path+'?batchId=51'
  assert.equal(workspaceRouteOwner(path,fullPath).modKey,'gd-batch-impl')
  const pages=GRADUATION_WORKSPACES.flatMap(m=>m.children.map(l=>({...l,id:l.path,moduleKey:m.key})))
  assert.equal(activeWorkspacePage(pages,{fullPath,query:{}},'gd-workbench').label,'批次与规则')
 }
})

test('graduation list forms retain their business menu instead of overview', () => {
 for(const [suffix,moduleKey,leafKey] of [
 ['students/create','gd-batch-impl','学生与进度'],['mentors/create','gd-batch-impl','导师与分配'],
 ['mentors/51/edit','gd-batch-impl','导师与分配'],['topic-lib/create','gd-topic-select','题目库'],
 ['topic-lib/51/edit','gd-topic-select','题目库'],['topic-rounds/create','gd-topic-select','选题轮次'],
 ['templates/create','gd-templates','全部模板'],['templates/51/edit','gd-templates','全部模板']]){
  const path='/admin/graduation/'+suffix
  const owner=workspaceRouteOwner(path,path+'?batchId=51')
  assert.equal(owner.modKey,moduleKey,suffix);assert.equal(owner.leafKey,leafKey,suffix)
 }
})
