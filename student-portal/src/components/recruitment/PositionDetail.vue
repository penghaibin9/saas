<template>
  <article class="position-detail">
    <header class="detail-hero">
      <div>
        <div class="detail-title-row">
          <h2>{{ position.title }}</h2>
          <strong>{{ position.remuneration }}</strong>
        </div>
        <div class="detail-company-row">
          <span>{{ position.companyName }}</span>
          <span v-if="position.companyVerified" class="verified">学校已核验</span>
          <span>· {{ position.workLocation }}</span>
        </div>
      </div>
      <button type="button" class="primary-action" :disabled="disabled" @click="$emit('add-volunteer', position)">
        {{ disabled ? '当前不可加入志愿' : '加入志愿' }}
      </button>
    </header>

    <section class="conditions-block" aria-label="工作安排与劳动条件">
      <div class="section-title">
        <div><strong>工作安排与劳动条件</strong><span>学校实习岗位必须明确展示</span></div>
      </div>
      <div class="condition-grid">
        <div v-for="row in conditions" :key="row[0]" class="condition-item">
          <span>{{ row[0] }}</span>
          <strong>{{ row[1] }}</strong>
        </div>
      </div>
    </section>

    <section class="detail-section">
      <h3>岗位介绍</h3>
      <p>{{ position.description || '企业暂未补充岗位介绍。' }}</p>
    </section>
    <section class="detail-section">
      <h3>岗位要求</h3>
      <p>{{ position.requirements || '企业暂未补充岗位要求。' }}</p>
      <div class="tag-row">
        <span v-for="major in position.majors" :key="major" class="tag">{{ major }}</span>
        <span v-for="grade in position.grades" :key="grade" class="tag">{{ grade }}</span>
        <span class="tag tag--match">{{ position.matchLabel }}</span>
      </div>
    </section>
    <section class="detail-section">
      <h3>薪酬福利</h3>
      <div class="benefit-line">
        <span>岗位薪酬：<strong>{{ position.remuneration }}</strong></span>
        <span>补贴：{{ position.subsidy || '待确认' }}</span>
        <span>住宿：{{ position.accommodation === true ? '提供' : position.accommodation === false ? '不提供' : '待确认' }}</span>
        <span>餐食：{{ position.meal === true ? '提供' : position.meal === false ? '不提供' : '待确认' }}</span>
      </div>
    </section>
    <section class="detail-section safety-section">
      <h3>安全权益</h3>
      <p><strong>危险因素：</strong>{{ position.hazardous || '无明确危险因素说明' }}</p>
      <p><strong>劳动防护/设备：</strong>{{ position.equipment || '待企业/学校确认' }}</p>
    </section>
    <section class="detail-section">
      <h3>企业信息</h3>
      <button type="button" class="company-link" :disabled="!position.companyId" @click="$emit('view-company', position.companyId)">
        <strong>{{ position.companyName }}</strong>
        <span>{{ [position.industry, position.companyNature, position.companyScale].filter(Boolean).join(' · ') || '查看学校公开企业资料' }}</span>
      </button>
      <p v-if="position.companyIntro">{{ position.companyIntro }}</p>
    </section>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { conditionRows } from '../../modules/internshipRecruitment/positionModel'

const props = defineProps({
  position: { type: Object, required: true },
  disabled: { type: Boolean, default: false }
})
defineEmits(['add-volunteer', 'view-company'])
const conditions = computed(() => conditionRows(props.position))
</script>

<style scoped>
.position-detail { min-width:0; border:1px solid #eef0f3; border-radius:10px; background:#fff; overflow:hidden; }
.detail-hero { display:flex; align-items:flex-start; justify-content:space-between; gap:18px; padding:20px; border-bottom:1px solid #f0f0f0; }
.detail-title-row { display:flex; align-items:baseline; gap:14px; flex-wrap:wrap; }
.detail-title-row h2 { margin:0; color:#1a1a1a; font-size:22px; }
.detail-title-row strong { color:#fa541c; font-size:18px; }
.detail-company-row { display:flex; gap:6px; flex-wrap:wrap; margin-top:7px; color:#666; font-size:13px; }
.verified { padding:1px 5px; border:1px solid #adc6ff; border-radius:4px; color:#2f6bff; font-size:11px; }
.primary-action { flex-shrink:0; min-width:112px; height:38px; border:0; border-radius:7px; background:#2f6bff; color:#fff; font-weight:600; cursor:pointer; }
.primary-action:disabled { background:#d9d9d9; cursor:not-allowed; }
.conditions-block { margin:16px 20px 0; padding:16px; border:1px solid #dfe8f8; border-radius:10px; background:#f8fbff; }
.section-title div { display:flex; align-items:baseline; gap:8px; flex-wrap:wrap; }
.section-title strong { color:#1a1a1a; }
.section-title span { color:#6f7f95; font-size:12px; }
.condition-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:12px; }
.condition-item { min-width:0; padding:9px 10px; border-radius:7px; background:#fff; }
.condition-item span { display:block; color:#8c8c8c; font-size:11px; }
.condition-item strong { display:block; margin-top:3px; color:#333; font-size:13px; overflow-wrap:anywhere; }
.detail-section { padding:18px 20px; border-bottom:1px solid #f3f3f3; }
.detail-section:last-child { border-bottom:0; }
.detail-section h3 { margin:0 0 10px; color:#1a1a1a; font-size:15px; }
.detail-section p { margin:0; color:#555; font-size:13px; line-height:1.75; white-space:pre-wrap; }
.safety-section { background:#fffdf7; }
.tag-row,.benefit-line { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
.tag { padding:3px 7px; border-radius:4px; background:#f0f5ff; color:#34527a; font-size:12px; }
.tag--match { font-weight:600; }
.benefit-line span { padding:7px 9px; border-radius:6px; background:#fafafa; color:#555; font-size:12px; }
.company-link { display:flex; align-items:center; justify-content:space-between; gap:12px; width:100%; padding:12px; border:1px solid #eef0f3; border-radius:8px; background:#fff; text-align:left; cursor:pointer; }
.company-link strong { color:#1a1a1a; }
.company-link span { color:#8c8c8c; font-size:12px; }
.company-link:disabled { cursor:default; }
.company-link + p { margin-top:10px; }
@media (max-width:1199px) { .condition-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:899px) {
  .detail-hero { flex-direction:column; }
  .primary-action { width:100%; }
  .condition-grid { grid-template-columns:1fr 1fr; }
  .conditions-block { margin:12px; }
  .detail-section { padding:16px 14px; }
}
</style>
