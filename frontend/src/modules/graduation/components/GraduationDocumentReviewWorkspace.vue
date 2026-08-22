<template>
  <div class="gd-review-workspace" :class="{ 'is-narrow': narrow }">
    <aside class="gd-review-workspace__queue">
      <div class="gd-review-workspace__queue-head">
        <strong>{{ queueTitle || (mode === 'proposal' ? '开题队列' : '成果队列') }}</strong>
        <span>{{ currentIndex + 1 }} / {{ queue.length }}</span>
      </div>
      <button
        v-for="(item, index) in queue" :key="queueKey(item, index)" type="button"
        :class="{ 'is-active': index === currentIndex }" :disabled="submitting"
        @click="$emit('select', item)"
      >
        <span class="gdq-name">{{ item.studentName || '学生' }}</span>
        <span class="gdq-class">{{ item.className || '' }}</span>
        <small>{{ item.topicTitle || '未填写课题' }}</small>
        <small>{{ item.statusLabel || item.status || '' }}</small>
      </button>
      <slot name="queue-footer" />
    </aside>

    <main class="gd-review-workspace__document">
      <div class="gd-review-workspace__business-bar">
        <div>
          <strong>{{ currentRecord?.studentName || '—' }}</strong>
          <span>{{ currentRecord?.topicTitle || '未填写课题' }}</span>
        </div>
        <div class="gd-review-workspace__nav">
          <button type="button" :disabled="submitting || currentIndex <= 0" @click="$emit('previous')">← 上一条</button>
          <button type="button" :disabled="submitting || currentIndex >= queue.length - 1" @click="$emit('next')">下一条 →</button>
        </div>
      </div>
      <div v-if="versionConflict" class="gd-review-workspace__conflict">
        学生材料版本已变化。当前阅读版本保持不动，批阅按钮已锁定；请切换到最新 canonical version 后重新核验。
      </div>
      <AppDocumentViewer
        v-if="descriptor && provider"
        :descriptor="descriptor" :provider="provider" :files="files" :versions="versions"
        :active-file-key="activeFileKey" :active-version-id="activeVersionId" :canonical-version-id="canonicalFileVersionId"
        :allow-download="allowDownload" :show-version-bar="true" :show-file-switcher="true"
        @select-file="$emit('select-file', $event)" @select-version="$emit('select-version', $event)" @download="$emit('download', $event)" @preview-error="$emit('reload')"
      />
      <div v-else class="gd-review-workspace__empty">当前记录没有可站内预览的安全文件版本。</div>
    </main>

    <aside class="gd-review-workspace__review">
      <div class="gd-review-workspace__summary">
        <div><span>学生</span><b>{{ currentRecord?.studentName || '—' }}</b></div>
        <div><span>班级</span><b>{{ currentRecord?.className || '—' }}</b></div>
        <div><span>指导教师</span><b>{{ currentRecord?.advisorName || '—' }}</b></div>
        <div><span>当前状态</span><b>{{ currentRecord?.statusLabel || currentRecord?.status || '—' }}</b></div>
        <div v-if="currentRecord?.plagiarismRate"><span>查重</span><b>{{ currentRecord.plagiarismRate }}</b></div>
      </div>
      <FileEvidencePanel :versions="evidenceVersions.length ? evidenceVersions : files" :canonical-file-version-id="canonicalFileVersionId" :review-ready="reviewReady" :version-conflict="versionConflict" />
      <label class="gd-review-workspace__auto"><input :checked="autoNext" :disabled="submitting" type="checkbox" @change="$emit('update:autoNext', $event.target.checked)" /> 批阅成功后自动下一条</label>
      <slot name="review" />
      <button type="button" class="gd-review-workspace__dossier" :disabled="submitting" @click="$emit('openStudentDossier', currentRecord)">查看学生完整档案 →</button>
    </aside>
  </div>
</template>

<script setup>
import AppDocumentViewer from '@/components/file/viewer/AppDocumentViewer.vue'
import FileEvidencePanel from './FileEvidencePanel.vue'

