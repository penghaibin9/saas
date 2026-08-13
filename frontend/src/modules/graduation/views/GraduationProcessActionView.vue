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

export default {
  name: 'GraduationProcessActionView',
  components: { GraduationProcessActionBaseView },
  props: { ctx: { type: Object, required: true } },
  beforeRouteLeave(to, from, next) {
    if (to.name !== 'graduation-process') return next()
    const query = { ...to.query }
    let changed = false
    const action = String(from.params.action || '')
    if (!query.panel) { query.panel = PANEL_BY_ACTION[action] || 'taskbook'; changed = true }
    if (!query.studentId && from.params.studentId) { query.studentId = String(from.params.studentId); changed = true }
    for (const key of ['batchId', 'queue', 'source']) {
      if ((query[key] === undefined || query[key] === null || query[key] === '') && from.query[key]) {
        query[key] = String(from.query[key])
        changed = true
      }
    }
    if (!changed) return next()
    return next({ name: 'graduation-process', query, replace: true })
  }
}
</script>
