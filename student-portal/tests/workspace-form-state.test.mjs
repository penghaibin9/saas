import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, ref, shallowRef } from 'vue'
const source=readFileSync(new URL('../src/layouts/PortalLayout.vue',import.meta.url),'utf8')
const code=source.slice(source.indexOf('const activeFormCheck ='),source.indexOf("provide('registerWorkspaceForm'"))
test('saved forms override historic input flags and late unregister cannot clear the next form',()=>{
  const edited=ref(true), dirty=ref(true)
  const state=new Function('computed','shallowRef','edited',code+';return {hasEdits,registerWorkspaceForm}')(computed,shallowRef,edited)
  const release=state.registerWorkspaceForm(()=>dirty.value)
  assert.equal(state.hasEdits.value,true)
  dirty.value=false;assert.equal(state.hasEdits.value,false)
  const releaseNext=state.registerWorkspaceForm(()=>true)
  release();assert.equal(state.hasEdits.value,true)
  releaseNext();assert.equal(state.hasEdits.value,true) // Legacy pages retain input protection.
})

test('busy material submissions block navigation, while a clean saved form leaves directly',()=>{
  const edited=ref(true), busy=ref(true), dirty=ref(true), notices=[]
  const guard=source.slice(source.indexOf('let leavePromise ='),source.indexOf('function resolveLeave'))
  const state=new Function('computed','shallowRef','edited','ui','openDialog','leaveDialog',code+guard+';return {mayLeave,registerWorkspaceForm}')(
    computed,shallowRef,edited,{notify:message=>notices.push(message)},()=>{throw Error('unexpected dialog')},ref(null))
  state.registerWorkspaceForm(()=>dirty.value,()=>busy.value)
  assert.equal(state.mayLeave(),false)
  assert.match(notices[0],/正在提交/)
  busy.value=false;dirty.value=false
  assert.equal(state.mayLeave(),true)
})
