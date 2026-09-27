<template>
  <ModulePageShell
    :watermark="false"
    :title="detail ? `${detail.studentName} · 三方协议档案` : '三方协议档案'"
    :subtitle="detail ? [detail.enterpriseName, detail.positionName, detail.templateName].filter(Boolean).join(' · ') : ''"
  >
    <template #actions>
      <AppButton variant="ghost" @click="backToList">返回协议列表</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" @back="backToList" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="detail" class="agd">
      <!-- 左：协议内容 -->
      <div class="mp-stack agd-main">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">协议信息</span>
            <AppStatusTag :status="detail.status">{{ detail.statusLabel }}</AppStatusTag>
          </div>
          <div class="mp-card__body">
            <AppDescriptionList :items="infoItems" :columns="2" size="compact" label-width="80px" />
            <p v-if="detail.rejectReason" class="agd-reason">驳回/作废原因：{{ detail.rejectReason }}</p>
          </div>
        </section>

        <nav class="agd-tabs" aria-label="协议档案内容">
          <button v-for="tab in detailTabs" :key="tab.key" type="button" :class="{ 'is-active': activeSection === tab.key }" :aria-current="activeSection === tab.key ? 'page' : undefined" @click="showSection(tab.key)">{{ tab.label }}</button>
        </nav>
        <section v-show="activeSection === 'body'" class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">协议正文</span>
            <div class="agd-ops">
              <AppPrintButton v-if="detail.renderedBody" print-selector="#agreement-print-body" label="打印正文" />
              <AppPermissionButton v-if="detail.renderedBody" code="internship.agreement.view" :allowed="canBtn('internship.agreement.view')"
                variant="ghost" size="sm" :loading="pdfLoading" @click="downloadPdf">下载 PDF</AppPermissionButton>
            </div>
          </div>
          <div class="mp-card__body">
            <p v-if="pdfError" class="agd-reason" role="alert">{{ pdfError }}</p>
            <pre v-if="detail.renderedBody" id="agreement-print-body" class="agd-body">{{ detail.renderedBody }}</pre>
            <p v-else class="mp-note" style="margin: 0">该协议未生成正文快照（早期数据或模板缺失）。</p>
          </div>
        </section>

        <section v-show="activeSection === 'files'" class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">签署扫描件</span></div>
          <div class="mp-card__body">
            <template v-if="detail.attachment">
              <p v-if="fileLoading" class="mp-note">正在读取签署材料…</p>
              <p v-else-if="fileError" class="agd-reason" role="alert">{{ fileError }} <AppButton variant="ghost" size="sm" @click="loadFile">重试</AppButton></p>
              <FilePreviewer v-else-if="file" :file="file" inline :provider="previewProvider" :download-handler="downloadAtt" @error="onFileError" />
            </template>
            <p v-else class="mp-note" style="margin: 0">暂无签署扫描件；企业签署环节上传后在此展示。</p>
          </div>
        </section>
        <section v-show="activeSection === 'history'" class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">办理记录</span></div>
          <div class="mp-card__body">
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无办理记录" />
          </div>
        </section>
      </div>

      <!-- 右：确认进度与办理 -->
      <aside class="mp-stack agd-rail">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">三方确认进度</span></div>
          <div class="mp-card__body agd-progress">
            <div class="agd-step">
              <span class="agd-step__lbl">学生确认</span>
              <AppStatusTag :type="confirmTone(detail.studentConfirm)">{{ detail.studentConfirmLabel }}</AppStatusTag>
            </div>
            <div class="agd-step">
              <span class="agd-step__lbl">企业确认</span>
              <AppStatusTag :type="confirmTone(detail.enterpriseConfirm)">{{ detail.enterpriseConfirmLabel }}</AppStatusTag>
            </div>
            <div class="agd-step">
              <span class="agd-step__lbl">学校确认</span>
              <AppStatusTag :type="confirmTone(detail.schoolConfirm)">{{ detail.schoolConfirmLabel }}</AppStatusTag>
            </div>
            <div class="agd-step">
              <span class="agd-step__lbl">内部确认时间线</span>
              <AppStatusTag :type="detail.esignStatus === 'INTERNAL_CONFIRMED' ? 'success' : detail.esignStatus === 'PENDING' ? 'warning' : 'default'">
                {{ detail.esignStatus === 'INTERNAL_CONFIRMED' ? '内部确认完成' : detail.esignStatus === 'PENDING' ? '确认中' : '未发起' }}
              </AppStatusTag>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">当前办理</span></div>
          <div class="mp-card__body">
            <p class="agd-next">{{ nextStepText }}</p>
            <p v-if="actionSubmitting" class="mp-note" role="status">正在提交，请等待处理结果。</p>
            <p v-if="actionError && !cd.visible" class="agd-reason" role="alert">{{ actionError }}</p>
            <!-- 记录企业签署（内联表单，取代原窄弹窗） -->
            <template v-if="detail.status === 'PENDING_ENTERPRISE'">
              <div class="agd-ent">
                <AppFormItem label="企业经办人">
                  <AppTextInput v-model="entForm.confirmBy" :disabled="entBusy || actionSubmitting || !canBtn('internship.agreement.manage')" placeholder="填写企业实际经办人" />
                </AppFormItem>
                <AppFormItem label="签署扫描件（企业已签的纸质三方协议）" required>
                  <input type="file" class="agd-file" :disabled="entBusy || actionSubmitting || !canBtn('internship.agreement.manage')" @change="onEntFile" />
                  <span v-if="uploadingFile" class="agd-att" role="status">正在上传，新文件上传成功后替换原材料…</span>
                  <span v-else-if="entForm.fileId" class="agd-att">{{ entAttachName }} · 待确认登记</span>
                  <div v-if="entForm.fileId" class="agd-upload-preview" :aria-busy="entFileLoading">
                    <p v-if="entFileLoading" class="mp-note" role="status">正在读取材料安全状态…</p>
                    <p v-else-if="entFileError" class="agd-reason" role="alert">{{ entFileError }}</p>
                    <FilePreviewer v-else-if="entFile" :file="entFile" inline :provider="previewProvider" @error="entFileError = $event?.message || '材料打开失败，请重试'" />
                    <p v-if="!entFileLoading && !enterpriseFileReady" class="mp-note">材料可安全查看后才能登记，请重新读取状态或更换文件。</p>
                    <AppButton variant="ghost" size="sm" :disabled="entBusy || actionSubmitting" @click="loadEnterpriseFile">重新读取材料</AppButton>
                  </div>
                </AppFormItem>
                <p v-if="entError" class="agd-reason" role="alert">{{ entError }}</p>
                <p class="mp-note">无电子签章时，以上传企业已签署的纸质三方协议扫描件为准。</p>
              </div>
            </template>

            <div class="agd-actions">
              <AppPermissionButton v-if="detail.status === 'DRAFT'" code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')"
                variant="primary" :disabled="actionBusy" @click="confirmAct('issue')">下发给学生确认</AppPermissionButton>
              <AppPermissionButton v-if="detail.esignStatus === 'NONE' && canReject" code="internship.agreement.sign" :allowed="canBtn('internship.agreement.sign')"
                variant="ghost" :disabled="actionBusy" @click="startEsign">发起内部确认</AppPermissionButton>
              <!-- 企业方禁止教师代签电子签；正式路径为上方纸质扫描件确认（对标企业真签） -->
              <AppPermissionButton v-if="detail.esignStatus === 'PENDING' && detail.status === 'PENDING_SCHOOL'"
                code="internship.agreement.sign" :allowed="canBtn('internship.agreement.sign')" variant="ghost" :disabled="actionBusy" @click="esignParty('SCHOOL')">学校内部确认</AppPermissionButton>
              <AppPermissionButton v-if="detail.status === 'PENDING_ENTERPRISE'" code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')"
                variant="primary" :disabled="!enterpriseFileReady || uploadingFile || actionSubmitting" :loading="entSubmitting"
                @click="submitEnterprise">确认企业已签署</AppPermissionButton>
              <AppButton v-if="detail.status === 'PENDING_SCHOOL' && detail.attachment?.fileId" variant="secondary" @click="showSection('files')">核对企业签署材料</AppButton>
              <AppPermissionButton v-if="detail.status === 'PENDING_SCHOOL'" code="internship.agreement.schoolConfirm" :allowed="canBtn('internship.agreement.schoolConfirm')"
                variant="primary" :disabled="actionBusy" @click="confirmAct('school')">学校确认生效</AppPermissionButton>
              <AppPermissionButton v-if="detail.status === 'EFFECTIVE'" code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')"
                variant="primary" :disabled="actionBusy" @click="confirmAct('archive')">归档协议</AppPermissionButton>
              <AppPermissionButton v-if="canReject" code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')"
                variant="ghost" :disabled="actionBusy" :danger="true" @click="confirmAct('reject')">驳回</AppPermissionButton>
              <AppPermissionButton v-if="canVoid" code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')"
                variant="ghost" :disabled="actionBusy" :danger="true" @click="confirmAct('void')">作废</AppPermissionButton>
            </div>
            <p v-if="isFinal" class="mp-note" style="margin-top: var(--space-2)">
              协议已处于终态（{{ detail.statusLabel }}），仅可查看与打印，不可再变更。
            </p>
          </div>
        </section>


      </aside>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="原因" :submitting="actionSubmitting" @confirm="onConfirm">
      <p v-if="actionError" class="agd-reason" role="alert">{{ actionError }}</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 三方协议独立档案页（/admin/internship/agreements/:id）。
 * 原协议详情/企业签署两个窄弹窗收口至此：正文 + 附件 + 三方进度 + 全部办理动作 + 审计留痕。
 * 状态流转全部走真实 agreementApi，越权与非法状态由后端拦截。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppPermissionButton, AppDescriptionList, AppAuditTrail,
  AppTextInput, AppFormItem, AppPrintButton } from '@/components/common'
