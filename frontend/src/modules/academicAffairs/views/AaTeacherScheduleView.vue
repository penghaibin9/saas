<template>
  <ModulePageShell
    title="教师课表"
    subtitle="按教师工号查看当前已发布课表；教师本人仅能查看自己，教务处/学院教务可查任意教师"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item aa-filter__item--grow">
          教师
          <AppTeacherPicker v-model="teacherKey" placeholder="搜索教师姓名/工号" />
        </label>
        <AppButton v-if="selfKey" @click="teacherKey = selfKey; load()">查看本人课表</AppButton>
        <label class="aa-filter__item">
          学期
          <AppTermEntityPicker v-model="termId" placeholder="当前已发布批次" />
        </label>
        <label class="aa-filter__item">
          周次
          <input v-model.number="week" type="number" min="1" max="30" class="aa-input aa-input--sm" placeholder="全部周次" />
        </label>
        <AppButton variant="primary" :disabled="!teacherKey" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!teacherKey" title="请先输入教师工号" description="或点击「查看本人课表」" />
      <template v-else>
        <div class="aa-summary">
          <span v-if="weeklyHours" class="aa-summary__item">本学期周学时合计（近似）：<b>{{ weeklyHours }}</b></span>
          <p v-if="note" class="mp-note">{{ note }}</p>
        </div>
        <AppSectionCard :title="`教师 ${teacherKey} · 周课表`">
          <AaScheduleGrid :items="items" :slots="slots" :editable="false" @item-click="onItemClick" />
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 教师课表（/admin/academic-affairs/schedule/teacher/:teacherKey?）：13B 课表管理 Tier1 R2。
 * GET /academic-affairs/schedule/teacher/{teacherKey}?termId=&week=；教师本人仅能查看自己（403002）。
 * 教师目录暂无统一主数据表（教务域历史沿用 teacher_key 自由文本标识），沿用既有「三视图」页同款
 * 工号输入约定，不新造教师选择器接口。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppTeacherPicker, AppTermEntityPicker } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTeacherScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppTeacherPicker, AppTermEntityPicker, AaScheduleGrid },
  props: { ctx: { type: Object, required: true } },
  data() {
    const u = currentUserFromToken() || {}
    return {
      teacherKey: this.$route.params.teacherKey || '',
      selfKey: String(u.userId || u.loginName || ''),
      termId: '', week: null,
      slots: [], items: [], weeklyHours: 0, note: '', loading: false, error: ''
    }
  },
  created() {
    this.loadSlots()
    if (this.teacherKey) this.load()
  },
  methods: {
    onItemClick(it) {
      toast.success(`${it.courseName || ''} · ${it.className || ''} · ${it.classroom || ''} · ${it.startWeek}-${it.endWeek}周`)
    },
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async load() {
      if (!this.teacherKey) return
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTeacherSchedule(this.teacherKey, {
        termId: this.termId || undefined, week: this.week || undefined
      })
      this.loading = false
      if (res.code === 0) {
        this.items = res.data.items || []
        this.weeklyHours = res.data.weeklyHours || 0
        this.note = res.data.note || ''
        this.$router.replace(`/admin/academic-affairs/schedule/teacher/${this.teacherKey}`).catch(() => {})
      } else {
        this.error = res.message
        this.items = []
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-filter__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); min-width: 160px; }
.aa-input, .aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 120px; }
.aa-summary { margin-bottom: 4px; }
.aa-summary__item { font-size: 13px; color: var(--text-700, #4e5969); }
</style>
