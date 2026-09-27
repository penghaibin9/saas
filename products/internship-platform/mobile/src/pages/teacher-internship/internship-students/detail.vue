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
        <view v-if="canResetPassword" class="card itd__account">
          <view class="itd__row">
            <view class="flex-1">
              <text class="itd__title">账号安全</text>
              <text class="itd__meta">仅能重置当前教师数据范围内的学生账号；旧密码不会显示。</text>
            </view>
            <MobileStatusTag v-if="account" :label="account.bound ? (account.mustChangePassword ? '待首次改密' : '账号正常') : '未绑定账号'" :type="account.bound && !account.mustChangePassword ? 'success' : 'warning'" />
          </view>
          <view v-if="accountLoading" class="itd__account-state">正在读取账号状态…</view>
          <MobileInlineAlert v-else-if="accountError" type="warning" :description="accountError" />
          <template v-else-if="account">
            <view class="itd__fact"><text>登录账号</text><text>{{ account.loginNameMasked || '—' }}</text></view>
            <view class="itd__fact"><text>绑定状态</text><text>{{ account.bound ? '已绑定' : '未绑定' }}</text></view>
            <view class="itd__fact"><text>账号状态</text><text>{{ account.accountStatus || '—' }}</text></view>
            <view class="itd__fact"><text>首次改密</text><text>{{ account.mustChangePassword ? '必须修改临时密码' : '否' }}</text></view>
            <button class="itd__reset" :disabled="resetting || !account.canReset" @click="resetPassword">
              {{ resetting ? '重置中…' : '重置学生密码' }}
            </button>
            <text class="itd__reset-note">重置后旧访问令牌立即失效；临时密码只在本次操作成功弹窗显示一次，不保存到本机。</text>
          </template>
        </view>
        <view class="card"><text class="itd__title">最近资格记录</text><view v-for="(item,index) in reviews" :key="index" class="itd__review"><view class="itd__row"><text>{{ labels[item.detail?.status] || '待认定' }}</text><text class="itd__meta">{{ item.operator }}</text></view><text v-if="item.detail?.reason" class="itd__reason">{{ item.detail.reason }}</text><text class="itd__meta">{{ formatDateTime(item.occurredAt) }}</text></view><text v-if="!reviews.length" class="itd__reason">暂无资格处理记录</text></view>
        <MobileInlineAlert type="info" description="资格认定由具备审核权限的学校经办人在教师 PC 端办理；此处用于核对学生进度和跟进安排。" />
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import { formatDateTime } from '@/utils/format'
import {
  teacherInternshipStudentAccount,
  teacherInternshipStudentDetail,
  teacherInternshipStudentResetPassword
} from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'
export default {
  data: () => ({
    state: 'loading', error: '', detail: null, id: '', batchId: '', sequence: 0,
    account: null, accountLoading: false, accountError: '', resetting: false,
    labels: { PENDING: '待认定', QUALIFIED: '合格', UNQUALIFIED: '不合格' }
  }),
  computed: {
    internshipContext() { return useInternshipContextStore() },
    canResetPassword() { return this.internshipContext.can('internship.student.password.reset') },
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
        this.detail = result
        this.state = 'ready'
        if (!this.internshipContext.loaded) {
          try { await this.internshipContext.load() } catch (e) {}
        }
        if (seq === this.sequence && this.canResetPassword) await this.loadAccount(seq)
      } catch (e) { if (seq === this.sequence) { this.error = e.message || '档案加载失败，请重试'; this.state = e.code === 403001 ? 'forbidden' : 'error' } }
    },
    async loadAccount(seq = this.sequence) {
      if (!this.id || !this.batchId || !this.canResetPassword) return
      this.accountLoading = true; this.accountError = ''
      try {
        const account = await teacherInternshipStudentAccount(this.id, this.batchId)
        if (seq !== this.sequence) return
        this.account = account || null
      } catch (e) {
        if (seq === this.sequence) {
          this.account = null
          this.accountError = e?.message || '账号状态读取失败'
        }
      } finally {
        if (seq === this.sequence) this.accountLoading = false
      }
    },
    resetPassword() {
      if (this.resetting || !this.account?.canReset || !this.canResetPassword) return
      uni.showModal({
        title: '重置学生密码',
        editable: true,
        placeholderText: '请填写重置原因（至少5字）',
        content: '重置后学生旧会话立即失效，并强制使用临时密码登录后修改密码。',
        confirmText: '确认重置',
        success: async (result) => {
          if (!result.confirm || this.resetting) return
          const reason = String(result.content || '').trim()
          if (reason.length < 5) return toast('重置原因至少5个字')
          const expectedVersion = this.account?.accountVersion
          this.resetting = true
          try {
            const response = await teacherInternshipStudentResetPassword(this.id, this.batchId, {
              batchId: this.batchId,
              reason,
              expectedAccountVersion: expectedVersion
            })
            const temporary = String(response?.tempPassword || '')
            await this.loadAccount()
            if (!temporary) return toast('密码已重置，但临时密码未返回，请联系管理员')
            // 仅把一次性凭据放在当前回调局部变量中展示，不写 data/store/storage/日志。
            uni.showModal({
              title: '临时密码（仅本次显示）',
              content: `学生：${this.detail?.name || ''}\n临时密码：${temporary}\n\n请立即转交学生。学生首次登录必须修改密码；关闭后本页面不会再次显示。`,
              showCancel: false,
              confirmText: '我已安全转交'
            })
          } catch (e) {
            if (e?.code === 'DATA_CONFLICT' || String(e?.code || '').includes('409')) {
              toast('学生账号状态已变化，已为你刷新')
              await this.loadAccount()
            } else {
              toast(e?.message || '密码重置失败')
            }
          } finally { this.resetting = false }
        }
      })
    }
  }
}
</script>
<style scoped>
.itd__batch,.itd__meta{display:block;font-size:12px;color:var(--text-tertiary);line-height:1.7}.itd__account{display:flex;flex-direction:column;gap:8px}.itd__account-state{padding:12px 0;color:var(--text-tertiary);font-size:13px}.itd__reset{width:100%;min-height:44px;margin-top:10px;border:0;border-radius:var(--radius-md);background:var(--teacher-600);color:#fff;font-size:14px;font-weight:600}.itd__reset[disabled]{opacity:.45}.itd__reset::after{border:none}.itd__reset-note{display:block;margin-top:4px;color:var(--text-tertiary);font-size:11px;line-height:1.6}.itd__heading{display:flex;align-items:center;justify-content:space-between;font-size:24px;font-weight:600;margin:12px 0 8px}.itd__row{display:flex;align-items:center;justify-content:space-between;gap:12px}.itd__title{font-size:16px;font-weight:600}.itd__reason{display:block;font-size:14px;line-height:1.8;color:var(--text-secondary);white-space:pre-wrap;word-break:break-word;margin:16px 0}.itd__qualification{border-top:3px solid var(--brand-primary)}.itd__fact{display:flex;align-items:flex-start;justify-content:space-between;gap:22px;margin-top:20px;font-size:13px;line-height:1.7}.itd__fact>text:first-child{color:var(--text-tertiary);flex:none}.itd__fact>text:last-child{text-align:right}.itd__review{border-top:1px solid var(--border-light);padding-top:16px;margin-top:18px;font-size:14px}
</style>
