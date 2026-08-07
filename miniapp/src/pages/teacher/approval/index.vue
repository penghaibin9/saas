<template>
  <view class="page-wrap">
    <view class="ap__hero hero-band is-teacher">
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="ap__navbar"><text class="ap__navbar-title">审批中心</text></view>
      <view class="ap__search"><text class="ap__search-icon">🔍</text><text class="ap__search-ph">搜索与已审批将在下一阶段接服务端分页</text></view>
    </view>

    <view class="ap__subtabs">
      <view class="ap__subtab" :class="{ 'is-on': sub === 'pending' }" @click="sub = 'pending'">
        待审批<text v-if="total" class="ap__subtab-badge">{{ total }}</text><text v-if="sub === 'pending'" class="ap__subtab-u" />
      </view>
      <view class="ap__subtab" :class="{ 'is-on': sub === 'done' }" @click="sub = 'done'">已审批<text v-if="sub === 'done'" class="ap__subtab-u" /></view>
      <view class="ap__subtab" :class="{ 'is-on': sub === 'mine' }" @click="sub = 'mine'">我发起的<text v-if="sub === 'mine'" class="ap__subtab-u" /></view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view v-if="sub === 'pending'" class="page-pad">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审批" description="这里只展示服务端当前分配给你的真实待办。" />
        <template v-else>
          <view class="ap__chips">
            <view class="ap__chip" :class="{ 'is-on': typeFilter === 'all' }" @click="typeFilter = 'all'">全部</view>
            <view v-for="t in typeOptions" :key="t" class="ap__chip" :class="{ 'is-on': typeFilter === t }" @click="typeFilter = t">{{ t }}</view>
          </view>

          <view class="stack">
            <view v-for="a in filteredList" :key="a.taskId" class="ap card">
              <view class="row-between">
                <view class="flex-1">
                  <view class="row ap__title-row"><text class="t-md t-bold">{{ a.title }}</text><text v-if="a.level === 'high'" class="ap__urgent">临期</text></view>
                  <text class="ap__type">{{ a.type }} · #{{ a.taskId }}</text>
                </view>
                <MobileStatusTag :status="a.status" />
              </view>

              <view class="ap__student">
                <text class="ap__student-avatar">{{ (a.student || '申').slice(0,1) }}</text>
                <text class="t-sm">{{ a.student }}<template v-if="a.className"> · {{ a.className }}</template></text>
                <text class="ap__time">{{ a.submitTime ? '提交 ' + a.submitTime.slice(5, 16) : '' }}</text>
              </view>

              <view v-if="a.fields && a.fields.length" class="ap__fields">
                <view v-for="(f, i) in a.fields" :key="i" class="ap__field"><text class="ap__field-k">{{ f.label }}</text><text class="ap__field-v flex-1">{{ f.value }}</text></view>
              </view>

              <view class="ap__semantics">
                <text class="ap__semantics-line">退回修改：流程继续，申请人可修改后重提。</text>
                <text class="ap__semantics-line is-danger">驳回终止：原流程结束，不生成原流程重提入口。</text>
              </view>

              <view v-if="a.status === 'PENDING_REVIEW'" class="ap__actions">
                <button class="btn btn-ghost flex-1" :disabled="acting || !canAct(a, 'RETURN')" @click="act(a, 'RETURN')">退回修改</button>
                <button class="ap__reject flex-1" :disabled="acting || !canAct(a, 'REJECT')" @click="act(a, 'REJECT')">驳回终止</button>
                <button class="ap__approve flex-1" :disabled="acting || !canAct(a, 'APPROVE')" @click="act(a, 'APPROVE')">通过</button>
              </view>
            </view>
          </view>
        </template>
      </view>

      <MobileGlobalState v-if="sub === 'done'" state="empty" title="已审批查询待下一阶段接入" description="A1 不用本地数组伪造历史；P1-03 将接真实服务端已办分页。" />
      <MobileGlobalState v-if="sub === 'mine'" state="empty" title="我发起的查询待下一阶段接入" description="A1 不用 mock 伪装记录；下一阶段再接真实分页合同。" />
    </MobileGlobalState>
  </view>
</template>

