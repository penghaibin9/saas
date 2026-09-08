<template>
  <div class="gd-review-workspace" :class="{ 'is-narrow': narrow, 'is-submitting': submitting }" :aria-busy="submitting ? 'true' : 'false'">
    <aside class="gd-review-workspace__queue" :aria-label="queueTitle || (mode === 'proposal' ? '开题队列' : '成果队列')">
      <div class="gd-review-workspace__queue-head">
        <strong>{{ queueTitle || (mode === 'proposal' ? '开题队列' : '成果队列') }}</strong>
        <span>{{ queue.length ? currentIndex + 1 : 0 }} / {{ queue.length }}</span>
      </div>
      <button
        v-for="(item, index) in queue"
        :key="queueKey(item, index)"
        type="button"
        :class="{ 'is-active': index === currentIndex }"
        :aria-current="index === currentIndex ? 'true' : undefined"
        :aria-label="`${item.studentName || '学生'} · ${item.topicTitle || '未填写课题'} · ${recordStatusLabel(item.status, item.statusLabel)}`"
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
      <div class="gd-review-workspace__business-bar" aria-live="polite">
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
        正在提交当前审核结论，暂不能切换学生或材料。
      </div>
      <div v-if="versionConflict" class="gd-review-workspace__conflict" role="alert">
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
      <div v-else class="gd-review-workspace__empty" role="status">当前材料尚不能在线查看，请确认文件已上传并完成安全检查。</div>
    </main>

    <aside class="gd-review-workspace__review" aria-label="当前材料批阅">
      <div
        class="gd-review-workspace__contract"
        data-testid="review-command-contract"
        :data-material-version="expectedVersion ?? ''"
        :data-file-version-id="canonicalFileVersionId ?? ''"
      >
        <div><span>提交版次</span><b>{{ expectedVersion != null ? `第 ${expectedVersion} 版` : '待确认' }}</b></div>
        <div><span>文件核对</span><b>{{ canonicalFileVersionId != null ? '已绑定当前文件' : '尚未绑定' }}</b></div>
        <div><span>批阅状态</span><b :class="reviewReady && !versionConflict ? 'is-ready' : 'is-blocked'">{{ reviewReady && !versionConflict ? '可以批阅' : '暂不可批阅' }}</b></div>
      </div>

      <details class="gd-review-workspace__evidence">
        <summary>文件检查与历史版本</summary>
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
/* Only Graduation-owned content containers opt in; the shared shell is untouched. */
:global(.gd-business-view .fr-workbench-stack),
:global(.gd-business-view .prc),
:global(.gd-business-view .w74-center) { container: gd-review / inline-size; min-width: 0; }
:global(.gd-business-view .pr-page) { container: gd-proposal / inline-size; }
.gd-review-workspace {
  display: grid;
  grid-template-columns:250px minmax(0,1fr) 318px;
  gap: 12px;
  align-items: start;
  min-width: 0;
  max-width: 100%;
  color: var(--text-primary, #10233f);
  font-size: 13px;
  line-height: 1.5;
}
.gd-review-workspace__queue, .gd-review-workspace__review { min-width: 0; border: 1px solid var(--border-light, #dce6f1); border-radius: 12px; background: var(--card, #fff); }
.gd-review-workspace__queue { position: sticky; top: 12px; max-height: calc(100vh - 160px); overflow: auto; scrollbar-width: thin; }
.gd-review-workspace__queue-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 12px; border-bottom: 1px solid var(--border-light, #dce6f1); font-size: 13px; }
.gd-review-workspace__queue-head span { flex-shrink: 0; font-size: 12px; color: var(--text-tertiary, #75879d); }
.gd-review-workspace__queue > button { width: 100%; min-height: 76px; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 8px; text-align: left; padding: 12px; border: 0; border-bottom: 1px solid var(--border-light, #dce6f1); background: var(--card, #fff); color: var(--text-primary, #10233f); font: inherit; cursor: pointer; }
.gd-review-workspace__queue > button:hover { background: var(--bg-hover, #eff6ff); }
.gd-review-workspace__queue > button.is-active { background: var(--pri-bg, #eff6ff); box-shadow: inset 3px 0 0 var(--pri, #2563eb); }
.gd-review-workspace__queue > button:focus-visible { outline: 2px solid var(--pri, #2563eb); outline-offset: -3px; }
.gd-review-workspace__queue > button:disabled { cursor: not-allowed; opacity: .65; }
.gdq-name { font-size: 14px; font-weight: 650; }
.gdq-class, .gd-review-workspace__queue small { font-size: 12px; color: var(--text-tertiary, #75879d); white-space: normal; overflow-wrap: anywhere; }
.gd-review-workspace__queue small { grid-column: 1 / -1; }
.gd-review-workspace__document { min-width: 0; max-width: 100%; }
.gd-review-workspace__business-bar { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px 12px; align-items: center; margin-bottom: 10px; padding: 10px 12px; border: 1px solid var(--border-light, #dce6f1); border-radius: 10px; background: var(--card, #fff); }
.gd-review-workspace__business-bar > div:first-child { display: grid; gap: 4px; min-width: 0; flex: 1 1 160px; }
.gd-review-workspace__business-bar strong { font-size: 15px; }
.gd-review-workspace__business-bar span { color: var(--text-secondary, #3f5878); font-size: 13px; overflow-wrap: anywhere; }
.gd-review-workspace__nav { display: flex; flex-wrap: wrap; gap: 8px; flex: 0 0 auto; }
.gd-review-workspace__nav button, .gd-review-workspace__dossier { min-height: 34px; border: 1px solid var(--border-light, #dce6f1); background: var(--card, #fff); color: var(--pri, #2563eb); border-radius: 8px; padding: 6px 10px; font: inherit; cursor: pointer; }
.gd-review-workspace__nav button:disabled, .gd-review-workspace__dossier:disabled { cursor: not-allowed; opacity: .55; }
.gd-review-workspace.is-submitting .gd-review-workspace__queue{pointer-events:none}
.gd-review-workspace__viewer.is-command-locked { pointer-events: none; }
.gd-review-workspace__lock, .gd-review-workspace__conflict { margin-bottom: 10px; padding: 10px 12px; border-radius: 10px; font-size: 13px; line-height: 1.6; font-weight: 600; overflow-wrap: anywhere; }
.gd-review-workspace__lock { border: 1px solid var(--warning-100, #fef3c7); background: var(--warning-50, #fffbeb); color: var(--warning-800, #92400e); }
.gd-review-workspace__conflict { border: 1px solid #fed7aa; background: #fff7ed; color: #9a3412; }
.gd-review-workspace__empty { min-height: 360px; display: grid; place-content: center; border: 1px dashed var(--border-light, #dce6f1); border-radius: 12px; background: var(--bg-subtle, #f8fafc); color: var(--text-tertiary, #75879d); text-align: center; padding: 20px; font-size: 13px; }
.gd-review-workspace__review { position: sticky; top: 12px; padding: 12px; display: grid; gap: 12px; max-height: calc(100vh - 160px); overflow: auto; scrollbar-width: thin; }
.gd-review-workspace__contract { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; padding: 10px; border: 1px solid var(--primary-100, #dbeafe); border-radius: 10px; background: var(--pri-bg, #eff6ff); }
.gd-review-workspace__contract div { display: grid; min-width: 0; align-content: start; gap: 4px; }
.gd-review-workspace__contract > div:last-child { grid-column: 1 / -1; display: flex; align-items: baseline; gap: 10px; }
.gd-review-workspace__contract span { color: var(--text-tertiary, #75879d); font-size: 12px; }
.gd-review-workspace__contract b { color: var(--text-primary, #10233f); font-size: 13px; white-space: normal; overflow-wrap: anywhere; }
.gd-review-workspace__contract b.is-ready { color: var(--text-primary, #10233f); border-left: 3px solid #16a34a; padding-left: 6px; }
.gd-review-workspace__contract b.is-blocked { color: var(--text-primary, #10233f); border-left: 3px solid #d97706; padding-left: 6px; }
.gd-review-workspace__evidence, .gd-review-workspace__subject { border: 1px solid var(--border-light, #dce6f1); border-radius: 10px; background: var(--bg-subtle, #f8fafc); }
.gd-review-workspace__evidence > summary, .gd-review-workspace__subject > summary { min-height: 36px; padding: 8px 10px; cursor: pointer; color: var(--text-secondary, #3f5878); font-size: 13px; font-weight: 600; }
.gd-review-workspace__evidence[open] > summary, .gd-review-workspace__subject[open] > summary { border-bottom: 1px solid var(--border-light, #dce6f1); }
.gd-review-workspace__evidence :deep(.file-evidence-panel) { border: 0; border-radius: 0; background: var(--card, #fff); }
.gd-review-workspace__summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; padding: 10px; }
.gd-review-workspace__summary div { display: grid; gap: 4px; min-width: 0; }
.gd-review-workspace__summary span { font-size: 12px; color: var(--text-tertiary, #75879d); }
.gd-review-workspace__summary b { font-size: 13px; white-space: normal; overflow-wrap: anywhere; }
.gd-review-workspace__auto { display: flex; align-items: center; gap: 8px; min-height: 34px; font-size: 13px; color: var(--text-secondary, #3f5878); cursor: pointer; }
.gd-review-workspace__auto input { width: 16px; height: 16px; accent-color: var(--pri, #2563eb); }
.gd-review-workspace__dossier { width: calc(100% - 20px); margin: 0 10px 10px; }
.gd-review-workspace__review :deep(.mp-note) { font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.gd-review-workspace__review :deep(.mp-textarea) { min-height: 120px; padding: 10px 12px; border: 1px solid var(--border-base, #cbd8e8); border-radius: 10px; background: var(--field-bg, #fff); color: var(--text-primary, #10233f); font-size: 13px; line-height: 1.65; resize: vertical; }
.gd-review-workspace__review :deep(button) { min-height: 34px; font-size: 13px; }
.gd-review-workspace__nav button:focus-visible, .gd-review-workspace__review :deep(button:focus-visible), .gd-review-workspace__review :deep(textarea:focus-visible), .gd-review-workspace__review summary:focus-visible { outline: 2px solid var(--pri, #2563eb); outline-offset: 2px; }
.gd-review-workspace.is-submitting { cursor: progress; }
.gd-review-workspace.is-narrow{grid-template-columns:1fr}
.gd-review-workspace.is-narrow .gd-review-workspace__queue, .gd-review-workspace.is-narrow .gd-review-workspace__review { position: static; max-height: none; }
/* Adapt the existing lists, not another menu, route or review engine. */
:global(.gd-business-view .pr-page .pr-list) { flex-basis: 260px; width: 260px; min-width: 0; box-shadow: none; }
:global(.gd-business-view .pr-page .pr-row__main) { flex-wrap: wrap; }
:global(.gd-business-view .pr-page .pr-row__name) { font-size: 14px; }
:global(.gd-business-view .pr-page .pr-row__cls),
:global(.gd-business-view .pr-page .pr-row__sub),
:global(.gd-business-view .pr-page .pr-row__meta) { font-size: 12px; }
:global(.gd-business-view .pr-page .pr-hero) { padding: 12px 14px; box-shadow: none; background: var(--card, #fff); }
:global(.gd-business-view .pr-page .pr-hero__metrics div) { background: var(--bg-subtle, #f8fafc); }
:global(.gd-business-view .pr-page .pr-hero__copy p) { font-size: 13px; }
:global(.gd-business-view .pr-page .pr-subject__identity > span) { font-size: 12px; }
:global(.gd-business-view .pr-page .pr-subject__identity small) { white-space: normal; overflow-wrap: anywhere; }
:global(.gd-business-view .pr-page .pr-pane__nav .mp-link),
:global(.gd-business-view .pr-page .mp-tabs .mp-tab),
:global(.gd-business-view .fr-workbench-stack .mp-tabs .mp-tab) { min-height: 34px; font-size: 13px; }
:global(.gd-business-view .fr-workbench-stack .fr-command) { padding: 12px 14px; border-radius: 12px; background: var(--card, #fff); }
:global(.gd-business-view .fr-workbench-stack .fr-command__copy strong) { font-size: 16px; line-height: 1.5; white-space: normal; overflow-wrap: anywhere; }
:global(.gd-business-view .fr-workbench-stack .fr-command__copy > span),
:global(.gd-business-view .fr-workbench-stack .fr-command__counts > span),
:global(.gd-business-view .fr-workbench-stack .fr-selected-summary) { font-size: 12px; }
:global(.gd-business-view .fr-workbench-stack .fr-command__counts b) { font-size: 20px; }
:global(.gd-business-view .fr-workbench-stack .fr-command__counts > span) { background: var(--bg-subtle, #f8fafc); }
:global(.gd-business-view .fr-workbench-stack .fr-selected-summary) { white-space: normal; overflow-wrap: anywhere; }
/* Narrow content keeps the queue compact while document and decision stay together. */
@container gd-review (max-width: 1179px) {
  :global(.gd-business-view .fr-workbench-stack .fr-command) { grid-template-columns: 1fr; }
  :global(.gd-business-view .fr-workbench-stack .fr-command__counts) { flex-wrap: wrap; }
  :global(.gd-business-view .fr-workbench-stack .fr-filter-row) { flex-wrap: wrap; }
  .gd-review-workspace:not(.is-narrow) { grid-template-columns: minmax(0, 1fr) 310px; grid-template-areas: 'queue queue' 'document review'; }
  .gd-review-workspace:not(.is-narrow) > .gd-review-workspace__queue { grid-area: queue; position: static; max-height: 180px; display: flex; flex-wrap: wrap; }
  .gd-review-workspace:not(.is-narrow) > .gd-review-workspace__queue > .gd-review-workspace__queue-head { flex: 1 0 100%; box-sizing: border-box; }
  .gd-review-workspace:not(.is-narrow) > .gd-review-workspace__queue > button { flex: 1 0 220px; width: auto; }
  .gd-review-workspace:not(.is-narrow) > .gd-review-workspace__queue :deep(.fr-list__foot),
  .gd-review-workspace:not(.is-narrow) > .gd-review-workspace__queue :deep(.w74-pagination) { flex: 1 0 100%; }
  .gd-review-workspace:not(.is-narrow) > .gd-review-workspace__document { grid-area: document; }
  .gd-review-workspace:not(.is-narrow) > .gd-review-workspace__review { grid-area: review; }
}
@container gd-review (max-width: 740px) {
  .gd-review-workspace:not(.is-narrow) { grid-template-columns: minmax(0, 1fr); grid-template-areas: 'queue' 'document' 'review'; }
  .gd-review-workspace:not(.is-narrow) > .gd-review-workspace__review { position: static; max-height: none; }
  /* Proposal's outer queue/identity remain unique; only its internal columns change. */
  :global(.gd-business-view .pr-pane .prc.is-compact .gd-review-workspace.is-narrow) { grid-template-columns: minmax(0, 1fr) !important; }
  :global(.gd-business-view .pr-pane .prc.is-compact .gd-review-workspace__review) { position: static; max-height: none; overflow: visible; }
}
@container gd-proposal (max-width: 1050px) {
  :global(.gd-business-view .pr-page .pr-list) { flex-basis: 220px; width: 220px; }
  :global(.gd-business-view .pr-page .pr-subject) { grid-template-columns: 1fr; }
  :global(.gd-business-view .pr-page .pr-subject__facts) { justify-content: flex-start; }
}
:global(.gd-business-view .pr-page .pr-split.is-narrow .pr-list) { flex-basis: auto; width: 100%; }
@supports not (container-type: inline-size) {
  @media(max-width:1599px) { .gd-review-workspace:not(.is-narrow) { grid-template-columns:205px minmax(0,1fr) 280px; } }
  @media(max-width:1279px) { .gd-review-workspace:not(.is-narrow) { grid-template-columns: 1fr; } .gd-review-workspace__queue, .gd-review-workspace__review { position: static; max-height: none; } }
}
/* Never hide the parent's permission, scope or real-message notices to save space. */
</style>
