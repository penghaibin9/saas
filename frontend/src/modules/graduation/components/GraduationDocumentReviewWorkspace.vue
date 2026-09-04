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
        正在提交当前审核结论；学生、记录、业务版本与文件版本已锁定。
      </div>
      <div v-if="versionConflict" class="gd-review-workspace__conflict">
        学生已提交新版本。当前阅读内容保持不动，批阅按钮已锁定；请切换最新版本后重新核验。
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
        <div><span>提交版本</span><b>{{ expectedVersion ?? '—' }}</b></div>
        <div><span>文件版本</span><b>{{ canonicalFileVersionId ?? '—' }}</b></div>
        <div><span>文件状态</span><b :class="reviewReady && !versionConflict ? 'is-ready' : 'is-blocked'">{{ reviewReady && !versionConflict ? '可以批阅' : '暂不可批阅' }}</b></div>
      </div>

      <details class="gd-review-workspace__evidence">
        <summary>文件证据与历史版本</summary>
        <FileEvidencePanel
          :versions="evidenceVersions.length ? evidenceVersions : files"
          :canonical-file-version-id="canonicalFileVersionId"
          :review-ready="reviewReady"
          :version-conflict="versionConflict"
        />
      </details>

      <slot name="review" />

      <label class="gd-review-workspace__auto">
        <input :checked="autoNext" :disabled="submitting" type="checkbox" @change="emitUnlocked('update:autoNext', $event.target.checked)" />
        批阅成功后自动下一条
      </label>

      <details class="gd-review-workspace__subject">
        <summary>当前学生与业务状态</summary>
        <div class="gd-review-workspace__summary">
          <div><span>学生</span><b>{{ currentRecord?.studentName || '—' }}</b></div>
          <div><span>班级</span><b>{{ currentRecord?.className || '—' }}</b></div>
          <div><span>指导教师</span><b>{{ currentRecord?.advisorName || '—' }}</b></div>
          <div><span>当前状态</span><b>{{ recordStatusLabel(currentRecord?.status, currentRecord?.statusLabel) }}</b></div>
          <div v-if="currentRecord?.plagiarismRate"><span>查重</span><b>{{ currentRecord.plagiarismRate }}</b></div>
        </div>
        <button type="button" class="gd-review-workspace__dossier" :disabled="submitting" @click="emitUnlocked('openStudentDossier', currentRecord)">查看学生完整档案 →</button>
      </details>
    </aside>
  </div>
</template>

<script setup>
import { safeLocalizedText } from '@/utils/presentationSafety'
import AppDocumentViewer from '@/components/file/viewer/AppDocumentViewer.vue'
import FileEvidencePanel from './FileEvidencePanel.vue'

const RECORD_STATUS_LABELS = {
  DRAFT: '草稿', SUBMITTED: '已提交', REVIEWING: '审核中', APPROVED: '已通过',
  REJECTED: '已驳回', RETURNED: '已退回', ARCHIVED: '已归档', COMPLETED: '已完成'
}
const recordStatusLabel = (status, providedLabel = '') => providedLabel || safeLocalizedText({ value: status, dictionary: RECORD_STATUS_LABELS, unknownLabel: '状态待确认' })

const props = defineProps({
  queue: { type: Array, default: () => [] },
  currentIndex: { type: Number, default: 0 },
  currentRecord: { type: Object, default: null },
  detail: { type: Object, default: null },
  files: { type: Array, default: () => [] },
  versions: { type: Array, default: () => [] },
  evidenceVersions: { type: Array, default: () => [] },
  canonicalFileVersionId: { type: [String, Number], default: null },
  reviewReady: { type: Boolean, default: false },
  expectedVersion: { type: [String, Number], default: null },
  comment: { type: String, default: '' },
  submitting: { type: Boolean, default: false },
  autoNext: { type: Boolean, default: true },
  mode: { type: String, default: 'final' },
  queueTitle: { type: String, default: '' },
  provider: { type: Object, default: null },
  descriptor: { type: Object, default: null },
  activeFileKey: { type: [String, Number], default: null },
  activeVersionId: { type: [String, Number], default: null },
  versionConflict: { type: Object, default: null },
  allowDownload: { type: Boolean, default: false },
  narrow: { type: Boolean, default: false }
})
const emit = defineEmits(['select', 'previous', 'next', 'update:comment', 'update:autoNext', 'approve', 'reject', 'reload', 'openStudentDossier', 'select-file', 'select-version', 'download'])
const queueKey = (item, index) => String(item?.caseKey ?? item?.id ?? item?.gdStudentId ?? index)
function emitUnlocked(event, payload) {
  if (props.submitting) return
  emit(event, payload)
}
</script>

