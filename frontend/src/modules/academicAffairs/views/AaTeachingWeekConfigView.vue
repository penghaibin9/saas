<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="教学周配置"
    subtitle="按学校校历配置教学周与考试开始周；草稿学期可修改。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="$route.query.returnToken" :disabled="saving" @click="academicFlow?.back($route.query.returnToken, '/admin/academic-affairs/terms')">返回原位置</AppButton>
      <AppButton variant="primary" :disabled="!editable" :loading="previewing" @click="previewChange">预览周次影响</AppButton>
    </template>
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">
          学期
          <AppTermEntityPicker v-model="termId" :options="termOptions" :disabled="saving || termsLoading" placeholder="选择学期" @change="onTermChange" />
        </label>
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
          v-if="current.status !== 'DRAFT'"
          type="warning"
          description="该学期的教学周已锁定。解冻只恢复业务办理，不会恢复草稿编辑权限。"
        />
        <AaCalendarMonth :term="current" :weeks="weeks" week-mode title="教学周配置" :loading="workspaceLoading" :error="workspaceError" @retry="loadWorkspace" />
        <AppSectionCard title="调整对照与影响" :subtitle="`学期 ${termId} · ${statusLabel(current.status)} · 定义版本 ${detail?.version ?? '待核对'}`">
          <div class="aa-form">
            <AppFormItem label="教学周总数" required>
              <AppNumberInput v-model="form.teachingWeeks" :min="1" :max="30" :disabled="!editable" />
            </AppFormItem>
            <AppFormItem label="考试周开始周次" hint="留空表示暂不设置考试周">
              <AppNumberInput v-model="form.examWeekStart" :min="1" :max="30" :disabled="!editable" />
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

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '已发布', FROZEN: '已冻结', ARCHIVED: '已归档' }

export default {
  name: 'AaTeachingWeekConfigView',
  components: { ModulePageShell, EmptyState, ErrorState, LoadingState, AppSectionCard, AppFormItem, AppNumberInput, AppInlineAlert, AppTermEntityPicker, AppButton, AaCalendarMonth },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      termsLoading: true, disposed: false, catalogVersion: 0,
      workspaceVersion: 0, workspaceLoading: false, workspaceError: '', detail: null, weeks: [],
      preview: null, previewSignature: '', previewing: false,
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
    editable() {
      return !this.termsLoading && !this.workspaceLoading && !this.workspaceError && !this.saving && !this.previewing && Number.isInteger(this.detail?.version) && matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.term.manage') && !!this.current && this.current.status === 'DRAFT'
    }
  },
  created() {
    this.refreshTermCatalog()
  },
  watch: {
    '$route.query.termId'(id) {
      if (String(id || '') === String(this.termId || '')) return
      this.termId = typeof id === 'string' && this.terms.some(term => String(term.termId) === id) ? id : ''
      this.onTermChange()
      if (!this.termId) this.catalogError = '入口指定的学期不可用，请重新选择学期。'
    },
    ctx: { deep: true, handler() { this.catalogVersion++; this.refreshTermCatalog() } }
  },
  beforeRouteUpdate(to, from, next) { if (this.saving) { toast.warning('正在保存教学周，请稍候再切换'); next(false) } else next() },
  beforeUnmount() { this.disposed = true; this.catalogVersion++; this.workspaceVersion++ },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || (s ? '状态待确认' : '') },
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
          this.termId = ''; this.onTermChange(); this.catalogError = '入口指定的学期不可用，请重新选择学期。'; this.termsLoading = false; return
        }
        const selected = explicit || resolved
        if (selected) {
          this.termId = selected.termId
          this.onTermChange()
        }
      } catch (error) {
        if (version !== this.catalogVersion || this.disposed || scope !== JSON.stringify(this.ctx)) return
        this.catalogError = error.message || '学期数据加载失败'
      }
      this.termsLoading = false
    },
    onTermChange() {
      this.workspaceVersion++; this.detail = null; this.weeks = []; this.preview = null; this.previewSignature = ''; this.previewing = false
      this.catalogError = ''
      if (this.termId && String(this.$route.query.termId || '') !== String(this.termId)) this.$router.replace?.({ query: { ...this.$route.query, termId: String(this.termId) } })
      this.formError = ''
      const t = this.current
      this.form = {
        teachingWeeks: t ? t.teachingWeeks || null : null,
        examWeekStart: t ? t.examWeekStart || null : null
      }
      if (t) this.loadWorkspace()
    },
    async loadWorkspace() {
      const version = ++this.workspaceVersion, id = this.termId, scope = JSON.stringify(this.ctx)
      this.workspaceLoading = true; this.workspaceError = ''; this.preview = null
      const [detail, weeks] = await Promise.all([termApi.get(id), academicAffairsApi.getTermWeeks(id)])
      if (this.disposed || version !== this.workspaceVersion || String(id) !== String(this.termId) || scope !== JSON.stringify(this.ctx)) return
      this.workspaceLoading = false
      if (detail.code !== 0 || String(detail.data?.termId) !== String(id) || weeks.code !== 0) {
        this.workspaceError = detail.message || weeks.message || '学期依据读取失败'; this.detail = null; return
      }
      this.detail = detail.data; this.weeks = weeks.data || []
      this.academicFlow?.restorePosition()
    },
    payload() { return { teachingWeeks: Number(this.form.teachingWeeks), examWeekStart: this.form.examWeekStart ? Number(this.form.examWeekStart) : null } },
    async previewChange() {
      if (!this.editable) return
      const signature = this.signature, id = this.termId
      this.previewing = true; this.preview = null; this.formError = ''
      const res = await termApi.preview(id, this.payload())
      if (this.disposed || signature !== this.signature) { if (!this.disposed) this.previewing = false; return }
      this.previewing = false
      if (res.code === 0 && String(res.data?.termId) === String(id)) { this.preview = res.data; this.previewSignature = signature }
      else this.formError = res.message || '影响预览失败，请刷新学期依据后重试'
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
      const termId = this.termId, version = this.catalogVersion, scope = JSON.stringify(this.ctx)
      const res = await termApi.update(termId, { ...this.payload(), expectedVersion: this.detail.version })
      if (this.disposed || version !== this.catalogVersion || termId !== this.termId || scope !== JSON.stringify(this.ctx)) { if (!this.disposed) this.saving = false; return }
      this.saving = false
      if (res.code === 0) {
        toast.success('教学周配置已保存')
        this.refreshTermCatalog()
      } else {
        this.preview = null; this.previewSignature = ''
        if (['DATA_CONFLICT', 'APPROVAL_VERSION_CONFLICT'].includes(res.code)) await this.loadWorkspace()
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
</style>
