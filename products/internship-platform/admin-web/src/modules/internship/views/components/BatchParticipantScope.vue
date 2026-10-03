<template>
  <section ref="root" class="mp-card bps-card">
    <div class="mp-card__head bps-head">
      <div>
        <span class="mp-card__title">参与学生范围</span>
        <p class="bps-subtitle">{{ isDraft && !frozen ? '选择参与范围，预览名单后确认启用。' : '查看本批次冻结或补录的参与名单。实习资格请在学生名单中继续核对。' }}</p>
      </div>
      <span class="bps-state" :class="{ 'is-frozen': frozen }">{{ stateText }}</span>
    </div>

    <div class="mp-card__body">
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" title="参与名单暂时无法读取" :description="error" @retry="load" />
      <template v-else>
        <template v-if="isDraft && !frozen && !readonly">
          <div class="bps-picker-grid">
            <div class="bps-field">
              <label>选择学院 <span>选填</span></label>
              <AppCollegePicker
                v-model="rule.collegeIds"
                multiple
                :disabled="acting"
                placeholder="选择一个或多个学院"
                data-scope-hint="仅显示当前身份有权管理的学院"
              />
              <small>学院、专业、班级和点名学生之间按“任一命中”合并，最终仍以后端权限范围收敛。</small>
            </div>
            <div class="bps-field">
              <label>选择专业 <span>选填</span></label>
              <AppMajorPicker
                v-model="rule.majorIds"
                multiple
                :disabled="acting"
                placeholder="选择一个或多个专业"
                data-scope-hint="仅显示当前身份有权管理的专业"
              />
            </div>
            <div class="bps-field bps-field--wide">
              <label>选择班级 <span>选填</span></label>
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
            <AppInlineAlert
              v-if="previewTruncated"
              type="warning"
              title="预览名单已截断"
              :description="`当前页面仅返回前 ${previewRows.length} 名用于核对，但规则实际命中 ${previewSummary.matchedCount} 名。确认冻结时，后端会按完整规则固化 ${previewSummary.matchedCount} 名学生，而不是只固化当前显示的预览行。`"
            />
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
              <p v-if="previewTruncated" class="bps-more is-warning">
                当前仅展示服务端返回的前 {{ previewRows.length }} 名中的前 {{ shownPreviewRows.length }} 名；完整规则实际命中 {{ previewSummary.matchedCount }} 名。
              </p>
              <p v-else-if="previewRows.length > shownPreviewRows.length" class="bps-more">
                当前展示前 {{ shownPreviewRows.length }} 人，冻结时将按完整规则加入 {{ previewSummary.matchedCount }} 人。
              </p>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="bps-metrics bps-metrics--compact">
            <div><strong>{{ summary.activeCount || 0 }}</strong><span>当前参与学生</span></div>
            <div><strong>{{ summary.removedCount || 0 }}</strong><span>已移出</span></div>
            <div><strong>{{ summary.plannedCount || 0 }}</strong><span>{{ summary.plannedCountScoped ? '当前范围人数' : '批次计划人数' }}</span></div>
          </div>
          <section v-if="canAdjustRoster" class="bps-manual">
            <div>
              <strong>人工补录学生</strong>
              <small>仅能补录当前身份数据范围内、符合学籍条件的学生；重复学生服务端幂等跳过。</small>
            </div>
            <AppInternshipCandidateStudentPicker
              v-model="manualStudentIds"
              multiple
              :disabled="manualActing"
              placeholder="搜索并选择要补录的学生"
            />
            <input
              v-model.trim="manualAddReason"
              class="bps-reason-input"
              maxlength="500"
              placeholder="补录原因（选填，如：转专业补录）"
            />
            <AppButton
              variant="secondary"
              :loading="manualActing"
              :disabled="manualActing || !manualStudentIds.length"
              @click="addManualParticipants"
            >补录到正式名单</AppButton>
          </section>
          <p v-if="!participantRows.length" class="bps-empty">该批次尚无参与学生记录。</p>
          <div v-else class="bps-table-wrap">
            <table class="bps-table">
              <thead><tr><th>学生</th><th>当前班级</th><th>学院</th><th>加入方式</th><th v-if="canAdjustRoster">操作</th></tr></thead>
              <tbody>
                <tr v-for="row in participantRows" :key="row.id">
                  <td><strong>{{ row.name }}</strong><small>{{ row.studentNo }}</small></td>
                  <td>{{ row.className || '—' }}<small v-if="row.classChanged">冻结后发生班级变更</small></td>
                  <td>{{ row.collegeName || '—' }}</td>
                  <td>{{ row.source === 'SCOPE' ? '范围规则' : '人工补录' }}</td>
                  <td v-if="canAdjustRoster">
                    <button type="button" class="bps-remove" :disabled="manualActing" @click="openRemove(row)">移出</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <footer v-if="participantTotal > participantPageSize" class="bps-pagebar">
              <button
                type="button"
                :disabled="participantLoading || participantPage <= 1"
                @click="changeParticipantPage(participantPage - 1)"
              >上一页</button>
              <span>第 {{ participantPage }} / {{ participantPageCount }} 页 · 共 {{ participantTotal }} 人</span>
              <button
                type="button"
                :disabled="participantLoading || participantPage >= participantPageCount"
                @click="changeParticipantPage(participantPage + 1)"
              >{{ participantLoading ? '加载中…' : '下一页' }}</button>
            </footer>
          </div>
        </template>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      title="冻结参与学生名单"
      :message="freezeConfirmMessage"
      type="primary"
      confirm-text="确认冻结并启用"
      :submitting="acting && actionMode === 'freeze'"
      @confirm="freezeParticipants"
    />
    <AppConfirmDialog
      v-model:visible="removeVisible"
      title="移出正式参与学生"
      :message="removeRow ? ('将 ' + removeRow.name + ' 从当前批次正式名单移出。仅 PREPARING 且尚未落实实习去向的学生允许直接移出。') : ''"
      type="danger"
      confirm-text="确认移出"
      require-reason
      reason-label="移出原因"
      :reason-min-length="2"
      :submitting="manualActing"
      @confirm="confirmRemove"
      @cancel="removeRow = null"
    />
  </section>
