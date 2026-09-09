<template>
  <AppSectionCard title="快速复制上一学期校历">
    <div class="aa-copy-toolbar">
      <label class="aa-copy-field">
        来源学期
        <AppSelect v-model="sourceTermId" :options="sourceOptions" :disabled="applying" placeholder="选择要参考的历史学期" />
      </label>
      <AppButton variant="primary" :disabled="disabled || !sourceTermId" :loading="loading" @click="loadPreview">
        预览复制结果
      </AppButton>
    </div>

    <AppInlineAlert
      v-if="disabled"
      type="info"
      description="当前学期已发布/锁定；复制校历仅用于草稿学期。"
    />
    <AppInlineAlert v-if="error" type="danger" :description="error" />

    <template v-if="preview">
      <div class="aa-copy-summary">
        <div class="aa-copy-stat"><strong>{{ preview.readyCount }}</strong><span>可直接复制</span></div>
        <div class="aa-copy-stat"><strong>{{ preview.reviewCount }}</strong><span>需人工复核</span></div>
        <div class="aa-copy-stat"><strong>{{ preview.blockedCount }}</strong><span>阻断</span></div>
        <div class="aa-copy-stat"><strong>{{ preview.targetExistingCount }}</strong><span>目标已有</span></div>
      </div>

      <AppInlineAlert
        :type="preview.blockedCount || preview.targetExistingCount ? 'warning' : 'info'"
        :description="preview.nextStep"
      />

      <div class="aa-copy-list">
        <div v-for="row in preview.items" :key="row.sourceEventId" class="aa-copy-row">
          <div class="aa-copy-row__main">
            <strong>{{ eventTypeLabel(row.eventType) }}</strong>
            <span>{{ row.startDate || '—' }}<template v-if="row.endDate && row.endDate !== row.startDate"> ~ {{ row.endDate }}</template></span>
            <span v-if="row.swapToDate">→ {{ row.swapToDate }}</span>
            <span v-if="row.remark" class="aa-copy-row__remark">{{ row.remark }}</span>
          </div>
          <StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot />
          <div v-if="row.reasons && row.reasons.length" class="aa-copy-row__reason">{{ row.reasons.join('；') }}</div>
        </div>
      </div>

      <label v-if="preview.reviewCount" class="aa-copy-confirm">
        <input v-model="reviewConfirmed" type="checkbox" />
        我已逐项核对节假日 / 调休日历，确认目标日期无误
      </label>

      <div class="aa-copy-actions">
        <AppButton variant="ghost" :disabled="applying" @click="loadPreview">重新核对</AppButton>
        <AppButton
          variant="primary"
          :loading="applying"
          :disabled="!canApply"
          @click="applyCopy"
        >
          确认复制 {{ preview.items.length }} 项
        </AppButton>
      </div>
    </template>
  </AppSectionCard>
</template>

<script>
import { StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppSectionCard, AppSelect } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { termCalendarConvenienceApi } from '@/modules/academicAffairs/api/term-calendar-convenience.api'
import { toast } from '@/utils/toast'

const EVENT_TYPES = { TEACHING: '教学', EXAM: '考试', INTERNSHIP: '实习', HOLIDAY: '节假日', SWAP: '补课日' }

