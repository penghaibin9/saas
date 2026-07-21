<template>
  <ModulePageShell
    title="教室课表"
    subtitle="按教室字典选择教室，查看当前已发布课表占用情况（教务处/学院教务只读）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item aa-filter__item--grow">
          教室
          <AppRemoteSelect v-model="classroomId" :remote-search="searchRooms" placeholder="搜索楼栋/教室编号" @change="onRoomChange" />
        </label>
        <label class="aa-filter__item">
          学期
          <AppSelect v-model="termId" :options="termOptions" placeholder="" />
        </label>
        <label class="aa-filter__item">
          周次
          <input v-model.number="week" type="number" min="1" max="30" class="aa-input aa-input--sm" placeholder="全部周次" />
        </label>
        <AppButton variant="primary" :disabled="!classroomId" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!classroomId" title="请先选择教室" description="搜索并选择教室后自动加载课表" />
      <template v-else>
        <p v-if="note" class="mp-note">{{ note }}</p>
        <p class="mp-note">按教室字典拼装文本精确匹配课表教室快照；手工排课时若教室文本与字典不一致可能查不全（与教室预约模块同口径）。</p>
        <AppSectionCard :title="classroomText ? `${classroomText} · 周课表` : '教室课表'">
          <AaScheduleGrid :items="items" :slots="slots" :editable="false" @item-click="onItemClick" />
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 教室课表（/admin/academic-affairs/schedule/room/:classroomId?）：13B 课表管理 Tier1 R2。
 * GET /academic-affairs/schedule/room/{classroomId}?termId=&week=；权限复用既有教室字典
 * academicAffairs.classroom.view，不新增教室专属 key。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppRemoteSelect, AppSelect } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaRoomScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppRemoteSelect, AppSelect, AaScheduleGrid },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      classroomId: this.$route.params.classroomId || '',
      classroomText: '', termId: '', week: null,
      terms: [], slots: [], items: [], note: '', loading: false, error: ''
    }
  },
  computed: {
    termOptions() {
      return [
        { value: '', label: '当前已发布批次' },
        ...this.terms.map((t) => ({ value: t.termId, label: `${t.yearCode} 第 ${t.termNo} 学期` }))
      ]
    }
  },
  created() {
    this.loadTerms()
    this.loadSlots()
    if (this.classroomId) this.load()
  },
  methods: {
    async searchRooms(keyword) {
      const res = await academicAffairsApi.getClassroomOptions(keyword)
      if (res.code !== 0) return []
      return (res.data || []).map((c) => ({ label: c.label || `${c.buildingName || ''}${c.roomCode || ''}`, value: c.classroomId }))
    },
    onRoomChange(_v, items) {
      this.classroomText = (items && items[0] && items[0].label) || ''
      this.$router.replace(`/admin/academic-affairs/schedule/room/${this.classroomId}`).catch(() => {})
      this.load()
    },
    onItemClick(it) {
      toast.success(`${it.courseName || ''} · ${it.className || ''} · ${it.teacherName || ''} · ${it.startWeek}-${it.endWeek}周`)
    },
    async loadTerms() {
      const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
      if (res.code === 0) this.terms = res.data.list
    },
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async load() {
      if (!this.classroomId) return
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRoomSchedule(this.classroomId, {
        termId: this.termId || undefined, week: this.week || undefined
      })
      this.loading = false
      if (res.code === 0) {
        this.items = res.data.items || []
        this.note = res.data.note || ''
        if (res.data.classroomText) this.classroomText = res.data.classroomText
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
