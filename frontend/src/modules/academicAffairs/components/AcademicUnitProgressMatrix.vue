<template>
  <section class="academic-unit-progress" aria-label="学院进度">
    <header><h2>{{ title }}</h2><p>各责任单位分别推进，学校统一办理条件单独核对。</p></header>
    <EmptyState v-if="!units.length" title="当前范围暂无学院进度" description="请核对学期与当前组织范围。" />
    <div v-else class="matrix-scroll" tabindex="0" aria-label="学院进度表，可横向滚动">
      <table><thead><tr><th scope="col">责任学院</th><th v-for="column in columns" :key="column.stageCode" scope="col">{{ column.label }}</th><th scope="col">当前阻断与责任</th></tr></thead>
        <tbody><tr v-for="unit in units" :key="unit.collegeId">
          <th scope="row">{{ unit.collegeName }}<small>{{ responsibility(unit.responsibility).assigneeLabel }}</small></th>
          <td v-for="column in columns" :key="column.stageCode"><StatusTag :label="status(stage(unit, column.stageCode)?.status).label" :type="status(stage(unit, column.stageCode)?.status).type" size="sm" /></td>
          <td><ul v-if="unit.blockers.length"><li v-for="(blocker, index) in unit.blockers" :key="index">{{ blockerMessage(blocker) }}</li></ul><span v-else>{{ status(unit.status).label }}</span></td>
        </tr></tbody>
      </table>
    </div>
  </section>
</template>

<script>
import { EmptyState, StatusTag } from '@/components/business'
import { ACADEMIC_FLOW_STAGES, academicFlowStatus, academicFlowResponsibility, academicFlowBlockerMessage } from '../config/academicFlowRegistry.js'
export default {
  name: 'AcademicUnitProgressMatrix', components: { EmptyState, StatusTag },
  props: { units: { type: Array, default: () => [] }, title: { type: String, default: '学院进度矩阵' } },
  computed: { columns() { return ACADEMIC_FLOW_STAGES.filter(column => this.units.some(unit => unit.stages.some(stage => stage.stageCode === column.stageCode))) } },
  methods: { status: academicFlowStatus, responsibility: academicFlowResponsibility, blockerMessage: academicFlowBlockerMessage, stage(unit, code) { return unit.stages.find(item => item.stageCode === code) } }
}
</script>

<style scoped>
.academic-unit-progress { border:1px solid var(--border-base); border-radius:10px; background:var(--bg-card); min-width:0; overflow:hidden; }.academic-unit-progress header { padding:14px 16px; }.academic-unit-progress h2 { font-size:15px; margin:0; }.academic-unit-progress p { margin:6px 0 0; color:var(--text-secondary); font-size:12px; line-height:1.7; }.matrix-scroll { overflow:auto; }.matrix-scroll:focus-visible { outline:2px solid var(--pri); outline-offset:-2px; }table { width:100%; border-collapse:collapse; text-align:left; font-size:12px; line-height:1.65; }th,td { padding:12px 14px; border-top:1px solid var(--border-base); vertical-align:top; }thead { background:var(--bg-soft,var(--bg-card)); }thead th { white-space:nowrap; font-weight:600; color:var(--text-secondary); }tbody th { min-width:150px; }small { display:block; margin-top:5px; color:var(--text-secondary); font-weight:400; }td:last-child { min-width:190px; max-width:300px; overflow-wrap:anywhere; }ul { padding-left:17px; margin:0; }
</style>
