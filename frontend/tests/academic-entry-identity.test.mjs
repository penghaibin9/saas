import assert from 'node:assert/strict'
import test from 'node:test'
import { NAV_PLAN, ACADEMIC_NAV_SOURCE_MODULES, getVisibleNavPlan } from '../src/config/navPlan.js'
import { buildAcademicNavigation } from '../src/modules/academicAffairs/config/academicNavigation.js'
import { ACADEMIC_ENTRY_IDENTITIES } from '../src/modules/academicAffairs/config/academicEntryIdentity.js'
import { workspacePages, restoreWorkspace } from '../src/components/workspace/teacherWorkspace.js'
import { activeWorkspacePage, workspaceRouteOwner } from '../src/components/workspace/workspaceRouting.js'

const academic = NAV_PLAN.find(group => group.key === 'academic-affairs')
const leaves = academic.children.flatMap(module => module.children)
const pages = workspacePages(getVisibleNavPlan({permissionPatterns:['*']}).find(group => group.key === 'academic-affairs').children)
const routeFor = (path, entry) => {
  const url = new URL(path, 'http://workspace.local')
  url.searchParams.set('_workspace', entry)
  return {path:url.pathname, fullPath:url.pathname+url.search, query:Object.fromEntries(url.searchParams)}
}

test('265 frozen identities retain 244 full refs, 16 hidden aliases and canonical authorization', () => {
  assert.equal(ACADEMIC_ENTRY_IDENTITIES.length, 265)
  assert.equal(new Set(leaves.map(leaf => leaf.leafId)).size, 265)
  assert.equal(new Set(leaves.map(leaf => leaf.sourceKey)).size, 265)
  assert.equal(new Set(leaves.map(leaf => leaf.path)).size, 244)
  assert.equal(leaves.filter(leaf => leaf.hidden).length, 16)
  for (const leaf of leaves) {
    const owner = leaves.find(item => item.leafId === leaf.canonicalLeafId)
    assert.ok(owner && !owner.hidden, leaf.sourceKey)
    for (const field of ['path','permissionKey','permissionAny','permissionAll','status','disabled']) assert.deepEqual(owner[field], leaf[field])
  }
})

test('source reordering and display-title changes cannot change entry identity or historical sourceKey', () => {
  const reordered = ACADEMIC_NAV_SOURCE_MODULES.toReversed().map(module => ({...module,
    children:module.children.toReversed().map(leaf => ({...leaf,label:leaf.label+'（改名）'}))}))
  const changed = buildAcademicNavigation(reordered).flatMap(module => module.children)
  for (const leaf of leaves) {
    const actual = changed.find(item => item.leafId === leaf.leafId)
    assert.equal(actual.sourceKey, leaf.sourceKey)
    assert.equal(actual.path, leaf.path)
  }
})

test('exact legacy titles, sourceKeys and hidden aliases restore tabs, favorites and their appearance', () => {
  for (const leaf of leaves) {
    const owner = pages.find(page => page.id === leaf.canonicalLeafId)
    for (const legacy of [leaf.leafId, leaf.sourceKey, ...leaf.legacyWorkspaceIds.filter(id => !id.startsWith('/'))]) {
      const restored = restoreWorkspace({tabs:[legacy], recent:[legacy], shortcuts:[legacy],
        appearance:{[legacy]:{label:'我的入口',icon:'star',color:'sage'}}},pages)
      assert.deepEqual(restored.tabs,[owner.id],legacy)
      assert.deepEqual(restored.shortcuts,[owner.id],legacy)
      assert.deepEqual(restored.recent,[owner.id],legacy)
      assert.equal(restored.appearance[owner.id].label,'我的入口',legacy)
      const route=routeFor(leaf.path,legacy)
      const routeOwner=workspaceRouteOwner(route.path,route.fullPath)
      assert.equal(routeOwner.modKey,owner.moduleKey,legacy)
      assert.equal(activeWorkspacePage(pages,route,routeOwner.modKey)?.id,owner.id,legacy)
    }
  }
})

test('legacy raw URLs migrate only when unambiguous; permission loss never revives an entry', () => {
  for (const page of pages) {
    const samePath=pages.filter(item=>item.path===page.path)
    if (samePath.length===1) assert.equal(page.destination,undefined,'unique routes keep their original URL')
    assert.deepEqual(restoreWorkspace({tabs:[page.path]},pages).tabs,samePath.length===1?[page.id]:[])
  }
  const allowed = workspacePages(getVisibleNavPlan({permissionPatterns:['academicAffairs.term.view']}).find(group=>group.key==='academic-affairs').children)
  const allAliases=leaves.flatMap(leaf=>[leaf.leafId,...leaf.legacyWorkspaceIds])
  const restored=restoreWorkspace({tabs:allAliases,shortcuts:allAliases},allowed)
  assert.ok(restored.tabs.length>0)
  assert.ok(restored.tabs.every(id=>allowed.some(page=>page.id===id)))
  const org=pages.find(page=>page.path==='/admin/academic-affairs/orgs?tab=major')
  assert.deepEqual(restoreWorkspace({tabs:[org.id,...org.legacyWorkspaceIds]},allowed).tabs,[])
  for (const page of allowed) assert.equal(page.id,pages.find(item=>item.leafId===page.leafId).id)
})

test('ambiguous aliases, unknown IDs and mismatched deep-link paths cannot select another object', () => {
  const first=pages[0], second=pages[1]
  const ambiguous=[{...first,legacyWorkspaceIds:['ambiguous']},{...second,legacyWorkspaceIds:['ambiguous']}]
  assert.deepEqual(restoreWorkspace({tabs:['ambiguous','unknown']},ambiguous).tabs,[])
  const terms=pages.find(page=>page.path==='/admin/academic-affairs/terms')
  const wrong=routeFor('/admin/academic-affairs/terms/123?objectId=123',first.id)
  assert.equal(activeWorkspacePage(pages,wrong,'aa-terms').id,terms.id)
  const restored=restoreWorkspace({tabs:[terms.path,terms.id],appearance:{[terms.path]:{label:'旧'},[terms.id]:{label:'新'}}},pages)
  assert.deepEqual(restored.tabs,[terms.id])
  assert.equal(restored.appearance[terms.id].label,'新')
  assert.deepEqual(restoreWorkspace(restored,pages),restored)
})

test('nonacademic duplicate routes keep legacy title IDs, URLs and preferences', () => {
  const modules=[{key:'sa-profile',label:'学工',children:[{label:'学生',path:'/same'},{label:'名单',path:'/same'}]},
    {key:'in-workbench',label:'实习',children:[{label:'实习工作台',path:'/internship'}]}]
  const other=workspacePages(modules)
  assert.deepEqual(other.map(page=>page.id),['sa-profile:学生','sa-profile:名单','/internship'])
  assert.equal(new URL(other[0].destination,'http://workspace.local').searchParams.get('_workspace'),'sa-profile:学生')
  const saved={tabs:other.map(page=>page.id),shortcuts:['/internship'],theme:'sage'}
  assert.deepEqual(restoreWorkspace(saved,other).tabs,saved.tabs)
  assert.deepEqual(restoreWorkspace(saved,other).shortcuts,saved.shortcuts)
  assert.equal(restoreWorkspace(saved,other).theme,'sage')
})
