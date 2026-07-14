<template>
  <view class="page-wrap">
    <view class="ap__hero hero-band is-teacher">
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="ap__navbar"><text class="ap__navbar-title">审批中心</text></view>
      <view class="ap__search"><text class="ap__search-icon">🔍</text><text class="ap__search-ph">搜索学生、审批单号</text></view>
    </view>

    <view class="ap__subtabs">
      <view class="ap__subtab" :class="{ 'is-on': sub === 'pending' }" @click="sub = 'pending'">
        待审批<text v-if="list && list.length" class="ap__subtab-badge">{{ list.length }}</text>
        <text v-if="sub === 'pending'" class="ap__subtab-u" />
      </view>
      <view class="ap__subtab" :class="{ 'is-on': sub === 'done' }" @click="sub = 'done'">已审批<text v-if="sub === 'done'" class="ap__subtab-u" /></view>
      <view class="ap__subtab" :class="{ 'is-on': sub === 'mine' }" @click="sub = 'mine'">我发起的<text v-if="sub === 'mine'" class="ap__subtab-u" /></view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list && sub === 'pending'">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审批" description="学生提交的请假、证明等申请会出现在这里。" />
        <template v-else>
          <view class="ap__chips">
            <view class="ap__chip" :class="{ 'is-on': typeFilter === 'all' }" @click="typeFilter = 'all'">全部</view>
            <view v-for="t in typeOptions" :key="t" class="ap__chip" :class="{ 'is-on': typeFilter === t }" @click="typeFilter = t">{{ t }}</view>
          </view>
          <view class="stack">
            <view v-for="a in filteredList" :key="a.id" class="ap card">
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
        </template>
      </view>
      <MobileGlobalState v-if="sub === 'done'" state="empty" title="暂无已审批记录" description="处理过的审批会显示在这里，方便追溯审批意见与时间。" />
      <MobileGlobalState v-if="sub === 'mine'" state="empty" title="暂无我发起的申请" description="你自己发起的申请（如请假、用章）会显示在这里。" />
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'
export default {
  data() { return { list: null, state: 'loading', acting: false, sub: 'pending', typeFilter: 'all', statusBarHeight: 20 } },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load()
  },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    typeOptions() {
      if (!this.list) return []
      return [...new Set(this.list.map((a) => a.type).filter(Boolean))]
    },
    filteredList() {
      if (!this.list) return []
      return this.typeFilter === 'all' ? this.list : this.list.filter((a) => a.type === this.typeFilter)
    }
  },
  methods: {
    load(done) {
      this.state = 'loading'
      teacherApi.getApprovals()
        .then((d) => { this.list = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    act(a, type) {
      if (this.acting) return
      const label = { approve: '通过', reject: '驳回', return: '退回' }[type]
      const need = type !== 'approve'
      uni.showModal({
        title: label + '审批', editable: need, placeholderText: need ? '请填写' + label + '意见' : '',
        content: need ? '' : '确认通过「' + a.title + '」？',
        success: (r) => {
          if (!r.confirm || this.acting) return
          const next = type === 'approve' ? 'APPROVED' : type === 'reject' ? 'REJECTED' : 'RETURNED'
          if (/^\d+$/.test(String(a.id))) {
            this.acting = true
            teacherApi.actApproval(a.id, type, r.content || '').then(() => {
              a.status = next
              toast('已' + label)
              this.load() // 成功后从服务器刷新列表，不依赖本地状态
            }).catch((e) => {
              if (e && String(e.code).startsWith('409')) {
                toast('该任务已被处理，正在刷新')
                this.load()
              } else if (e && String(e.code).startsWith('403')) {
                toast((e && e.message) || '没有权限处理该审批')
              } else {
                toast((e && e.message) || label + '失败，请重试')
              }
            }).finally(() => { this.acting = false })
          } else {
            // 离线兜底数据（非数字 id）：不能假装成功，提示等网络恢复
            toast('当前为离线数据，无法提交审批，请恢复网络后重试')
          }
        }
      })
    }
  }
}
</script>

<style scoped>
.ap__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.ap__navbar { height: 40px; display: flex; align-items: center; justify-content: center; }
.ap__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.ap__search { display: flex; align-items: center; gap: var(--space-2); background: rgba(255,255,255,.94); border-radius: var(--radius-md); padding: 10px var(--space-4); margin-top: var(--space-1); color: var(--text-tertiary); font-size: var(--font-size-base); }
.ap__subtabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.ap__subtab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.ap__subtab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.ap__subtab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.ap__subtab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.ap__chips { display: flex; gap: var(--space-2); overflow-x: auto; margin-bottom: var(--space-3); }
.ap__chip { flex-shrink: 0; font-size: var(--font-size-sm); padding: 6px 13px; border-radius: var(--radius-full); background: var(--bg-card); color: var(--text-secondary); font-weight: var(--font-weight-medium); box-shadow: var(--shadow-card); }
.ap__chip.is-on { background: var(--teacher-600); color: #fff; }
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