</template>

<script>
import { LoadingState, ErrorState } from '@/components/business'
import {
  AppInlineAlert, AppConfirmDialog, AppCollegePicker, AppMajorPicker,
  AppClassPicker, AppInternshipCandidateStudentPicker
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
    LoadingState, ErrorState, AppInlineAlert, AppConfirmDialog, AppCollegePicker, AppMajorPicker,
    AppClassPicker, AppInternshipCandidateStudentPicker, AppButton
  },
  props: {
    batchId: { type: [String, Number], required: true },
    batchStatus: { type: String, default: '' },
    readonly: { type: Boolean, default: false }
  },
  emits: ['frozen'],
  data() {
    return {
      loading: true,
      loadSequence: 0,
      acting: false,
      actionMode: '',
      error: '',
      frozen: false,
      ruleReady: false,
      rule: blankRule(),
      previewDirty: true,
      previewed: false,
      previewRows: [],
      previewTruncated: false,
      previewSummary: { matchedCount: 0, alreadyInCount: 0, excludedCount: 0, outOfScopeCount: 0 },
      participantRows: [],
      participantPage: 1,
      participantPageSize: 100,
      participantTotal: 0,
      participantLoading: false,
      summary: {},
      confirmVisible: false,
      manualStudentIds: [],
      manualAddReason: '',
      manualActing: false,
      removeRow: null,
      removeVisible: false
    }
  },
  computed: {
    isDraft() { return this.batchStatus === 'DRAFT' },
    canAdjustRoster() { return !this.readonly && this.batchStatus === 'RUNNING' && this.frozen },
    hasScope() {
      return !!(
        this.rule.collegeIds.length || this.rule.majorIds.length
        || this.rule.classIds.length || this.rule.studentIds.length
      )
    },
    shownPreviewRows() { return this.previewRows.slice(0, 50) },
    participantPageCount() {
      return Math.max(1, Math.ceil(this.participantTotal / this.participantPageSize))
    },
    freezeConfirmMessage() {
      const matchedCount = Number(this.previewSummary.matchedCount || this.previewRows.length || 0)
      if (this.previewTruncated) {
        return `当前预览因人数较多只返回前 ${this.previewRows.length} 名，完整规则实际命中 ${matchedCount} 名。确认后将按完整规则固化 ${matchedCount} 名学生并立即启用批次，不是只固化当前预览行。冻结后班级规则不可再修改，请确认范围规则无误。`
      }
      return `将当前规则命中的 ${matchedCount} 名学生固化为正式实习名单，并立即启用批次。冻结后班级规则不可再修改，请确认预览无误。`
    },
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
        this.previewTruncated = false
      }
    },
    batchId() {
      this.participantPage = 1
      this.participantLoading = false
      this.confirmVisible = false
      this.removeVisible = false
      this.removeRow = null
      this.manualStudentIds = []
      this.manualAddReason = ''
      this.acting = false
      this.load()
    },
    batchStatus() {
      this.participantPage = 1
      this.load()
    }
  },
  created() { this.load() },
  beforeUnmount() { this.loadSequence++ },
  methods: {
    focus() { this.$refs.root?.scrollIntoView({ behavior: 'smooth', block: 'start' }) },
    async load() {
      const sequence = ++this.loadSequence
      const batchId = this.batchId
      this.loading = true
      this.error = ''
      this.ruleReady = false
      this.previewed = false
      this.previewDirty = true
      this.previewRows = []
      this.previewTruncated = false
      try {
        const [ruleRes, summaryRes, listRes] = await Promise.all([
          internshipApi.getBatchParticipantRule(batchId),
          internshipApi.getBatchParticipantSummary(batchId),
          internshipApi.getBatchParticipants(batchId, { page: this.participantPage, pageSize: this.participantPageSize })
        ])
        if (sequence !== this.loadSequence || batchId !== this.batchId) return
        for (const [response, label] of [[ruleRes, '参与范围'], [summaryRes, '名单汇总'], [listRes, '学生名单']]) {
          if (response.code !== 0) throw new Error(response.message || `${label}加载失败，请重试`)
        }
        this.rule = { ...blankRule(), ...(ruleRes.data.rule || {}) }
        this.frozen = !!ruleRes.data.frozen
        this.summary = summaryRes.data || {}
        this.participantRows = listRes.data?.list || []
        this.participantTotal = Number(listRes.data?.total || 0)
        this.participantPage = Number(listRes.data?.page || this.participantPage)
        this.participantPageSize = Number(listRes.data?.pageSize || this.participantPageSize)
        await this.$nextTick()
        if (sequence === this.loadSequence) this.ruleReady = true
      } catch (e) {
        if (sequence === this.loadSequence) this.error = e.message || '参与名单加载失败，请重试'
      } finally {
        if (sequence === this.loadSequence) this.loading = false
      }
    },
    async previewParticipants() {
      if (this.readonly) return
      if (!this.hasScope || this.acting) return
      this.acting = true
      this.actionMode = 'preview'
      const batchId = this.batchId
      const res = await internshipApi.previewBatchParticipants(this.batchId, this.rule)
      if (batchId !== this.batchId) return
      this.acting = false
      if (res.code !== 0) return toast.error(res.message || '名单预览失败')
      this.ruleReady = false
      this.rule = { ...blankRule(), ...(res.data.rule || this.rule) }
      this.previewRows = res.data.rows || []
      this.previewTruncated = !!res.data.truncated
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
    async changeParticipantPage(page) {
      const target = Math.max(1, Math.min(Number(page || 1), this.participantPageCount))
      if (target === this.participantPage || this.participantLoading) return
      this.participantLoading = true
      const batchId = this.batchId
      const res = await internshipApi.getBatchParticipants(this.batchId, {
        page: target,
        pageSize: this.participantPageSize
      })
      if (batchId !== this.batchId) return
      this.participantLoading = false
      if (res.code !== 0) return toast.error(res.message || '参与学生名单加载失败')
      this.participantRows = res.data?.list || []
      this.participantTotal = Number(res.data?.total || 0)
      this.participantPage = Number(res.data?.page || target)
      this.participantPageSize = Number(res.data?.pageSize || this.participantPageSize)
    },
    async addManualParticipants() {
      if (!this.canAdjustRoster || this.manualActing || !this.manualStudentIds.length) return
      this.manualActing = true
      const batchId = this.batchId
      const res = await internshipApi.addBatchParticipants(
        batchId,
        [...this.manualStudentIds],
        this.manualAddReason || '人工补录'
      )
      if (batchId !== this.batchId) return
      this.manualActing = false
      if (res.code !== 0) return toast.error(res.message || '补录学生失败')
      const data = res.data || {}
      this.manualStudentIds = []
      this.manualAddReason = ''
      toast.success(
        `已补录 ${data.added || 0} 人`
        + (data.skippedExisting ? `，重复跳过 ${data.skippedExisting} 人` : '')
        + ((data.rejectedOutOfScope || []).length ? `，越权/不符合条件 ${data.rejectedOutOfScope.length} 人未加入` : '')
      )
      await this.load()
    },
    openRemove(row) {
      if (!this.canAdjustRoster || this.manualActing) return
      this.removeRow = row
      this.removeVisible = true
    },
    async confirmRemove({ reason }) {
      const row = this.removeRow
      if (!row?.id || !this.canAdjustRoster || this.manualActing) return
      this.manualActing = true
      const batchId = this.batchId
      const res = await internshipApi.removeBatchParticipant(batchId, row.id, {
        reason,
        version: row.version
      })
      if (batchId !== this.batchId) return
      this.manualActing = false
      if (res.code !== 0) return toast.error(res.message || '移出学生失败')
      this.removeVisible = false
      this.removeRow = null
      toast.success('学生已从正式名单移出，原参与记录和审计仍保留')
      await this.load()
    },
    async freezeParticipants() {
      if (this.readonly) return
      if (this.previewDirty || !this.previewRows.length || this.acting) return
      this.acting = true
      this.actionMode = 'freeze'
      const batchId = this.batchId
      const res = await internshipApi.freezeBatchParticipants(this.batchId, this.rule)
      if (batchId !== this.batchId) return
      this.acting = false
      if (res.code !== 0) return toast.error(res.message || '名单冻结失败')
      this.confirmVisible = false
      toast.success(`已将 ${res.data.total || this.previewSummary.matchedCount || this.previewRows.length} 名学生加入批次，批次已启用`)
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
.bps-picker-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-4); }
.bps-field--wide { grid-column: 1 / -1; }
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
.bps-metrics--compact { display:flex; flex-wrap:wrap; gap:12px 28px; margin-bottom:16px; }
.bps-metrics--compact > div { display:flex; align-items:baseline; gap:8px; padding:0; border:0; background:transparent; }
.bps-metrics--compact strong { font-size:18px; }
.bps-manual { display:grid; grid-template-columns:minmax(240px,1.4fr) minmax(260px,2fr) minmax(220px,1fr) auto; gap:10px; align-items:end; margin-bottom:14px; padding:12px; border:1px solid var(--border-light); border-radius:10px; background:var(--bg-subtle,#f8fafc); }
.bps-manual > div { display:grid; gap:4px; align-self:center; }
.bps-manual small { color:var(--text-tertiary); font-size:var(--font-size-xs); line-height:1.5; }
.bps-reason-input { height:36px; box-sizing:border-box; padding:0 10px; border:1px solid var(--border-base); border-radius:7px; background:var(--bg-card); color:var(--text-primary); }
.bps-remove { border:0; background:transparent; color:var(--danger-600); cursor:pointer; font-size:12px; }
.bps-remove:disabled { opacity:.5; cursor:not-allowed; }
.bps-table-wrap { overflow: auto; border: 1px solid var(--border-light); border-radius: 10px; }
.bps-table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.bps-table th { background: var(--bg-subtle, #f8fafc); color: var(--text-secondary); text-align: left; font-size: var(--font-size-xs); font-weight: 600; }
.bps-table th, .bps-table td { padding: 10px 12px; border-bottom: 1px solid var(--border-light); white-space: nowrap; }
.bps-table tbody tr:last-child td { border-bottom: 0; }
.bps-table td strong, .bps-table td small { display: block; }
.bps-table td small { margin-top: 2px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.bps-empty, .bps-more { margin: 0; padding: var(--space-4); color: var(--text-tertiary); font-size: var(--font-size-sm); text-align: center; }
.bps-more { border-top: 1px solid var(--border-light); }
.bps-more.is-warning { color: var(--warning-700, #a16207); background: var(--warning-50, #fffbeb); }
.bps-pagebar { display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding: 10px 12px; border-top: 1px solid var(--border-light); color: var(--text-tertiary); font-size: var(--font-size-xs); }
.bps-pagebar button { border: 1px solid var(--border-light); border-radius: 7px; background: #fff; padding: 5px 10px; cursor: pointer; }
.bps-pagebar button:disabled { opacity: .45; cursor: default; }
@media (max-width: 760px) {
  .bps-metrics, .bps-metrics--compact { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .bps-pagebar { justify-content: center; flex-wrap: wrap; }
}
@media (max-width: 980px) {
  .bps-picker-grid,.bps-manual { grid-template-columns:1fr; }
  .bps-field--wide { grid-column:auto; }
}
</style>
