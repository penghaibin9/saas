<template>
  <article class="enterprise-public">
    <header class="enterprise-hero">
      <div class="enterprise-brand">
        <img v-if="company.logo" :src="company.logo" :alt="`${company.name} logo`" />
        <div v-else class="enterprise-logo-fallback">企</div>
        <div>
          <div class="enterprise-title-row">
            <h1>{{ company.name }}</h1>
            <span v-if="company.schoolVerified" class="verified">学校已核验</span>
          </div>
          <p>{{ summaryLine }}</p>
        </div>
      </div>
      <div class="enterprise-metrics">
        <div><strong>{{ company.internCount }}</strong><span>在岗实习生</span></div>
        <div><strong>{{ company.activeJobs }}</strong><span>当前岗位</span></div>
      </div>
    </header>

    <section class="enterprise-section">
      <h2>企业简介</h2>
      <p>{{ company.shortIntro || '企业暂未补充公开简介。' }}</p>
    </section>
    <section class="enterprise-section">
      <h2>主营业务</h2>
      <p>{{ company.mainBusiness || '企业暂未补充主营业务。' }}</p>
    </section>
    <section class="enterprise-section enterprise-grid">
      <div><span>所属行业</span><strong>{{ company.industry || '待完善' }}</strong></div>
      <div><span>企业性质</span><strong>{{ company.nature || '待完善' }}</strong></div>
      <div><span>企业规模</span><strong>{{ company.scale || '待完善' }}</strong></div>
      <div><span>所在地区</span><strong>{{ locationText }}</strong></div>
    </section>
    <section v-if="company.website" class="enterprise-section">
      <h2>官方网站</h2>
      <a :href="company.website" target="_blank" rel="noopener noreferrer">{{ company.website }}</a>
    </section>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ company: { type: Object, required: true } })
const summaryLine = computed(() => [props.company.industry, props.company.nature, props.company.scale].filter(Boolean).join(' · ') || '学校合作企业')
const locationText = computed(() => [props.company.city, props.company.region].filter(Boolean).join(' · ') || '待完善')
</script>

<style scoped>
.enterprise-public { min-width:0; border:1px solid #eef0f3; border-radius:12px; background:#fff; overflow:hidden; }
.enterprise-hero { display:flex; align-items:flex-start; justify-content:space-between; gap:24px; padding:22px; border-bottom:1px solid #f0f0f0; }
.enterprise-brand { display:flex; gap:14px; min-width:0; }
.enterprise-brand img,.enterprise-logo-fallback { width:56px; height:56px; flex-shrink:0; border-radius:10px; object-fit:cover; background:#f0f5ff; color:#2f6bff; display:grid; place-items:center; font-size:22px; font-weight:700; }
.enterprise-title-row { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.enterprise-title-row h1 { margin:0; color:#1a1a1a; font-size:22px; }
.enterprise-brand p { margin:6px 0 0; color:#666; font-size:13px; }
.verified { padding:2px 6px; border:1px solid #adc6ff; border-radius:4px; color:#2f6bff; font-size:11px; }
.enterprise-metrics { display:flex; gap:10px; flex-shrink:0; }
.enterprise-metrics div { min-width:84px; padding:10px 12px; border-radius:8px; background:#f8faff; text-align:center; }
.enterprise-metrics strong { display:block; color:#1a1a1a; font-size:18px; }
.enterprise-metrics span { display:block; margin-top:3px; color:#8c8c8c; font-size:11px; }
.enterprise-section { padding:18px 22px; border-bottom:1px solid #f3f3f3; }
.enterprise-section:last-child { border-bottom:0; }
.enterprise-section h2 { margin:0 0 9px; color:#1a1a1a; font-size:15px; }
.enterprise-section p { margin:0; color:#555; font-size:13px; line-height:1.75; white-space:pre-wrap; }
.enterprise-section a { color:#2f6bff; font-size:13px; overflow-wrap:anywhere; }
.enterprise-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }
.enterprise-grid div { padding:10px; border-radius:8px; background:#fafafa; }
.enterprise-grid span { display:block; color:#8c8c8c; font-size:11px; }
.enterprise-grid strong { display:block; margin-top:4px; color:#333; font-size:13px; }
@media (max-width:899px) {
  .enterprise-hero { flex-direction:column; padding:16px; }
  .enterprise-metrics { width:100%; }
  .enterprise-metrics div { flex:1; }
  .enterprise-section { padding:16px; }
  .enterprise-grid { grid-template-columns:1fr 1fr; }
}
</style>
