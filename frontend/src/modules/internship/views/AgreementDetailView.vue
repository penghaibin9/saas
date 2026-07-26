<template>
  <ModulePageShell
    :title="detail ? `${detail.studentName} · 三方协议档案` : '三方协议档案'"
    :subtitle="detail ? [detail.enterpriseName, detail.positionName, detail.templateName].filter(Boolean).join(' · ') : ''"
    role-name="指导教师 / 管理员"
    data-scope-name="指导教师仅本人指导学生；管理员全校"
    :watermark="false"
  >
    <template #actions>
      <AppButton variant="ghost" @click="backToList">← 返回协议列表</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" @back="backToList" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="detail" class="mp-grid-2 agd">
      <!-- 左：协议内容 -->
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">协议信息</span>
            <AppStatusTag :status="detail.status">{{ detail.statusLabel }}</AppStatusTag>
          </div>
          <div class="mp-card__body">
            <AppDescriptionList :items="infoItems" :columns="2" />
            <p v-if="detail.rejectReason" class="agd-reason">驳回/作废原因：{{ detail.rejectReason }}</p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">协议正文（模板渲染快照）</span>
            <div class="agd-ops">
              <AppPrintButton v-if="detail.renderedBody" print-selector="#agreement-print-body" label="打印正文" />
              <AppPermissionButton v-if="detail.renderedBody" code="internship.agreement.view" :allowed="canBtn('internship.agreement.view')"
                variant="ghost" size="sm" :loading="pdfLoading" @click="downloadPdf">下载 PDF 套打</AppPermissionButton>
            </div>
          </div>
          <div class="mp-card__body">
            <pre v-if="detail.renderedBody" id="agreement-print-body" class="agd-body">{{ detail.renderedBody }}</pre>
            <p v-else class="mp-note" style="margin: 0">该协议未生成正文快照（早期数据或模板缺失）。</p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">签署扫描件</span></div>
          <div class="mp-card__body">
            <AppFilePreview v-if="detail.attachment" :files="attachmentFiles" @download="downloadAtt" />
            <p v-else class="mp-note" style="margin: 0">暂无签署扫描件；企业签署环节上传后在此展示。</p>
          </div>
        </section>
      </div>

      <!-- 右：确认进度 + 办理 + 留痕 -->
      <div class="mp-stack">
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
          <div class="mp-card__head"><span class="mp-card__title">协议办理</span></div>
          <div class="mp-card__body">
            <!-- 记录企业签署（内联表单，取代原窄弹窗） -->
            <template v-if="detail.status === 'PENDING_ENTERPRISE'">
              <div class="agd-ent">
                <AppFormItem label="企业经办人">
                  <AppTextInput v-model="entForm.confirmBy" placeholder="如：企业 HR 张三" />
                </AppFormItem>
                <AppFormItem label="签署扫描件（企业已签的纸质三方协议）" required>
                  <input type="file" class="agd-file" @change="onEntFile" />
                  <span v-if="entForm.fileId" class="agd-att">已上传：{{ entAttachName }}</span>
                  <span v-else-if="uploadingFile" class="agd-att">上传中…</span>
                </AppFormItem>
                <p class="mp-note">无电子签章时，以上传企业已签署的纸质三方协议扫描件为准。</p>
              </div>
            </template>

            <div class="agd-actions">
              <AppPermissionButton v-if="detail.status === 'DRAFT'" code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')"
                variant="primary" @click="confirmAct('issue')">下发给学生确认</AppPermissionButton>
              <AppPermissionButton v-if="detail.esignStatus === 'NONE' && canVoid" code="internship.agreement.sign" :allowed="canBtn('internship.agreement.sign')"
                variant="ghost" @click="startEsign">发起内部确认</AppPermissionButton>
              <!-- 企业方禁止教师代签电子签；正式路径为上方纸质扫描件确认（对标企业真签） -->
              <AppPermissionButton v-if="detail.esignStatus === 'PENDING' && detail.status === 'PENDING_SCHOOL'"
                code="internship.agreement.sign" :allowed="canBtn('internship.agreement.sign')" variant="ghost" @click="esignParty('SCHOOL')">学校内部确认</AppPermissionButton>
              <AppPermissionButton v-if="detail.status === 'PENDING_ENTERPRISE'" code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')"
                variant="primary" :disabled="!entForm.fileId" :loading="entSubmitting"
                @click="submitEnterprise">确认企业已签署</AppPermissionButton>
              <AppPermissionButton v-if="detail.status === 'PENDING_SCHOOL'" code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')"
                variant="primary" @click="confirmAct('school')">学校确认生效</AppPermissionButton>
              <AppPermissionButton v-if="detail.status === 'EFFECTIVE'" code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')"
                variant="secondary" @click="confirmAct('archive')">归档</AppPermissionButton>
              <AppPermissionButton v-if="canReject" code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')"
                variant="ghost" :danger="true" @click="confirmAct('reject')">驳回</AppPermissionButton>
              <AppPermissionButton v-if="canVoid" code="internship.agreement.manage" :allowed="canBtn('internship.agreement.manage')"
                variant="ghost" :danger="true" @click="confirmAct('void')">作废</AppPermissionButton>
            </div>
            <p v-if="isFinal" class="mp-note" style="margin-top: var(--space-2)">
              协议已处于终态（{{ detail.statusLabel }}），仅可查看与打印，不可再变更。
            </p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">三方确认与办理留痕</span></div>
          <div class="mp-card__body">
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无办理记录" />
          </div>
        </section>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="原因" :submitting="cd.submitting" @confirm="onConfirm" />
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
  AppTextInput, AppFormItem, AppFilePreview, AppPrintButton } from '@/components/common'
