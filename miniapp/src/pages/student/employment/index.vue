<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="e">
        <!-- 去向状态 -->
        <view class="em__hero card">
          <view class="row-between">
            <text class="t-lg t-bold">就业去向</text>
            <MobileStatusTag :status="e.reportStatus" />
          </view>
          <text class="em__hero-stage">{{ e.stageText }}</text>
          <view class="em__intent">
            <view class="em__intent-item"><text class="em__intent-k">意向类型</text><text class="em__intent-v">{{ e.intention.type }}</text></view>
            <view class="em__intent-item"><text class="em__intent-k">目标行业</text><text class="em__intent-v">{{ e.intention.industry }}</text></view>
            <view class="em__intent-item"><text class="em__intent-k">意向城市</text><text class="em__intent-v">{{ e.intention.city }}</text></view>
            <view class="em__intent-item"><text class="em__intent-k">期望薪资</text><text class="em__intent-v">{{ e.intention.salaryExpect }}</text></view>
          </view>
          <button class="btn btn-primary btn-block" style="margin-top:12px;" @click="report">填报 / 更新就业去向</button>
        </view>

        <!-- 去向流程 -->
        <view class="section-head"><text class="section-head__title">去向办理流程</text></view>
        <view class="card"><MobileTimeline :nodes="e.steps" /></view>

        <!-- 岗位推荐 -->
        <view class="section-head">
          <text class="section-head__title">为你推荐</text>
          <text class="section-head__more">按意向匹配</text>
        </view>
        <view class="stack-sm">
          <view v-for="j in e.recommendedJobs" :key="j.id" class="em__job card" @click="toast('查看岗位：' + j.post)">
            <view class="row-between">
              <text class="t-md t-bold">{{ j.post }}</text>
              <text class="em__job-salary">{{ j.salary }}</text>
            </view>
            <view class="row-between" style="margin-top:6px;">
              <text class="em__job-company">{{ j.company }} · {{ j.city }}</text>
              <text class="em__job-match">匹配 {{ j.match }}%</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'
export default {
  data() { return { e: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    toast,
    load() {
      this.state = 'loading'
      studentApi.getEmployment().then((d) => { this.e = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    report() { toast('去向填报入口即将开放，可先联系就业指导老师登记') }
  }
}
</script>

<style scoped>
.em__hero-stage { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin: 6px 0 var(--space-3); }
.em__intent { display: flex; flex-wrap: wrap; }
.em__intent-item { width: 50%; padding: 8px 0; }
.em__intent-k { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.em__intent-v { display: block; font-size: var(--font-size-base); color: var(--text-primary); margin-top: 2px; }
.em__job-salary { font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); color: var(--danger-500); }
.em__job-company { font-size: var(--font-size-sm); color: var(--text-secondary); }
.em__job-match { font-size: var(--font-size-xs); color: var(--success-600); background: var(--success-50); padding: 2px 8px; border-radius: var(--radius-full); }
</style>
