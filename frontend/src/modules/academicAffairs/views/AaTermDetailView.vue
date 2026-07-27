<template>
  <ModulePageShell
    title="学期详情"
    subtitle="查看学期时间轴、关联业务、修改影响和状态变更记录"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <div class="atd-actions">
        <AppButton variant="ghost" @click="goBack">返回学期列表</AppButton>
        <AppButton variant="ghost" @click="goReadiness">查看学期运行结论</AppButton>
        <AppButton
          v-if="detail.allowedActions?.publish"
          variant="primary"
          @click="openAction('PUBLISH')"
        >发布并设为当前</AppButton>
        <AppButton
          v-if="detail.allowedActions?.setCurrent"
          variant="primary"
          @click="openAction('SET_CURRENT')"
        >设为当前学期</AppButton>
        <AppButton
          v-if="detail.allowedActions?.freeze"
          variant="ghost"
          @click="openAction('FREEZE')"
        >冻结学期</AppButton>
        <AppButton
          v-if="detail.allowedActions?.archive"
          variant="primary"
          @click="goArchive"
        >进入归档预检</AppButton>
      </div>
    </template>

    <LoadingState v-if="loading" text="正在加载学期详情…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else>
      <section class="atd-hero">
        <div>
          <div class="atd-eyebrow">
            <AppStatusTag :status="detail.status" dot>{{ statusLabel(detail.status) }}</AppStatusTag>
            <AppStatusTag v-if="detail.isCurrent" type="success" dot>当前学期</AppStatusTag>
            <span>版本 {{ detail.version ?? 0 }}</span>
          </div>
          <h2>{{ detail.termName || `${detail.yearCode} 第 ${detail.termNo} 学期` }}</h2>
          <p>{{ detail.yearCode }} · 第 {{ detail.termNo }} 学期 · {{ termRange }}</p>
        </div>
        <div class="atd-hero-metrics">
          <article><b>{{ detail.teachingWeeks || 0 }}</b><span>教学周</span></article>
          <article><b>{{ detail.examWeekStart || '—' }}</b><span>考试周起</span></article>
          <article><b>{{ linkedTotal }}</b><span>关联业务记录</span></article>
        </div>
      </section>

      <div class="atd-grid">
        <AppSectionCard title="学期基本信息" :subtitle="editHint">
          <div class="atd-form">
            <label>
              <span>学年</span>
              <input :value="detail.yearCode" disabled />
            </label>
            <label>
              <span>学期</span>
              <input :value="`第 ${detail.termNo} 学期`" disabled />
            </label>
            <label class="atd-span-2">
              <span>学期名称</span>
              <input
                v-model.trim="form.termName"
                :disabled="!canEditName"
                maxlength="100"
                placeholder="填写学校正式使用的学期名称"
                @input="invalidatePreview"
              />
            </label>
            <label>
              <span>开学日期</span>
              <input v-model="form.startDate" type="date" :disabled="!canEditTimeline" @input="invalidatePreview" />
            </label>
            <label>
              <span>结束日期</span>
              <input v-model="form.endDate" type="date" :disabled="!canEditTimeline" @input="invalidatePreview" />
            </label>
            <label>
              <span>教学周数</span>
              <input
                v-model.number="form.teachingWeeks"
                type="number"
                min="1"
                max="30"
                :disabled="!canEditTimeline"
                @input="invalidatePreview"
              />
            </label>
            <label>
              <span>考试周开始</span>
              <input
                v-model.number="form.examWeekStart"
                type="number"
                min="1"
                max="30"
                :disabled="!canEditTimeline"
                @input="invalidatePreview"
              />
            </label>
          </div>

          <div class="atd-warning" :class="{ 'is-locked': !canEditTimeline }">
            <strong>{{ canEditTimeline ? '修改前必须预览影响' : '当前时间轴已锁定' }}</strong>
            <p>{{ detail.impactWarning }}</p>
          </div>

          <div v-if="canEditName" class="atd-savebar">
            <span v-if="!hasChanges">当前没有未保存修改</span>
            <span v-else-if="!previewCurrent">修改后请重新执行影响预览</span>
            <span v-else>{{ preview.conclusion }}</span>
            <div>
              <AppButton :disabled="!hasChanges" :loading="previewing" variant="ghost" @click="previewChange">
                预览修改影响
              </AppButton>
              <AppButton
                variant="primary"
                :loading="saving"
                :disabled="!previewCurrent || !preview.canSave"
                @click="save"
              >保存修改</AppButton>
            </div>
          </div>
        </AppSectionCard>

        <AppSectionCard title="状态与操作后果" subtitle="状态转换沿用统一学期状态机">
          <div class="atd-state-list">
            <article :class="{ active: detail.status === 'DRAFT' }">
              <b>草稿</b><span>可维护日期、教学周和考试周；发布前完成校历与节次检查。</span>
            </article>
            <article :class="{ active: detail.status === 'PUBLISHED' }">
              <b>进行中</b><span>可设为当前和冻结；时间轴不可直接修改，只允许更正显示名称。</span>
            </article>
            <article :class="{ active: detail.status === 'FROZEN' }">
              <b>已冻结</b><span>教学结构保持稳定，完成成绩和业务收口后进入归档预检。</span>
            </article>
            <article :class="{ active: detail.status === 'ARCHIVED' }">
              <b>已归档</b><span>全字段只读，所有关联业务按正式归档规则封存。</span>
            </article>
          </div>
          <button class="mp-link atd-archive-link" @click="goArchive">查看归档语义预检 →</button>
        </AppSectionCard>
      </div>

      <AppSectionCard title="关联业务影响" subtitle="全部通过稳定 termId 或批次回链统计，不按名称和日期猜归属">
        <div class="atd-linked-grid">
          <button v-for="card in linkedCards" :key="card.key" class="atd-linked" @click="goTarget(card.route)">
            <span>{{ card.label }}</span>
            <b>{{ card.count }}</b>
            <small>{{ card.note }}</small>
          </button>
        </div>
      </AppSectionCard>

      <AppSectionCard
        v-if="previewCurrent"
        title="本次修改影响预览"
        :subtitle="`变化 ${preview.changes?.length || 0} 项 · 冲突 ${preview.conflictCount || 0} 条`"
      >
        <div :class="['atd-preview-conclusion', preview.canSave ? 'is-safe' : 'is-blocked']">
          <strong>{{ preview.canSave ? '可以保存' : '当前不可保存' }}</strong>
          <span>{{ preview.conclusion }}</span>
        </div>

        <div v-if="preview.blockers?.length" class="atd-blockers">
          <article v-for="row in preview.blockers" :key="row.code">
            <code>{{ row.code }}</code>
            <span>{{ row.message }}</span>
          </article>
        </div>

        <div v-if="preview.changes?.length" class="atd-change-list">
          <article v-for="row in preview.changes" :key="row.field">
            <b>{{ row.label }}</b>
            <span>{{ valueText(row.before) }}</span>
            <i>→</i>
            <span>{{ valueText(row.after) }}</span>
          </article>
        </div>

        <div class="atd-impact-grid">
          <button v-for="row in preview.impacts || []" :key="row.domain" @click="goTarget(row.route)">
            <header><strong>{{ row.label }}</strong><b>{{ row.affectedCount || 0 }}</b></header>
            <p>{{ row.summary }}</p>
            <span v-if="row.conflictCount" class="atd-conflict">冲突 {{ row.conflictCount }} 条</span>
            <span v-else>查看关联业务 →</span>
          </button>
        </div>
      </AppSectionCard>

      <AppSectionCard title="学期状态时间线" subtitle="读取 append-only 审计流水，保留操作者、角色和发生时间">
        <EmptyState v-if="!detail.timeline?.length" title="暂无状态变更记录" description="创建、发布、冻结和归档后会在这里形成记录" />
        <ol v-else class="atd-timeline">
          <li v-for="row in detail.timeline" :key="row.auditId">
            <span class="atd-timeline-dot" />
            <div>
              <header><strong>{{ row.actionLabel || row.action }}</strong><time>{{ row.occurredAt || '—' }}</time></header>
              <p>{{ row.operator || '系统' }}<template v-if="row.roleName"> · {{ row.roleName }}</template></p>
              <small v-if="row.detail">{{ row.detail }}</small>
            </div>
          </li>
        </ol>
      </AppSectionCard>
    </template>

    <AppConfirmDialog
      v-model:visible="actionDialog.visible"
      :title="actionDialog.title"
      :message="actionDialog.message"
      confirm-text="确认执行"
      :submitting="actionDialog.submitting"
      @confirm="confirmAction"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicAffairsTermDetailApi as termApi } from '@/modules/academicAffairs/api/academic-affairs-term-detail.api'
