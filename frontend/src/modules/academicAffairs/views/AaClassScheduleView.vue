<template>
  <ModulePageShell
    title="班级课表"
    subtitle="按班级查看当前已发布课表（自动取最近一次发布批次，周次可选过滤）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item aa-filter__item--grow">
          班级
          <AppClassPicker v-model="classId" placeholder="搜索班级名称" @change="onClassChange" />
        </label>
        <label class="aa-filter__item">
          学期
          <AppTermEntityPicker v-model="termId" placeholder="当前已发布批次" />
        </label>
        <label class="aa-filter__item">
          周次
          <input v-model.number="week" type="number" min="1" max="30" class="aa-input aa-input--sm" placeholder="全部周次" />
        </label>
        <AppButton variant="primary" :disabled="!classId" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!classId" title="请先选择班级" description="搜索并选择班级后自动加载课表" />
      <template v-else>
        <p v-if="note" class="mp-note">{{ note }}</p>
        <AppSectionCard :title="className ? `${className} · 周课表` : '班级课表'">
          <AaScheduleGrid :items="items" :slots="slots" :editable="false" @item-click="onItemClick" />
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 班级课表（/admin/academic-affairs/schedule/class/:classId?）：13B 课表管理 Tier1 R2。
 * 与「课表批次/排课」页下的「三视图」（需先选批次）不同：本页自动取当前已发布批次，
 * 面向导航菜单三级页，供教务处/学院教务/辅导员（本班）直接按班级查询。
 * GET /academic-affairs/schedule/class/{classId}?termId=&week=；越范围 → 403002。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppClassPicker, AppTermEntityPicker } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaClassScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppClassPicker, AppTermEntityPicker, AaScheduleGrid },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      classId: this.$route.params.classId || '',
      className: '', termId: '', week: null,
      slots: [], items: [], note: '', loading: false, error: ''
    }
  },
  created() {
    this.loadSlots()
    if (this.classId) this.load()
  },
  methods: {
    onClassChange(_v, items) {
      this.className = (items && items[0] && items[0].label) || ''
      this.$router.replace(`/admin/academic-affairs/schedule/class/${this.classId}`).catch(() => {})
      this.load()
    },
    onItemClick(it) {
      toast.success(`${it.courseName || ''} · ${it.teacherName || ''} · ${it.classroom || ''} · ${it.startWeek}-${it.endWeek}周`)
    },
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async load() {
      if (!this.classId) return
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getClassSchedule(this.classId, {
        termId: this.termId || undefined, week: this.week || undefined
      })
      this.loading = false
      if (res.code === 0) {
        this.items = res.data.items || []
        this.note = res.data.note || ''
        if (res.data.className) this.className = res.data.className
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
.aa-filter__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); min-width: 200px; }
.aa-filter__item--grow { flex: 1; min-width: 260px; }
.aa-input, .aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 120px; }
</style>
