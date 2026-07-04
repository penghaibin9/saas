<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审批" description="学生提交的请假、证明等申请会出现在这里。" />
        <view v-else class="stack">
          <view v-for="a in list" :key="a.id" class="ap card">
            <view class="row-between">
              <view class="flex-1">
                <view class="row" style="gap:6px;">
                  <text class="t-md t-bold">{{ a.title }}</text>
                  <text v-if="a.level === 'high'" class="ap__urgent">加急</text>
                </view>
                <text class="ap__type">{{ a.type }}</text>
              </view>
              <MobileStatusTag :status="a.status" />
            </view>

            <view class="ap__student">
              <text class="ap__student-avatar">{{ a.student.slice(0,1) }}</text>
              <text class="t-sm">{{ a.student }} · {{ a.className }}</text>
              <text class="ap__time">提交 {{ a.submitTime.slice(5, 16) }}</text>
            </view>

            <view class="ap__fields">
              <view v-for="(f, i) in a.fields" :key="i" class="ap__field">
                <text class="ap__field-k">{{ f.label }}</text>
                <text class="ap__field-v flex-1">{{ f.value }}</text>
              </view>
            </view>

            <!-- 审批流 -->
            <view class="ap__flow">
              <view v-for="(n, i) in a.flow" :key="i" class="ap__flow-node" :class="{ 'is-done': n.done, 'is-current': n.current }">
                <view class="ap__flow-dot" />
                <text class="ap__flow-name">{{ n.node }}</text>
                <text class="ap__flow-time">{{ n.time }}</text>
              </view>
            </view>

            <view v-if="a.status === 'PENDING_REVIEW'" class="ap__actions">
              <button class="btn btn-ghost flex-1" @click="act(a, 'return')">退回</button>
              <button class="ap__reject flex-1" @click="act(a, 'reject')">驳回</button>
              <button class="ap__approve flex-1" @click="act(a, 'approve')">通过</button>
            </view>
            <view v-else class="ap__done">
              <text class="ap__done-text">已{{ a.status === 'APPROVED' ? '通过' : a.status === 'REJECTED' ? '驳回' : '处理' }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'
export default {
  data() { return { list: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      teacherApi.getApprovals().then((d) => { this.list = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    act(a, type) {
      const label = { approve: '通过', reject: '驳回', return: '退回' }[type]
      const need = type !== 'approve'
      uni.showModal({
        title: label + '审批', editable: need, placeholderText: need ? '请填写' + label + '意见' : '',
        content: need ? '' : '确认通过「' + a.title + '」？',
        success: (r) => {
          if (!r.confirm) return
          a.status = type === 'approve' ? 'APPROVED' : type === 'reject' ? 'REJECTED' : 'RETURNED'
          toast('已' + label + '（演示）')
        }
      })
    }
  }
}
</script>

<style scoped>
.ap__urgent { font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 6px; border-radius: var(--radius-sm); }
.ap__type { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; }
.ap__student { display: flex; align-items: center; gap: var(--space-2); margin: var(--space-3) 0; }
.ap__student-avatar { width: 26px; height: 26px; border-radius: var(--radius-full); background: var(--teacher-50); color: var(--teacher-700); display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xs); }
.ap__time { margin-left: auto; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ap__fields { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.ap__field { display: flex; gap: var(--space-3); padding: 5px 0; }
.ap__field-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 76px; flex-shrink: 0; }
.ap__field-v { font-size: var(--font-size-sm); color: var(--text-primary); }
.ap__flow { display: flex; margin: var(--space-3) 0; }
.ap__flow-node { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; position: relative; }
.ap__flow-node::before { content: ''; position: absolute; top: 5px; left: -50%; width: 100%; height: 2px; background: var(--border-base); z-index: 0; }
.ap__flow-node:first-child::before { display: none; }
.ap__flow-node.is-done::before { background: var(--success-500); }
.ap__flow-dot { width: 12px; height: 12px; border-radius: var(--radius-full); background: var(--gray-300); z-index: 1; }
.ap__flow-node.is-done .ap__flow-dot { background: var(--success-500); }
.ap__flow-node.is-current .ap__flow-dot { background: var(--teacher-600); box-shadow: 0 0 0 3px var(--teacher-50); }
.ap__flow-name { font-size: var(--font-size-xs); color: var(--text-secondary); }
.ap__flow-time { font-size: 10px; color: var(--text-tertiary); }
.ap__actions { display: flex; gap: var(--space-2); }
.ap__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ap__reject::after { border: none; }
.ap__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.ap__approve::after { border: none; }
.ap__done { text-align: center; padding: var(--space-2); }
.ap__done-text { font-size: var(--font-size-sm); color: var(--text-tertiary); }
</style>
