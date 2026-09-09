<template>
  <ModulePageShell
    class="aa-foundation-workspace"
    title="教学周配置"
    subtitle="按学校校历配置教学周与考试开始周；草稿学期可修改。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
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

      <template v-else-if="current">
        <AppInlineAlert
          v-if="current.status !== 'DRAFT'"
          type="warning"
          description="该学期的教学周已锁定。解冻只恢复业务办理，不会恢复草稿编辑权限。"
        />
        <AppSectionCard title="教学周配置">
          <div class="aa-form">
            <AppFormItem label="教学周总数" required>
              <AppNumberInput v-model="form.teachingWeeks" :min="1" :max="30" :disabled="!editable" />
            </AppFormItem>
            <AppFormItem label="考试周开始周次" hint="留空表示暂不设置考试周">
              <AppNumberInput v-model="form.examWeekStart" :min="1" :max="30" :disabled="!editable" />
            </AppFormItem>
            <AppInlineAlert v-if="formError" type="danger" :description="formError" />
          </div>
          <template #footer>
            <AppButton variant="primary" :disabled="!editable" :loading="saving" @click="submit">保存教学周配置</AppButton>
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
import { loadAcademicTermCatalog } from '@/modules/academicAffairs/pickerAdapters'
import { toast } from '@/utils/toast'
import { matchPermission } from '@/config/navPlan'

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '进行中', FROZEN: '已冻结', ARCHIVED: '已归档' }

export default {
  name: 'AaTeachingWeekConfigView',
  components: { ModulePageShell, EmptyState, ErrorState, LoadingState, AppSectionCard, AppFormItem, AppNumberInput, AppInlineAlert, AppTermEntityPicker, AppButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      termsLoading: true,
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
      return !this.termsLoading && !this.saving && matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.term.manage') && !!this.current && this.current.status === 'DRAFT'
    }
  },
  created() {
    this.refreshTermCatalog()
  },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || (s ? '状态待确认' : '') },
    isResolvedCurrent(term) {
      return Boolean(term && this.currentContext?.termId) && String(term.termId) === String(this.currentContext.termId)
    },
    async loadCurrentContext() {
      this.currentError = ''
      const res = await academicAffairsApi.getCurrentTerm()
      if (res.code === 0) {
        this.currentContext = res.data || null
      } else {
        this.currentContext = null
        this.currentError = res.message || '当前学期解析失败'
      }
    },
    async refreshTermCatalog() {
      this.termsLoading = true
      this.catalogError = ''
      try {
        this.terms = await loadAcademicTermCatalog()
        await this.loadCurrentContext()
        const resolved = this.terms.find((t) => this.isResolvedCurrent(t))
        const selected = this.terms.find(t => String(t.termId) === String(this.termId || this.$route.query.termId || '')) || resolved || this.terms[0]
        if (selected) {
          this.termId = selected.termId
          this.onTermChange()
        }
      } catch (error) {
        this.catalogError = error.message || '学期数据加载失败'
      }
      this.termsLoading = false
    },
    onTermChange() {
      this.formError = ''
      const t = this.current
      this.form = {
        teachingWeeks: t ? t.teachingWeeks || null : null,
        examWeekStart: t ? t.examWeekStart || null : null
      }
    },
    async submit() {
      if (!this.termId || !this.editable) return
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
      const res = await academicAffairsApi.updateTeachingWeeks(this.termId, {
        teachingWeeks: Number(this.form.teachingWeeks),
        examWeekStart: this.form.examWeekStart ? Number(this.form.examWeekStart) : null
      })
      this.saving = false
      if (res.code === 0) {
        toast.success('教学周配置已保存')
        this.refreshTermCatalog()
      } else {
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
</style>
