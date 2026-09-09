<template>
  <section class="file-evidence-panel">
    <div class="file-evidence-panel__head">
      <strong>本次审核材料</strong>
      <span :class="reviewReady ? 'is-ready' : 'is-blocked'">{{ reviewReady ? '文件已就绪' : '文件暂不可审核' }}</span>
    </div>
    <div v-if="versionConflict" class="file-evidence-panel__conflict">
      检测到学生已提交新版本：本次审核锁定 v{{ versionConflict.old || '—' }}，最新为 v{{ versionConflict.latest || '—' }}。请切换最新版本并重新核验后再批阅。
    </div>
    <div v-if="canonical" class="file-evidence-panel__canonical">
      <span>{{ canonical.materialName || canonical.fileName || '审核主文件' }}</span>
      <b>当前提交第 {{ canonical.versionNo ?? '—' }} 版</b>
      <span>{{ scanLabel(canonical.scanStatus) }}</span>
    </div>
    <details v-if="canonical" class="file-evidence-panel__history">
      <summary>查看文件校验证据与历史版本</summary>
      <div class="file-evidence-panel__technical">
        <code>FileVersion {{ canonical.fileVersionId ?? canonical.versionId ?? '—' }}</code>
        <code :title="canonical.sourceSha256 || canonical.sha256">SHA-256 {{ shortHash(canonical.sourceSha256 || canonical.sha256) }}</code>
      </div>
      <div v-for="item in versions" :key="String(item.fileVersionId ?? item.versionId ?? item.id)" class="file-evidence-panel__row">
        <span>第 {{ item.versionNo ?? '—' }} 版</span><span>{{ item.versionStatus || item.status || '—' }}</span><code>{{ shortHash(item.sourceSha256 || item.sha256) }}</code>
      </div>
    </details>
  </section>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ versions: { type: Array, default: () => [] }, canonicalFileVersionId: { type: [String, Number], default: null }, reviewReady: { type: Boolean, default: false }, versionConflict: { type: Object, default: null } })
const canonical = computed(() => props.versions.find((item) => String(item.fileVersionId ?? item.versionId ?? item.id) === String(props.canonicalFileVersionId)) || props.versions[0] || null)
function shortHash(value) { const text = String(value || ''); return text.length > 16 ? `${text.slice(0, 8)}…${text.slice(-8)}` : (text || '—') }
function scanLabel(value) { return ({ CLEAN: '安全检查通过', PASSED: '安全检查通过', READY: '可以审核', PENDING: '正在进行安全检查', BLOCKED: '文件被安全策略拦截' })[value] || '文件状态已记录' }
</script>
<style scoped>
.file-evidence-panel{border:1px solid var(--border-light);border-radius:9px;background:var(--gray-50,#f8fafc);padding:9px}.file-evidence-panel__head{display:flex;justify-content:space-between;gap:8px;align-items:center}.file-evidence-panel__head span{font-size:12px}.is-ready{color:var(--success-600,#16a34a)}.is-blocked{color:var(--warning-700,#a16207)}.file-evidence-panel__conflict{margin-top:8px;padding:8px;border-radius:7px;background:#fff7ed;color:#c2410c;font-size:12px;line-height:1.5}.file-evidence-panel__canonical{margin-top:8px;display:grid;gap:4px;font-size:12px}.file-evidence-panel code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;overflow:hidden;text-overflow:ellipsis}.file-evidence-panel__history{margin-top:8px;font-size:12px}.file-evidence-panel__technical{display:grid;gap:4px;margin-top:6px;padding:7px;border-radius:6px;background:#fff}.file-evidence-panel__row{display:grid;grid-template-columns:70px 1fr minmax(90px,1fr);gap:6px;padding-top:5px}
</style>