<script>
import { getPendingApprovals, actApproval } from '@/services/approvalApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      list: [], total: 0, state: 'loading', acting: false,
      sub: 'pending', typeFilter: 'all', statusBarHeight: 20
    }
  },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load()
  },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    typeOptions() { return [...new Set(this.list.map((a) => a.type).filter(Boolean))] },
    filteredList() { return this.typeFilter === 'all' ? this.list : this.list.filter((a) => a.type === this.typeFilter) }
  },
  methods: {
    canAct(task, action) { return Array.isArray(task.allowedActions) && task.allowedActions.includes(action) },
    load(done) {
      this.state = 'loading'
      getPendingApprovals(1, 50)
        .then((d) => {
          this.list = d.items || []
          this.total = Number(d.total || 0)
          this.state = 'ready'
        })
        .catch((e) => {
          this.state = 'error'
          const err = normalizeError(e)
          if (err.kind === 'forbidden') toast(err.text)
        })
        .finally(() => { if (done) done() })
    },
    act(task, action) {
      if (this.acting || !this.canAct(task, action)) return
      const labels = { APPROVE: '通过', RETURN: '退回修改', REJECT: '驳回终止' }
      const label = labels[action]
      const needReason = action !== 'APPROVE'
      uni.showModal({
        title: label,
        editable: needReason,
        placeholderText: action === 'RETURN' ? '请填写退回原因与修改要求' : action === 'REJECT' ? '请填写终止原流程的原因' : '',
        content: needReason ? '' : `确认通过「${task.title}」？`,
        success: async (r) => {
          if (!r.confirm || this.acting) return
          const reason = String(r.content || '').trim()
          if (needReason && !reason) { toast(action === 'RETURN' ? '请填写退回修改原因' : '请填写驳回终止原因'); return }
          this.acting = true
          try {
            const result = await actApproval(task, action, reason)
            const expectedStatus = { APPROVE: 'APPROVED', RETURN: 'RETURNED', REJECT: 'REJECTED' }[action]
            if (!result || String(result.status || '').toUpperCase() !== expectedStatus) {
              throw { code: 'BAD_RESPONSE', message: '服务端审批结果与请求动作不一致' }
            }
            toast(action === 'RETURN' ? '已退回修改，申请人可修改后重提' : action === 'REJECT' ? '已驳回终止原流程' : '审批已通过')
            // 不修改 task.status；动作成功后只重新读取服务端真实待办，下一条自然顶上来。
            await this.load()
          } catch (e) {
            const err = normalizeError(e)
            if (err.kind === 'conflict') {
              toast('该审批事实已变化，正在刷新')
              await this.load()
            } else {
              toast(err.text || `${label}失败，请重试`)
            }
          } finally {
            this.acting = false
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
.ap__search { display: flex; align-items: center; gap: var(--space-2); background: rgba(255,255,255,.94); border-radius: var(--radius-md); padding: 10px var(--space-4); margin-top: var(--space-1); color: var(--text-tertiary); font-size: var(--font-size-sm); }
.ap__subtabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.ap__subtab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.ap__subtab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.ap__subtab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.ap__subtab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.ap__chips { display: flex; gap: var(--space-2); overflow-x: auto; margin-bottom: var(--space-3); }
.ap__chip { flex-shrink: 0; font-size: var(--font-size-sm); padding: 6px 13px; border-radius: var(--radius-full); background: var(--bg-card); color: var(--text-secondary); box-shadow: var(--shadow-card); }
.ap__chip.is-on { background: var(--teacher-600); color: #fff; }
.ap__title-row { gap: 6px; }
.ap__urgent { font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 6px; border-radius: var(--radius-sm); }
.ap__type { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; }
.ap__student { display: flex; align-items: center; gap: var(--space-2); margin: var(--space-3) 0; }
.ap__student-avatar { width: 26px; height: 26px; border-radius: var(--radius-full); background: var(--teacher-50); color: var(--teacher-700); display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xs); }
.ap__time { margin-left: auto; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ap__fields { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.ap__field { display: flex; gap: var(--space-3); padding: 5px 0; }
.ap__field-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 76px; flex-shrink: 0; }
.ap__field-v { font-size: var(--font-size-sm); color: var(--text-primary); }
.ap__semantics { margin: var(--space-3) 0; padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); background: var(--gray-50); display: flex; flex-direction: column; gap: 4px; }
.ap__semantics-line { font-size: var(--font-size-xs); color: var(--text-secondary); }
.ap__semantics-line.is-danger { color: var(--danger-600); }
.ap__actions { display: flex; gap: var(--space-2); }
.ap__reject, .ap__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); }
.ap__reject { border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ap__approve { border: none; background: var(--teacher-600); color: #fff; }
.ap__reject::after, .ap__approve::after { border: none; }
button[disabled] { opacity: .45; }
</style>
