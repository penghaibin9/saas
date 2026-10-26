<template>
  <AppSectionCard title="标准作息模板">
    <div class="aa-template-toolbar">
      <div class="aa-template-choice">
        <AppButton :variant="templateKey === 'STANDARD_8' ? 'primary' : 'ghost'" :disabled="disabled || busy" @click="choose('STANDARD_8')">标准 8 节</AppButton>
        <AppButton :variant="templateKey === 'STANDARD_10' ? 'primary' : 'ghost'" :disabled="disabled || busy" @click="choose('STANDARD_10')">标准 10 节</AppButton>
      </div>
      <AppButton variant="primary" :loading="loading" :disabled="disabled || applying" @click="loadPreview">检查当前作息</AppButton>
    </div>

    <p class="aa-template-note">模板只提供候选，不覆盖现有节次；确认时仅创建“可新增”项，每一项仍会经过节次序号与时间重叠校验。</p>
    <AppInlineAlert v-if="writeOutcome" type="danger" :description="writeOutcome" />
    <AppInlineAlert v-if="error" type="danger" :description="error" />

    <template v-if="preview">
      <div class="aa-template-summary">
        <span><strong>{{ preview.readyCount }}</strong> 可新增</span>
        <span><strong>{{ preview.existingCount }}</strong> 已存在</span>
        <span><strong>{{ preview.blockedCount }}</strong> 冲突</span>
      </div>
      <AppInlineAlert :type="preview.blockedCount ? 'warning' : 'info'" :description="preview.nextStep" />

      <div class="aa-template-grid">
        <article v-for="row in preview.items" :key="row.desired.slotNo" class="aa-template-item">
          <div>
            <strong>第 {{ row.desired.slotNo }} 节</strong>
            <span>{{ row.desired.startTime }}–{{ row.desired.endTime }}</span>
          </div>
          <StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot />
          <p v-if="row.reason">{{ row.reason }}</p>
        </article>
      </div>

      <div class="aa-template-actions">
        <AppButton variant="ghost" :disabled="disabled || busy" @click="loadPreview">刷新权威预览</AppButton>
        <AppButton variant="primary" :loading="applying" :disabled="!canApply" @click="applyTemplate">
          创建 {{ preview.readyCount }} 个缺失节次
        </AppButton>
      </div>
    </template>
  </AppSectionCard>
</template>

