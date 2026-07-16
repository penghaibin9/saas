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
      <button type="button" class="fc-btn fc-btn--primary" :disabled="!studentId" @click="openCreate">登记联系</button>
    </div>

    <EmptyState v-if="!studentId" title="请选择一名学生" description="查看并登记该生的家校联系记录" />
    <LoadingState v-else-if="loading" text="正在加载联系记录…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <EmptyState v-else-if="!contacts.length" title="暂无家校联系记录" description="点「登记联系」记录一次家校沟通" />
    <template v-else>
      <ul class="fc-list">
        <li v-for="c in contacts" :key="c.contactId" class="fc-item">
          <div class="fc-item__head">
            <span class="fc-item__type">{{ contactTypeLabel(c.contactType) }}</span>
            <span v-if="c.fullPhoneViewed" class="fc-item__sensitive">🔒 曾查看完整号码</span>
            <span class="fc-item__time"><AppDateDisplay :value="c.occurredAt" mode="datetime" empty-text="" /></span>
          </div>
          <div v-if="c.reason" class="fc-item__row">事由：{{ c.reason }}</div>
          <div v-if="c.result" class="fc-item__row">结果：{{ c.result }}</div>
        </li>
      </ul>
      <AppPagination
        v-if="total > pageSize"
        class="fc-pagination"
        v-model:page="page"
        v-model:pageSize="pageSize"
        :total="total"
        @change="load"
      />
    </template>

    <!-- 登记联系 drawer -->
    <AppDrawer v-model:visible="createModal.visible" title="登记家校联系">
      <AppFormItem label="联系方式" required>
        <AppSelect v-model="createModal.contactType" :options="contactTypeOptions" />
      </AppFormItem>
      <AppFormItem label="联系事由">
        <AppQuickPhrases scene-key="sa.family.reason" @pick="onPickReason" />
        <AppTextInput ref="reasonInput" v-model="createModal.reason" placeholder="如：反馈近期学业情况" />
      </AppFormItem>
      <AppFormItem label="联系结果">
        <AppQuickPhrases scene-key="sa.family.result" @pick="onPickResult" />
        <AppTextarea ref="resultTa" v-model="createModal.result" :rows="3" placeholder="家长反馈、约定事项等" />
      </AppFormItem>
      <label class="fc-check">
        <input v-model="createModal.fullPhoneView" type="checkbox" /> 本次需查看家长完整号码（将记敏感审计）
      </label>
      <AppFormItem v-if="createModal.fullPhoneView" label="查看原因（≥5字）" required>
        <AppQuickPhrases scene-key="common.revealReason" @pick="onPickViewReason" />
        <AppTextInput ref="viewReasonInput" v-model="createModal.viewReason" placeholder="说明查看完整号码的原因，不少于 5 字" />
      </AppFormItem>
      <AppInlineAlert v-if="createModal.error" type="danger" :description="createModal.error" />
      <template #footer>
        <button type="button" class="fc-btn" @click="createModal.visible = false">取消</button>
        <button type="button" class="fc-btn fc-btn--primary" :disabled="acting" @click="submitCreate">登记</button>
      </template>
    </AppDrawer>
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
  AppDateDisplay, AppFormItem, AppInlineAlert, AppPagination,
  AppQuickPhrases, AppSelect, AppStudentPicker, AppTextInput, AppTextarea
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'

const CONTACT_TYPE = { PHONE: '电话', WECHAT: '微信', VISIT: '家访', MESSAGE: '短信' }
const CONTACT_TYPE_OPTIONS = Object.entries(CONTACT_TYPE).map(([value, label]) => ({ value, label }))

export default {
  name: 'FamilyContactView',
  components: {
    ModulePageShell, LoadingState, ErrorState, EmptyState,
    AppDateDisplay, AppDrawer, AppFormItem, AppInlineAlert, AppPagination,
    AppQuickPhrases, AppSelect, AppStudentPicker, AppTextInput, AppTextarea
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      studentId: '', loading: false, error: '', contacts: [], acting: false,
      page: 1, pageSize: 20, total: 0,
      contactTypeOptions: CONTACT_TYPE_OPTIONS,
      createModal: { visible: false, contactType: 'PHONE', reason: '', result: '', fullPhoneView: false, viewReason: '', error: '' }
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    }
  },
  methods: {
    contactTypeLabel(t) {
      return CONTACT_TYPE[t] || t || '—'
    },
    searchStudents(keyword) {
      return studentAffairsApi.searchStudents(keyword)
    },
    onPick() {
      this.page = 1
      if (this.studentId) this.load()
    },
    async load() {
      if (!this.studentId) return
      this.loading = true
      this.error = ''
      const res = await studentAffairsApi.getFamilyContacts(this.studentId, { page: this.page, pageSize: this.pageSize })
      this.loading = false
      if (res.code === 0 && res.data) { this.contacts = res.data.items || []; this.total = res.data.total || 0 }
      else { this.contacts = []; this.total = 0; this.error = res.message || '加载失败' }
    },
    openCreate() {
      this.createModal = { visible: true, contactType: 'PHONE', reason: '', result: '', fullPhoneView: false, viewReason: '', error: '' }
    },
    onPickReason(text) {
      const el = this.$refs.reasonInput && this.$refs.reasonInput.$refs.input
      const { value, selStart, selEnd } = insertAtCursor(el, this.createModal.reason, text)
      this.createModal.reason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    onPickResult(text) {
      const el = this.$refs.resultTa && this.$refs.resultTa.$refs.el
      const { value, selStart, selEnd } = insertAtCursor(el, this.createModal.result, text)
      this.createModal.result = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    onPickViewReason(text) {
      const el = this.$refs.viewReasonInput && this.$refs.viewReasonInput.$refs.input
      const { value, selStart, selEnd } = insertAtCursor(el, this.createModal.viewReason, text)
      this.createModal.viewReason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async submitCreate() {
      const m = this.createModal
      const reason = (m.reason || '').trim()
      const result = (m.result || '').trim()
      const viewReason = (m.viewReason || '').trim()
      if (m.fullPhoneView && viewReason.length < 5) { m.error = '查看完整号码原因不少于 5 字'; return }
      this.acting = true
      const res = await studentAffairsApi.createFamilyContact(this.studentId, {
        contactType: m.contactType, reason, result,
        fullPhoneView: !!m.fullPhoneView, viewReason
      })
      this.acting = false
      if (res.code === 0) {
        toast.success(m.fullPhoneView ? '已登记（含完整号码查看审计）' : '已登记')
        this.createModal.visible = false
        this.page = 1
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
.fc-check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}
.fc-pagination {
  margin-top: var(--space-4);
}
</style>
