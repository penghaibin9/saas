<template>
  <div class="gd-review-workspace" :class="{ 'is-narrow': narrow, 'is-submitting': submitting }" :aria-busy="submitting">
    <aside class="gd-review-workspace__queue">
      <div class="gd-review-workspace__queue-head">
        <strong>{{ queueTitle || (mode === 'proposal' ? '开题队列' : '成果队列') }}</strong>
        <span>{{ currentIndex + 1 }} / {{ queue.length }}</span>
      </div>
      <button
        v-for="(item, index) in queue"
        :key="queueKey(item, index)"
        type="button"
        :class="{ 'is-active': index === currentIndex }"
        :disabled="submitting"
        @click="emitUnlocked('select', item)"
      >
        <span class="gdq-name">{{ item.studentName || '学生' }}</span>
        <span class="gdq-class">{{ item.className || '' }}</span>
        <small>{{ item.topicTitle || '未填写课题' }}</small>
        <small>{{ recordStatusLabel(item.status, item.statusLabel) }}</small>
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
          <button type="button" :disabled="submitting || currentIndex <= 0" @click="emitUnlocked('previous')">← 上一条</button>
          <button type="button" :disabled="submitting || currentIndex >= queue.length - 1" @click="emitUnlocked('next')">下一条 →</button>
        </div>
      </div>
      <div v-if="submitting" class="gd-review-workspace__lock" role="status">
        正在提交当前审核结论；学生、记录、业务版本与 FileVersion 已锁定。
      </div>
      <div v-if="versionConflict" class="gd-review-workspace__conflict">
        学生材料版本已变化。当前阅读版本保持不动，批阅按钮已锁定；请切换到最新 canonical version 后重新核验。
      </div>
      <AppDocumentViewer
        v-if="descriptor && provider"
        class="gd-review-workspace__viewer"
        :class="{ 'is-command-locked': submitting }"
        :descriptor="descriptor"
        :provider="provider"
        :files="files"
        :versions="versions"
        :active-file-key="activeFileKey"
        :active-version-id="activeVersionId"
        :canonical-version-id="canonicalFileVersionId"
        :allow-download="Boolean(allowDownload && !submitting)"
        :show-version-bar="true"
        :show-file-switcher="true"
        @select-file="emitUnlocked('select-file', $event)"
        @select-version="emitUnlocked('select-version', $event)"
        @download="emitUnlocked('download', $event)"
      />
      <div v-else class="gd-review-workspace__empty">当前记录没有可站内预览的安全文件版本。</div>
    </main>

    <aside class="gd-review-workspace__review">
      <div class="gd-review-workspace__contract" data-testid="review-command-contract">
        <div><span>业务版本</span><b>{{ expectedVersion ?? '—' }}</b></div>
        <div><span>FileVersion</span><b>{{ canonicalFileVersionId ?? '—' }}</b></div>
        <div><span>安全门</span><b :class="reviewReady && !versionConflict ? 'is-ready' : 'is-blocked'">{{ reviewReady && !versionConflict ? '已通过' : '未通过' }}</b></div>
      </div>
      <FileEvidencePanel
        :versions="evidenceVersions.length ? evidenceVersions : files"
        :canonical-file-version-id="canonicalFileVersionId"
        :review-ready="reviewReady"
        :version-conflict="versionConflict"
      />
      <slot name="review" />
      <label class="gd-review-workspace__auto"><input :checked="autoNext" :disabled="submitting" type="checkbox" @change="emitUnlocked('update:autoNext', $event.target.checked)" /> 批阅成功后自动下一条</label>
      <div class="gd-review-workspace__summary">
        <div><span>学生</span><b>{{ currentRecord?.studentName || '—' }}</b></div>
        <div><span>班级</span><b>{{ currentRecord?.className || '—' }}</b></div>
        <div><span>指导教师</span><b>{{ currentRecord?.advisorName || '—' }}</b></div>
        <div><span>当前状态</span><b>{{ recordStatusLabel(currentRecord?.status, currentRecord?.statusLabel) }}</b></div>
        <div v-if="currentRecord?.plagiarismRate"><span>查重</span><b>{{ currentRecord.plagiarismRate }}</b></div>
      </div>
      <button type="button" class="gd-review-workspace__dossier" :disabled="submitting" @click="emitUnlocked('openStudentDossier', currentRecord)">查看学生完整档案 →</button>
    </aside>
  </div>