import { agreementApi } from '@/modules/internship/api/agreement.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'

const INFO = [
  { key: 'studentName', label: '学生' }, { key: 'studentNo', label: '学号' },
  { key: 'advisorName', label: '指导教师' }, { key: 'enterpriseName', label: '企业' },
  { key: 'positionName', label: '岗位' }, { key: 'templateName', label: '协议模板' }
]

export default {
  name: 'AgreementDetailView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, LoadingState, ErrorState, AppButton, AppStatusTag, AppConfirmDialog,
    AppPermissionButton, AppDescriptionList, AppAuditTrail, AppTextInput, AppFormItem, AppFilePreview, AppPrintButton },
  data() {
    return {
      loading: true, error: '', detail: null,
      entForm: { confirmBy: '', fileId: '' }, entAttachName: '', uploadingFile: false, entSubmitting: false,
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pendingKind: '', pdfLoading: false
    }
  },
  computed: {
    infoItems() { const d = this.detail || {}; return INFO.map((f) => ({ label: f.label, value: d[f.key] || '—' })) },
    attachmentFiles() { const a = this.detail?.attachment; return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : [] },
    auditRecords() {
      return (this.detail?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.reason || t.detail.confirmBy || ''), at: t.occurredAt
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
      this.load()
    }
  },
  created() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    confirmTone(s) { return s === 'CONFIRMED' ? 'success' : s === 'REJECTED' ? 'danger' : 'warning' },
    backToList() {
      // 从列表进入时走历史返回（保留筛选/页码/panel）；深链直入时兜底到列表
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && back.startsWith('/admin/internship/agreements')) this.$router.back()
      else this.$router.push('/admin/internship/agreements')
    },
    async load() {
      this.loading = true; this.error = ''
      const id = this.$route.params.id
      const res = await agreementApi.getDetail(id)
      if (id !== this.$route.params.id) return
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '协议不存在或无权查看'; return }
      this.detail = res.data
      this.entForm = { confirmBy: '', fileId: '' }
      this.entAttachName = ''
    },
    async onEntFile(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.uploadingFile = true
      const res = await agreementApi.uploadAttachment(file)
      this.uploadingFile = false
      if (res.code !== 0) return toast.error(res.message || '上传失败')
      this.entForm.fileId = res.data.fileId
      this.entAttachName = res.data.fileName || file.name
      toast.success('扫描件已上传')
    },
    async submitEnterprise() {
      if (!this.entForm.fileId) return toast.error('请先上传企业已签署的扫描件')
      this.entSubmitting = true
      const res = await agreementApi.enterpriseConfirm(this.detail.id, {
        confirmBy: this.entForm.confirmBy, fileId: this.entForm.fileId,
        expectedVersion: this.detail.version
      })
      this.entSubmitting = false
      if (res.code !== 0) return toast.error(res.message || '提交失败')
      toast.success('已记录企业签署，进入学校确认环节')
      this.load()
    },
    async downloadAtt() {
      const a = this.detail?.attachment
      if (!a) return
      try { await agreementApi.downloadAttachment(a.fileId, a.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    async downloadPdf() {
      if (!this.detail?.id || this.pdfLoading) return
      this.pdfLoading = true
      const res = await agreementApi.exportAgreementPdf(this.detail.id)
      this.pdfLoading = false
      if (res.code !== 0) return toast.error(res.message || 'PDF 生成失败')
      downloadXlsxFromApi(res.data)
      toast.success('PDF 套打已下载（含水印与导出留痕）')
    },
    confirmAct(kind) {
      const name = this.detail.studentName
      const map = {
        issue: { title: '下发协议', content: `将「${name}」的协议下发给学生确认？`, danger: false, confirmText: '下发', requireReason: false },
        school: { title: '学校确认', content: `确认「${name}」三方协议生效？`, danger: false, confirmText: '确认生效', requireReason: false },
        archive: { title: '归档协议', content: `归档「${name}」的已生效协议？归档后进入只读台账。`, danger: false, confirmText: '归档', requireReason: false },
        reject: { title: '驳回协议', content: `驳回「${name}」的协议，原因将写入审计。`, danger: true, confirmText: '驳回', requireReason: true },
        void: { title: '作废协议', content: `作废「${name}」的协议，原因将写入审计。`, danger: true, confirmText: '作废', requireReason: true }
      }[kind]
      this.pendingKind = kind
      this.cd = { visible: true, ...map, submitting: false }
    },
    async onConfirm({ reason }) {
      const id = this.detail.id
      const ver = { expectedVersion: this.detail.version }
      this.cd.submitting = true
      let res
      if (this.pendingKind === 'issue') res = await agreementApi.issue(id, ver)
      else if (this.pendingKind === 'school') res = await agreementApi.schoolConfirm(id, ver)
      else if (this.pendingKind === 'archive') res = await agreementApi.archive(id, ver)
      else if (this.pendingKind === 'reject') res = await agreementApi.reject(id, { reason, ...ver })
      else res = await agreementApi.voidAgreement(id, { reason, ...ver })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false
      toast.success('操作成功，已写审计')
      this.load()
    },
    async startEsign() {
      const res = await agreementApi.startEsign(this.detail.id)
      if (res.code !== 0) return toast.error(res.message)
      toast.success(res.data.message || '已发起内部确认时间线')
      this.load()
    },
    async esignParty(party) {
      const res = await agreementApi.esignSign(this.detail.id, { party })
      if (res.code !== 0) return toast.error(res.message)
      toast.success(`${party === 'SCHOOL' ? '学校' : '企业'}内部确认完成`)
      this.load()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.agd-body { white-space: pre-wrap; word-break: break-word; background: var(--bg-subtle, #f8fafc); border: 1px solid var(--border-light); border-radius: 8px; padding: 12px; font-size: 12.5px; line-height: 1.8; max-height: 480px; overflow: auto; margin: 0; }
.agd-reason { margin: var(--space-3) 0 0; padding: var(--space-2) var(--space-3); background: var(--danger-50, #fef2f2); color: var(--danger-700, #b91c1c); border-radius: 8px; font-size: var(--font-size-sm); }
.agd-ops { display: flex; gap: var(--space-2); align-items: center; }
.agd-progress { display: flex; flex-direction: column; gap: var(--space-2); }
.agd-step { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; border-bottom: 1px dashed var(--border-light); }
.agd-step:last-child { border-bottom: none; }
.agd-step__lbl { font-size: var(--font-size-sm); color: var(--text-secondary); }
.agd-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
.agd-ent { border: 1px solid var(--border-light); border-radius: 10px; padding: var(--space-3); margin-bottom: var(--space-2); background: var(--bg-subtle, #f8fafc); }
.agd-file { font-size: var(--font-size-xs); }
.agd-att { font-size: var(--font-size-xs); color: var(--success-700); margin-left: var(--space-2); }
</style>
