<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="缓考审批" subtitle="待我审批" show-back />

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审批缓考申请"
          description="轮到你审批的缓考申请会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="x in list" :key="x.deferId" class="card ed" :class="{ 'is-target': isTarget(x) }">
            <text v-if="isTarget(x)" class="ed__target">从工作台直达的申请</text>
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.studentName || '—' }}</text>
                <text class="ed__sub">{{ x.courseName || '' }}</text>
              </view>
              <MobileStatusTag :label="statusLabel(x.status)" type="warning" />
            </view>
            <view class="ed__row" v-if="x.reasonType"><text class="ed__row-k">原因类型</text><text class="flex-1 t-sm">{{ x.reasonType }}</text></view>
            <view class="ed__row" v-if="x.reason"><text class="ed__row-k">事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
            <view class="ed__row"><text class="ed__row-k">申请时间</text><text class="flex-1 t-sm">{{ fmt(x.applyAt) }}</text></view>
            <view class="ed__actions">
              <button class="ed__reject flex-1" :disabled="acting" @click="doAct(x, 'RETURN')">退回</button>
              <button class="ed__reject flex-1" :disabled="acting" @click="doAct(x, 'REJECT')">驳回</button>
              <button class="ed__approve flex-1" :disabled="acting" @click="doAct(x, 'APPROVE')">通过</button>
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

const STATUS_LABELS = { COUNSELOR_REVIEW: '辅导员审批中', TEACHER_CONFIRM: '任课教师确认中' }

export default {
  data() { return { list: [], state: 'loading', acting: false, targetDeferId: '' } },
  onLoad(options = {}) {
    this.targetDeferId = String(options.id || options.deferId || '')
    this.load()
  },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    fmt(v) { return (v || '').slice(0, 16).replace('T', ' ') },
    statusLabel(s) { return STATUS_LABELS[s] || s },
    isTarget(item) { return !!this.targetDeferId && String(item.deferId || item.id || '') === this.targetDeferId },
    focusTarget(rows) {
      if (!this.targetDeferId) return rows
      const index = rows.findIndex((item) => this.isTarget(item))
      if (index < 0) {
        toast('该缓考申请不存在、已处理或不在当前审批范围内')
        this.targetDeferId = ''
        return rows
      }
      if (index === 0) return rows
      return [rows[index], ...rows.slice(0, index), ...rows.slice(index + 1)]
    },
    load(done) {
      this.state = 'loading'
      teacherApi.getAcademicDeferPending().then((d) => {
        this.list = this.focusTarget((d && (d.list || d.items)) || [])
        this.state = 'ready'
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    _err(e, label) {
      const code = e && String(e.code)
      if (code === 'APPROVAL_VERSION_CONFLICT' || code.startsWith('409')) {
        toast((e && e.message) || '该申请已处理，正在刷新')
        this.targetDeferId = ''
        this.load()
      } else if (code && code.startsWith('403')) toast((e && e.message) || '无权处理该申请')
      else toast((e && e.message) || label + '失败，请重试')
    },
    doAct(x, action) {
      if (this.acting) return
      const needReason = action !== 'APPROVE'
      const title = { APPROVE: '通过缓考申请', RETURN: '退回补材料', REJECT: '驳回缓考申请' }[action]
      uni.showModal({
        title, editable: needReason, placeholderText: needReason ? '请填写原因（≥5 字）' : '', content: '',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (needReason && reason.length < 5) { toast('原因至少 5 个字'); return }
          this.acting = true
          teacherApi.reviewAcademicDefer(x.deferId, action, reason)
            .then(() => { toast(action === 'APPROVE' ? '已通过' : action === 'RETURN' ? '已退回' : '已驳回'); this.targetDeferId = ''; this.load() })
            .catch((e) => this._err(e, '审批'))
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.ed { display: flex; flex-direction: column; gap: var(--space-2); }
.ed.is-target { border: 1px solid var(--teacher-500); box-shadow: 0 0 0 2px var(--teacher-50); }
.ed__target { color: var(--teacher-700); font-size: var(--font-size-xs); font-weight: 600; }
.ed__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ed__row { display: flex; gap: var(--space-3); }
.ed__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 64px; flex-shrink: 0; }
.ed__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.ed__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ed__reject::after { border: none; }
.ed__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.ed__approve::after { border: none; }
</style>
