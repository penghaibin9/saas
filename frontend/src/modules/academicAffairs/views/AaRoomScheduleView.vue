<template>
  <ModulePageShell
    title="教室课表"
    subtitle="选择教室查看已发布的课程安排。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <AaScheduleObjectBar
        :name="classroomText || '课表查询范围'"
        :identity="termId ? '按所选学期查询' : '使用默认学期'"
        source="维修和预约情况请到教学资源占用页核对。"
        :status="classroomId ? '仅供查看' : '未选择教室'"
        :owner="ctx.currentRole.roleName || '教务排课岗'"
        next-owner="排课岗核对资源后继续编排"
      />
      <div class="aa-filter">
        <label class="aa-filter__item aa-filter__item--grow">
          教室
          <AppClassroomPicker v-model="classroomId" placeholder="搜索楼栋/教室编号" @change="onRoomChange" />
        </label>
        <label class="aa-filter__item">
          学期
          <AppTermEntityPicker v-model="termId" placeholder="默认学期" />
        </label>
        <label class="aa-filter__item">
          周次
          <input v-model.number="week" type="number" min="1" max="30" class="aa-input aa-input--sm" placeholder="全部周次" />
        </label>
        <AppButton variant="primary" :disabled="!classroomId" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!classroomId" title="请先选择教室" description="可按楼栋或教室编号搜索" />
      <template v-else>
        <p v-if="note" class="mp-note">{{ note }}</p>
        <p class="mp-note">课表中的教室名称须与教室资料一致，否则可能漏查。</p>
        <AppSectionCard title="课程安排">
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
import { AppSectionCard, AppClassroomPicker, AppTermEntityPicker } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import AaScheduleObjectBar from '../components/AaScheduleObjectBar.vue'

export default {
  name: 'AaRoomScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppClassroomPicker, AppTermEntityPicker, AaScheduleGrid, AaScheduleObjectBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      classroomId: this.$route.params.classroomId || '',
      classroomText: '', termId: '', week: null,
      slots: [], items: [], note: '', loading: false, error: ''
    }
  },
  created() {
    this.loadSlots()
    if (this.classroomId) this.load()
  },
  methods: {
    onRoomChange(_v, items) {
      this.classroomText = (items && items[0] && items[0].label) || ''
      this.$router.replace(`/admin/academic-affairs/schedule/room/${this.classroomId}`).catch(() => {})
      this.load()
    },
    onItemClick(it) {
      toast.success(`${it.courseName || ''} · ${it.className || ''} · ${it.teacherName || ''} · ${it.startWeek}-${it.endWeek}周`)
    },
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async load() {
      if (!this.classroomId) return
      this.loading = true
      this.error = ''
      try {
        const res = await academicAffairsApi.getRoomSchedule(this.classroomId, {
          termId: this.termId || undefined, week: this.week || undefined
        })
        if (res.code === 0) {
          this.items = res.data?.items || []
          this.note = res.data?.note || ''
          if (res.data?.classroomText) this.classroomText = res.data.classroomText
        } else {
          this.error = res.message || '教室课表读取失败'
          this.items = []
        }
      } catch (error) {
        this.error = error?.message || '网络连接中断，未能读取教室课表'
        this.items = []
      } finally { this.loading = false }
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
