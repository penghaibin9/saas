<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="我的班级" subtitle="本人担任辅导员/班主任的行政班" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <MobileGlobalState v-if="!d.items.length" state="empty" :title="d.note || '暂无负责班级'" description="如信息有误请联系系统管理员核实班级归属。" />
        <view class="list-group" v-else>
          <view v-for="c in d.items" :key="c.classId" class="list-row" @click="openClass(c)">
            <view class="flex-1">
              <text class="t-md">{{ c.className }}</text>
              <text class="mc__sub">{{ c.grade || '—' }}级 · 在校 {{ c.studentCount }} 人</text>
            </view>
            <MobileStatusTag :label="c.status === 'ACTIVE' ? '在读' : c.status" :type="c.status === 'ACTIVE' ? 'success' : 'default'" />
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
  data() { return { d: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      teacherApi.getMyClasses().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    openClass(c) { go(`/pages/teacher/my-students/index?classId=${c.classId}&className=${encodeURIComponent(c.className)}`) }
  }
}
</script>

<style scoped>
.mc__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
</style>