export default {
  name: 'AaCalendarCopyPanel',
  components: { StatusTag, AppButton, AppInlineAlert, AppSectionCard, AppSelect },
  props: {
    terms: { type: Array, default: () => [] },
    targetTermId: { type: [String, Number], default: '' },
    disabled: { type: Boolean, default: false }
  },
  emits: ['applied', 'busy'],
  data() {
    return {
      sourceTermId: '',
      requestVersion: 0,
      preview: null,
      loading: false,
      applying: false,
      reviewConfirmed: false,
      error: ''
    }
  },
  computed: {
    sourceOptions() {
      return this.terms
        .filter((term) => String(term.termId) !== String(this.targetTermId))
        .map((term) => ({
          value: term.termId,
          label: term.termName || `${term.yearCode} 第 ${term.termNo} 学期`
        }))
    },
    canApply() {
      if (!this.preview || this.applying || this.disabled) return false
      if (!this.preview.canConfirm || this.preview.blockedCount || this.preview.targetExistingCount) return false
      return !this.preview.reviewCount || this.reviewConfirmed
    }
  },
  watch: {
    sourceTermId() { this.invalidatePreview() },
    targetTermId: {
      immediate: true,
      handler() {
        this.invalidatePreview()
        if (!this.sourceOptions.some((item) => String(item.value) === String(this.sourceTermId))) {
          this.sourceTermId = this.sourceOptions[0]?.value || ''
        }
      }
    }
  },
  beforeUnmount() { this.requestVersion++ },
  methods: {
    invalidatePreview() { this.requestVersion++; this.preview = null; this.reviewConfirmed = false; this.error = ''; this.loading = false },
    eventTypeLabel(type) { return EVENT_TYPES[type] || (type ? '类型待确认' : '—') },
    statusLabel(status) { return { READY: '可复制', REVIEW: '需复核', BLOCKED: '阻断' }[status] || (status ? '状态待确认' : '—') },
    statusTone(status) { return { READY: 'success', REVIEW: 'warning', BLOCKED: 'danger' }[status] || 'default' },
    async loadPreview() {
      if (!this.targetTermId || !this.sourceTermId || this.loading || this.applying || this.disabled) return
      const version = ++this.requestVersion
      this.preview = null
      this.loading = true
      this.error = ''
      this.reviewConfirmed = false
      const res = await termCalendarConvenienceApi.previewCalendarCopy(this.targetTermId, this.sourceTermId)
      if (version !== this.requestVersion) return
      this.loading = false
      if (res.code === 0) {
        this.preview = res.data
      } else {
        this.preview = null
        this.error = res.message || '复制预览失败'
      }
    },
    async applyCopy() {
      if (!this.canApply) return
      this.applying = true
      this.$emit('busy', true)
      this.error = ''
      const targetTermId = this.targetTermId
      const items = this.preview.items
      let applied = 0
      for (const row of items) {
        if (!['READY', 'REVIEW'].includes(row.status)) continue
        const body = {
          eventType: row.eventType,
          startDate: row.startDate,
          endDate: row.eventType === 'SWAP' ? undefined : (row.endDate || row.startDate),
          swapToDate: row.eventType === 'SWAP' ? row.swapToDate : undefined,
          remark: row.remark || undefined
        }
        const res = await academicAffairsApi.addCalendarEvent(targetTermId, body)
        if (res.code !== 0) {
          this.error = `已复制 ${applied} 项；第 ${applied + 1} 项未能复制：${res.message || '发生冲突'}。请重新核对目标校历，已复制的安排无需重复添加。`
          this.preview = null
          this.applying = false
          this.$emit('busy', false)
          this.$emit('applied', { applied, partial: true })
          return
        }
        applied += 1
      }
      this.applying = false
      this.$emit('busy', false)
      toast.success(`已复制 ${applied} 项校历事件`)
      this.$emit('applied', { applied, partial: false })
      this.preview = null
      this.reviewConfirmed = false
    }
  }
}
</script>

<style scoped>
.aa-copy-toolbar { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; }
.aa-copy-field { min-width: 280px; display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-copy-summary { display: grid; grid-template-columns: repeat(4, minmax(110px, 1fr)); gap: 10px; margin: 14px 0; }
.aa-copy-stat { padding: 12px; border: 1px solid var(--border-100, #eef0f3); border-radius: 10px; background: var(--bg-50, #fafbfc); display: flex; flex-direction: column; gap: 4px; }
.aa-copy-stat strong { font-size: 20px; }
.aa-copy-stat span { font-size: 12px; color: var(--text-500, #646a73); }
.aa-copy-list { display: flex; flex-direction: column; gap: 8px; margin: 14px 0; max-height: 360px; overflow: auto; }
.aa-copy-row { padding: 10px 12px; border: 1px solid var(--border-100, #eef0f3); border-radius: 8px; }
.aa-copy-row__main { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; font-size: 13px; }
.aa-copy-row__remark { color: var(--text-500, #646a73); }
.aa-copy-row__reason { margin-top: 6px; font-size: 12px; color: var(--warning-700, #b54708); }
.aa-copy-confirm { display: flex; align-items: flex-start; gap: 8px; margin: 12px 0; font-size: 13px; }
.aa-copy-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 12px; }
@media (max-width: 900px) { .aa-copy-summary { grid-template-columns: repeat(2, minmax(110px, 1fr)); } }
</style>