</template>

<script setup>
import { safeLocalizedText } from '@/utils/presentationSafety'
import AppDocumentViewer from '@/components/file/viewer/AppDocumentViewer.vue'
import FileEvidencePanel from './FileEvidencePanel.vue'

const RECORD_STATUS_LABELS = { DRAFT: '草稿', SUBMITTED: '已提交', REVIEWING: '审核中', APPROVED: '已通过', REJECTED: '已驳回', RETURNED: '已退回', ARCHIVED: '已归档', COMPLETED: '已完成' }
const recordStatusLabel = (status, providedLabel = '') => providedLabel || safeLocalizedText({ value: status, dictionary: RECORD_STATUS_LABELS, unknownLabel: '状态待确认' })

const props = defineProps({
  queue: { type: Array, default: () => [] }, currentIndex: { type: Number, default: 0 }, currentRecord: { type: Object, default: null }, detail: { type: Object, default: null },
  files: { type: Array, default: () => [] }, versions: { type: Array, default: () => [] }, evidenceVersions: { type: Array, default: () => [] }, canonicalFileVersionId: { type: [String, Number], default: null },
  reviewReady: { type: Boolean, default: false }, expectedVersion: { type: [String, Number], default: null }, comment: { type: String, default: '' }, submitting: { type: Boolean, default: false }, autoNext: { type: Boolean, default: true }, mode: { type: String, default: 'final' }, queueTitle: { type: String, default: '' },
  provider: { type: Object, default: null }, descriptor: { type: Object, default: null }, activeFileKey: { type: [String, Number], default: null }, activeVersionId: { type: [String, Number], default: null },
  versionConflict: { type: Object, default: null }, allowDownload: { type: Boolean, default: false }, narrow: { type: Boolean, default: false }
})
const emit = defineEmits(['select', 'previous', 'next', 'update:comment', 'update:autoNext', 'approve', 'reject', 'reload', 'openStudentDossier', 'select-file', 'select-version', 'download'])
const queueKey = (item, index) => String(item?.caseKey ?? item?.id ?? item?.gdStudentId ?? index)
function emitUnlocked(event, payload) {
  if (props.submitting) return
  emit(event, payload)
}
</script>