<style scoped>
.gd-review-workspace{display:grid;grid-template-columns:250px minmax(0,1fr) 318px;gap:10px;align-items:start;min-width:0;max-width:100%}.gd-review-workspace__queue,.gd-review-workspace__review{min-width:0;border:1px solid var(--border-light);border-radius:10px;background:var(--card,#fff);overflow:hidden}.gd-review-workspace__queue{position:sticky;top:10px;max-height:calc(100vh - 132px);overflow:auto}.gd-review-workspace__queue-head{display:flex;justify-content:space-between;padding:9px;border-bottom:1px solid var(--border-light);font-size:12px}.gd-review-workspace__queue>button{width:100%;display:grid;grid-template-columns:1fr auto;gap:2px 5px;text-align:left;padding:8px 9px;border:0;border-bottom:1px solid var(--border-light);background:#fff;cursor:pointer}.gd-review-workspace__queue>button.is-active{background:var(--primary-50,#eff6ff);box-shadow:inset 3px 0 0 var(--brand-primary,#2563eb)}.gd-review-workspace__queue>button:disabled{cursor:not-allowed;opacity:.65}.gdq-name{font-weight:600}.gdq-class,.gd-review-workspace__queue small{font-size:10px;color:var(--text-tertiary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gd-review-workspace__document{min-width:0;max-width:100%;overflow:hidden}.gd-review-workspace__business-bar{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:6px;padding:7px 9px;border:1px solid var(--border-light);border-radius:9px;background:#fff}.gd-review-workspace__business-bar>div:first-child{display:flex;gap:7px;min-width:0}.gd-review-workspace__business-bar span{color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gd-review-workspace__nav{display:flex;gap:5px;flex:0 0 auto}.gd-review-workspace__nav button,.gd-review-workspace__dossier{border:1px solid var(--border-light);background:#fff;border-radius:7px;padding:5px 7px;cursor:pointer}.gd-review-workspace__nav button:disabled,.gd-review-workspace__dossier:disabled{cursor:not-allowed;opacity:.55}.gd-review-workspace.is-submitting .gd-review-workspace__queue{pointer-events:none}.gd-review-workspace__viewer.is-command-locked{pointer-events:none}.gd-review-workspace__lock,.gd-review-workspace__conflict{margin-bottom:6px;padding:8px 9px;border-radius:8px;font-size:11px;font-weight:600}.gd-review-workspace__lock{border:1px solid var(--warning-100,#fef3c7);background:var(--warning-50,#fffbeb);color:var(--warning-800,#92400e)}.gd-review-workspace__conflict{background:#fff7ed;color:#c2410c}.gd-review-workspace__empty{min-height:500px;display:grid;place-content:center;border:1px dashed var(--border-light);border-radius:10px;color:var(--text-tertiary)}.gd-review-workspace__review{position:sticky;top:10px;padding:9px;display:grid;gap:7px;max-height:calc(100vh - 132px);overflow:auto}.gd-review-workspace__contract{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;padding:6px;border:1px solid var(--primary-100,#dbeafe);border-radius:8px;background:var(--primary-50,#eff6ff)}.gd-review-workspace__contract div{display:grid;min-width:0;gap:1px}.gd-review-workspace__contract span{color:var(--text-tertiary);font-size:9px}.gd-review-workspace__contract b{overflow:hidden;color:var(--text-primary);font-size:11px;text-overflow:ellipsis;white-space:nowrap}.gd-review-workspace__contract b.is-ready{color:var(--success-600,#16a34a)}.gd-review-workspace__contract b.is-blocked{color:var(--warning-700,#a16207)}.gd-review-workspace__evidence,.gd-review-workspace__subject{border:1px solid var(--border-light);border-radius:8px;background:var(--gray-50,#f8fafc)}.gd-review-workspace__evidence>summary,.gd-review-workspace__subject>summary{padding:7px 8px;cursor:pointer;color:var(--text-secondary);font-size:10px;font-weight:650}.gd-review-workspace__evidence[open]>summary,.gd-review-workspace__subject[open]>summary{border-bottom:1px solid var(--border-light)}.gd-review-workspace__evidence :deep(.file-evidence-panel){border:0;border-radius:0;background:#fff}.gd-review-workspace__summary{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:8px}.gd-review-workspace__summary div{display:grid;gap:1px;min-width:0}.gd-review-workspace__summary span{font-size:9px;color:var(--text-tertiary)}.gd-review-workspace__summary b{font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gd-review-workspace__auto{font-size:11px;color:var(--text-secondary)}.gd-review-workspace__dossier{width:calc(100% - 16px);margin:0 8px 8px}.gd-review-workspace.is-submitting{cursor:progress}.gd-review-workspace.is-narrow{grid-template-columns:1fr}.gd-review-workspace.is-narrow .gd-review-workspace__queue,.gd-review-workspace.is-narrow .gd-review-workspace__review{position:static;max-height:none}
@media(max-width:1599px){.gd-review-workspace:not(.is-narrow){grid-template-columns:205px minmax(0,1fr) 280px;gap:8px}}@media(max-width:1279px){.gd-review-workspace{grid-template-columns:1fr}.gd-review-workspace__queue,.gd-review-workspace__review{position:static;max-height:none}}
:global(.gd-business-view:has(.gd-review-workspace)>.gd-scope-alert.app-inline-alert){display:none}:global(.gd-business-view:has(.gd-review-workspace) .mps){gap:8px}:global(.gd-business-view:has(.gd-review-workspace) .mps__head){gap:8px;align-items:center}
</style>
