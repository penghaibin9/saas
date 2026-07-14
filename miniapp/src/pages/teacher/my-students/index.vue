<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="我的学生" :subtitle="className || '本人负责班级学生'" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <MobileGlobalState v-if="!d.items.length" state="empty" :title="d.note || '暂无学生'" description="如信息有误请联系系统管理员核实班级归属。" />
        <view class="list-group" v-else>
          <view v-for="s in d.items" :key="s.studentId" class="list-row" @click="openStudent(s)">
            <view class="ms__avatar">{{ (s.name || '').slice(0, 1) }}</view>
            <view class="flex-1">
              <text class="t-md">{{ s.name }}</text>
              <text class="ms__sub">{{ s.studentNo }} · {{ s.className || '—' }}</text>
            </view>
            <MobileStatusTag :status="s.status" />
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { go } from '@/utils/nav'

export default {
  data() { return { d: null, state: 'loading', classId: '', className: '' } },
  onLoad(q) {
    this.classId = (q && q.classId) || ''
    this.className = (q && q.className) ? decodeURIComponent(q.className) : ''
    this.load()
  },
  methods: {
    load() {
      this.state = 'loading'
      teacherApi.getMyStudents(this.classId).then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    openStudent(s) { go('/pages/teacher/student-detail/index?id=' + s.studentId) }
  }
}
</script>

<style scoped>
.ms__avatar { width: 40px; height: 40px; border-radius: var(--radius-full); background: var(--teacher-50); color: var(--teacher-700); display: flex; align-items: center; justify-content: center; font-size: var(--font-size-lg); flex-shrink: 0; }
.ms__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
</style>
