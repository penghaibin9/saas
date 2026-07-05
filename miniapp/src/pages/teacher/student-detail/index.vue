<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="学生详情" subtitle="学生360摘要" :show-back="true" />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="s">
        <!-- 头部 -->
        <view class="sd__head card">
          <view class="sd__avatar">{{ s.base.name.slice(0,1) }}</view>
          <view class="flex-1">
            <view class="row" style="gap:6px;">
              <text class="t-lg t-bold">{{ s.base.name }}</text>
              <MobileRiskTag v-if="s.risk" :level="s.risk.level" />
            </view>
            <text class="sd__sub">{{ s.base.className }} · {{ s.base.major }} · {{ s.base.stage }}</text>
            <view class="sd__tags">
              <text v-for="t in (s.tags||[])" :key="t" class="sd__tag">{{ t }}</text>
            </view>
          </view>
          <view class="sd__call" @click="call">☎</view>
        </view>

        <!-- 风险提示 -->
        <MobileInlineAlert v-if="s.risk" type="danger" :title="'风险等级：' + riskText(s.risk.level)"
          :description="(s.risk.types||[]).join('、') + ' · 自 ' + s.risk.since" />

        <!-- 待处理事项 -->
        <template v-if="s.pendingItems && s.pendingItems.length">
          <view class="section-head"><text class="section-head__title">待处理事项</text></view>
          <view class="stack-sm">
            <view v-for="p in s.pendingItems" :key="p.id" class="sd__pending card">
              <text class="t-md flex-1">{{ p.title }}</text>
              <text class="sd__pending-btn" @click="toast(p.action + '（演示）')">{{ p.action }}</text>
            </view>
          </view>
        </template>

        <!-- 实习信息 -->
        <template v-if="s.intern">
          <view class="section-head"><text class="section-head__title">实习信息</text></view>
          <view class="card">
            <view class="sd__row"><text class="sd__k">实习企业</text><text class="sd__v">{{ s.intern.company }}</text></view>
            <view class="sd__row"><text class="sd__k">实习岗位</text><text class="sd__v">{{ s.intern.post }}</text></view>
            <view class="sd__row"><text class="sd__k">校内导师</text><text class="sd__v">{{ s.intern.mentor }}</text></view>
            <view class="sd__row"><text class="sd__k">企业导师</text><text class="sd__v">{{ s.intern.companyMentor }}</text></view>
          </view>
        </template>

        <!-- 动态时间线 -->
        <view class="section-head"><text class="section-head__title">学生动态</text></view>
        <view class="card">
          <view v-for="a in s.timeline" :key="a.id" class="sd__act">
            <view class="sd__act-dot" :class="`is-${a.type}`" />
            <view class="flex-1">
              <text class="sd__act-text">{{ a.text }}</text>
              <text class="sd__act-time">{{ a.time }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="s">
      <button class="btn btn-ghost flex-1" @click="record">记录联系</button>
      <button class="btn btn-primary flex-1" style="background:var(--teacher-600);" @click="care">创建关怀</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'
const RISK = { LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '严重' }
export default {
  data() { return { s: null, state: 'loading', id: '' } },
  onLoad(q) { this.id = (q && q.id) || 'S002'; this.load() },
  methods: {
    toast,
    riskText(l) { return RISK[l] || l },
    load() {
      this.state = 'loading'
      // 只走 mobile 范围接口（不再拉 PC 全列表）；403/404 明确提示，不白屏
      teacherApi.getStudent360(this.id).then((detail) => {
        if (detail) { this.s = detail; this.state = 'ready' } else { this.s = null; this.state = 'empty' }
      }).catch((e) => {
        const code = e && e.code ? String(e.code) : ''
        if (code.startsWith('403')) { toast('无权限查看该学生'); this.state = 'empty' }
        else if (code.startsWith('404')) { toast('未找到该学生'); this.state = 'empty' }
        else { this.state = 'error' }
      })
    },
    call() { uni.makePhoneCall({ phoneNumber: '13600000000', fail: () => toast('拨打学生电话（演示）') }) },
    record() { uni.showModal({ title: '记录联系', editable: true, placeholderText: '填写联系方式与结果', success: (r) => r.confirm && toast('已记录（演示）') }) },
    care() { toast('已创建关怀任务（演示）') }
  }
}
</script>

<style scoped>
.sd__head { display: flex; align-items: center; gap: var(--space-3); }
.sd__avatar { width: 50px; height: 50px; border-radius: var(--radius-full); background: var(--teacher-50); color: var(--teacher-700); display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xl); }
.sd__sub { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; }
.sd__tags { display: flex; gap: var(--space-2); margin-top: var(--space-2); }
.sd__tag { font-size: var(--font-size-xs); color: var(--teacher-700); background: var(--teacher-50); padding: 2px 8px; border-radius: var(--radius-full); }
.sd__call { width: 40px; height: 40px; border-radius: var(--radius-full); background: var(--teacher-600); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.sd__pending { display: flex; align-items: center; gap: var(--space-3); }
.sd__pending-btn { font-size: var(--font-size-sm); color: #fff; background: var(--teacher-600); border-radius: var(--radius-md); padding: 6px 14px; }
.sd__row { display: flex; justify-content: space-between; padding: 8px 0; }
.sd__k { font-size: var(--font-size-base); color: var(--text-tertiary); }
.sd__v { font-size: var(--font-size-base); color: var(--text-primary); }
.sd__act { display: flex; gap: var(--space-3); padding: 8px 0; }
.sd__act-dot { width: 10px; height: 10px; border-radius: var(--radius-full); margin-top: 5px; flex-shrink: 0; background: var(--gray-300); }
.sd__act-dot.is-risk { background: var(--danger-500); }
.sd__act-dot.is-warn { background: var(--warning-500); }
.sd__act-dot.is-ok { background: var(--success-500); }
.sd__act-text { font-size: var(--font-size-base); color: var(--text-primary); }
.sd__act-time { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
</style>
