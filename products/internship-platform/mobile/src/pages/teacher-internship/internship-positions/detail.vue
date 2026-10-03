<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="岗位详情" subtitle="指导批次 · 岗位条件核对" show-back :fallback-url="returnUrl" />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view v-if="detail" class="page-pad stack">
        <view class="card ipd__identity"><text class="ipd__batch">{{ detail.batchName }}</text><view class="ipd__heading"><text>{{ detail.title }}</text><MobileStatusTag :label="detail.statusLabel" :type="detail.statusTone" /></view><text class="ipd__company">{{ detail.companyName }}</text><view class="ipd__capacity"><text>剩余名额</text><text>{{ detail.remaining ?? '—' }} / {{ detail.headcount ?? '—' }} 人</text></view></view>
        <MobileInlineAlert v-if="detail.riskFlag" type="warning" description="此岗位已标记风险。请联系学校经办人核对处置进度。" />
        <view class="card"><text class="ipd__title">工作内容</text><text class="ipd__content">{{ detail.workContent || '待补充' }}</text><view v-for="item in basics" :key="item[0]" class="ipd__fact"><text>{{ item[0] }}</text><text>{{ item[1] || '待补充' }}</text></view></view>
        <view v-for="group in groups" :key="group.title" class="card"><text class="ipd__title">{{ group.title }}</text><view v-for="item in group.items" :key="item[0]" class="ipd__fact"><text>{{ item[0] }}</text><text>{{ item[1] }}</text></view></view>
        <MobileInlineAlert type="info" :description="publicationNote" />
        <text v-if="detail.updatedAt" class="ipd__updated">资料更新于 {{ formatDateTime(detail.updatedAt) }}</text>
        <button class="ipd__return" @click="returnToList">返回本批次岗位</button>
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import { useInternshipContextStore } from '@/stores/internshipContext'
import { teacherInternshipPositionDetail } from '@/services/internshipApi'
import { positionQuery, positionListUrl, positionFacts } from '@/modules/internshipPositionModel'
import { formatDateTime } from '@/utils/format'
export default {
  data: () => ({ state: 'loading', error: '', detail: null, id: '', scope: positionQuery(), sequence: 0 }),
  computed: {
    context() { return useInternshipContextStore() },
    returnUrl() { return positionListUrl(this.scope) },
    groups() { return positionFacts(this.detail) },
    basics() { const d = this.detail || {}; return [['工作地址', d.workAddress || d.workLocation], ['专业要求', d.majorRequirement], ['年级要求', d.gradeRequirement], ['企业导师', d.mentorName]] },
    publicationNote() { return this.detail?.campaignId ? '本页用于教师核对岗位条件。学生能否选报，还取决于招聘季开放范围、个人资格及岗位余量；审核和发布由学校经办人在 PC 端办理。' : '此岗位尚未关联招聘季，上架后也不会自动进入学生选岗目录。请联系学校经办人核对供给安排。' }
  },
  onLoad(query) { this.id = String(query?.id || ''); this.scope = positionQuery(query) },
  onShow() { this.load() },
  onUnload() { this.sequence++ },
  methods: {
    formatDateTime,
    returnToList() { uni.redirectTo({ url: this.returnUrl }) },
    async load() {
      const sequence = ++this.sequence; this.state = 'loading'; this.error = ''; this.detail = null
      try {
        if (!/^\d+$/.test(this.id) || !this.scope.batchId) throw new Error('岗位链接不完整，请从本批次岗位列表重新进入')
        await this.context.load(true)
        if (sequence !== this.sequence) return
        if (!this.context.can('internship.position.view')) { this.state = 'forbidden'; return }
        if (!this.context.selectBatch(this.scope.batchId)) throw new Error('此批次不在当前指导学生范围内')
        const result = await teacherInternshipPositionDetail(this.id, this.scope.batchId)
        if (sequence !== this.sequence) return
        if (String(result.id) !== this.id || String(result.batchId) !== this.scope.batchId) throw new Error('岗位不属于当前批次，请从列表重新进入')
        this.detail = result; this.state = 'ready'
      } catch (e) { if (sequence === this.sequence) { this.error = e.message || '岗位暂时无法读取'; this.state = 'error' } }
    }
  }
}
</script>
<style scoped>
.ipd__batch,.ipd__updated{display:block;font-size:12px;color:var(--text-tertiary);line-height:1.7}.ipd__identity{border-top:3px solid var(--brand-primary)}.ipd__heading{display:flex;align-items:flex-start;gap:12px;justify-content:space-between;margin:12px 0}.ipd__heading>text{flex:1;min-width:0;font-size:22px;line-height:1.5;font-weight:600;overflow-wrap:anywhere}.ipd__company{display:block;font-size:14px;color:var(--text-secondary);line-height:1.7}.ipd__capacity{display:flex;justify-content:space-between;border-top:1px solid var(--border-light);margin-top:18px;padding-top:14px;font-size:14px}.ipd__capacity>text:first-child{color:var(--text-tertiary)}.ipd__title{font-size:16px;font-weight:600}.ipd__content{display:block;font-size:14px;line-height:1.9;margin:14px 0 4px;white-space:pre-wrap;overflow-wrap:anywhere;color:var(--text-secondary)}.ipd__fact{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-top:17px;font-size:13px;line-height:1.8}.ipd__fact>text:first-child{flex:none;color:var(--text-tertiary)}.ipd__fact>text:last-child{text-align:right;overflow-wrap:anywhere;min-width:0}.ipd__return{font-size:14px;color:var(--brand-primary);background:var(--brand-50);border:0}.ipd__return::after{border:0}
</style>
