<template>
  <section class="recruitment-context" aria-label="招聘季上下文">
    <div class="context-heading">
      <div>
        <div class="eyebrow">当前招聘季</div>
        <h2>{{ context.campaignName }}</h2>
      </div>
      <span class="phase" :class="`phase--${context.status.toLowerCase()}`">{{ context.phaseLabel }}</span>
    </div>

    <div class="conclusion" :class="{ 'is-blocked': !context.canSelect, 'is-locked': context.groupStatus === 'LOCKED' }">
      <strong>{{ conclusion }}</strong>
      <span v-if="context.groupStatus === 'LOCKED' && context.schoolConfirmDeadline">
        学校确认截止：{{ formatDeadline(context.schoolConfirmDeadline) }}
      </span>
      <span v-else>学生选岗截止：{{ formatDeadline(context.selectionDeadline) }}</span>
    </div>

    <div class="metrics">
      <div class="metric"><span>已发布岗位</span><strong>{{ context.publishedPositions }}</strong></div>
      <div class="metric"><span>合作企业</span><strong>{{ context.partnerCompanies }}</strong></div>
      <div class="metric"><span>匹配岗位</span><strong>{{ context.matchedPositions }}</strong></div>
      <div class="metric"><span>已选志愿</span><strong>{{ context.selectedVolunteers }}/3</strong></div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { formatDeadline, selectionConclusion } from '../../modules/internshipRecruitment/contextModel'

const props = defineProps({ context: { type: Object, required: true } })
const conclusion = computed(() => selectionConclusion(props.context))
</script>

<style scoped>
.recruitment-context { background:#fff; border:1px solid #eef0f3; border-radius:12px; padding:18px 20px; }
.context-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
.eyebrow { color:#8c8c8c; font-size:12px; margin-bottom:4px; }
h2 { margin:0; color:#1a1a1a; font-size:20px; line-height:1.4; }
.phase { padding:4px 10px; border-radius:999px; background:#f0f5ff; color:#2f6bff; font-size:12px; font-weight:600; white-space:nowrap; }
.phase--closed,.phase--archived { background:#f5f5f5; color:#595959; }
.phase--frozen { background:#fff7e6; color:#d46b08; }
.conclusion { display:flex; justify-content:space-between; gap:16px; margin-top:16px; padding:12px 14px; border-radius:8px; background:#f6f9ff; color:#24456f; font-size:13px; }
.conclusion strong { color:#163d72; }
.conclusion.is-blocked { background:#fafafa; color:#666; }
.conclusion.is-locked { background:#fff7e6; color:#874d00; }
.metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:14px; }
.metric { min-width:0; padding:10px 12px; border:1px solid #f0f0f0; border-radius:8px; background:#fcfcfc; }
.metric span { display:block; color:#8c8c8c; font-size:12px; }
.metric strong { display:block; margin-top:3px; color:#1a1a1a; font-size:18px; }
@media (max-width:899px) {
  .conclusion { flex-direction:column; gap:4px; }
  .metrics { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
</style>