import { toast } from '@/utils/toast'

const STATUS_LABEL = {
  DRAFT: '草稿',
  PUBLISHED: '进行中',
  FROZEN: '已冻结',
  ARCHIVED: '已归档'
}

export default {
  name: 'AaTermDetailView',
  components: {
    ModulePageShell, LoadingState, ErrorState, EmptyState,
    AppButton, AppSectionCard, AppStatusTag, AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      detail: {},
      form: { termName: '', startDate: '', endDate: '', teachingWeeks: null, examWeekStart: null },
      baselineSignature: '',
      previewSignature: '',
      preview: {},
      previewing: false,
      saving: false,
      actionDialog: { visible: false, submitting: false, type: '', title: '', message: '' }
    }
  },
  computed: {
    termId() { return this.$route.params.termId },
    canEditTimeline() { return Boolean(this.detail.allowedActions?.editBasic) },
    canEditName() { return Boolean(this.detail.allowedActions?.editBasic || this.detail.allowedActions?.editNameOnly) },
    termRange() {
      if (this.detail.startDate && this.detail.endDate) return `${this.detail.startDate} 至 ${this.detail.endDate}`
      return '起止日期未完整设置'
    },
    editHint() {
      if (this.detail.status === 'ARCHIVED') return '已归档学期保持只读'
      if (this.canEditTimeline) return '草稿状态可维护完整时间轴，保存前必须执行影响预览'
      return '当前仅允许更正学期显示名称，日期和教学周时间轴已经锁定'
    },
    currentSignature() { return JSON.stringify(this.normalizedForm()) },
    hasChanges() { return this.currentSignature !== this.baselineSignature },
    previewCurrent() { return Boolean(this.previewSignature && this.previewSignature === this.currentSignature) },
    linkedTotal() {
      const d = this.detail.linkedData || {}
      return Number(d.calendar?.count || 0) + Number(d.teachingTasks?.recordCount || 0) +
        Number(d.schedules?.recordCount || 0) + Number(d.exams?.recordCount || 0) +
        Number(d.selections?.recordCount || 0) + Number(d.grades?.count || 0)
    },
    linkedCards() {
      const d = this.detail.linkedData || {}
      return [
        { key: 'calendar', label: '校历事件', count: d.calendar?.count || 0, note: '节假日、调休与教学周事件', route: d.calendar?.route },
        { key: 'tasks', label: '教学任务', count: d.teachingTasks?.recordCount || 0, note: `${d.teachingTasks?.batchCount || 0} 个任务批次`, route: d.teachingTasks?.route },
        { key: 'schedule', label: '课表项', count: d.schedules?.recordCount || 0, note: `${d.schedules?.batchCount || 0} 个课表批次`, route: d.schedules?.route },
        { key: 'exam', label: '考试课程', count: d.exams?.recordCount || 0, note: `${d.exams?.batchCount || 0} 个考试批次`, route: d.exams?.route },
        { key: 'selection', label: '选课供给', count: d.selections?.recordCount || 0, note: `${d.selections?.batchCount || 0} 个选课批次`, route: d.selections?.route },
        { key: 'grade', label: '成绩任务', count: d.grades?.count || 0, note: '录入、审核、发布与归档', route: d.grades?.route }
      ]
    }
  },
  created() { this.load() },
  methods: {
    statusLabel(status) { return STATUS_LABEL[status] || status || '未知状态' },
    valueText(value) { return value === null || value === undefined || value === '' ? '未设置' : String(value) },
    normalizedForm() {
      return {
        termName: (this.form.termName || '').trim(),
        startDate: this.form.startDate || null,
        endDate: this.form.endDate || null,
        teachingWeeks: this.form.teachingWeeks === '' ? null : this.form.teachingWeeks,
        examWeekStart: this.form.examWeekStart === '' ? null : this.form.examWeekStart
      }
    },
    invalidatePreview() {
      this.preview = {}
      this.previewSignature = ''
    },
    hydrateForm(detail) {
      this.form = {
        termName: detail.termName || '',
        startDate: (detail.startDate || '').slice(0, 10),
        endDate: (detail.endDate || '').slice(0, 10),
        teachingWeeks: detail.teachingWeeks ?? null,
        examWeekStart: detail.examWeekStart ?? null
      }
      this.baselineSignature = JSON.stringify(this.normalizedForm())
      this.invalidatePreview()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await termApi.get(this.termId)
      if (res.code === 0) {
        this.detail = res.data || {}
        this.hydrateForm(this.detail)
      } else {
        this.error = res.message || '学期详情加载失败'
      }
      this.loading = false
    },
    async previewChange() {
      if (!this.hasChanges || this.previewing) return
      this.previewing = true
      const signature = this.currentSignature
      const res = await termApi.preview(this.termId, this.normalizedForm())
      this.previewing = false
      if (res.code === 0) {
        this.preview = res.data || {}
        this.previewSignature = signature
        if (this.preview.canSave) toast.success('影响预览完成，本次修改可以保存')
        else toast.error(this.preview.conclusion || '当前修改不可保存')
      } else {
        toast.error(res.message || '影响预览失败')
      }
    },
    async save() {
      if (!this.previewCurrent || !this.preview.canSave || this.saving) return
      this.saving = true
      const res = await termApi.update(this.termId, {
        ...this.normalizedForm(),
        expectedVersion: this.detail.version ?? 0
      })
      this.saving = false
      if (res.code === 0) {
        toast.success('学期信息已保存')
        this.detail = res.data || {}
        this.hydrateForm(this.detail)
      } else {
        toast.error(res.message || '保存失败')
        if (res.code === 'APPROVAL_VERSION_CONFLICT' || res.code === 409) this.load()
      }
    },
    goBack() { this.$router.push('/admin/academic-affairs/terms') },
    goReadiness() { this.$router.push(`/admin/academic-affairs?termId=${this.termId}`) },
    goArchive() { this.$router.push(this.detail.archiveRoute || `/admin/academic-affairs/archive/precheck?termId=${this.termId}`) },
    goTarget(route) { if (route) this.$router.push(route) },
    openAction(type) {
      const labels = {
        PUBLISH: ['发布并设为当前', '发布后学期时间轴将锁定，后续只能更正显示名称。确认继续？'],
        SET_CURRENT: ['设为当前学期', '确认将该学期设为当前学期？系统会取消其它学期的当前标记。'],
        FREEZE: ['冻结学期', '冻结后教学结构保持稳定，需完成业务收口后再进入归档。确认继续？']
      }
      const [title, message] = labels[type]
      this.actionDialog = { visible: true, submitting: false, type, title, message }
    },
    async confirmAction() {
      const type = this.actionDialog.type
      this.actionDialog.submitting = true
      let res
      if (type === 'PUBLISH') res = await academicAffairsApi.publishTerm(this.termId)
      if (type === 'SET_CURRENT') res = await academicAffairsApi.setCurrentTerm(this.termId)
      if (type === 'FREEZE') res = await academicAffairsApi.freezeTerm(this.termId)
      this.actionDialog.submitting = false
      if (res?.code === 0) {
        this.actionDialog.visible = false
        toast.success(`${this.actionDialog.title}成功`)
        this.load()
      } else {
        toast.error(res?.message || `${this.actionDialog.title}失败`)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.atd-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.atd-hero {
  display: flex; justify-content: space-between; gap: 24px; align-items: center;
  padding: 24px; margin-bottom: 16px; border: 1px solid var(--border-200, #e5e6eb);
  border-radius: 12px; background: var(--bg-white, #fff);
}
.atd-eyebrow { display: flex; align-items: center; gap: 10px; color: var(--text-500, #646a73); font-size: 13px; }
.atd-hero h2 { margin: 10px 0 6px; font-size: 24px; color: var(--text-900, #1d2129); }
.atd-hero p { margin: 0; color: var(--text-500, #646a73); }
.atd-hero-metrics { display: grid; grid-template-columns: repeat(3, minmax(90px, 1fr)); gap: 12px; }
.atd-hero-metrics article { min-width: 92px; padding: 14px; border-radius: 10px; background: var(--fill-50, #f7f8fa); text-align: center; }
.atd-hero-metrics b { display: block; font-size: 22px; color: var(--text-900, #1d2129); }
.atd-hero-metrics span { font-size: 12px; color: var(--text-500, #646a73); }
.atd-grid { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(320px, .8fr); gap: 16px; margin-bottom: 16px; }
.atd-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.atd-form label { display: flex; flex-direction: column; gap: 6px; }
.atd-form label > span { font-size: 13px; color: var(--text-700, #4e5969); }
.atd-form input { height: 36px; padding: 0 11px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 7px; box-sizing: border-box; color: var(--text-900, #1d2129); background: var(--bg-white, #fff); }
.atd-form input:disabled { background: var(--fill-50, #f7f8fa); color: var(--text-400, #8a9099); cursor: not-allowed; }
.atd-span-2 { grid-column: span 2; }
.atd-warning { margin-top: 16px; padding: 13px 14px; border-radius: 8px; background: var(--warning-50, #fff7e8); }
.atd-warning.is-locked { background: var(--fill-50, #f7f8fa); }
.atd-warning strong { color: var(--text-900, #1d2129); }
.atd-warning p { margin: 5px 0 0; color: var(--text-600, #4e5969); font-size: 13px; line-height: 1.6; }
.atd-savebar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border-200, #e5e6eb); }
.atd-savebar > span { font-size: 13px; color: var(--text-500, #646a73); }
.atd-savebar > div { display: flex; gap: 8px; }
.atd-state-list { display: flex; flex-direction: column; gap: 9px; }
.atd-state-list article { padding: 11px 12px; border-left: 3px solid var(--border-300, #d0d3d9); background: var(--fill-50, #f7f8fa); }
.atd-state-list article.active { border-left-color: var(--primary-600, #3370ff); background: var(--primary-50, #f0f4ff); }
.atd-state-list b { display: block; color: var(--text-900, #1d2129); }
.atd-state-list span { display: block; margin-top: 4px; font-size: 12px; line-height: 1.5; color: var(--text-500, #646a73); }
.atd-archive-link { margin-top: 14px; }
.atd-linked-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }
.atd-linked { display: flex; flex-direction: column; align-items: flex-start; gap: 5px; padding: 14px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 9px; background: var(--bg-white, #fff); text-align: left; cursor: pointer; }
.atd-linked:hover { border-color: var(--primary-300, #8fb1ff); }
.atd-linked span { color: var(--text-600, #4e5969); }
.atd-linked b { font-size: 22px; color: var(--text-900, #1d2129); }
.atd-linked small { color: var(--text-400, #8a9099); }
.atd-preview-conclusion { display: flex; gap: 12px; align-items: center; padding: 13px 14px; border-radius: 8px; }
.atd-preview-conclusion.is-safe { background: var(--success-50, #eafff3); }
.atd-preview-conclusion.is-blocked { background: var(--danger-50, #fff0f0); }
.atd-blockers { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
.atd-blockers article { display: flex; gap: 10px; padding: 10px 12px; border: 1px solid var(--danger-200, #ffccc7); border-radius: 8px; }
.atd-blockers code { white-space: nowrap; }
.atd-change-list { display: flex; flex-direction: column; gap: 7px; margin-top: 14px; }
.atd-change-list article { display: grid; grid-template-columns: 140px 1fr 28px 1fr; align-items: center; gap: 8px; padding: 9px 10px; background: var(--fill-50, #f7f8fa); border-radius: 7px; }
.atd-change-list i { text-align: center; font-style: normal; color: var(--text-400, #8a9099); }
.atd-impact-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; margin-top: 14px; }
.atd-impact-grid button { padding: 13px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; background: var(--bg-white, #fff); text-align: left; cursor: pointer; }
.atd-impact-grid header { display: flex; justify-content: space-between; }
.atd-impact-grid p { min-height: 42px; margin: 8px 0; font-size: 12px; line-height: 1.55; color: var(--text-500, #646a73); }
.atd-impact-grid span { font-size: 12px; color: var(--primary-600, #3370ff); }
.atd-impact-grid .atd-conflict { color: var(--danger-600, #f53f3f); }
.atd-timeline { list-style: none; margin: 0; padding: 0; }
.atd-timeline li { position: relative; display: flex; gap: 13px; padding: 0 0 18px; }
.atd-timeline li:not(:last-child)::before { content: ''; position: absolute; left: 5px; top: 12px; bottom: 0; width: 1px; background: var(--border-200, #e5e6eb); }
.atd-timeline-dot { z-index: 1; width: 11px; height: 11px; margin-top: 4px; border-radius: 50%; background: var(--primary-500, #4e83fd); }
.atd-timeline li > div { flex: 1; }
.atd-timeline header { display: flex; justify-content: space-between; gap: 16px; }
.atd-timeline time, .atd-timeline p, .atd-timeline small { color: var(--text-500, #646a73); font-size: 12px; }
.atd-timeline p { margin: 4px 0; }
@media (max-width: 1000px) {
  .atd-grid { grid-template-columns: 1fr; }
  .atd-hero { align-items: flex-start; flex-direction: column; }
}
@media (max-width: 680px) {
  .atd-form { grid-template-columns: 1fr; }
  .atd-span-2 { grid-column: span 1; }
  .atd-savebar { align-items: flex-start; flex-direction: column; }
  .atd-change-list article { grid-template-columns: 1fr; }
}
</style>
