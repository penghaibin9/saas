<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="title" subtitle="按数据范围与指派人收敛" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <MobileGlobalState v-if="!list.length" state="empty" :title="'暂无' + title"
          description="有待办时会显示在这里；处理权限与 PC 学工工作台一致。" />
        <view class="stack" v-else>
          <view v-for="x in list" :key="rowKey(x)" class="card ar">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.realName || x.studentName || '—' }}</text>
                <text class="ar__sub">{{ x.studentNo || '' }} · {{ x.statusLabel || x.status || '' }}</text>
              </view>
              <MobileStatusTag :label="x.statusLabel || x.status || '待处理'" type="warning" />
            </view>
            <view class="ar__row" v-if="x.title || x.topic || x.applyLevel">
              <text class="ar__k">摘要</text>
              <text class="flex-1 t-sm">{{ x.title || x.topic || ('申请等级 ' + (x.applyLevel || '')) }}</text>
            </view>
            <view class="ar__row" v-if="x.riskLevel">
              <text class="ar__k">等级</text>
              <text class="flex-1 t-sm">{{ x.riskLevel }}</text>
            </view>

            <view class="ar__actions" v-if="kind === 'RISK_HANDLE'">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="doRiskProcess(x)">填写处置</button>
              <button class="ar__ok flex-1" :disabled="acting" @click="doRiskClose(x)">关闭</button>
            </view>
            <view class="ar__actions" v-else>
              <button class="ar__no flex-1" :disabled="acting" @click="doReview(x, 'REJECT')">驳回</button>
              <button class="ar__ok flex-1" :disabled="acting" @click="doReview(x, 'APPROVE')">通过</button>
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

const META = {
  AID_APPROVAL: { title: '困难认定待审', load: 'getAffairsAidPending', review: 'reviewAffairsAid' },
  AID_ADJUST: { title: '困难等级调整', load: 'getAffairsAidPending', review: 'reviewAffairsAid' },
  FUNDING_APPROVAL: { title: '奖助待审', load: 'getAffairsFundingPending', review: 'reviewAffairsFunding' },
  DISCIPLINE_APPROVAL: { title: '处分待审', load: 'getAffairsDisciplinePending', review: 'reviewAffairsDiscipline' },
  DISCIPLINE_REMOVE: { title: '处分解除待审', load: 'getAffairsDisciplinePending', review: 'reviewAffairsDiscipline' },
  RISK_HANDLE: { title: '风险待处置', load: 'getAffairsRiskPending' }
}

export default {
  data() {
    return { kind: 'AID_APPROVAL', list: [], state: 'loading', acting: false }
  },
  computed: {
    title() { return (META[this.kind] && META[this.kind].title) || '学工待办' }
  },
  onLoad(q) {
    this.kind = (q && q.type) || 'AID_APPROVAL'
    this.load()
  },
  methods: {
    rowKey(x) {
      return x.applyId || x.applicationId || x.caseId || x.riskId || x.id
    },
    load() {
      const m = META[this.kind]
      if (!m || !teacherApi[m.load]) { this.state = 'error'; return }
      this.state = 'loading'
      teacherApi[m.load]().then((d) => {
        let rows = (d && d.list) || []
        if (this.kind === 'AID_ADJUST') rows = rows.filter((x) => x.status === 'ADJUST_REVIEW')
        if (this.kind === 'AID_APPROVAL') {
          rows = rows.filter((x) => x.status !== 'ADJUST_REVIEW')
        }
        if (this.kind === 'DISCIPLINE_REMOVE') rows = rows.filter((x) => x.status === 'REMOVE_REVIEW')
        if (this.kind === 'DISCIPLINE_APPROVAL') {
          rows = rows.filter((x) => x.status !== 'REMOVE_REVIEW')
        }
        this.list = rows
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    _err(e, label) {
      const code = e && String(e.code)
      if (code === 'APPROVAL_VERSION_CONFLICT' || code === 'DATA_CONFLICT') {
        toast((e && e.message) || '状态已变化，正在刷新'); this.load()
      } else if (code && code.startsWith('403')) toast((e && e.message) || '无权处理')
      else toast((e && e.message) || label + '失败')
    },
    doReview(x, action) {
      const m = META[this.kind]
      const id = this.rowKey(x)
      if (!m || !m.review || !id) return
      const needReason = action === 'REJECT'
      const run = (reason) => {
        if (needReason && (!reason || reason.trim().length < 5)) {
          toast('驳回原因不少于 5 字'); return
        }
        this.acting = true
        teacherApi[m.review](id, { action, reason: reason || '' })
          .then(() => { toast(action === 'APPROVE' ? '已通过' : '已驳回'); this.load() })
          .catch((e) => this._err(e, '审批'))
          .finally(() => { this.acting = false })
      }
      if (needReason) {
        uni.showModal({
          title: '驳回原因', editable: true, placeholderText: '不少于 5 字',
          success: (r) => { if (r.confirm) run(r.content || '') }
        })
      } else run('')
    },
    doRiskProcess(x) {
      const id = x.riskId || x.id
      uni.showModal({
        title: '处置内容', editable: true, placeholderText: '不少于 5 字',
        success: (r) => {
          if (!r.confirm) return
          const content = (r.content || '').trim()
          if (content.length < 5) { toast('处置内容不少于 5 字'); return }
          this.acting = true
          teacherApi.processAffairsRisk(id, content)
            .then(() => { toast('已记录'); this.load() })
            .catch((e) => this._err(e, '处置'))
            .finally(() => { this.acting = false })
        }
      })
    },
    doRiskClose(x) {
      const id = x.riskId || x.id
      uni.showModal({
        title: '关闭结论', editable: true, placeholderText: '不少于 5 字',
        success: (r) => {
          if (!r.confirm) return
          const conclusion = (r.content || '').trim()
          if (conclusion.length < 5) { toast('关闭结论不少于 5 字'); return }
          this.acting = true
          teacherApi.closeAffairsRisk(id, conclusion)
            .then(() => { toast('已关闭'); this.load() })
            .catch((e) => this._err(e, '关闭'))
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.ar { padding: var(--space-4); }
.ar__sub { display: block; margin-top: 4px; color: var(--text-tertiary); font-size: 12px; }
.ar__row { display: flex; gap: 8px; margin-top: 8px; }
.ar__k { width: 40px; color: var(--text-tertiary); font-size: 12px; }
.ar__actions { display: flex; gap: 8px; margin-top: 12px; }
.ar__ok { background: var(--brand-primary); color: #fff; border-radius: 8px; font-size: 14px; }
.ar__no { background: #fee2e2; color: #b91c1c; border-radius: 8px; font-size: 14px; }
</style>
