<template>
  <GraduationProcessActionBaseView :ctx="ctx" />
</template>

<script>
import GraduationProcessActionBaseView from './GraduationProcessActionBaseView.vue'

const PANEL_BY_ACTION = {
  taskbook: 'taskbook',
  guidance: 'guidance',
  plan: 'plan',
  eval: 'eval',
  midterm: 'midterm',
  rectify: 'midterm'
}

function fillProcessContext(query, route, sourceQuery = {}) {
  const nextQuery = { ...query }
  let changed = false
  const action = String(route.params.action || '')
  if (!nextQuery.panel) { nextQuery.panel = PANEL_BY_ACTION[action] || 'taskbook'; changed = true }
  if (!nextQuery.studentId && route.params.studentId) { nextQuery.studentId = String(route.params.studentId); changed = true }
  for (const key of ['batchId', 'queue', 'source']) {
    if ((nextQuery[key] === undefined || nextQuery[key] === null || nextQuery[key] === '') && sourceQuery[key]) {
      nextQuery[key] = String(sourceQuery[key])
      changed = true
    }
  }
  return { query: nextQuery, changed }
}

export default {
  name: 'GraduationProcessActionView',
  components: { GraduationProcessActionBaseView },
  props: { ctx: { type: Object, required: true } },
  beforeRouteEnter(to, from, next) {
    if (from.name !== 'graduation-process') return next()
    const resolved = fillProcessContext(to.query, to, from.query)
    if (!resolved.changed) return next()
    return next({ path: to.path, query: resolved.query, replace: true })
  },
  beforeRouteLeave(to, from, next) {
    if (to.name !== 'graduation-process') return next()
    const resolved = fillProcessContext(to.query, from, from.query)
    if (!resolved.changed) return next()
    return next({ name: 'graduation-process', query: resolved.query, replace: true })
  }
}
</script>
