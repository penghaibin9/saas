<template>
  <ModulePageShell
    title="家校联系"
    subtitle="家校联系记录（留痕）· 查看完整号码需原因与审计"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="家校联系查阅"
  >
    <section class="sa-summary-strip">
      <div class="sa-summary-strip__content">
        <span class="sa-summary-strip__eyebrow">家校沟通工作区</span>
        <h2 class="sa-summary-strip__title">先选择学生查看历史沟通，再登记本次联系事由、反馈和约定事项</h2>
        <p class="sa-summary-strip__text">联系记录按时间留痕。只有确需拨打或核对时才查看完整号码，查看原因会进入敏感审计。</p>
      </div>
    </section>

    <div class="sa-workflow-strip" aria-label="家校联系流程">
      <div class="sa-workflow-step" data-step="1"><strong>选择学生</strong><br>按姓名或学号定位当前学生</div>
      <div class="sa-workflow-step" data-step="2"><strong>回看历史</strong><br>了解此前事由、家长反馈与约定</div>
      <div class="sa-workflow-step" data-step="3"><strong>完成联系</strong><br>通过电话、微信、家访或短信沟通</div>
      <div class="sa-workflow-step" data-step="4"><strong>登记留痕</strong><br>记录结果、后续安排和敏感查看审计</div>
    </div>

    <div class="fc-picker sa-filter-bar">
      <div class="fc-picker__copy">
        <span class="fc-picker__label">当前学生</span>
        <small>选择后加载该生完整家校联系时间线</small>
      </div>
      <div class="fc-picker__control">
        <AppStudentPicker v-model="studentId" placeholder="按姓名 / 学号搜索学生" @change="onPick" />
      </div>
      <AppPermissionButton :allowed="canBtn('studentAffairs.homeSchool.record.create')" code="studentAffairs.homeSchool.record.create" variant="primary" size="sm" :disabled="!studentId" @click="openCreate">登记联系</AppPermissionButton>
    </div>

    <EmptyState v-if="!studentId" title="请选择一名学生" description="选择后可查看该生家校联系历史，并登记新的沟通记录" />
    <LoadingState v-else-if="loading" text="正在加载联系记录…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <EmptyState v-else-if="!contacts.length" title="暂无家校联系记录" description="该生尚未建立家校沟通记录，可点击“登记联系”记录首次沟通" />
    <template v-else>
      <div class="fc-timeline-head">
        <div>
          <strong>家校联系时间线</strong>
          <span>共 {{ total }} 条记录，按时间顺序查看沟通事由与结果</span>
        </div>
        <AppPermissionButton :allowed="canBtn('studentAffairs.homeSchool.record.create')" code="studentAffairs.homeSchool.record.create" variant="primary" size="sm" :disabled="!studentId" @click="openCreate">登记本次联系</AppPermissionButton>
      </div>
      <ul class="fc-list">
        <li v-for="c in contacts" :key="c.contactId" class="fc-item">
          <div class="fc-item__rail"><span></span></div>
          <div class="fc-item__content">
            <div class="fc-item__head">
              <span class="fc-item__type">{{ contactTypeLabel(c.contactType) }}</span>
              <span v-if="c.fullPhoneViewed" class="fc-item__sensitive">🔒 已记录完整号码查看审计</span>
              <span class="fc-item__time"><AppDateDisplay :value="c.occurredAt" mode="datetime" empty-text="" /></span>
            </div>
            <div class="fc-item__body">
              <div class="fc-item__row"><span>联系事由</span><p>{{ c.reason || '未记录' }}</p></div>
              <div class="fc-item__row"><span>沟通结果</span><p>{{ c.result || '未记录' }}</p></div>
            </div>
          </div>
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

    <AppDrawer v-model:visible="createModal.visible" title="登记家校联系" mode="modal" size="large">
      <div class="fc-form-note">请客观记录联系事由、家长反馈和下一步约定。完整号码只在确有联系需要时查看。</div>
      <AppFormItem label="联系方式" required>
        <AppSelect v-model="createModal.contactType" :options="contactTypeOptions" />
      </AppFormItem>
      <AppFormItem label="联系事由">
        <AppQuickPhrases scene-key="sa.family.reason" @pick="onPickReason" />
        <AppTextInput ref="reasonInput" v-model="createModal.reason" placeholder="如：反馈近期学业情况" />
      </AppFormItem>
      <AppFormItem label="联系结果">
        <AppQuickPhrases scene-key="sa.family.result" @pick="onPickResult" />
        <AppTextarea ref="resultTa" v-model="createModal.result" :rows="3" placeholder="记录家长反馈、达成共识和后续约定" />
      </AppFormItem>
      <label class="fc-check" :class="{ 'is-on': createModal.fullPhoneView }">
        <input v-model="createModal.fullPhoneView" type="checkbox" />
        <span><strong>本次需查看家长完整号码</strong><small>查看行为和原因将写入敏感审计</small></span>
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
  AppDateDisplay, AppFormItem, AppInlineAlert, AppPagination, AppPermissionButton,
  AppQuickPhrases, AppSelect, AppStudentPicker, AppTextInput, AppTextarea
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const CONTACT_TYPE = { PHONE: '电话', WECHAT: '微信', VISIT: '家访', MESSAGE: '短信' }
const CONTACT_TYPE_OPTIONS = Object.entries(CONTACT_TYPE).map(([value, label]) => ({ value, label }))

