<template>
  <ModulePageShell
    title="家校联系"
    subtitle="家校联系记录（留痕）· 查看完整号码需原因与审计"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="家校联系查阅"
  >
    <div class="fc-picker">
      <span class="fc-picker__label">选择学生</span>
      <div class="fc-picker__control">
        <AppStudentPicker v-model="studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索学生" @change="onPick" />
      </div>
      <AppPermissionButton code="studentAffairs.homeSchool.record.create" variant="primary" size="sm" :disabled="!studentId" @click="openCreate">登记联系</AppPermissionButton>
    </div>

    <EmptyState v-if="!studentId" title="请选择一名学生" description="查看并登记该生的家校联系记录" />
    <LoadingState v-else-if="loading" text="正在加载联系记录…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <EmptyState v-else-if="!contacts.length" title="暂无家校联系记录" description="点「登记联系」记录一次家校沟通" />
    <ul v-else class="fc-list">
      <li v-for="c in contacts" :key="c.contactId" class="fc-item">
        <div class="fc-item__head">
          <span class="fc-item__type">{{ contactTypeLabel(c.contactType) }}</span>
          <span v-if="c.fullPhoneViewed" class="fc-item__sensitive">🔒 曾查看完整号码</span>
          <span class="fc-item__time">{{ fmt(c.occurredAt) }}</span>
        </div>
        <div v-if="c.reason" class="fc-item__row">事由：{{ c.reason }}</div>
        <div v-if="c.result" class="fc-item__row">结果：{{ c.result }}</div>
      </li>
    </ul>

    <!-- 登记联系（原为手搓 fc-mask 弹窗，对齐 FamilyReceiptView 的 AppConfirmDialog 模式） -->
    <AppConfirmDialog
      v-model:visible="createModal.visible" title="登记家校联系" type="primary"
      confirm-text="登记" :submitting="acting" @confirm="submitCreate"
    >
      <AppFormItem label="联系方式" required>
        <AppSelect v-model="createModal.contactType" :options="CONTACT_TYPE_OPTIONS" placeholder="" />
      </AppFormItem>
      <AppFormItem label="联系事由">
        <AppTextInput v-model="createModal.reason" placeholder="如：反馈近期学业情况" />
      </AppFormItem>
      <AppFormItem label="联系结果">
        <AppTextarea v-model="createModal.result" :rows="3" placeholder="家长反馈、约定事项等" />
      </AppFormItem>
      <label class="fc-check">
        <input v-model="createModal.fullPhoneView" type="checkbox" /> 本次需查看家长完整号码（将记敏感审计）
      </label>
      <AppFormItem v-if="createModal.fullPhoneView" label="查看原因（≥5字）" required>
        <AppTextInput v-model="createModal.viewReason" placeholder="说明查看完整号码的原因，不少于 5 字" />
      </AppFormItem>
      <p v-if="createModal.error" class="fc-err">{{ createModal.error }}</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 家校联系（/admin/student-affairs/family）—— 13A P6。
 * 真实对接 /api/v1/student-affairs/students/{id}/family-contacts：联系记录(append-only) + 登记。
 * 查看完整号码需填原因(≥5字)，后端落 SENSITIVE 审计。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import {
  AppConfirmDialog, AppFormItem, AppPermissionButton, AppSelect, AppStudentPicker,
  AppTextInput, AppTextarea
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const CONTACT_TYPE = { PHONE: '电话', WECHAT: '微信', VISIT: '家访', MESSAGE: '短信' }
const CONTACT_TYPE_OPTIONS = Object.entries(CONTACT_TYPE).map(([value, label]) => ({ value, label }))

export default {
  name: 'FamilyContactView',
  components: {
    ModulePageShell, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppFormItem,
    AppPermissionButton, AppSelect, AppStudentPicker, AppTextInput, AppTextarea
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      studentId: '', loading: false, error: '', contacts: [], acting: false,
      createModal: { visible: false, contactType: 'PHONE', reason: '', result: '', fullPhoneView: false, viewReason: '', error: '' }
    }
  },
  computed: {
    CONTACT_TYPE_OPTIONS: () => CONTACT_TYPE_OPTIONS,
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    }
  },
  methods: {
    fmt(t) {
      return t ? String(t).replace('T', ' ').slice(0, 16) : ''
    },
    contactTypeLabel(t) {
      return CONTACT_TYPE[t] || t || '—'
    },
    searchStudents(keyword) {
      return studentAffairsApi.searchStudents(keyword)
    },
    onPick() {
      if (this.studentId) this.load()
    },
    async load() {
      if (!this.studentId) return
      this.loading = true
      this.error = ''
      const res = await studentAffairsApi.getFamilyContacts(this.studentId, { page: 1, pageSize: 100 })
      this.loading = false
      if (res.code === 0 && res.data) this.contacts = res.data.items || []
      else { this.contacts = []; this.error = res.message || '加载失败' }
    },
    openCreate() {
      this.createModal = { visible: true, contactType: 'PHONE', reason: '', result: '', fullPhoneView: false, viewReason: '', error: '' }
    },
    async submitCreate() {
      const m = this.createModal
      const viewReason = (m.viewReason || '').trim()
      if (m.fullPhoneView && (!viewReason || viewReason.length < 5)) { m.error = '查看完整号码原因不少于 5 字'; return }
      this.acting = true
      const res = await studentAffairsApi.createFamilyContact(this.studentId, {
        contactType: m.contactType, reason: (m.reason || '').trim(), result: (m.result || '').trim(),
        fullPhoneView: !!m.fullPhoneView, viewReason
      })
      this.acting = false
      if (res.code === 0) {
        toast.success(m.fullPhoneView ? '已登记（含完整号码查看审计）' : '已登记')
        this.createModal.visible = false
        this.load()
      } else {
        m.error = res.message || '登记失败'
        toast.error(m.error)
      }
    }
  }
}
</script>

<style scoped>
.fc-picker {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.fc-picker__label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
.fc-picker__control {
  min-width: 300px;
}
.fc-btn {
  height: 32px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.fc-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.fc-btn--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
}
.fc-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.fc-item {
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
}
.fc-item__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}
.fc-item__type {
  font-weight: 600;
  color: var(--primary-700);
}
.fc-item__sensitive {
  font-size: var(--font-size-xs);
  color: var(--danger-600, #dc2626);
}
.fc-item__time {
  margin-left: auto;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.fc-item__row {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.fc-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.fc-modal {
  width: 440px;
  max-width: calc(100vw - 32px);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-lg, 0 10px 40px rgba(0, 0, 0, 0.2));
}
.fc-modal__title {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.fc-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
}
.fc-field > span {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.fc-field i {
  color: var(--danger-600, #dc2626);
  font-style: normal;
}
.fc-check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}
.fc-input,
.fc-textarea {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: var(--space-2);
  outline: none;
}
.fc-textarea {
  resize: vertical;
}
.fc-err {
  margin: 0 0 var(--space-2);
  color: var(--danger-600, #dc2626);
  font-size: var(--font-size-xs);
}
.fc-modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
</style>
