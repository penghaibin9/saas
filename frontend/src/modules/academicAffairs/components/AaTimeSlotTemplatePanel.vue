<template>
  <AppSectionCard title="标准作息模板">
    <div class="aa-template-toolbar">
      <div class="aa-template-choice">
        <AppButton :variant="templateKey === 'STANDARD_8' ? 'primary' : 'ghost'" @click="choose('STANDARD_8')">标准 8 节</AppButton>
        <AppButton :variant="templateKey === 'STANDARD_10' ? 'primary' : 'ghost'" @click="choose('STANDARD_10')">标准 10 节</AppButton>
      </div>
      <AppButton variant="primary" :loading="loading" @click="loadPreview">检查当前作息</AppButton>
    </div>

    <p class="aa-template-note">模板只负责给出候选，不覆盖现有节次；确认时仅创建「可新增」项，每一项继续经过服务端节次序号与时间重叠校验。</p>
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
        <AppButton variant="ghost" :disabled="applying" @click="loadPreview">刷新权威预览</AppButton>
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
  emits: ['applied'],
  data() {
    return {
      templateKey: 'STANDARD_8',
      preview: null,
      loading: false,
      applying: false,
      error: ''
    }
  },
  computed: {
    canApply() {
      return !!this.preview && !this.preview.blockedCount && this.preview.readyCount > 0 && !this.applying
    }
  },
  methods: {
    statusLabel(status) { return { READY: '可新增', EXISTS: '已存在', BLOCKED: '冲突' }[status] || status },
    statusTone(status) { return { READY: 'success', EXISTS: 'default', BLOCKED: 'danger' }[status] || 'default' },
    choose(key) {
      this.templateKey = key
      this.preview = null
      this.error = ''
    },
    async loadPreview() {
      if (this.loading) return
      this.loading = true
      this.error = ''
      const res = await termCalendarConvenienceApi.previewTimeSlotTemplate(this.templateKey)
      this.loading = false
      if (res.code === 0) {
        this.preview = res.data
      } else {
        this.preview = null
        this.error = res.message || '作息模板预览失败'
      }
    },
    async applyTemplate() {
      if (!this.canApply) return
      this.applying = true
      this.error = ''
      let applied = 0
      for (const row of this.preview.items) {
        if (row.status !== 'READY') continue
        const res = await academicAffairsApi.createTimeSlot(row.desired)
        if (res.code !== 0) {
          this.error = `已成功创建 ${applied} 项；后续节次被服务端拒绝：${res.message || '发生冲突'}。已保留模板选择，请刷新权威预览后再确认。`
          this.applying = false
          this.$emit('applied', { applied, partial: true })
          await this.loadPreview()
          return
        }
        applied += 1
      }
      this.applying = false
      toast.success(`已创建 ${applied} 个缺失节次`)
      this.$emit('applied', { applied, partial: false })
      await this.loadPreview()
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
