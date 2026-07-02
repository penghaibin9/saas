<template>
  <div class="sp-page">
    <AppSectionHeader title="身份认证管理" subtitle="待核验 / 已核验 / 已退回 / 证件过期，核验与退回全程留痕" />

    <div class="sp-actions-row">
      <div class="si-tabs">
        <button
          v-for="t in tabs"
          :key="t.key"
          type="button"
          class="si-tab"
          :class="{ 'is-active': activeTab === t.key }"
          @click="switchTab(t.key)"
        >{{ t.label }}（{{ countOf(t.key) }}）</button>
      </div>
    </div>

    <AppInlineAlert
      v-if="expiredCount > 0"
      type="warning"
      :description="`有 ${expiredCount} 名学生证件已过期，请通知学生更新证件后重新核验。`"
    />

    <StudentStateBlock :loading="loading" :error="error" :empty="!list.length" :no-permission="noPermission" @retry="load">
      <AppCard class="sp-card">
        <table class="sp-table">
          <thead>
            <tr><th>姓名</th><th>学号</th><th>班级</th><th>证件号</th><th>有效期</th><th>认证状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="s in list" :key="s.studentId">
              <td>{{ s.name }}</td>
              <td>{{ s.studentNo }}</td>
              <td>{{ s.className }}</td>
              <td>{{ s.idCard ? maskIdCard(s.idCard) : '未登记' }}</td>
              <td>{{ s.idCardExpireDate }}</td>
              <td><AppBadge :type="identityBadge(s.identityVerifyStatus)">{{ identityText(s.identityVerifyStatus) }}</AppBadge></td>
              <td>
                <div class="si-ops">
                  <AppButton
                    v-if="s.identityVerifyStatus !== 'VERIFIED'"
                    variant="primary"
                    :disabled="!canVerify || submittingId === s.studentId"
                    :loading="submittingId === s.studentId"
                    @click="onVerify(s)"
                  >通过</AppButton>
                  <AppButton
                    v-if="s.identityVerifyStatus !== 'VERIFIED'"
                    variant="warning"
                    :disabled="!canVerify"
                    @click="openReject(s)"
                  >退回</AppButton>
                  <AppButton variant="ghost" @click="$router.push(`/admin/student/${s.studentId}`)">详情</AppButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </AppCard>
    </StudentStateBlock>

    <AppConfirmDialog
      v-model:visible="rejectVisible"
      type="warning"
      :title="`退回 ${rejectTarget ? rejectTarget.name : ''} 的身份认证`"
      message="退回后学生需补充或更正材料重新提交核验。退回原因将写入核验记录与审计。"
      confirm-text="确认退回"
      require-reason
      reason-label="退回原因"
      :submitting="submittingId !== ''"
      @confirm="onRejectConfirm"
    />
  </div>
</template>

<script>
/** 页面 5：/admin/student/identity 身份认证管理（退回原因≥5字，AppConfirmDialog 统一承载） */
import { AppCard, AppButton, AppBadge, AppSectionHeader } from '@/components/ui'
import AppInlineAlert from '@/components/common/AppInlineAlert.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import StudentStateBlock from '@/modules/student/components/StudentStateBlock.vue'
import {
  studentProvider,
  hasStudentPermission,
  STUDENT_PERMISSION,
  formatIdentityVerifyStatus,
  getIdentityBadge,
  maskIdCard,
  IDENTITY_VERIFY_STATUS
} from '@/modules/student'
import { toast } from '@/utils/toast'

const TABS = [
  { key: 'PENDING', label: '待核验' },
  { key: 'VERIFIED', label: '已核验' },
  { key: 'REJECTED', label: '已退回' },
  { key: 'EXPIRED', label: '证件过期' },
  { key: 'UNVERIFIED', label: '未认证' }
]

export default {
  name: 'StudentIdentityView',
  components: { AppCard, AppButton, AppBadge, AppSectionHeader, AppInlineAlert, AppConfirmDialog, StudentStateBlock },
  data() {
    return {
      loading: false,
      error: '',
      all: [],
      activeTab: 'PENDING',
      rejectVisible: false,
      rejectTarget: null,
      submittingId: ''
    }
  },
  computed: {
    tabs: () => TABS,
    noPermission() {
      return !hasStudentPermission(STUDENT_PERMISSION.IDENTITY_VIEW)
    },
    canVerify() {
      return hasStudentPermission(STUDENT_PERMISSION.IDENTITY_VERIFY)
    },
    list() {
      return this.all.filter((s) => s.identityVerifyStatus === this.activeTab)
    },
    expiredCount() {
      return this.all.filter((s) => s.identityVerifyStatus === IDENTITY_VERIFY_STATUS.EXPIRED).length
    }
  },
  created() {
    if (!this.noPermission) this.load()
  },
  methods: {
    maskIdCard,
    identityText: formatIdentityVerifyStatus,
    identityBadge: getIdentityBadge,
    countOf(key) {
      return this.all.filter((s) => s.identityVerifyStatus === key).length
    },
    switchTab(key) {
      this.activeTab = key
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await studentProvider.getStudentList({ page: 1, pageSize: 100 })
        if (res.code === 0) this.all = res.data.list
        else this.error = res.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    async onVerify(s) {
      this.submittingId = s.studentId
      try {
        const res = await studentProvider.verifyStudentIdentity(s.studentId)
        if (res.code === 0) {
          toast.success(`已通过 ${s.name} 的身份核验`)
          await this.load()
        } else toast.warning(res.message)
      } finally {
        this.submittingId = ''
      }
    },
    openReject(s) {
      this.rejectTarget = s
      this.rejectVisible = true
    },
    async onRejectConfirm({ reason }) {
      if (!this.rejectTarget) return
      this.submittingId = this.rejectTarget.studentId
      try {
        const res = await studentProvider.rejectStudentIdentity(this.rejectTarget.studentId, { reason })
        if (res.code === 0) {
          toast.success('已退回，原因已写入核验记录与审计')
          this.rejectVisible = false
          await this.load()
        } else toast.warning(res.message)
      } finally {
        this.submittingId = ''
        this.rejectTarget = null
      }
    }
  }
}
</script>

<style scoped>
@import './student-page.css';
.si-tabs { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.si-tab {
  height: 30px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-full);
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.si-tab.is-active {
  background: var(--primary-50);
  border-color: var(--primary-600);
  color: var(--primary-600);
  font-weight: var(--font-weight-medium);
}
.si-ops { display: flex; gap: var(--space-2); }
</style>
