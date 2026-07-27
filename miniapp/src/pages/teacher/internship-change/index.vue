<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="调岗退岗初审" subtitle="对比当前去向与拟变更内容后审核" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad ic__page" v-if="list">
        <view class="card ic__summary">
          <view class="ic__summary-main">
            <text class="ic__summary-label">待初审变更</text>
            <view class="ic__summary-value"><text>{{ list.length }}</text><text>条</text></view>
            <text class="ic__summary-note">{{ summaryConclusion }}</text>
          </view>
          <view class="ic__summary-types">
            <view><text>{{ enterpriseChangeCount }}</text><text>换单位</text></view>
            <view><text>{{ positionChangeCount }}</text><text>换岗位</text></view>
            <view><text>{{ otherChangeCount }}</text><text>其他变更</text></view>
          </view>
        </view>

        <MobileInlineAlert type="info" description="审核前重点比较当前单位/岗位与拟变更内容，并核对申请理由是否具体。通过或驳回仍按原业务流程办理。" />

        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审变更"
          description="本人指导学生发起换岗、换单位或自主实习变更后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="c in list" :key="c.id" class="card ic">
            <view class="row-between ic__head">
              <view class="flex-1 ic__identity">
                <text class="t-md t-bold">{{ c.studentName || '—' }}</text>
                <text class="ic__sub">{{ c.studentNo || '' }}</text>
              </view>
              <MobileStatusTag :label="c.statusLabel" type="warning" />
            </view>

            <view class="ic__type-row">
              <text class="ic__type-label">申请类型</text>
              <text class="ic__type-value">{{ c.changeTypeLabel || '实习去向变更' }}</text>
            </view>

            <view class="ic__compare">
              <view class="ic__compare-block">
                <text class="ic__compare-title">当前单位 / 岗位</text>
                <text class="ic__compare-value">{{ c.currentEnterprise || '—' }}</text>
                <text class="ic__compare-position">{{ c.currentPosition || '—' }}</text>
              </view>
              <view class="ic__compare-arrow"><text>变更为</text><text>↓</text></view>
              <view class="ic__compare-block is-target">
                <text class="ic__compare-title">拟变更单位 / 岗位</text>
                <text class="ic__compare-value">{{ c.targetEnterpriseName || c.currentEnterprise || '—' }}</text>
                <text class="ic__compare-position">{{ c.targetPositionName || '—' }}</text>
              </view>
            </view>

            <view class="ic__reason">
              <text class="ic__section-label">学生申请理由</text>
              <text class="ic__reason-text">{{ c.reason || '未填写具体理由' }}</text>
            </view>

            <view class="ic__next">
              <text class="ic__next-label">审核重点</text>
              <text class="ic__next-text">核对变更原因、目标单位和岗位是否真实明确；需要补充时通过驳回意见写清材料或信息要求。</text>
            </view>

            <view class="ic__actions">
              <button class="ic__reject flex-1" :disabled="acting" @click="review(c, 'REJECT')">驳回补充</button>
              <button class="ic__approve flex-1" :disabled="acting" @click="review(c, 'APPROVE')">初审通过</button>
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
  data() { return { list: null, state: 'loading', acting: false } },
  computed: {
    enterpriseChangeCount() { return (this.list || []).filter((item) => String(item.changeType || item.changeTypeLabel || '').includes('ENTERPRISE') || String(item.changeTypeLabel || '').includes('单位')).length },
    positionChangeCount() { return (this.list || []).filter((item) => String(item.changeType || item.changeTypeLabel || '').includes('POSITION') || String(item.changeTypeLabel || '').includes('岗位')).length },
    otherChangeCount() { return Math.max(0, (this.list || []).length - this.enterpriseChangeCount - this.positionChangeCount) },
    summaryConclusion() {
      if (!this.list?.length) return '当前没有需要初审的实习变更。'
      return '按申请顺序核对变更前后信息，优先处理理由不清或目标去向不完整的记录。'
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    load(done) {
      this.state = 'loading'
      teacherApi.getInternshipChangePending()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    review(c, action) {
      if (this.acting) return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回变更' : '通过变更',
        editable: true, placeholderText: reject ? '请填写驳回原因（≥5 字）' : '可填写审核意见（可选）',
        content: '',
        success: (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('驳回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.reviewInternshipChange(c.id, action, comment)
            .then(() => { toast(reject ? '已驳回' : '已通过'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code === 'DATA_CONFLICT') { toast('该申请已被处理，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) toast((e && e.message) || '不在你的数据范围内')
              else toast((e && e.message) || (reject ? '驳回' : '通过') + '失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.ic__page{display:flex;flex-direction:column;gap:var(--space-3)}.ic__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.ic__summary-main{flex:1;min-width:0}.ic__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ic__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.ic__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.ic__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.ic__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ic__summary-types{width:48%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.ic__summary-types>view{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 3px;border-left:1px solid var(--border-light);text-align:center}.ic__summary-types>view:first-child{border-left:0}.ic__summary-types text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.ic__summary-types text:last-child{font-size:10px;color:var(--text-tertiary)}.ic{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.ic__head{align-items:flex-start}.ic__identity{min-width:0}.ic__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px}.ic__type-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 11px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.ic__type-label{font-size:var(--font-size-xs);color:var(--text-tertiary)}.ic__type-value{font-size:var(--font-size-sm);font-weight:600;color:var(--teacher-700);text-align:right}.ic__compare{display:grid;grid-template-columns:1fr 48px 1fr;align-items:stretch;gap:8px}.ic__compare-block{min-width:0;padding:11px 12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50);display:flex;flex-direction:column;gap:5px}.ic__compare-block.is-target{border-color:var(--teacher-200,#bfdbfe);background:var(--teacher-50,#eff6ff)}.ic__compare-title{font-size:10px;color:var(--text-tertiary)}.ic__compare-value{font-size:var(--font-size-sm);font-weight:600;line-height:1.45;color:var(--text-primary);word-break:break-word}.ic__compare-position{font-size:var(--font-size-xs);line-height:1.45;color:var(--text-secondary);word-break:break-word}.ic__compare-arrow{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;color:var(--teacher-600)}.ic__compare-arrow text:first-child{font-size:10px}.ic__compare-arrow text:last-child{font-size:18px}.ic__reason{padding:var(--space-2) var(--space-3);border:1px solid var(--border-light);border-radius:var(--radius-md)}.ic__section-label{display:block;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ic__reason-text{display:block;margin-top:5px;font-size:var(--font-size-sm);line-height:1.6;color:var(--text-primary);white-space:pre-wrap;word-break:break-word}.ic__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--warning-50,#fff7ed)}.ic__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ic__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ic__actions{display:flex;gap:var(--space-2)}.ic__reject,.ic__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.ic__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.ic__reject::after{border:none}.ic__approve{border:none;background:var(--teacher-600);color:#fff}.ic__approve::after{border:none}.ic__reject[disabled],.ic__approve[disabled]{opacity:.5}@media(max-width:360px){.ic__summary{flex-direction:column}.ic__summary-types{width:100%}.ic__compare{grid-template-columns:1fr}.ic__compare-arrow{flex-direction:row}.ic__compare-arrow text:last-child{transform:rotate(-90deg)}}
</style>