defineProps({
  queue: { type: Array, default: () => [] }, currentIndex: { type: Number, default: 0 }, currentRecord: { type: Object, default: null }, detail: { type: Object, default: null },
  files: { type: Array, default: () => [] }, versions: { type: Array, default: () => [] }, evidenceVersions: { type: Array, default: () => [] }, canonicalFileVersionId: { type: [String, Number], default: null },
  reviewReady: { type: Boolean, default: false }, expectedVersion: { type: [String, Number], default: null }, comment: { type: String, default: '' }, submitting: { type: Boolean, default: false }, autoNext: { type: Boolean, default: true }, mode: { type: String, default: 'final' }, queueTitle: { type: String, default: '' },
  provider: { type: Object, default: null }, descriptor: { type: Object, default: null }, activeFileKey: { type: [String, Number], default: null }, activeVersionId: { type: [String, Number], default: null },
  versionConflict: { type: Object, default: null }, allowDownload: { type: Boolean, default: false }, narrow: { type: Boolean, default: false }
})
defineEmits(['select', 'previous', 'next', 'update:comment', 'update:autoNext', 'approve', 'reject', 'reload', 'openStudentDossier', 'select-file', 'select-version', 'download'])
const queueKey = (item, index) => String(item?.caseKey ?? item?.id ?? item?.gdStudentId ?? index)
</script>

<style scoped>
.gd-review-workspace{display:grid;grid-template-columns:272px minmax(680px,1fr) 340px;gap:12px;align-items:start;min-width:0}.gd-review-workspace__queue,.gd-review-workspace__review{border:1px solid var(--border-light);border-radius:10px;background:var(--card,#fff);overflow:hidden}.gd-review-workspace__queue{position:sticky;top:12px;max-height:calc(100vh - 150px);overflow:auto}.gd-review-workspace__queue-head{display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid var(--border-light);font-size:13px}.gd-review-workspace__queue>button{width:100%;display:grid;grid-template-columns:1fr auto;gap:3px 6px;text-align:left;padding:9px 10px;border:0;border-bottom:1px solid var(--border-light);background:#fff;cursor:pointer}.gd-review-workspace__queue>button.is-active{background:var(--primary-50,#eff6ff);box-shadow:inset 3px 0 0 var(--brand-primary,#2563eb)}.gd-review-workspace__queue>button:disabled{cursor:not-allowed;opacity:.65}.gdq-name{font-weight:600}.gdq-class,.gd-review-workspace__queue small{font-size:11px;color:var(--text-tertiary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gd-review-workspace__document{min-width:0}.gd-review-workspace__business-bar{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px;padding:8px 10px;border:1px solid var(--border-light);border-radius:9px;background:#fff}.gd-review-workspace__business-bar>div:first-child{display:flex;gap:8px;min-width:0}.gd-review-workspace__business-bar span{color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gd-review-workspace__nav{display:flex;gap:6px}.gd-review-workspace__nav button,.gd-review-workspace__dossier{border:1px solid var(--border-light);background:#fff;border-radius:7px;padding:5px 8px;cursor:pointer}.gd-review-workspace__nav button:disabled,.gd-review-workspace__dossier:disabled{cursor:not-allowed;opacity:.55}.gd-review-workspace__conflict{margin-bottom:8px;padding:9px 10px;border-radius:8px;background:#fff7ed;color:#c2410c;font-size:13px}.gd-review-workspace__empty{min-height:520px;display:grid;place-content:center;border:1px dashed var(--border-light);border-radius:10px;color:var(--text-tertiary)}.gd-review-workspace__review{position:sticky;top:12px;padding:10px;display:grid;gap:10px}.gd-review-workspace__summary{display:grid;grid-template-columns:1fr 1fr;gap:7px}.gd-review-workspace__summary div{display:grid;gap:2px}.gd-review-workspace__summary span{font-size:11px;color:var(--text-tertiary)}.gd-review-workspace__summary b{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gd-review-workspace__auto{font-size:12px;color:var(--text-secondary)}.gd-review-workspace__dossier{width:100%}.gd-review-workspace.is-narrow{grid-template-columns:1fr}.gd-review-workspace.is-narrow .gd-review-workspace__queue,.gd-review-workspace.is-narrow .gd-review-workspace__review{position:static;max-height:none}
@media(max-width:1439px){.gd-review-workspace:not(.is-narrow){grid-template-columns:264px minmax(560px,1fr) 320px}}@media(max-width:1100px){.gd-review-workspace{grid-template-columns:1fr}.gd-review-workspace__queue,.gd-review-workspace__review{position:static;max-height:none}}
</style>
