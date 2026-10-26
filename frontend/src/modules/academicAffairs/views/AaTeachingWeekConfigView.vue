<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="教学周配置"
    subtitle="按学校校历配置教学周与考试开始周；草稿学期可修改。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="$route.query.returnToken" :disabled="saving || recovering" @click="academicFlow?.back($route.query.returnToken, '/admin/academic-affairs/terms')">返回原位置</AppButton>
      <AppButton variant="primary" :disabled="!editable" :loading="previewing" @click="previewChange">预览周次影响</AppButton>
    </template>
    <div class="mp-stack">
      <div class="aa-filter">
        <div class="aa-filter__item" role="group" aria-labelledby="aa-teaching-week-term-label" data-dirty-ignore="true">
          <span id="aa-teaching-week-term-label">学期</span>
          <AppTermEntityPicker :model-value="termId" :options="termOptions" :disabled="saving || recovering || termsLoading" placeholder="选择学期" @update:model-value="onTermChange" />
        </div>
      </div>

      <AppInlineAlert
        v-if="currentError"
        type="warning"
        :description="`当前学期解析失败，未自动猜测“当前”；仍可显式选择草稿学期维护教学周。${currentError}`"
      />

      <ErrorState v-if="catalogError" :description="catalogError" @retry="refreshTermCatalog" />
      <LoadingState v-else-if="termsLoading" />
      <EmptyState
        v-else-if="!terms.length"
        title="还没有学年学期"
        description="请先到「学年学期」创建一个学期"
      >
        <AppButton variant="primary" @click="$router.push('/admin/academic-affairs/terms')">前往学年学期</AppButton>
      </EmptyState>

      <EmptyState v-else-if="!current" title="请选择学期" description="未解析到当前学期时，请显式选择需要维护的学期。" />
      <template v-else-if="current">
        <AppInlineAlert
          v-if="(detail?.status || current.status) !== 'DRAFT'"
          type="warning"
          description="该学期的教学周已锁定。解冻只恢复业务办理，不会恢复草稿编辑权限。"
        />
        <AaCalendarMonth :term="calendarTerm" :weeks="weeks" week-mode title="教学周配置" :loading="workspaceLoading || recovering" :error="workspaceError" @retry="loadWorkspace" />
        <AppSectionCard title="调整对照与影响" :subtitle="`学期 ${termId} · ${statusLabel(detail?.status || current.status)} · 定义版本 ${detail?.version ?? '待核对'}`">
          <section v-if="versionConflict || recoveryComparison.length" class="aa-recovery" aria-label="教学周修改冲突恢复">
            <strong>{{ versionConflict ? '学期信息已被其他人修改' : '已读取最新信息，请核对后重新预览' }}</strong>
            <p>未保存的周次已保留。读取最新信息后，请核对原值、最新值和保留值，再预览并保存。</p>
            <AppButton v-if="versionConflict" :loading="recovering" :disabled="recovering" @click="recoverVersion">读取最新信息并保留我的修改</AppButton>
            <AppInlineAlert v-if="recoveryError" type="danger" :description="recoveryError" />
            <div v-if="recoveryComparison.length" class="aa-recovery__scroll">
              <table><thead><tr><th>项目</th><th>原值</th><th>最新值</th><th>保留值</th></tr></thead>
                <tbody><tr v-for="row in recoveryComparison" :key="row.field"><th>{{ row.label }}</th><td>{{ valueText(row.original) }}</td><td>{{ valueText(row.latest) }}</td><td>{{ valueText(row.retained) }}</td></tr></tbody>
              </table>
            </div>
            <AppInlineAlert v-if="!versionConflict && !workspaceWritable" type="warning" description="最新学期依据已锁定教学周编辑，保留的输入不会自动提交。" />
          </section>
          <div class="aa-form">
            <AppFormItem label="教学周总数" required>
              <AppNumberInput :model-value="form.teachingWeeks" :min="1" :max="30" :disabled="!editable" @update:model-value="updateWeekField('teachingWeeks', $event)" />
            </AppFormItem>
            <AppFormItem label="考试周开始周次" hint="留空表示暂不设置考试周">
              <AppNumberInput :model-value="form.examWeekStart" :min="1" :max="30" :disabled="!editable" @update:model-value="updateWeekField('examWeekStart', $event)" />
            </AppFormItem>
            <AppInlineAlert v-if="formError" type="danger" :description="formError" />
          </div>
          <div v-if="previewCurrent" class="aa-impact" aria-live="polite">
            <AppInlineAlert :type="preview.canSave ? 'success' : 'warning'" :description="preview.conclusion || '影响结论待核对'" />
            <p v-for="(blocker, index) in preview.blockers || []" :key="index">{{ blocker.message || blocker.reason || blocker.code }}</p>
            <div v-for="row in preview.changes || []" :key="row.field"><strong>{{ row.label || row.field }}</strong>：{{ row.before ?? '未设置' }} → {{ row.after ?? '未设置' }}</div>
            <div v-for="row in preview.impacts || []" :key="row.domain"><strong>{{ row.label || row.domain }}</strong>：{{ row.summary || row.message || '请进入学期详情核对引用' }}</div>
          </div>
          <template #footer>
            <AppButton :disabled="!editable" :loading="previewing" @click="previewChange">预览周次影响</AppButton>
            <AppButton variant="primary" :disabled="!editable || !previewCurrent || preview.canSave !== true" :loading="saving" @click="submit">保存教学周配置</AppButton>
            <span class="mp-note">保存后由校历与节次管理岗位继续核对；当前学期保持原权威。</span>
          </template>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 教学周配置（/admin/academic-affairs/terms/teaching-weeks）：显式 term 可编辑；默认 term 由 A-C1 /terms/current 决定。 */