<style scoped>
.gd-review-workspace{display:grid;grid-template-columns:272px minmax(0,1fr) 340px;gap:12px;align-items:start;min-width:0;max-width:100%}.gd-review-workspace__queue,.gd-review-workspace__review{min-width:0;border:1px solid var(--border-light);border-radius:10px;background:var(--card,#fff);overflow:hidden}.gd-review-workspace__queue{position:sticky;top:12px;max-height:calc(100vh - 150px);overflow:auto}.gd-review-workspace__queue-head{display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid var(--border-light);font-size:13px}.gd-review-workspace__queue>button{width:100%;display:grid;grid-template-columns:1fr auto;gap:3px 6px;text-align:left;padding:9px 10px;border:0;border-bottom:1px solid var(--border-light);background:#fff;cursor:pointer}.gd-review-workspace__queue>button.is-active{background:var(--primary-50,#eff6ff);box-shadow:inset 3px 0 0 var(--brand-primary,#2563eb)}.gd-review-workspace__queue>button:disabled{cursor:not-allowed;opacity:.65}.gdq-name{font-weight:600}.gdq-class,.gd-review-workspace__queue small{font-size:11px;color:var(--text-tertiary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gd-review-workspace__document{min-width:0;max-width:100%;overflow:hidden}.gd-review-workspace__business-bar{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px;padding:8px 10px;border:1px solid var(--border-light);border-radius:9px;background:#fff}.gd-review-workspace__business-bar>div:first-child{display:flex;gap:8px;min-width:0}.gd-review-workspace__business-bar span{color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gd-review-workspace__nav{display:flex;gap:6px;flex:0 0 auto}.gd-review-workspace__nav button,.gd-review-workspace__dossier{border:1px solid var(--border-light);background:#fff;border-radius:7px;padding:5px 8px;cursor:pointer}.gd-review-workspace__nav button:disabled,.gd-review-workspace__dossier:disabled{cursor:not-allowed;opacity:.55}.gd-review-workspace.is-submitting .gd-review-workspace__queue{pointer-events:none}.gd-review-workspace__viewer.is-command-locked{pointer-events:none}.gd-review-workspace__lock{margin-bottom:8px;padding:9px 10px;border:1px solid var(--warning-100,#fef3c7);border-radius:8px;background:var(--warning-50,#fffbeb);color:var(--warning-800,#92400e);font-size:12px;font-weight:600}.gd-review-workspace__conflict{margin-bottom:8px;padding:9px 10px;border-radius:8px;background:#fff7ed;color:#c2410c;font-size:13px}.gd-review-workspace__empty{min-height:520px;display:grid;place-content:center;border:1px dashed var(--border-light);border-radius:10px;color:var(--text-tertiary)}.gd-review-workspace__review{position:sticky;top:12px;padding:10px;display:grid;gap:8px}.gd-review-workspace__contract{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;padding:7px;border:1px solid var(--primary-100,#dbeafe);border-radius:8px;background:var(--primary-50,#eff6ff)}.gd-review-workspace__contract div{display:grid;min-width:0;gap:2px}.gd-review-workspace__contract span{color:var(--text-tertiary);font-size:10px}.gd-review-workspace__contract b{overflow:hidden;color:var(--text-primary);font-size:12px;text-overflow:ellipsis;white-space:nowrap}.gd-review-workspace__contract b.is-ready{color:var(--success-600,#16a34a)}.gd-review-workspace__contract b.is-blocked{color:var(--warning-700,#a16207)}.gd-review-workspace__summary{display:grid;grid-template-columns:1fr 1fr;gap:7px;padding-top:2px;border-top:1px solid var(--border-light)}.gd-review-workspace__summary div{display:grid;gap:2px;min-width:0}.gd-review-workspace__summary span{font-size:11px;color:var(--text-tertiary)}.gd-review-workspace__summary b{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gd-review-workspace__auto{font-size:12px;color:var(--text-secondary)}.gd-review-workspace__dossier{width:100%}.gd-review-workspace.is-submitting{cursor:progress}.gd-review-workspace.is-narrow{grid-template-columns:1fr}.gd-review-workspace.is-narrow .gd-review-workspace__queue,.gd-review-workspace.is-narrow .gd-review-workspace__review{position:static;max-height:none}
@media(max-width:1599px){.gd-review-workspace:not(.is-narrow){grid-template-columns:220px minmax(0,1fr) 290px;gap:10px}}@media(max-width:1279px){.gd-review-workspace{grid-template-columns:1fr}.gd-review-workspace__queue,.gd-review-workspace__review{position:static;max-height:none}}
:global(.gd-page-intro:has(+ .gd-business-view .gd-review-workspace)){grid-template-columns:minmax(0,1fr) minmax(220px,.8fr);gap:8px;margin-bottom:8px;padding:7px 12px;align-items:center}:global(.gd-page-intro:has(+ .gd-business-view .gd-review-workspace) p),:global(.gd-page-intro:has(+ .gd-business-view .gd-review-workspace) .gd-page-intro__eyebrow),:global(.gd-page-intro:has(+ .gd-business-view .gd-review-workspace) .gd-page-intro__next>span),:global(.gd-page-intro:has(+ .gd-business-view .gd-review-workspace) .gd-page-intro__scope){display:none}:global(.gd-page-intro:has(+ .gd-business-view .gd-review-workspace) .gd-page-intro__next){padding-left:10px}:global(.gd-business-view:has(.gd-review-workspace)>.gd-scope-alert.app-inline-alert){display:none}:global(.gd-business-view:has(.gd-review-workspace) .mps){gap:8px}:global(.gd-business-view:has(.gd-review-workspace) .mps__head){gap:8px;align-items:center}
</style>
