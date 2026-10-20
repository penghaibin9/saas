<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="学生实习档案" subtitle="核对本批次安排与资格结果" show-back :fallback-url="'/pages/teacher-internship/internship-students/index?batchId=' + batchId" />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view v-if="detail" class="page-pad stack">
        <view class="card itd__identity"><text class="itd__batch">{{ detail.batchName }}</text><view class="itd__heading"><text>{{ detail.name }}</text><MobileStatusTag :label="detail.statusLabel" /></view><text class="itd__meta">{{ detail.className }} · {{ maskedNo(detail.studentNo) }}</text></view>
        <view class="card itd__qualification">
          <view class="itd__row"><text class="itd__title">资格认定结果</text><MobileStatusTag :label="detail.eligibilityLabel" :type="detail.eligibilityStatus === 'QUALIFIED' ? 'success' : detail.eligibilityStatus === 'UNQUALIFIED' ? 'danger' : 'warning'" /></view>
          <text class="itd__reason">{{ detail.eligibilityReview?.reason || '暂无认定说明' }}</text>
          <text v-if="detail.eligibilityReview?.reviewedAt" class="itd__meta">更新于 {{ formatDateTime(detail.eligibilityReview.reviewedAt) }}</text>
          <text v-if="detail.eligibilityReview?.reason" class="itd__meta">{{ detail.eligibilityReview.studentVisible ? '该说明已向学生展示' : '历史内部说明，仅教师可见' }}</text>
        </view>
        <view class="card"><text class="itd__title">实习安排</text><view v-for="item in facts" :key="item.label" class="itd__fact"><text>{{ item.label }}</text><text>{{ item.value || '待落实' }}</text></view></view>
        <view class="card"><text class="itd__title">最近资格记录</text><view v-for="(item,index) in reviews" :key="index" class="itd__review"><view class="itd__row"><text>{{ labels[item.detail?.status] || '待认定' }}</text><text class="itd__meta">{{ item.operator }}</text></view><text v-if="item.detail?.reason" class="itd__reason">{{ item.detail.reason }}</text><text class="itd__meta">{{ formatDateTime(item.occurredAt) }}</text></view><text v-if="!reviews.length" class="itd__reason">暂无资格处理记录</text></view>
        <MobileInlineAlert type="info" description="资格认定由具备审核权限的学校经办人在教师 PC 端办理；此处用于核对学生进度和跟进安排。" />
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import { formatDateTime } from '@/utils/format'
import { teacherInternshipStudentDetail } from '@/services/internshipApi'
export default {
  data: () => ({ state: 'loading', error: '', detail: null, id: '', batchId: '', sequence: 0, labels: { PENDING: '待认定', QUALIFIED: '合格', UNQUALIFIED: '不合格' } }),
  computed: {
    reviews() { return (this.detail?.auditTrail || []).filter((a) => a.action === 'ELIGIBILITY') },
    facts() { const d = this.detail || {}; return [{ label: '实习企业', value: d.enterpriseName }, { label: '实习岗位', value: d.positionName }, { label: '实习去向', value: d.destinationLabel }, { label: '校内导师', value: d.advisorName }, { label: '企业导师', value: d.mentorName }, { label: '实习时间', value: d.internRange }] }
  },
  onLoad(query) { this.id = String(query?.id || ''); this.batchId = String(query?.batchId || ''); this.load() },
  onUnload() { this.sequence++ },
  methods: {
    formatDateTime,
    maskedNo(value) { const no = String(value || ''); return no.length > 4 ? no.slice(0,2) + '****' + no.slice(-2) : '****' },
    async load() {
      const seq = ++this.sequence; this.state = 'loading'; this.error = ''
      try {
        if (!this.id || !this.batchId) throw new Error('档案链接不完整，请从实习学生名单重新进入')
        const result = await teacherInternshipStudentDetail(this.id)
        if (seq !== this.sequence) return
        if (String(result.batchId) !== this.batchId) throw new Error('此档案不属于当前批次，请从名单重新进入')
        this.detail = result; this.state = 'ready'
      } catch (e) { if (seq === this.sequence) { this.error = e.message || '档案加载失败，请重试'; this.state = e.code === 403001 ? 'forbidden' : 'error' } }
    }
  }
}
</script>
<style scoped>
.itd__batch,.itd__meta{display:block;font-size:12px;color:var(--text-tertiary);line-height:1.7}.itd__heading{display:flex;align-items:center;justify-content:space-between;font-size:24px;font-weight:600;margin:12px 0 8px}.itd__row{display:flex;align-items:center;justify-content:space-between;gap:12px}.itd__title{font-size:16px;font-weight:600}.itd__reason{display:block;font-size:14px;line-height:1.8;color:var(--text-secondary);white-space:pre-wrap;word-break:break-word;margin:16px 0}.itd__qualification{border-top:3px solid var(--brand-primary)}.itd__fact{display:flex;align-items:flex-start;justify-content:space-between;gap:22px;margin-top:20px;font-size:13px;line-height:1.7}.itd__fact>text:first-child{color:var(--text-tertiary);flex:none}.itd__fact>text:last-child{text-align:right}.itd__review{border-top:1px solid var(--border-light);padding-top:16px;margin-top:18px;font-size:14px}
</style>