import { ModulePageShell, EmptyState, ErrorState, LoadingState } from '@/components/business'
import { AppSectionCard, AppFormItem, AppNumberInput, AppInlineAlert, AppTermEntityPicker } from '@/components/common'
import { AppButton } from '@/components/ui'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicAffairsTermDetailApi as termApi } from '@/modules/academicAffairs/api/academic-affairs-term-detail.api'
import AaCalendarMonth from '@/modules/academicAffairs/components/AaCalendarMonth.vue'
import { loadAcademicTermCatalog } from '@/modules/academicAffairs/pickerAdapters'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'
import { systemConfirm } from '@/services/systemDialog'

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '已发布', FROZEN: '已冻结', ARCHIVED: '已归档' }

export default {
  name: 'AaTeachingWeekConfigView',
  components: { ModulePageShell, EmptyState, ErrorState, LoadingState, AppSectionCard, AppFormItem, AppNumberInput, AppInlineAlert, AppTermEntityPicker, AppButton, AaCalendarMonth },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      termsLoading: true, disposed: false, releaseDirtyConfirmation: null, catalogVersion: 0,
      workspaceVersion: 0, workspaceLoading: false, workspaceError: '', detail: null, weeks: [],
      preview: null, previewSignature: '', previewing: false, previewVersion: 0,
      baselineForm: { teachingWeeks: null, examWeekStart: null }, workspaceLoaded: false,
      versionConflict: false, recovering: false, recoveryVersion: 0, recoveryError: '', recoveryComparison: [],
      catalogError: '',
      terms: [],
      termId: '',
      currentContext: null,
      currentError: '',
      form: { teachingWeeks: null, examWeekStart: null },
      formError: '',
      saving: false
    }
  },
  computed: {
    signature() { return JSON.stringify([this.termId, this.catalogVersion, this.detail?.version, this.form, this.ctx]) },
    previewCurrent() { return !!this.preview && this.previewSignature === this.signature },
    termOptions() {
      return this.terms.map((t) => ({
        value: t.termId,
        label: `${t.yearCode} 第 ${t.termNo} 学期${this.isResolvedCurrent(t) ? '（全校当前）' : ''}（${this.statusLabel(t.status)}）`,
        raw: t
      }))
    },
    current() {
      return this.terms.find((t) => String(t.termId) === String(this.termId)) || null
    },
    calendarTerm() { return String(this.detail?.termId) === String(this.termId) ? this.detail : this.current },
    workspaceWritable() { return this.detail?.status === 'DRAFT' && this.detail?.allowedActions?.editBasic === true },
    editable() {
      return !this.termsLoading && !this.workspaceLoading && !this.workspaceError && !this.saving && !this.previewing && !this.versionConflict && !this.recovering && Number.isInteger(this.detail?.version) && matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.term.manage') && !!this.current && this.current.status === 'DRAFT' && this.workspaceWritable
    }
  },
  created() {
    this.refreshTermCatalog()
  },
  mounted() {
    const guard = window.__SAAS_DIRTY_FORM_GUARD__
    if (!guard?.registerConfirmation) return
    this.releaseDirtyConfirmation = guard.registerConfirmation(async (message) => {
      const context = JSON.stringify([this.contextKey(), this.academicFlow?.identity?.() || '']), sourceFullPath = this.$route?.fullPath
      const accepted = await systemConfirm({ title: '确认离开当前页面', message, confirmText: '放弃修改并离开', type: 'danger' })
      if (accepted !== true || this.$route?.fullPath !== sourceFullPath) return accepted
      return context === JSON.stringify([this.contextKey(), this.academicFlow?.identity?.() || '']) ? accepted : false
    })
  },
  watch: {
    '$route.query.termId'(id) {
      if (String(id || '') === String(this.termId || '')) return
      this.applyTermSelection(typeof id === 'string' && this.terms.some(term => String(term.termId) === id) ? id : '')
      if (!this.termId) this.catalogError = '入口指定的学期不可用，请重新选择学期。'
    },
    ctx: { deep: true, handler() { this.catalogVersion++; this.applyTermSelection(''); this.refreshTermCatalog() } }
  },
  beforeRouteUpdate(to, from, next) { if (this.saving || this.recovering) { toast.warning('正在核对或保存教学周，请稍候再切换'); next(false) } else next() },
  beforeUnmount() {
    this.disposed = true; this.catalogVersion++; this.workspaceVersion++; this.recoveryVersion++; this.invalidatePreview()
    this.releaseDirtyConfirmation?.()
    this.releaseDirtyConfirmation = null
  },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || (s ? '状态待确认' : '') },
    valueText(value) { return value === null || value === undefined || value === '' ? '未设置' : String(value) },
    normalizedForm(value = this.form) {
      return {
        teachingWeeks: value.teachingWeeks === '' || value.teachingWeeks == null ? null : Number(value.teachingWeeks),
        examWeekStart: value.examWeekStart === '' || value.examWeekStart == null ? null : Number(value.examWeekStart)
      }
    },
    hydrateForm(detail) {
      this.form = this.normalizedForm(detail)
      this.baselineForm = { ...this.form }
      this.invalidatePreview()
    },
    updateWeekField(field, value) {
      if (!this.editable || !['teachingWeeks', 'examWeekStart'].includes(field) || this.form[field] === value) return
      this.form[field] = value
      this.invalidatePreview()
      window.__SAAS_DIRTY_FORM_GUARD__?.markDirty?.()
    },
    invalidatePreview() { this.previewVersion++; this.preview = null; this.previewSignature = ''; this.previewing = false },
    contextKey() { return JSON.stringify([this.disposed, this.catalogVersion, this.workspaceVersion, this.termId, this.ctx]) },
    isResolvedCurrent(term) {
      return Boolean(term && this.currentContext?.termId) && String(term.termId) === String(this.currentContext.termId)
    },
    async loadCurrentContext() {
      const version = this.catalogVersion, scope = JSON.stringify(this.ctx)
      this.currentError = ''
      this.currentContext = null
      const res = await academicAffairsApi.getCurrentTerm()
      if (version !== this.catalogVersion || this.disposed || scope !== JSON.stringify(this.ctx)) return
      if (res.code === 0) {
        this.currentContext = res.data || null
      } else {
        this.currentContext = null
        this.currentError = res.message || '当前学期解析失败'
      }
    },
    async refreshTermCatalog() {
      if (this.saving || this.recovering) return
      this.invalidatePreview()
      const version = ++this.catalogVersion, scope = JSON.stringify(this.ctx)
      this.termsLoading = true
      this.catalogError = ''
      try {
        const terms = await loadAcademicTermCatalog()
        if (version !== this.catalogVersion || this.disposed || scope !== JSON.stringify(this.ctx)) return
        this.terms = terms
        await this.loadCurrentContext()
        if (version !== this.catalogVersion || this.disposed || scope !== JSON.stringify(this.ctx)) return
        const resolved = this.terms.find((t) => this.isResolvedCurrent(t))
        const requested = this.termId || this.$route.query.termId
        const explicit = typeof requested === 'string' && this.terms.find(t => String(t.termId) === requested)
        if (requested && !explicit) {
          this.applyTermSelection(''); this.catalogError = '入口指定的学期不可用，请重新选择学期。'; this.termsLoading = false; return
        }
        const selected = explicit || resolved
        if (selected) {
          if (String(this.termId) !== String(selected.termId) || !this.workspaceLoaded) this.applyTermSelection(String(selected.termId))
          else await this.loadWorkspace()
        }
      } catch (error) {
        if (version !== this.catalogVersion || this.disposed || scope !== JSON.stringify(this.ctx)) return
        this.catalogError = error.message || '学期数据加载失败'
      }
      this.termsLoading = false
    },
    async onTermChange(id) {
      if (this.saving || this.recovering || this.termsLoading || String(id || '') === String(this.termId || '')) return
      if (id && !this.terms.some(term => String(term.termId) === String(id))) return
      try {
        await this.$router.replace({ query: { ...this.$route.query, termId: id ? String(id) : undefined } })
      } catch { toast.warning('学期切换未完成，已保留当前输入') }
    },
    applyTermSelection(id) {
      this.termId = id
      this.workspaceVersion++; this.recoveryVersion++; this.detail = null; this.weeks = []; this.invalidatePreview()
      this.workspaceLoaded = false; this.workspaceError = ''; this.workspaceLoading = false
      this.saving = false
      this.versionConflict = false; this.recovering = false; this.recoveryError = ''; this.recoveryComparison = []
      this.catalogError = ''
      this.formError = ''
      const t = this.current
      this.hydrateForm(t || {})
      if (t) this.loadWorkspace()
    },
    async loadWorkspace() {
      if (!this.termId || this.recovering || this.saving || this.versionConflict) return
      const version = ++this.workspaceVersion, id = this.termId, scope = JSON.stringify(this.ctx)
      const localSignature = JSON.stringify(this.normalizedForm())
      this.workspaceLoading = true; this.workspaceError = ''; this.invalidatePreview()
      const [detail, weeks] = await Promise.all([termApi.get(id), academicAffairsApi.getTermWeeks(id)])
      if (this.disposed || version !== this.workspaceVersion || String(id) !== String(this.termId) || scope !== JSON.stringify(this.ctx)) return
      this.workspaceLoading = false
      if (detail.code !== 0 || String(detail.data?.termId) !== String(id) || weeks.code !== 0) {
        this.workspaceError = detail.code !== 0 ? detail.message || '学期依据读取失败' : weeks.code !== 0 ? weeks.message || '周次依据读取失败' : '学期依据与当前对象不匹配'; return
      }
      if (!Number.isInteger(detail.data?.version)) { this.workspaceError = '学期版本依据不完整，请重新读取'; return }
      if (this.workspaceLoaded && this.detail?.version !== detail.data.version) {
        this.versionConflict = true; this.formError = '学期依据已更新，请读取最新信息并核对保留的修改'; return
      }
      this.detail = detail.data; this.weeks = weeks.data || []
      if (!this.workspaceLoaded && localSignature === JSON.stringify(this.normalizedForm())) this.hydrateForm(this.detail)
      this.workspaceLoaded = true
      this.academicFlow?.restorePosition()
    },
    payload() { return { teachingWeeks: Number(this.form.teachingWeeks), examWeekStart: this.form.examWeekStart ? Number(this.form.examWeekStart) : null } },
    async recoverVersion() {
      if (!this.versionConflict || this.recovering || this.saving || this.previewing || this.workspaceLoading) return
      this.invalidatePreview(); this.recovering = true; this.recoveryError = ''
      const context = this.contextKey(), id = this.termId, signature = this.signature, generation = ++this.recoveryVersion
      const original = { ...this.baselineForm }, local = this.normalizedForm()
      const [res, weeks] = await Promise.all([termApi.get(id), academicAffairsApi.getTermWeeks(id)])
      if (this.disposed || context !== this.contextKey() || generation !== this.recoveryVersion) return
      this.recovering = false
      if (signature !== this.signature) { this.recoveryError = '输入已变化，请重新读取最新信息'; return }
      if (res.code !== 0 || String(res.data?.termId) !== String(id) || !Number.isInteger(res.data?.version) || weeks.code !== 0) {
        this.recoveryError = res.code !== 0 ? res.message || '最新学期依据读取失败，请重试' : weeks.code !== 0 ? weeks.message || '最新周次依据读取失败，请重试' : '最新学期依据不完整或与当前对象不匹配，请重试'; return
      }
      const latest = this.normalizedForm(res.data), merged = { ...latest }
      const labels = { teachingWeeks: '教学周总数', examWeekStart: '考试周开始周次' }
      this.recoveryComparison = Object.keys(latest).map(field => {
        if (local[field] !== original[field]) merged[field] = local[field]
        return { field, label: labels[field], original: original[field], latest: latest[field], retained: merged[field] }
      })
      this.detail = res.data; this.weeks = weeks.data || []; this.baselineForm = latest; this.form = merged
      this.workspaceLoaded = true; this.workspaceError = ''; this.versionConflict = false; this.formError = ''
      this.invalidatePreview()
    },
    async previewChange() {
      if (!this.editable) return
      const signature = this.signature, id = this.termId, generation = ++this.previewVersion, context = this.contextKey()
      this.previewing = true; this.preview = null; this.formError = ''
      const res = await termApi.preview(id, this.payload())
      if (this.disposed || generation !== this.previewVersion || context !== this.contextKey()) return
      this.previewing = false
      if (signature !== this.signature) return
      if (res.code === 0 && String(res.data?.termId) === String(id)) { this.preview = res.data; this.previewSignature = signature }
      else this.formError = res.code !== 0 ? res.message || '影响预览失败，请刷新学期依据后重试' : '影响预览与当前学期不匹配，请重新预览'
    },
    async submit() {
      if (!this.termId || !this.editable || !this.previewCurrent || this.preview.canSave !== true) return
      this.formError = ''
      if (!Number.isInteger(Number(this.form.teachingWeeks)) || this.form.teachingWeeks < 1 || this.form.teachingWeeks > 30) {
        this.formError = '教学周总数须为 1—30 之间的整数'
        return
      }
      if (this.form.examWeekStart && Number(this.form.examWeekStart) > Number(this.form.teachingWeeks)) {
        this.formError = '考试周开始周次不能超过教学周总数'
        return
      }
      this.saving = true
      const termId = this.termId, context = this.contextKey(), signature = this.signature
      const res = await termApi.update(termId, { ...this.payload(), expectedVersion: this.detail.version })
      if (this.disposed || context !== this.contextKey()) return
      this.saving = false
      if (signature !== this.signature) return
      if (res.code === 0) {
        if (String(res.data?.termId) !== String(termId) || !Number.isInteger(res.data?.version)) { this.formError = '保存回执不完整，请核对学期最新依据'; this.invalidatePreview(); return }
        this.detail = res.data; this.hydrateForm(res.data)
        this.workspaceLoaded = true; this.versionConflict = false; this.recoveryComparison = []; this.recoveryError = ''
        window.__SAAS_DIRTY_FORM_GUARD__?.markSaved?.()
        toast.success('教学周配置已保存')
        await this.refreshTermCatalog()
      } else {
        this.invalidatePreview()
        this.versionConflict = res.bizCode === 'APPROVAL_VERSION_CONFLICT'
        this.formError = res.message || '保存失败'
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/foundation-workspace.css';
.aa-filter { display: flex; gap: 16px; align-items: center; margin-bottom: 4px; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-select {
  height: 32px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px;
}
.aa-form { display: flex; flex-direction: column; gap: 14px; max-width: 360px; }
.aa-impact { display: grid; gap: 10px; margin-top: 18px; font-size: 13px; }
.aa-recovery { display: grid; gap: 12px; margin-bottom: 18px; }
.aa-recovery p { margin: 0; }
.aa-recovery__scroll { max-width: 100%; overflow-x: auto; }
.aa-recovery table { width: 100%; border-collapse: collapse; }
.aa-recovery th, .aa-recovery td { padding: 8px; text-align: left; border-bottom: 1px solid var(--border-300, #d0d3d9); }
</style>
