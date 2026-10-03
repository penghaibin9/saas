<template>
  <view class="page-wrap">
    <MobileNavBar title="轮岗与工资" subtitle="轮岗项目、分项成绩和月度实发工资" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="context.batchId" class="page-pad stack">
        <MobileInlineAlert type="info"
          description="轮岗按部门独立记录，不会覆盖上一部门；工资单按月份留版本，约定报酬与实际发放金额分开。" />

        <view class="section-head"><text class="section-head__title">轮岗全过程</text><text class="section-head__more">{{ rotations.length }} 个部门</text></view>
        <MobileGlobalState v-if="!rotations.length" state="empty" title="暂无轮岗安排" description="指导教师创建轮岗安排后，会显示部门、项目、自评和分项成绩。" />
        <view v-for="item in rotations" :key="item.id" class="card pf">
          <view class="row-between">
            <view class="flex-1">
              <text class="t-md t-bold">第{{ item.rotationSeq }}轮 · {{ item.departmentName }}</text>
              <text class="pf__sub">{{ item.startDate }} ～ {{ item.endDate }} · 带教 {{ item.mentorName }}</text>
            </view>
            <MobileStatusTag :label="rotationLabel(item.status)" :type="item.status === 'COMPLETED' ? 'success' : item.status === 'ACTIVE' ? 'info' : 'default'" />
          </view>

          <view class="pf__projects">
            <view v-for="project in item.projects" :key="project.id" class="pf__project">
              <text class="pf__project-name">{{ project.projectName }}</text>
              <text class="pf__sub">{{ project.projectContent || '暂无项目说明' }}</text>
              <text v-if="project.startDate || project.endDate" class="pf__sub">{{ project.startDate || '—' }} ～ {{ project.endDate || '—' }}</text>
            </view>
            <text v-if="!item.projects.length" class="pf__sub">当前部门还未登记项目。</text>
          </view>

          <view class="pf__score">
            <view><text>{{ scoreText(item.scores?.theory) }}</text><text>理论</text></view>
            <view><text>{{ scoreText(item.scores?.skill) }}</text><text>技能</text></view>
            <view><text>{{ scoreText(item.scores?.mentor) }}</text><text>带教评价</text></view>
            <view class="is-total"><text>{{ scoreText(item.scores?.total) }}</text><text>轮岗总分</text></view>
          </view>

          <view v-if="item.studentSelfEvaluation" class="pf__self-read">
            <text class="pf__label">我的自评 · {{ item.studentSelfRating }}/5</text>
            <text>{{ item.studentSelfEvaluation }}</text>
          </view>
          <view v-else-if="item.status !== 'CANCELLED'" class="pf__self">
            <text class="pf__label">提交本部门自评</text>
            <textarea v-model="selfDrafts[item.id].text" maxlength="2000" class="pf__textarea" placeholder="写清做了哪些项目、掌握了什么、还需要改进什么（至少20字）" />
            <picker :range="[1,2,3,4,5]" :value="Math.max(0, Number(selfDrafts[item.id].rating || 3)-1)" @change="selfDrafts[item.id].rating = Number($event.detail.value)+1">
              <view class="pf__picker">自评分：{{ selfDrafts[item.id].rating }}/5 ▾</view>
            </picker>
            <button class="btn btn-primary" :disabled="busyRotationId === item.id" @click="submitSelf(item)">
              {{ busyRotationId === item.id ? '提交中…' : '提交自评' }}
            </button>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">月度工资单</text><button class="pf__add" @click="openPayroll()">新增本月工资单</button></view>
        <MobileGlobalState v-if="!payrolls.length" state="empty" title="暂无工资单" description="收到工资后按月份上传实际金额、币种和工资凭证照片。" />
        <view v-for="item in payrolls" :key="item.id" class="card pf">
          <view class="row-between">
            <view>
              <text class="t-md t-bold">{{ item.payMonth }}</text>
              <text class="pf__sub">约定报酬：{{ money(item.agreedSalary, item.agreedSalaryCurrency) }}</text>
            </view>
            <MobileStatusTag :label="item.current?.statusLabel || '无当前版本'" :type="payrollTone(item.current?.status)" />
          </view>
          <view v-if="item.current" class="pf__pay-current">
            <view><text>实际发放</text><text>{{ money(item.current.actualAmount, item.current.currency) }}</text></view>
            <view><text>发薪日期</text><text>{{ item.current.paidOn || '未填写' }}</text></view>
            <view><text>当前版本</text><text>V{{ item.current.revisionNo }}</text></view>
          </view>
          <button v-if="item.current?.evidenceFileId" class="pf__file" @click="previewPayroll(item.current)">查看工资凭证</button>
          <text v-if="item.current?.reviewComment" class="pf__review">审核意见：{{ item.current.reviewComment }}</text>
          <button v-if="item.current && item.current.status !== 'SUBMITTED'" class="btn btn-ghost" @click="openPayroll(item)">更正并产生新版本</button>
          <details v-if="item.history?.length > 1" class="pf__history">
            <summary>查看历史版本（{{ item.history.length }}）</summary>
            <view v-for="version in item.history" :key="version.id" class="pf__history-row">
              <text>V{{ version.revisionNo }} · {{ version.statusLabel }}</text>
              <text>{{ money(version.actualAmount, version.currency) }}</text>
            </view>
          </details>
        </view>
      </view>
    </MobileGlobalState>

    <view v-if="payrollForm.visible" class="pf__mask" @click.self="closePayroll">
      <view class="pf__dialog">
        <view class="row-between"><text class="t-lg t-bold">{{ payrollForm.statementId ? '更正工资单' : '新增工资单' }}</text><button class="pf__close" @click="closePayroll">×</button></view>
        <picker mode="date" fields="month" :value="payrollForm.payMonth + '-01'" :disabled="!!payrollForm.statementId" @change="payrollForm.payMonth = String($event.detail.value).slice(0,7)">
          <view class="pf__picker">工资月份：{{ payrollForm.payMonth || '请选择' }} ▾</view>
        </picker>
        <input v-model.trim="payrollForm.actualAmount" type="digit" class="pf__input" placeholder="实际发放金额，例如 3200.00" />
        <input v-model.trim="payrollForm.currency" class="pf__input" maxlength="3" placeholder="币种，例如 CNY" />
        <picker mode="date" :value="payrollForm.paidOn" @change="payrollForm.paidOn = $event.detail.value">
          <view class="pf__picker">发薪日期：{{ payrollForm.paidOn || '未填写' }} ▾</view>
        </picker>
        <textarea v-if="payrollForm.statementId" v-model="payrollForm.correctionReason" class="pf__textarea" maxlength="500" placeholder="更正原因（至少5字）" />
        <view class="row-between">
          <view class="flex-1"><text class="pf__label">工资凭证照片</text><text class="pf__sub">{{ payrollForm.evidenceName || '须上传工资单或到账凭证图片' }}</text></view>
          <button class="btn btn-ghost" :disabled="payrollUploading" @click="pickPayrollPhoto">{{ payrollUploading ? '上传中…' : '选择照片' }}</button>
        </view>
        <button class="btn btn-primary" :disabled="payrollSubmitting" @click="submitPayroll">{{ payrollSubmitting ? '提交中…' : '提交审核' }}</button>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import {
  studentInternshipPayroll,
  studentInternshipPayrollSubmit,
  studentInternshipRotations,
  studentInternshipRotationSelfEvaluation
} from '@/services/internshipApi'
import { openBusinessFile, uploadBusinessFile } from '@/services/fileApi'
import { toast } from '@/utils/nav'