export default {
  name: 'FamilyContactView',
  components: {
    ModulePageShell, LoadingState, ErrorState, EmptyState,
    AppDateDisplay, AppDrawer, AppFormItem, AppInlineAlert, AppPagination, AppPermissionButton,
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
  created() {
    const q = this.$route.query || {}
    if (q.studentId) {
      this.studentId = String(q.studentId)
      this.load()
    }
  },
  watch: {
    '$route.query.studentId'(v) {
      if (v) {
        this.studentId = String(v)
        this.page = 1
        this.load()
      }
    }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    contactTypeLabel(t) {
      return CONTACT_TYPE[t] || t || '—'
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
.fc-picker { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-4); }
.fc-picker__copy { display: grid; gap: 2px; min-width: 150px; }
.fc-picker__copy small { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.fc-picker__label { font-size: var(--font-size-sm); color: var(--text-primary); font-weight: 600; white-space: nowrap; }
.fc-picker__control { flex: 1 1 360px; min-width: 260px; }
.fc-timeline-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); padding-bottom: var(--space-3); border-bottom: 1px solid var(--border-light); }
.fc-timeline-head > div { display: grid; gap: 3px; }
.fc-timeline-head strong { color: var(--text-primary); }
.fc-timeline-head span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.fc-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-3); }
.fc-item { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: var(--space-2); min-width: 0; }
.fc-item__rail { position: relative; display: flex; justify-content: center; }
.fc-item__rail::after { content: ''; position: absolute; top: 16px; bottom: calc(-1 * var(--space-3) - 4px); width: 2px; background: var(--border-light); }
.fc-item:last-child .fc-item__rail::after { display: none; }
.fc-item__rail span { position: relative; z-index: 1; width: 10px; height: 10px; margin-top: 16px; border: 2px solid var(--primary-500); border-radius: 50%; background: var(--bg-card); }
.fc-item__content { min-width: 0; padding: var(--space-3) var(--space-4); border: 1px solid var(--border-base); border-radius: var(--radius-lg); background: var(--bg-card); }
.fc-item__head { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); padding-bottom: var(--space-2); border-bottom: 1px solid var(--border-light); }
.fc-item__type { font-weight: 700; color: var(--primary-700); }
.fc-item__sensitive { padding: 2px 7px; border-radius: var(--radius-full); background: var(--danger-50); color: var(--danger-700, #b91c1c); font-size: var(--font-size-xs); }
.fc-item__time { margin-left: auto; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.fc-item__body { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }
.fc-item__row { min-width: 0; font-size: var(--font-size-sm); color: var(--text-secondary); }
.fc-item__row > span { display: block; margin-bottom: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.fc-item__row p { margin: 0; white-space: normal; overflow-wrap: anywhere; line-height: 1.6; }
.fc-form-note { margin-bottom: var(--space-4); padding: 10px 12px; border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.fc-check { display: flex; align-items: flex-start; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-md); color: var(--text-secondary); font-size: var(--font-size-sm); }
.fc-check.is-on { border-color: var(--warning-300, #fcd34d); background: var(--warning-50, #fffbeb); }
.fc-check span { display: grid; gap: 2px; }
.fc-check strong { color: var(--text-primary); }
.fc-check small { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.fc-btn { height: 34px; padding: 0 var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-base); background: var(--bg-card); color: var(--text-primary); font-size: var(--font-size-sm); cursor: pointer; }
.fc-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.fc-btn--primary { background: var(--primary-600); border-color: var(--primary-600); color: #fff; }
.fc-pagination { margin-top: var(--space-4); }
@media (max-width: 760px) { .fc-picker, .fc-timeline-head { align-items: stretch; flex-direction: column; } .fc-picker__control { width: 100%; min-width: 0; } .fc-item__body { grid-template-columns: 1fr; } .fc-item__time { margin-left: 0; } .fc-item__head { flex-wrap: wrap; } }
</style>
