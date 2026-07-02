<template>
  <AppCard class="stu-panel">
    <AppSectionHeader title="身份认证" compact>
      <template #extra>
        <AppBadge :type="badge">{{ statusText }}</AppBadge>
      </template>
    </AppSectionHeader>
    <dl class="stu-kv">
      <dt>证件号码</dt><dd>{{ maskedIdCard || '未登记' }}</dd>
      <dt>证件有效期</dt>
      <dd :class="{ 'stu-identity__expired': expired }">{{ identity.idCardExpireDate || '—' }}{{ expired ? '（已过期）' : '' }}</dd>
    </dl>

    <div v-if="identity.verifyRecords && identity.verifyRecords.length" class="stu-identity__records">
      <div v-for="(r, i) in identity.verifyRecords" :key="i" class="stu-identity__record">
        <span>{{ r.time }}</span>
        <span>{{ r.operator }}</span>
        <AppBadge :type="r.action === 'APPROVE' ? 'success' : 'danger'">{{ r.action === 'APPROVE' ? '通过' : '退回' }}</AppBadge>
        <span v-if="r.comment" class="stu-identity__comment">{{ r.comment }}</span>
      </div>
    </div>

    <div v-if="rejectMode" class="stu-identity__reject">
      <textarea
        v-model="reason"
        rows="2"
        class="stu-identity__textarea"
        placeholder="请填写退回原因，便于学生补充材料"
        :disabled="readonly"
      />
      <div class="stu-identity__count" :class="{ 'is-invalid': !check.valid }">
        当前 {{ check.length }} 字 / 至少 {{ check.minLength }} 字
      </div>
    </div>

    <div class="stu-panel__actions">
      <template v-if="rejectMode">
        <AppButton variant="secondary" @click="cancelReject">取消</AppButton>
        <AppButton variant="danger" :disabled="readonly || !check.valid || submitting" :loading="submitting" @click="confirmReject">
          确认退回
        </AppButton>
      </template>
      <template v-else>
        <AppButton variant="warning" :disabled="readonly || !canVerify || finished || submitting" @click="rejectMode = true">
          退回
        </AppButton>
        <AppButton variant="primary" :disabled="readonly || !canVerify || finished || submitting" :loading="submitting" @click="$emit('verify')">
          核验通过
        </AppButton>
      </template>
    </div>
  </AppCard>
</template>

<script>
/**
 * StudentIdentityPanel — 身份认证面板（证件脱敏 + 核验/退回；退回原因≥5字复用 workflow 校验）
 */
import { AppCard, AppButton, AppBadge, AppSectionHeader } from '@/components/ui'
import { maskIdCard } from '../helpers/student-security.helper'
import { validateRejectReason } from '../helpers/student-validate.helper'
import { formatIdentityVerifyStatus } from '../helpers/student-format.helper'
import { getIdentityBadge } from '../helpers/student-status.helper'
import { IDENTITY_VERIFY_STATUS } from '../constants/student.constants'

export default {
  name: 'StudentIdentityPanel',
  components: { AppCard, AppButton, AppBadge, AppSectionHeader },
  props: {
    identity: { type: Object, required: true },
    canVerify: { type: Boolean, default: false },
    readonly: { type: Boolean, default: false },
    submitting: { type: Boolean, default: false }
  },
  emits: ['verify', 'reject'],
  data() {
    return { rejectMode: false, reason: '' }
  },
  computed: {
    maskedIdCard() {
      return this.identity.idCard ? maskIdCard(this.identity.idCard) : ''
    },
    statusText() {
      return formatIdentityVerifyStatus(this.identity.identityVerifyStatus)
    },
    badge() {
      return getIdentityBadge(this.identity.identityVerifyStatus)
    },
    expired() {
      return this.identity.identityVerifyStatus === IDENTITY_VERIFY_STATUS.EXPIRED
    },
    finished() {
      return this.identity.identityVerifyStatus === IDENTITY_VERIFY_STATUS.VERIFIED
    },
    check() {
      return validateRejectReason(this.reason)
    }
  },
  watch: {
    'identity.studentId'() {
      this.cancelReject()
    }
  },
  methods: {
    cancelReject() {
      this.rejectMode = false
      this.reason = ''
    },
    confirmReject() {
      if (!this.check.valid) return
      this.$emit('reject', this.reason.trim())
      this.cancelReject()
    }
  }
}
</script>

<style scoped>
@import './student-panel.css';
.stu-identity__expired { color: var(--danger-600); }
.stu-identity__records { display: flex; flex-direction: column; gap: var(--space-2); }
.stu-identity__record { display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-xs); color: var(--text-secondary); flex-wrap: wrap; }
.stu-identity__comment { color: var(--warning-700); }
.stu-identity__textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  font: inherit;
  resize: vertical;
}
.stu-identity__textarea:focus { outline: none; border-color: var(--primary-500); }
.stu-identity__count { margin-top: var(--space-1); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.stu-identity__count.is-invalid { color: var(--danger-600); }
</style>
