<template>
  <section ref="root" class="mp-card bps-card">
    <div class="mp-card__head bps-head">
      <div>
        <span class="mp-card__title">参与学生范围</span>
        <p class="bps-subtitle">按班级批量圈选学生，预览无误后冻结名单并启用批次。</p>
      </div>
      <span class="bps-state" :class="{ 'is-frozen': frozen }">{{ stateText }}</span>
    </div>

    <div class="mp-card__body">
      <LoadingState v-if="loading" />
      <template v-else>
        <AppInlineAlert
          v-if="error"
          type="danger"
          title="参与学生范围加载失败"
          :description="error"
        />

        <template v-if="isDraft && !frozen">
          <div class="bps-picker-grid">
            <div class="bps-field bps-field--wide">
              <label>选择班级 <em>必选</em></label>
              <AppClassPicker
                v-model="rule.classIds"
                multiple
                :disabled="acting"
                placeholder="选择一个或多个班级"
                data-scope-hint="仅显示当前身份有权管理的班级"
              />
              <small>选中班级后，该班符合在籍条件的学生会一起进入预览名单。</small>
            </div>
            <div class="bps-field">
              <label>补充指定学生 <span>选填</span></label>
              <AppInternshipCandidateStudentPicker
                v-model="rule.studentIds"
                multiple
                :disabled="acting"
                placeholder="搜索并补充个别学生"
              />
            </div>
          </div>

          <div class="bps-actions">
            <AppButton
              variant="secondary"
              :disabled="acting || !hasScope"
              @click="previewParticipants"
            >{{ acting && actionMode === 'preview' ? '正在生成预览…' : '预览学生名单' }}</AppButton>
            <AppButton
              variant="primary"
              :disabled="acting || previewDirty || !previewRows.length"
              @click="confirmVisible = true"
            >冻结名单并启用批次</AppButton>
            <span v-if="!hasScope" class="bps-hint">请先选择至少一个班级或指定学生。</span>
            <span v-else-if="previewDirty" class="bps-hint">范围已变化，请重新预览后再冻结。</span>
          </div>

          <div v-if="previewed" class="bps-result">
            <div class="bps-metrics">
              <div><strong>{{ previewSummary.matchedCount }}</strong><span>符合条件</span></div>
              <div><strong>{{ previewSummary.alreadyInCount }}</strong><span>已在批次</span></div>
              <div><strong>{{ previewSummary.excludedCount }}</strong><span>被规则排除</span></div>
              <div><strong>{{ previewSummary.outOfScopeCount }}</strong><span>超出权限范围</span></div>
            </div>
            <p v-if="!previewRows.length" class="bps-empty">当前范围没有符合条件的学生，请调整班级后重试。</p>
            <div v-else class="bps-table-wrap">
              <table class="bps-table">
                <thead><tr><th>学生</th><th>班级</th><th>学院 / 专业</th><th>年级</th></tr></thead>
                <tbody>
                  <tr v-for="row in shownPreviewRows" :key="row.studentId">
                    <td><strong>{{ row.name }}</strong><small>{{ row.studentNo }}</small></td>
                    <td>{{ row.className || '—' }}</td>
                    <td>{{ [row.collegeName, row.majorName].filter(Boolean).join(' / ') || '—' }}</td>
                    <td>{{ row.grade || '—' }}</td>
                  </tr>
                </tbody>
              </table>
              <p v-if="previewRows.length > shownPreviewRows.length" class="bps-more">
                当前展示前 {{ shownPreviewRows.length }} 人，冻结时将按完整规则加入 {{ previewRows.length }} 人。
              </p>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="bps-metrics bps-metrics--compact">
            <div><strong>{{ summary.activeCount || 0 }}</strong><span>当前参与学生</span></div>
            <div><strong>{{ summary.removedCount || 0 }}</strong><span>已移出</span></div>
            <div><strong>{{ summary.plannedCount || 0 }}</strong><span>批次计划人数</span></div>
          </div>
          <p v-if="!participantRows.length" class="bps-empty">该批次尚无参与学生记录。</p>
          <div v-else class="bps-table-wrap">
            <table class="bps-table">
              <thead><tr><th>学生</th><th>当前班级</th><th>学院</th><th>加入方式</th></tr></thead>
              <tbody>
                <tr v-for="row in participantRows" :key="row.id">
                  <td><strong>{{ row.name }}</strong><small>{{ row.studentNo }}</small></td>
                  <td>{{ row.className || '—' }}<small v-if="row.classChanged">冻结后发生班级变更</small></td>
                  <td>{{ row.collegeName || '—' }}</td>
                  <td>{{ row.source === 'SCOPE' ? '按班级规则' : '人工补录' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      title="冻结参与学生名单"
      :message="`将当前预览的 ${previewRows.length} 名学生固化为正式实习名单，并立即启用批次。冻结后班级规则不可再修改，请确认预览无误。`"
      type="primary"
      confirm-text="确认冻结并启用"
      :submitting="acting && actionMode === 'freeze'"
      @confirm="freezeParticipants"
    />
  </section>
</template>

<script>
import { LoadingState } from '@/components/business'
import {
  AppInlineAlert, AppConfirmDialog, AppClassPicker, AppInternshipCandidateStudentPicker
} from '@/components/common'
import { AppButton } from '@/components/ui'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

const blankRule = () => ({
  collegeIds: [], majorIds: [], classIds: [], studentIds: [], grades: [],
  excludeCollegeIds: [], excludeMajorIds: [], excludeClassIds: [], excludeStudentIds: [],
  stages: [], studentStatuses: []
})

export default {
  name: 'BatchParticipantScope',
  components: {
    LoadingState, AppInlineAlert, AppConfirmDialog, AppClassPicker,
    AppInternshipCandidateStudentPicker, AppButton
  },
  props: {
    batchId: { type: [String, Number], required: true },
    batchStatus: { type: String, default: '' }
  },
  emits: ['frozen'],
  data() {
    return {
      loading: true,
      acting: false,
      actionMode: '',
      error: '',
      frozen: false,
      ruleReady: false,
      rule: blankRule(),
      previewDirty: true,
      previewed: false,
      previewRows: [],
      previewSummary: { matchedCount: 0, alreadyInCount: 0, excludedCount: 0, outOfScopeCount: 0 },
      participantRows: [],
      summary: {},
      confirmVisible: false
    }
  },
  computed: {
    isDraft() { return this.batchStatus === 'DRAFT' },
    hasScope() { return !!(this.rule.classIds.length || this.rule.studentIds.length) },
    shownPreviewRows() { return this.previewRows.slice(0, 50) },
    stateText() {
      if (this.frozen) return '名单已冻结'
      if (this.isDraft) return '待配置名单'
      return '正式名单'
    }
  },
  watch: {
    rule: {
      deep: true,
      handler() {
        if (!this.ruleReady) return
        this.previewDirty = true
        this.previewed = false
        this.previewRows = []
      }
    },
    batchStatus() { this.load() }
  },
  created() { this.load() },
  methods: {
    focus() { this.$refs.root?.scrollIntoView({ behavior: 'smooth', block: 'start' }) },
    async load() {
      this.loading = true
      this.error = ''
      const [ruleRes, summaryRes, listRes] = await Promise.all([
        internshipApi.getBatchParticipantRule(this.batchId),
        internshipApi.getBatchParticipantSummary(this.batchId),
        internshipApi.getBatchParticipants(this.batchId, { page: 1, pageSize: 100 })
      ])
      this.loading = false
      if (ruleRes.code !== 0) {
        this.error = ruleRes.message || '名单规则加载失败'
        return
      }
      this.ruleReady = false
      this.rule = { ...blankRule(), ...(ruleRes.data.rule || {}) }
      this.frozen = !!ruleRes.data.frozen
      this.summary = summaryRes.code === 0 ? (summaryRes.data || {}) : {}
      this.participantRows = listRes.code === 0 ? (listRes.data?.list || []) : []
      this.previewDirty = true
      this.$nextTick(() => { this.ruleReady = true })
    },
    async previewParticipants() {
      if (!this.hasScope || this.acting) return
      this.acting = true
      this.actionMode = 'preview'
      const res = await internshipApi.previewBatchParticipants(this.batchId, this.rule)
      this.acting = false
      if (res.code !== 0) return toast.error(res.message || '名单预览失败')
      this.ruleReady = false
      this.rule = { ...blankRule(), ...(res.data.rule || this.rule) }
      this.previewRows = res.data.rows || []
      this.previewSummary = {
        matchedCount: Number(res.data.matchedCount || 0),
        alreadyInCount: Number(res.data.alreadyInCount || 0),
        excludedCount: Number(res.data.excludedCount || 0),
        outOfScopeCount: Number(res.data.outOfScopeCount || 0)
      }
      this.previewed = true
      this.previewDirty = false
      this.$nextTick(() => { this.ruleReady = true })
    },
    async freezeParticipants() {
      if (this.previewDirty || !this.previewRows.length || this.acting) return
      this.acting = true
      this.actionMode = 'freeze'
      const res = await internshipApi.freezeBatchParticipants(this.batchId, this.rule)
      this.acting = false
      if (res.code !== 0) return toast.error(res.message || '名单冻结失败')
      this.confirmVisible = false
      toast.success(`已将 ${res.data.total || this.previewRows.length} 名学生加入批次，批次已启用`)
      this.$emit('frozen', res.data)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.bps-card { scroll-margin-top: 78px; }
.bps-head { align-items: flex-start; }
.bps-subtitle { margin: 4px 0 0; color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 400; }
.bps-state { flex: none; padding: 4px 10px; border-radius: 999px; background: var(--warning-50, #fffbeb); color: var(--warning-700, #a16207); font-size: var(--font-size-xs); font-weight: 600; }
.bps-state.is-frozen { background: var(--success-50, #ecfdf5); color: var(--success-700, #047857); }
.bps-picker-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-4); }
.bps-field label { display: flex; gap: 6px; margin-bottom: var(--space-2); color: var(--text-primary); font-size: var(--font-size-sm); font-weight: 600; }
.bps-field label em { color: var(--danger-600); font-style: normal; }
.bps-field label span, .bps-field small { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 400; }
.bps-field small { display: block; margin-top: 6px; }
.bps-actions { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-4); }
.bps-hint { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.bps-result { margin-top: var(--space-4); border-top: 1px solid var(--border-light); padding-top: var(--space-4); }
.bps-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.bps-metrics--compact { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.bps-metrics > div { border: 1px solid var(--border-light); border-radius: 10px; background: var(--bg-subtle, #f8fafc); padding: 12px 14px; }
.bps-metrics strong { display: block; color: var(--primary-700, #1d4ed8); font-size: 22px; line-height: 1.2; }
.bps-metrics span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.bps-table-wrap { overflow: auto; border: 1px solid var(--border-light); border-radius: 10px; }
.bps-table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.bps-table th { background: var(--bg-subtle, #f8fafc); color: var(--text-secondary); text-align: left; font-size: var(--font-size-xs); font-weight: 600; }
.bps-table th, .bps-table td { padding: 10px 12px; border-bottom: 1px solid var(--border-light); white-space: nowrap; }
.bps-table tbody tr:last-child td { border-bottom: 0; }
.bps-table td strong, .bps-table td small { display: block; }
.bps-table td small { margin-top: 2px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.bps-empty, .bps-more { margin: 0; padding: var(--space-4); color: var(--text-tertiary); font-size: var(--font-size-sm); text-align: center; }
.bps-more { border-top: 1px solid var(--border-light); }
@media (max-width: 760px) {
  .bps-metrics, .bps-metrics--compact { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
