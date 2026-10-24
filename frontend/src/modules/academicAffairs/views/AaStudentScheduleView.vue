<template>
  <ModulePageShell
    title="学生课表"
    subtitle="选择学生查看已发布的课程安排。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <AaScheduleObjectBar
        :name="studentName || '课表查询范围'"
        :identity="[studentNo ? `学号 ${studentNo}` : '', termId ? '按所选学期查询' : '使用默认学期'].filter(Boolean).join(' · ')"
        source="包括行政班课程和本人已确认的选课。"
        :status="studentId ? '仅供查看' : '未选择学生'"
        :owner="ctx.currentRole.roleName || '教务排课岗'"
        next-owner="学生按课表上课"
      />
      <div class="aa-reg-search">
        <AppStudentPicker v-model="studentId" class="aa-input--grow" placeholder="按姓名/学号检索学生" @change="onStudentChange" />
      </div>

      <template v-if="studentId">
        <div class="aa-filter">
          <label class="aa-filter__item">
            学期
            <AppTermEntityPicker v-model="termId" placeholder="默认学期" @change="load" />
          </label>
          <label class="aa-filter__item">
            周次
            <input v-model.number="week" type="number" min="1" max="30" class="aa-input aa-input--sm" placeholder="全部周次" @keyup.enter="load" />
          </label>
          <AppButton variant="primary" @click="load">查询</AppButton>
        </div>

        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <template v-else>
          <p v-if="note" class="mp-note">{{ note }}</p>
          <AppSectionCard title="课程安排">
            <AaScheduleGrid :items="items" :slots="slots" :editable="false" @item-click="onItemClick" />
          </AppSectionCard>
        </template>
      </template>
      <EmptyState v-else title="请先选择学生" description="可按姓名或学号搜索" />
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 学生课表（/admin/academic-affairs/schedule/student/:studentId?）：13B 课表管理续工第三轮新增。
 * GET /academic-affairs/schedule/student/{studentId}?termId=&week=；数据范围按学生所在行政班收敛
 * （与班级课表同一 build_affairs_context 口径），越范围 → 403002。
 * 学生检索沿用「学生成绩单」页同款 getRoster 搜索惯例，不新造学生选择器接口。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStudentPicker, AppTermEntityPicker } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import AaScheduleObjectBar from '../components/AaScheduleObjectBar.vue'

export default {
  name: 'AaStudentScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStudentPicker, AppTermEntityPicker, AaScheduleGrid, AaScheduleObjectBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      studentId: this.$route.params.studentId || '',
      studentName: this.$route.query.name || '', studentNo: '',
      termId: '', week: null,
      slots: [], items: [], note: '', loading: false, error: ''
    }
  },
  created() {
    this.loadSlots()
    if (this.studentId) this.load()
  },
  methods: {
    onStudentChange(value, items) {
      const item = items?.[0]
      const student = item?.raw || item || {}
      this.studentName = student.realName || student.studentName || item?.label || ''
      this.studentNo = student.studentNo || ''
      if (!value) return
      this.$router.replace(`/admin/academic-affairs/schedule/student/${this.studentId}`).catch(() => {})
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
      if (!this.studentId) return
      this.loading = true
      this.error = ''
      try {
        const res = await academicAffairsApi.getStudentSchedule(this.studentId, {
          termId: this.termId || undefined, week: this.week || undefined
        })
        if (res.code === 0) {
          this.items = res.data?.items || []
          this.note = res.data?.note || ''
          if (res.data?.studentName) this.studentName = res.data.studentName
          if (res.data?.studentNo) this.studentNo = res.data.studentNo
        } else {
          this.error = res.message || '学生课表读取失败'
          this.items = []
        }
      } catch (error) {
        this.error = error?.message || '网络连接中断，未能读取学生课表'
        this.items = []
      } finally { this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-reg-search { display: flex; gap: 12px; align-items: center; margin-bottom: 4px; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input--grow { flex: 1; }
.aa-input--sm { width: 120px; }
.aa-cand-list { list-style: none; margin: 0; padding: 0; border: 1px solid var(--border-100, #f0f1f2); border-radius: 6px; }
.aa-cand-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 13px; }
.aa-cand-item:last-child { border-bottom: none; }
.aa-filter { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-filter__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); min-width: 160px; }
.aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
</style>