const emptyPayroll = () => ({
  visible: false, statementId: '', payMonth: '', actualAmount: '', currency: 'CNY',
  paidOn: '', evidenceFileId: '', evidenceName: '', correctionReason: ''
})

export default {
  data() {
    return {
      state: 'loading',
      context: { batchId: '', internshipId: '' },
      rotations: [], payrolls: [], selfDrafts: {}, busyRotationId: '',
      payrollForm: emptyPayroll(), payrollUploading: false, payrollSubmitting: false
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    rotationLabel(status) { return ({ PLANNED: '待开始', ACTIVE: '轮岗中', COMPLETED: '已完成', CANCELLED: '已取消' })[status] || status },
    scoreText(value) { return value == null ? '—' : Number(value).toFixed(1) },
    money(value, currency = 'CNY') { return value == null ? '未填写' : `${currency || 'CNY'} ${Number(value).toFixed(2)}` },
    payrollTone(status) { return status === 'APPROVED' ? 'success' : status === 'RETURNED' ? 'danger' : status === 'SUBMITTED' ? 'warning' : 'default' },
    ensureSelfDrafts() {
      const next = { ...this.selfDrafts }
      for (const row of this.rotations) if (!next[row.id]) next[row.id] = { text: '', rating: 3 }
      this.selfDrafts = next
    },
    async load(done) {
      this.state = 'loading'
      try {
        const dashboard = await studentApi.getInternship()
        this.context = { batchId: dashboard?.batchId || '', internshipId: dashboard?.recordId || '' }
        if (!this.context.batchId || !this.context.internshipId) {
          this.rotations = []; this.payrolls = []; this.state = 'ready'; return
        }
        const [rotations, payrolls] = await Promise.all([
          studentInternshipRotations(this.context.batchId, this.context.internshipId),
          studentInternshipPayroll(this.context.batchId, this.context.internshipId)
        ])
        this.rotations = Array.isArray(rotations) ? rotations : []
        this.payrolls = Array.isArray(payrolls) ? payrolls : []
        this.ensureSelfDrafts()
        this.state = 'ready'
      } catch (e) {
        this.state = 'error'
        toast(e?.message || '轮岗与工资信息加载失败')
      } finally { if (done) done() }
    },
    async submitSelf(item) {
      if (this.busyRotationId) return
      const draft = this.selfDrafts[item.id] || {}
      if (String(draft.text || '').trim().length < 20) return toast('轮岗自评至少20个字')
      this.busyRotationId = item.id
      try {
        await studentInternshipRotationSelfEvaluation(item.id, {
          ...this.context,
          selfEvaluation: String(draft.text || '').trim(),
          selfRating: Number(draft.rating || 3),
          expectedVersion: item.version
        })
        toast('轮岗自评已提交')
        await this.load()
      } catch (e) { toast(e?.message || '轮岗自评提交失败') }
      finally { this.busyRotationId = '' }
    },
    openPayroll(statement = null) {
      const current = statement?.current
      const now = new Date()
      this.payrollForm = {
        ...emptyPayroll(),
        visible: true,
        statementId: statement?.id || '',
        payMonth: statement?.payMonth || `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`,
        actualAmount: current?.actualAmount == null ? '' : String(current.actualAmount),
        currency: current?.currency || 'CNY',
        paidOn: current?.paidOn || '',
        correctionReason: ''
      }
    },
    closePayroll() { if (!this.payrollSubmitting && !this.payrollUploading) this.payrollForm = emptyPayroll() },
    pickPayrollPhoto() {
      if (this.payrollUploading) return
      this.payrollUploading = true
      uni.chooseImage({
        count: 1, sourceType: ['camera', 'album'], sizeType: ['original'],
        success: async (res) => {
          try {
            const path = (res.tempFilePaths || [])[0]
            const source = (res.tempFiles || [])[0] || {}
            if (!path) return
            const uploaded = await uploadBusinessFile({
              path, name: source.name || `payroll-${Date.now()}.jpg`, size: source.size || 0
            }, { bizType: 'TEMP_PRIVATE' })
            this.payrollForm.evidenceFileId = uploaded.fileId
            this.payrollForm.evidenceName = uploaded.fileName || '工资凭证照片'
          } catch (e) { toast(e?.message || '工资凭证上传失败') }
          finally { this.payrollUploading = false }
        },
        fail: () => { this.payrollUploading = false }
      })
    },
    async submitPayroll() {
      if (this.payrollSubmitting) return
      const f = this.payrollForm
      if (!/^20\d{2}-(0[1-9]|1[0-2])$/.test(f.payMonth)) return toast('请选择工资月份')
      if (!/^\d+(\.\d{1,2})?$/.test(String(f.actualAmount || ''))) return toast('请输入正确的实际发放金额')
      if (!/^[A-Za-z]{3}$/.test(f.currency)) return toast('币种请输入3位代码，如 CNY')
      if (!f.evidenceFileId) return toast('请上传工资凭证照片')
      if (f.statementId && String(f.correctionReason || '').trim().length < 5) return toast('更正原因至少5个字')
      this.payrollSubmitting = true
      try {
        await studentInternshipPayrollSubmit({
          ...this.context,
          payMonth: f.payMonth,
          actualAmount: f.actualAmount,
          currency: String(f.currency).toUpperCase(),
          paidOn: f.paidOn || '',
          evidenceFileId: f.evidenceFileId,
          correctionReason: String(f.correctionReason || '').trim(),
          submitNote: f.statementId ? '学生提交工资单更正版本' : '学生首次提交月度工资单'
        })
        toast(f.statementId ? '工资单更正版本已提交' : '工资单已提交')
        this.payrollForm = emptyPayroll()
        await this.load()
      } catch (e) { toast(e?.message || '工资单提交失败') }
      finally { this.payrollSubmitting = false }
    },
    async previewPayroll(version) {
      if (!version?.evidenceFileId) return
      try { await openBusinessFile(version.evidenceFileId) }
      catch (e) { toast(e?.message || '工资凭证无法打开') }
    }
  }
}
</script>

<style scoped>
.pf{display:flex;flex-direction:column;gap:12px;padding:14px}.pf__sub{display:block;margin-top:4px;font-size:11px;color:var(--text-tertiary);line-height:1.55}.pf__projects{display:flex;flex-direction:column;gap:7px}.pf__project{padding:9px;border-radius:8px;background:var(--gray-50)}.pf__project-name,.pf__label{display:block;font-size:12px;font-weight:600;color:var(--text-primary)}.pf__score{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;padding:9px;border-radius:8px;background:var(--gray-50)}.pf__score view{display:flex;flex-direction:column;align-items:center;gap:3px}.pf__score text:first-child{font-size:17px;font-weight:700}.pf__score text:last-child{font-size:9px;color:var(--text-tertiary)}.pf__score .is-total text:first-child{color:var(--brand-primary)}.pf__self-read,.pf__self{padding:10px;border-radius:8px;background:var(--primary-50)}.pf__self-read>text:last-child{display:block;margin-top:6px;font-size:12px;line-height:1.7;color:var(--text-secondary)}.pf__textarea,.pf__input,.pf__picker{box-sizing:border-box;width:100%;border:1px solid var(--border-base);border-radius:8px;padding:10px 12px;background:#fff;font-size:13px}.pf__textarea{min-height:90px;margin:8px 0}.pf__picker{margin:8px 0}.pf__add{margin:0;padding:2px 4px;min-height:0;border:0;background:transparent;color:var(--brand-primary);font-size:12px}.pf__add::after{border:none}.pf__pay-current{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;padding:10px;border-radius:8px;background:var(--gray-50)}.pf__pay-current view{display:flex;flex-direction:column;gap:4px}.pf__pay-current text:first-child{font-size:9px;color:var(--text-tertiary)}.pf__pay-current text:last-child{font-size:12px;font-weight:600}.pf__file{margin:0;padding:5px 0;min-height:0;border:0;background:transparent;color:var(--brand-primary);font-size:12px;text-align:left}.pf__file::after{border:none}.pf__review{display:block;padding:8px;border-radius:6px;background:var(--warning-50);color:var(--warning-700);font-size:12px}.pf__history{font-size:11px;color:var(--text-secondary)}.pf__history-row{display:flex;justify-content:space-between;padding:7px 0;border-top:1px solid var(--border-light)}.pf__mask{position:fixed;inset:0;z-index:999;display:flex;align-items:flex-end;background:rgba(15,23,42,.48)}.pf__dialog{box-sizing:border-box;width:100%;max-height:88vh;overflow:auto;padding:18px;border-radius:18px 18px 0 0;background:#fff;display:flex;flex-direction:column;gap:10px}.pf__close{margin:0;padding:0 6px;min-height:0;border:0;background:transparent;font-size:24px;color:var(--text-tertiary)}.pf__close::after{border:none}
</style>
