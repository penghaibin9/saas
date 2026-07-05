<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="g && !g.hasBatch">
        <MobileGlobalState state="empty" title="当前暂无毕业设计任务" description="进入毕业设计阶段后，这里会显示课题、任务书、开题、中期、答辩等节点。" />
      </view>
      <view class="page-pad stack" v-else-if="g">
        <!-- 课题卡 -->
        <view class="gd__hero card">
          <text class="gd__hero-batch">{{ g.batch }}</text>
          <text class="gd__hero-topic">{{ g.topic }}</text>
          <text class="gd__hero-mentor">指导教师 · {{ g.mentor }}</text>
        </view>

        <!-- 当前主任务 -->
        <MobileActionCard
          :title="g.primaryAction.title"
          :description="g.primaryAction.desc"
          icon="→"
          :action-text="g.primaryAction.actionText"
          @action="submitNode"
          @click="submitNode"
        />
        <MobileInlineAlert v-if="g.returnedNote" type="danger" title="材料被退回" :description="g.returnedNote" />

        <!-- 节点进度 -->
        <view class="section-head"><text class="section-head__title">毕设节点</text></view>
        <view class="card"><MobileTimeline :nodes="g.nodes" /></view>

        <!-- 指导记录 -->
        <view class="section-head"><text class="section-head__title">指导记录</text></view>
        <view class="card stack-sm">
          <view v-for="l in g.guideLogs" :key="l.id" class="gd__log">
            <view class="gd__log-head">
              <text class="gd__log-from">{{ l.from }}</text>
              <text class="gd__log-date">{{ l.date }}</text>
            </view>
            <text class="gd__log-text">{{ l.text }}</text>
          </view>
        </view>

        <!-- 功能入口 -->
        <view class="section-head"><text class="section-head__title">毕设功能</text></view>
        <view class="gd__entries card">
          <text v-for="e in g.entries" :key="e" class="gd__entry" @click="toast(e + '：入口即将开放')">{{ e }}</text>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'
export default {
  data() { return { g: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    toast,
    load() {
      this.state = 'loading'
      studentApi.getGraduation().then((d) => { this.g = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    submitNode() { toast('「' + this.g.primaryAction.title + '」材料上传请在 PC 端毕设中心完成') }
  }
}
</script>

<style scoped>
.gd__hero-batch { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.gd__hero-topic { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); margin: 6px 0; line-height: 1.4; }
.gd__hero-mentor { font-size: var(--font-size-sm); color: var(--text-secondary); }
.gd__log { border-left: 3px solid var(--primary-100); padding-left: var(--space-3); }
.gd__log-head { display: flex; align-items: center; justify-content: space-between; }
.gd__log-from { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--brand-primary); }
.gd__log-date { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.gd__log-text { display: block; font-size: var(--font-size-base); color: var(--text-secondary); margin-top: 4px; line-height: 1.5; }
.gd__entries { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.gd__entry { font-size: var(--font-size-sm); color: var(--text-secondary); background: var(--gray-50); border: 1px solid var(--border-base); padding: 7px 12px; border-radius: var(--radius-md); }
</style>