import { agreementApi } from '@/modules/internship/api/agreement.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import FilePreviewer from '@/components/file/FilePreviewer.vue'
import { fileSdk } from '@/services/file/fileSdk'
import { normalizeUiError } from '@/utils/presentationSafety'

const INFO = [
  { key: 'studentName', label: '学生' }, { key: 'studentNo', label: '学号' },
  { key: 'advisorName', label: '指导教师' }, { key: 'enterpriseName', label: '企业' },
  { key: 'positionName', label: '岗位' }, { key: 'templateName', label: '协议模板' }
]
const AUDIT_ACTION_LABELS = {
  GENERATE: '生成协议草稿', ISSUE: '下发学生确认', STUDENT_CONFIRM: '学生确认协议',
  STUDENT_REJECT: '学生驳回协议', ENTERPRISE_CONFIRM: '登记企业签署', SCHOOL_CONFIRM: '学校确认生效',
  REJECT: '驳回协议', VOID: '作废协议', ARCHIVE: '归档协议',
  ESIGN_START: '发起内部确认', ESIGN_SIGN: '记录内部确认'
}

export default {
  name: 'AgreementDetailView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, LoadingState, ErrorState, AppButton, AppStatusTag, AppConfirmDialog,
    AppPermissionButton, AppDescriptionList, AppAuditTrail, AppTextInput, AppFormItem, FilePreviewer, AppPrintButton },
  data() {
    return {
      loading: true, error: '', detail: null, loadTicket: 0,
      entForm: { confirmBy: '', fileId: '' }, entAttachName: '', entFile: null, entFileLoading: false, entFileError: '', entFileTicket: 0, entError: '', uploadingFile: false, entSubmitting: false,
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false },
      pendingKind: '', pendingTarget: null, actionSubmitting: false, actionError: '', pdfLoading: false, pdfError: '', file: null, fileLoading: false, fileError: '',
      previewProvider: { fetchBytes: descriptor => fileSdk.blob(descriptor.fileId), dispose() {} },
      detailTabs: [{ key: 'body', label: '协议正文' }, { key: 'files', label: '签署材料' }, { key: 'history', label: '办理记录' }]
    }
  },
  computed: {
    recordScope() { return [this.ctx?.ctxKey || '', this.$route.params?.id || '', this.$route.query.batchId || ''].join('|') },
    entBusy() { return this.uploadingFile || this.entSubmitting || this.entFileLoading },
    enterpriseFileReady() {
      return !!this.entForm.fileId && String(this.entFile?.fileId) === String(this.entForm.fileId)
        && this.entFile.readyForBusiness && (this.entFile.canPreview || this.entFile.canDownload)
        && !this.entFileLoading && !this.entFileError
    },
    actionBusy() { return this.entBusy || this.actionSubmitting },
    infoItems() { const d = this.detail || {}; return INFO.map((f) => ({ label: f.label, value: d[f.key] || '—' })) },
    activeSection() { return this.detailTabs.some(tab => tab.key === this.$route.query.section) ? this.$route.query.section : 'body' },
    nextStepText() {
      return ({ DRAFT: '核对正文后下发，由学生继续确认。', PENDING_STUDENT: '等待学生确认协议内容。', PENDING_ENTERPRISE: '核对企业签署材料，登记后交学校确认。', PENDING_SCHOOL: '核对三方信息及签署材料，确认协议生效。', EFFECTIVE: '协议已生效，可归档留存。', REJECTED: '协议已驳回，请查看原因及办理记录。', VOIDED: '协议已作废，保留档案供查阅。', ARCHIVED: '归档已完成，可查阅正文、材料与办理记录。' })[this.detail?.status] || '请核对当前协议状态。'
    },
    auditRecords() {
      return (this.detail?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actionLabel: AUDIT_ACTION_LABELS[t.action] || '协议操作', actor: t.operator, reason: t.detail && (t.detail.reason || t.detail.confirmBy || ''), at: t.occurredAt
      }))
    },
    canReject() { return ['PENDING_STUDENT', 'PENDING_ENTERPRISE', 'PENDING_SCHOOL'].includes(this.detail?.status) },
    canVoid() { return ['DRAFT', 'PENDING_STUDENT', 'PENDING_ENTERPRISE', 'PENDING_SCHOOL'].includes(this.detail?.status) },
    isFinal() { return ['REJECTED', 'VOIDED', 'ARCHIVED'].includes(this.detail?.status) }
  },
  watch: {
    '$route.params.id'(id, oldId) {
      if (!id || id === oldId) return
      this.detail = null
      this.cd.visible = false
      this.load()
      this.focusHeading()
    }
  },
  created() { this.load() },
  mounted() { this.focusHeading() },
  beforeUnmount() { this.loadTicket++ },
  methods: {
    focusHeading() {
      this.$nextTick(() => {
        const heading = this.$el?.querySelector('h1')
        if (!heading) return
        heading.setAttribute('tabindex', '-1')
        heading.style.scrollMarginTop = '16px'
        heading.focus({ preventScroll: true })
        heading.scrollIntoView({ block: 'start', behavior: 'instant' })
      })
    },
    canBtn(code) { return Array.isArray(this.ctx?.permissionPatterns) && canCode(this.ctx, code) },
    confirmTone(s) { return s === 'CONFIRMED' ? 'success' : s === 'REJECTED' ? 'danger' : 'warning' },
    backToList() {
      const query = { ...this.$route.query }; delete query.section
      this.$router.push({ path: '/admin/internship/agreements', query })
    },
    showSection(section) { this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, section } }) },
    onFileError(error) { this.fileError = normalizeUiError(error, { fallback: '签署材料暂时无法读取，请重试。' }).userMessage },
    async loadFile() {
      const id = this.detail?.attachment?.fileId
      const ticket = this.loadTicket, scope = this.recordScope
      const current = () => ticket === this.loadTicket && scope === this.recordScope && this.detail?.attachment?.fileId === id
      this.file = null; this.fileError = ''; this.fileLoading = false
      if (!id) return
      this.fileLoading = true
      try { const file = await fileSdk.metadata(String(id)); if (current()) this.file = file }
      catch (error) { if (current()) this.onFileError(error) }
      finally { if (current()) this.fileLoading = false }
    },
    async load() {
      const ticket = ++this.loadTicket
      this.loading = true; this.error = ''; this.detail = null
      this.entForm = { confirmBy: '', fileId: '' }; this.entAttachName = ''; this.entError = ''
      this.entFileTicket++; this.entFile = null; this.entFileLoading = false; this.entFileError = ''
      this.uploadingFile = false; this.entSubmitting = false
      this.actionSubmitting = false; this.actionError = ''; this.cd.visible = false; this.pendingTarget = null; this.pendingKind = ''
      this.pdfLoading = false; this.pdfError = ''
      const id = this.$route.params.id
      try {
        const res = await agreementApi.getDetail(id)
        if (ticket !== this.loadTicket || id !== this.$route.params.id) return
        if (res.code !== 0 || !res.data) throw new Error(res.message || '协议不存在或无权查看')
        if (this.$route.query.batchId && String(res.data.batchId) !== String(this.$route.query.batchId)) throw new Error('该协议不属于当前批次，请返回列表核对')
        this.detail = res.data
        this.loadFile()
      } catch (error) {
        if (ticket === this.loadTicket) this.error = error.message || '协议加载失败，请重试'
      } finally { if (ticket === this.loadTicket) this.loading = false }
    },
    async onEntFile(e) {
      if (this.entBusy || this.actionSubmitting || this.loading || this.detail?.status !== 'PENDING_ENTERPRISE' || !this.canBtn('internship.agreement.manage')) return
      const file = e.target.files && e.target.files[0]
      if (!file) return
      const ticket = this.loadTicket, scope = this.recordScope
      this.uploadingFile = true
      this.entError = ''
      try {
        const res = await agreementApi.uploadAttachment(file)
        if (ticket !== this.loadTicket || scope !== this.recordScope) return
        if (res.code !== 0 || !res.data?.fileId) throw new Error(res.message || '扫描件上传失败，请重新选择文件')
        this.entForm.fileId = String(res.data.fileId)
        this.entAttachName = res.data.fileName || file.name
        await this.loadEnterpriseFile()
      } catch (error) {
        if (ticket === this.loadTicket && scope === this.recordScope) this.entError = `${error.message || '扫描件上传失败，请重新选择文件'}${this.entForm.fileId ? '。原材料已保留。' : ''}`
      } finally {
        e.target.value = ''
        if (ticket === this.loadTicket && scope === this.recordScope) this.uploadingFile = false
      }
    },
    async loadEnterpriseFile() {
      if (!this.entForm.fileId || this.entFileLoading || this.entSubmitting || this.actionSubmitting) return
      const fileId = String(this.entForm.fileId), ticket = this.loadTicket, scope = this.recordScope
      const seq = ++this.entFileTicket
      const current = () => seq === this.entFileTicket && ticket === this.loadTicket && scope === this.recordScope && String(this.entForm.fileId) === fileId
      this.entFileLoading = true; this.entFileError = ''; this.entFile = null
      try {
        const file = await fileSdk.metadata(fileId)
        if (current()) this.entFile = file
      } catch (error) {
        if (current()) this.entFileError = error?.message || '材料读取失败，请重试'
      } finally { if (current()) this.entFileLoading = false }
    },
    async submitEnterprise() {
      if (this.entBusy || this.actionSubmitting || this.loading || this.detail?.status !== 'PENDING_ENTERPRISE' || !this.canBtn('internship.agreement.manage')) return
      if (!this.entForm.fileId) { this.entError = '请先上传企业已签署的扫描件'; return }
      if (!this.enterpriseFileReady) { this.entError = '请先读取并核对安全可用的企业签署材料'; return }
      const ticket = this.loadTicket, scope = this.recordScope, id = this.detail.id
      this.entSubmitting = true
      this.entError = ''
      try {
        const res = await agreementApi.enterpriseConfirm(id, {
          confirmBy: this.entForm.confirmBy, fileId: this.entForm.fileId,
          expectedVersion: this.detail.version
        })
        if (ticket !== this.loadTicket || scope !== this.recordScope) return
        if (res.code !== 0) throw new Error(res.message || '登记失败，请重试')
        toast.success('已记录企业签署，进入学校确认环节')
        await this.load()
      } catch (error) {
        if (ticket === this.loadTicket && scope === this.recordScope) this.entError = `${error.message || '登记失败，请重试'}。经办人与扫描件已保留。`
      } finally {
        if (ticket === this.loadTicket && scope === this.recordScope) this.entSubmitting = false
      }
    },
    async downloadAtt() {
      const a = this.detail?.attachment
      if (!a) return
      try { await agreementApi.downloadAttachment(a.fileId, a.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    async downloadPdf() {
      if (!this.detail?.id || this.pdfLoading || !this.canBtn('internship.agreement.view')) return
      const ticket = this.loadTicket, scope = this.recordScope, id = this.detail.id
      this.pdfLoading = true
      this.pdfError = ''
      try {
        const res = await agreementApi.exportAgreementPdf(id)
        if (ticket !== this.loadTicket || scope !== this.recordScope) return
        if (res.code !== 0) throw new Error(res.message || 'PDF 生成失败，请重试')
        downloadXlsxFromApi(res.data)
        toast.success('PDF 套打已下载（含水印与导出留痕）')
      } catch (error) {
        if (ticket === this.loadTicket && scope === this.recordScope) this.pdfError = error.message || 'PDF 下载失败，请重试'
      } finally {
        if (ticket === this.loadTicket && scope === this.recordScope) this.pdfLoading = false
      }
    },
    confirmAct(kind) {
      if (!this.detail || this.loading || this.actionBusy || !this.canConfirmKind(kind)) return
      const name = this.detail.studentName
      const map = {
        issue: { title: '下发协议', content: `将「${name}」的协议下发给学生确认？`, danger: false, confirmText: '下发', requireReason: false },
        school: { title: '学校确认', content: `确认「${name}」三方协议生效？`, danger: false, confirmText: '确认生效', requireReason: false },
        archive: { title: '归档协议', content: `归档「${name}」的已生效协议？归档后进入只读台账。`, danger: false, confirmText: '归档', requireReason: false },
        reject: { title: '驳回协议', content: `驳回「${name}」的协议，原因将写入审计。`, danger: true, confirmText: '驳回', requireReason: true },
        void: { title: '作废协议', content: `作废「${name}」的协议，原因将写入审计。`, danger: true, confirmText: '作废', requireReason: true }
      }[kind]
      this.pendingKind = kind
      this.pendingTarget = { id: this.detail.id, version: this.detail.version, scope: this.recordScope, ticket: this.loadTicket }
      this.actionError = ''
      this.cd = { visible: true, ...map }
    },
    canConfirmKind(kind) {
      const allowed = { issue: this.detail?.status === 'DRAFT', school: this.detail?.status === 'PENDING_SCHOOL', archive: this.detail?.status === 'EFFECTIVE', reject: this.canReject, void: this.canVoid }
      return allowed[kind] === true && this.canBtn(kind === 'school' ? 'internship.agreement.schoolConfirm' : 'internship.agreement.manage')
    },
    async runAgreementAction(operation, successText) {
      if (!this.detail || this.loading || this.actionBusy) return
      const ticket = this.loadTicket, scope = this.recordScope
      this.actionSubmitting = true; this.actionError = ''
      try {
        const res = await operation()
        if (ticket !== this.loadTicket || scope !== this.recordScope) return
        if (res?.code !== 0) throw new Error(res?.message || '操作未完成，请重试')
        this.cd.visible = false
        toast.success(successText)
        await this.load()
      } catch (error) {
        if (ticket === this.loadTicket && scope === this.recordScope) this.actionError = error.message || '操作未完成，请重试'
      } finally {
        if (ticket === this.loadTicket && scope === this.recordScope) this.actionSubmitting = false
      }
    },
    async onConfirm({ reason = '' } = {}) {
      if (!this.cd.visible || !this.canConfirmKind(this.pendingKind)) return
      const target = this.pendingTarget
      if (!target || target.id !== this.detail?.id || target.version !== this.detail?.version || target.scope !== this.recordScope || target.ticket !== this.loadTicket) {
        this.actionError = '协议信息已变化，请关闭确认框并重新核对'
        return
      }
      const ver = { expectedVersion: target.version }, id = target.id
      const commands = {
        issue: () => agreementApi.issue(id, ver), school: () => agreementApi.schoolConfirm(id, ver),
        archive: () => agreementApi.archive(id, ver), reject: () => agreementApi.reject(id, { reason, ...ver }),
        void: () => agreementApi.voidAgreement(id, { reason, ...ver })
      }
      const receipts = { issue: '协议已下发，等待学生确认', school: '协议已生效，可归档留存', archive: '协议已归档，可查阅正文与签署材料', reject: '协议已驳回，原因已记录', void: '协议已作废，历史档案保留' }
      await this.runAgreementAction(commands[this.pendingKind], receipts[this.pendingKind])
    },
    async startEsign() {
      if (this.detail?.esignStatus !== 'NONE' || !this.canReject || !this.canBtn('internship.agreement.sign')) return
      const id = this.detail.id
      await this.runAgreementAction(() => agreementApi.startEsign(id), '已发起内部确认时间线')
    },
    async esignParty(party) {
      if (party !== 'SCHOOL' || this.detail?.esignStatus !== 'PENDING' || this.detail?.status !== 'PENDING_SCHOOL' || !this.canBtn('internship.agreement.sign')) return
      const id = this.detail.id
      await this.runAgreementAction(() => agreementApi.esignSign(id, { party }), '学校内部确认已记录')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.agd-upload-preview { display: grid; gap: 8px; min-width: 0; margin-top: 10px; padding: 12px; border: 1px solid var(--color-border, #e2e8f0); border-radius: 8px; background: var(--color-bg-card, #fff); }
.agd { display: grid; grid-template-columns: minmax(0, 1fr) 310px; gap: 20px; align-items: start; }
.agd-main, .agd-rail { min-width: 0; }.agd-rail { position: sticky; top: 16px; }
.agd .mp-card { border-radius: 8px; box-shadow: none; }.agd .mp-card__head { padding: 12px 16px; }.agd .mp-card__body { padding: 14px 16px; }
.agd-tabs { display: flex; gap: 24px; padding: 0 20px; background: var(--card, #fff); border-bottom: 1px solid var(--border-light); border-radius: 10px 10px 0 0; }
.agd-tabs button { padding: 15px 0; border: 0; border-bottom: 3px solid transparent; background: transparent; font: inherit; font-size: 14px; color: var(--text-secondary); cursor: pointer; }
.agd-tabs button.is-active { color: var(--pri, #315fba); border-bottom-color: var(--pri, #315fba); font-weight: 600; }.agd-tabs button:focus-visible { outline: 2px solid var(--pri, #315fba); outline-offset: -3px; }
.agd-body { white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; color: var(--text-primary); background: var(--card, #fff); padding: 8px; font-size: 14px; line-height: 1.95; margin: 0; }
.agd-next { margin: 0 0 18px; font-size: 13px; line-height: 1.8; color: var(--text-secondary); }
.agd-reason { margin: var(--space-3) 0 0; padding: var(--space-2) var(--space-3); background: var(--danger-50, #fef2f2); color: var(--danger-700, #b91c1c); border-radius: 8px; font-size: var(--font-size-sm); }
.agd-ops { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; }
.agd-progress { display: flex; flex-direction: column; gap: var(--space-2); }
.agd-step { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; border-bottom: 1px dashed var(--border-light); }
.agd-step:last-child { border-bottom: none; }
.agd-step__lbl { font-size: var(--font-size-sm); color: var(--text-secondary); }
.agd-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
.agd-ent { border: 1px solid var(--border-light); border-radius: 10px; padding: var(--space-3); margin-bottom: var(--space-2); background: var(--bg-subtle, #f8fafc); }
.agd-file { font-size: var(--font-size-xs); }
.agd-att { font-size: var(--font-size-xs); color: var(--success-700); margin-left: var(--space-2); }
@media (max-width: 1180px) { .agd { grid-template-columns: minmax(0, 1fr) 280px; } }
@media (max-width: 980px) { .agd { grid-template-columns: 1fr; }.agd-rail { position: static; }.agd .mp-card__head { flex-wrap: wrap; gap: 12px; } }
</style>