<script>
import { StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppSectionCard } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { termCalendarConvenienceApi } from '@/modules/academicAffairs/api/term-calendar-convenience.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTimeSlotTemplatePanel',
  components: { StatusTag, AppButton, AppInlineAlert, AppSectionCard },
  props: { disabled: { type: Boolean, default: false }, ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  emits: ['applied', 'busy'],
  data() {
    return {
      templateKey: 'STANDARD_8',
      preview: null,
      loading: false,
      applying: false,
      error: '',
      writeOutcome: '',
      requestEpoch: 0,
      disposed: false,
      previewContext: ''
    }
  },
  computed: {
    contextKey() { return JSON.stringify([this.ctx, this.academicFlow?.identity?.() || '']) },
    busy() { return this.loading || this.applying },
    canApply() {
      return !this.disabled && !this.busy && !this.disposed && this.previewContext === this.contextKey && !!this.preview && !this.preview.blockedCount && this.preview.readyCount > 0
    }
  },
  watch: {
    contextKey() { this.invalidatePreview() },
    busy: { immediate: true, flush: 'sync', handler(value) { this.$emit('busy', value) } }
  },
  beforeUnmount() { this.disposed = true; this.invalidatePreview(); this.$emit('busy', false) },
  methods: {
    invalidatePreview() {
      this.requestEpoch++
      this.preview = null
      this.previewContext = ''
      this.loading = false
      this.applying = false
      this.error = ''
      this.writeOutcome = ''
    },
    beginRequest() {
      const epoch = ++this.requestEpoch, context = this.contextKey, key = this.templateKey
      return () => !this.disposed && epoch === this.requestEpoch && context === this.contextKey && key === this.templateKey
    },
    statusLabel(status) { return { READY: '可新增', EXISTS: '已存在', BLOCKED: '冲突' }[status] || (status ? '状态待确认' : '—') },
    statusTone(status) { return { READY: 'success', EXISTS: 'default', BLOCKED: 'danger' }[status] || 'default' },
    choose(key) {
      if (this.disabled || this.busy || this.disposed || !['STANDARD_8', 'STANDARD_10'].includes(key)) return
      this.invalidatePreview()
      this.templateKey = key
    },
    async loadPreview(options = {}) {
      if (this.disabled || this.busy || this.disposed) return
      const current = this.beginRequest()
      this.loading = true
      this.error = ''
      if (options?.preserveWriteOutcome !== true) this.writeOutcome = ''
      try {
        const res = await termCalendarConvenienceApi.previewTimeSlotTemplate(this.templateKey)
        if (!current()) return
        if (res.code === 0) {
          this.preview = res.data
          this.previewContext = this.contextKey
        } else {
          this.preview = null
          this.previewContext = ''
          this.error = res.message || '作息模板预览失败'
        }
      } catch {
        if (current()) { this.preview = null; this.previewContext = ''; this.error = '作息模板预览失败，请重试' }
      } finally { if (current()) this.loading = false }
    },
    validTemplateAcknowledgement(data, desired) {
      if (!data || typeof data !== 'object' || Array.isArray(data)) return false
      if (typeof data.slotId !== 'string' || !data.slotId.trim() || !Number.isInteger(data.version) || data.version < 0) return false
      if (!['ENABLED', 'DISABLED'].includes(data.status) || typeof data.enabled !== 'boolean' || typeof data.campusCode !== 'string') return false
      return Number.isInteger(data.slotNo) && data.slotNo === desired.slotNo && ['slotName', 'startTime', 'endTime'].every(key => typeof data[key] === 'string' && data[key] === (desired[key] || ''))
    },
    async applyTemplate() {
      if (!this.canApply) return
      const current = this.beginRequest()
      this.applying = true
      this.error = ''
      this.writeOutcome = ''
      let applied = 0
      try {
        for (const row of this.preview.items) {
          if (!current()) return
          if (row.status !== 'READY') continue
          const res = await academicAffairsApi.createTimeSlot(row.desired)
          if (!current()) return
          if (res.code !== 0 || !this.validTemplateAcknowledgement(res.data, row.desired)) {
            const unknown = res.code === 0 || (res.code === 503002 && (res.httpStatus === undefined || res.httpStatus === null))
            this.writeOutcome = unknown
              ? `已成功创建 ${applied} 项（仅计已收到成功回执的项目）；后续节次的创建结果尚未确认。请核对权威作息与操作记录，不要自动重发；已保留模板选择。`
              : `已成功创建 ${applied} 项；后续节次被系统拒绝：${res.message || '发生冲突'}。已保留模板选择，请刷新预览后再确认。`
            this.applying = false
            this.$emit('applied', { applied, partial: true })
            await this.loadPreview({ preserveWriteOutcome: true })
            return
          }
          applied += 1
        }
        this.applying = false
        toast.success(`已创建 ${applied} 个缺失节次`)
        this.$emit('applied', { applied, partial: false })
        await this.loadPreview()
      } finally { if (current()) this.applying = false }
    }
  }
}
</script>

<style scoped>
.aa-template-toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; align-items: center; }
.aa-template-choice { display: flex; gap: 8px; }
.aa-template-note { margin: 10px 0; color: var(--text-500, #646a73); font-size: 13px; line-height: 1.6; }
.aa-template-summary { display: flex; gap: 18px; margin: 12px 0; font-size: 13px; }
.aa-template-summary strong { font-size: 18px; margin-right: 4px; }
.aa-template-grid { display: grid; grid-template-columns: repeat(2, minmax(240px, 1fr)); gap: 10px; margin: 14px 0; }
.aa-template-item { border: 1px solid var(--border-100, #eef0f3); border-radius: 8px; padding: 10px 12px; }
.aa-template-item > div { display: flex; gap: 10px; align-items: center; }
.aa-template-item p { margin: 6px 0 0; font-size: 12px; color: var(--warning-700, #b54708); }
.aa-template-actions { display: flex; justify-content: flex-end; gap: 10px; }
@media (max-width: 900px) { .aa-template-grid { grid-template-columns: 1fr; } }
</style>
