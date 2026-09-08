import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'

function filters(initial = {}) {
  const source = parse(fs.readFileSync(new URL('../src/components/recruitment/PositionSearchFilters.vue', import.meta.url), 'utf8')).descriptor.scriptSetup.content
    .replace(/^import.*$/gm, '')
    .replace(/^const props = defineProps.*$/m, '').replace(/^const emit = defineEmits.*$/m, '')
  const props = reactive({ modelValue: initial })
  const events = []
  const timers = new Map()
  let timerId = 0
  const scope = effectScope()
  const state = scope.run(() => new Function('props', 'emit', 'computed', 'reactive', 'ref', 'watch', 'onBeforeUnmount', 'setTimeout', 'clearTimeout', source + '\nreturn { draft, reset, onKeywordInput };')(
    props, (...event) => events.push(event), computed, reactive, ref, watch, () => {},
    (fn) => { timers.set(++timerId, fn); return timerId }, (id) => timers.delete(id)))
  return { props, events, timers, state, stop: () => scope.stop() }
}

test('missing optional catalog filters select their default options and external resets clear previous values', async () => {
  const f = filters({ sort: 'LATEST' })
  try {
    assert.equal(f.state.draft.accommodation, '')
    assert.equal(f.state.draft.majorMatched, '')
    f.props.modelValue = { city: '长沙', accommodation: 'true', sort: 'LATEST' }
    await nextTick()
    assert.equal(f.state.draft.city, '长沙')
    f.props.modelValue = { sort: 'RECOMMENDED' }
    await nextTick()
    assert.equal(f.state.draft.city, '')
    assert.equal(f.state.draft.accommodation, '')
    assert.equal(f.events.length, 0)
  } finally { f.stop() }
})

test('external filter navigation cancels an old debounced search', async () => {
  const f = filters()
  try {
    f.state.onKeywordInput({ target: { value: '旧搜索' } })
    assert.equal(f.timers.size, 1)
    f.props.modelValue = { keyword: '新搜索' }
    await nextTick()
    assert.equal(f.timers.size, 0)
    assert.equal(f.state.draft.keyword, '新搜索')
    assert.equal(f.events.length, 0)
    f.state.reset()
    assert.equal(f.events.find(([event]) => event === 'search')[1].keyword, '')
    assert.equal(f.events.find(([event]) => event === 'search')[1].page, 1)
  } finally { f.stop() }
})
