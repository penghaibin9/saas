<template>
  <ModulePageShell title="学生就业详情" :subtitle="detail ? `${detail.student.className} · ${detail.student.studentNo}` : ''" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="就业详情查阅">
    <template #actions>
      <button type="button" class="emp-back" @click="$router.back()">← 返回列表</button>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="detail">
      <ModuleToolbar :actions="toolbarActions" :hint="detail.student.recordStatus === 'VOIDED' ? `该记录已作废：${detail.student.voidReason}` : '编辑与作废操作全程留痕'" @action="onToolbar" />

      <div class="emp-detail-grid">
        <div class="emp-col">
          <section class="emp-section">
            <div class="emp-section__head">
              <h3 class="emp-section__title">
                {{ detail.student.name }}
                <StatusTag :type="destinationTagType[detail.student.destinationType] || 'default'" :label="labelOf('destinationType', detail.student.destinationType)" dot style="margin-left: 8px" />
                <RiskTag v-if="detail.student.helpLevel === 'KEY_HELP'" level="HIGH" label="重点帮扶" style="margin-left: 6px" />
                <StatusTag v-if="detail.student.recordStatus === 'VOIDED'" type="default" label="已作废" style="margin-left: 6px" />
              </h3>
            </div>
            <div class="emp-kv">
              <div v-for="item in profileItems" :key="item.label" class="emp-kv__item">
                <span class="emp-kv__label">{{ item.label }}</span>
                <span class="emp-kv__value">{{ item.value || '—' }}</span>
              </div>
            </div>
          </section>

          <!-- TP-E02：教师 PC 独立的去向核验工作区。之前 PC 只能靠"材料审核"隐式
               完成核验，老师看不到证据是否成立，也没有单独的退回补正入口。 -->
          <section v-if="verification" class="emp-section" style="margin-top: var(--space-4)">
            <div class="emp-section__head">
              <h3 class="emp-section__title">
                去向核验
                <StatusTag
                  :type="verification.verifyStatus === 'VERIFIED' ? 'success' : verification.verifyStatus === 'RETURNED' ? 'warning' : 'default'"
                  :label="verification.verifyStatusLabel"
                  dot
                  style="margin-left: 8px"
                />
              </h3>
            </div>
            <p class="emp-verify__evidence">
              可用正式证据：<b>{{ verification.formalApprovedCount }}</b> 份（已审核通过且完成正式文件绑定与安全扫描）
            </p>
            <p v-if="verification.blockedReason" class="emp-verify__blocked">{{ verification.blockedReason }}</p>
            <div class="emp-review-ops">
              <AppButton
                variant="primary"
                :disabled="!canVerify || submitting"
                :title="verification.blockedReason"
                @click="verifyVisible = true"
              >核验通过</AppButton>
              <AppButton
                variant="danger"
                :disabled="!canReturnVerification || submitting"
                @click="verifyReturnVisible = true"
              >退回补正</AppButton>
            </div>
          </section>

          <section class="emp-section" style="margin-top: var(--space-4)">
            <div class="emp-section__head">
              <h3 class="emp-section__title">就业材料</h3>
              <button type="button" class="emp-section__more" @click="$router.push('/admin/employment/materials')">前往材料审核 →</button>
            </div>
            <EmptyState v-if="!detail.materials.length" title="暂无就业材料" description="学生尚未提交就业协议 / 劳动合同等材料" />
            <table v-else class="emp-mat-table">
              <thead>
                <tr><th>材料类型</th><th>文件</th><th>提交时间</th><th>状态</th><th>审核意见</th></tr>
              </thead>
              <tbody>
                <tr v-for="m in detail.materials" :key="m.id">
                  <td>{{ labelOf('materialType', m.materialType) }}</td>
                  <!-- TP-E05：正式证据 vs 历史文件名文本必须在列表上就能区分，
                       否则老师只看到一个文件名，无从判断这份材料能不能作为核验凭据。 -->
                  <td>
                    {{ m.file?.fileName || m.fileName || '—' }}
                    <StatusTag
                      v-if="m.formalEvidence"
                      type="success"
                      label="正式材料"
                      style="margin-left: 6px"
                    />
                    <StatusTag
                      v-else-if="m.legacyFileNameOnly"
                      type="warning"
                      label="历史文本记录"
                      style="margin-left: 6px"
                    />
                  </td>
                  <td>{{ m.submitTime }}</td>
                  <td><StatusTag :type="materialTagType[m.status] || 'default'" :label="labelOf('materialStatus', m.status)" /></td>
                  <td class="emp-inline-note">{{ m.returnReason || m.remark || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </section>

          <section class="emp-section" style="margin-top: var(--space-4)">
            <div class="emp-section__head">
              <h3 class="emp-section__title">跟进记录</h3>
              <button type="button" class="emp-section__more" @click="$router.push('/admin/employment/followups')">全部跟进记录 →</button>
            </div>
            <EmptyState v-if="!detail.followUps.length" title="暂无跟进记录" />
            <div v-for="f in detail.followUps" :key="f.id" class="emp-follow">
              <div class="emp-follow__head">
                <span>{{ f.followTime }} · {{ labelOf('followUpWay', f.way) }} · {{ f.operator }}</span>
                <StatusTag :type="followTagType[f.status] || 'default'" :label="labelOf('followUpStatus', f.status)" />
              </div>
              <div class="emp-follow__content">{{ f.content }}</div>
              <div class="emp-inline-note">结果:{{ f.result || '—' }} · 下一步:{{ f.nextPlan || '—' }}</div>
            </div>
          </section>
        </div>

        <div class="emp-col">
          <section class="emp-section">
            <h3 class="emp-section__title">操作留痕</h3>
            <AuditTrailPanel :logs="detail.auditLogs" />
          </section>
        </div>
      </div>

      <EditDrawer v-model:visible="editVisible" title="编辑就业信息" :fields="editFields" :model="detail.student" :submitting="submitting" @submit="onEditSubmit" />
      <DeleteConfirmDialog
        v-model:visible="voidVisible"
        title="作废就业记录"
        :message="`确认作废「${detail.student.name}」的就业记录？`"
        :submitting="submitting"
        @confirm="onVoidConfirm"
      />
      <AppConfirmDialog
        v-model:visible="verifyVisible"
        title="去向核验通过"
        :message="`确认核验通过「${detail.student.name}」的就业去向？核验依据为 ${verification ? verification.formalApprovedCount : 0} 份正式材料证据，结果将计入就业统计并全程留痕。`"
        type="primary"
        confirm-text="确认核验"
        :submitting="submitting"
        @confirm="submitVerification('VERIFY', '')"
      />
      <AppConfirmDialog
        v-model:visible="verifyReturnVisible"
        title="去向核验退回补正"
        :message="`退回「${detail.student.name}」的去向核验，学生将收到补正通知。`"
        type="danger"
        confirm-text="确认退回"
        require-reason
        reason-label="补正意见"
        reason-placeholder="请写明需要补交/更正的具体内容（不少于 5 字）"
        :submitting="submitting"
        @confirm="({ reason }) => submitVerification('RETURN', reason)"
      />
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 3：/admin/employment/students/:id 学生就业详情（材料 / 跟进 / 留痕一体）。 */
import { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppButton } from '@/components/ui'
import { EditDrawer, DeleteConfirmDialog, AuditTrailPanel } from '@/modules/employment/components'
import * as api from '@/modules/employment/api/employment.api'
import { DESTINATION_TAG_TYPE, MATERIAL_TAG_TYPE, FOLLOWUP_TAG_TYPE, toLabelMap } from '@/modules/employment/constants/employment.constants'
import { toast } from '@/utils/toast'

export default {
  name: 'EmploymentStudentDetailView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, EmptyState, LoadingState, ErrorState, EditDrawer, DeleteConfirmDialog, AuditTrailPanel, AppConfirmDialog, AppButton },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      submitting: false,
      detail: null,
      statusOptions: {},
      filterOptions: {},
      editVisible: false,
      voidVisible: false,
      verification: null,
      verifyVisible: false,
      verifyReturnVisible: false,
      destinationTagType: DESTINATION_TAG_TYPE,
      materialTagType: MATERIAL_TAG_TYPE,
      followTagType: FOLLOWUP_TAG_TYPE
    }
  },
  computed: {
    canVerify() {
      return !!this.verification && (this.verification.allowedActions || []).includes('VERIFY')
    },
    canReturnVerification() {
      return !!this.verification && (this.verification.allowedActions || []).includes('RETURN')
    },
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    perms() {
      return this.ctx?.permissionActions || {}
    },
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    profileItems() {
      const s = this.detail?.student
      if (!s) return []
      return [
        { label: '学号', value: s.studentNo },
        { label: '班级', value: `${s.collegeName} · ${s.className}` },
        { label: '专业', value: s.majorName },
        { label: '联系电话（脱敏）', value: s.phone },
        { label: '身份证（脱敏）', value: s.idCard },
        { label: '单位 / 院校', value: s.companyName },
        { label: '岗位', value: s.jobTitle },
        { label: '薪资区间（脱敏）', value: s.salaryRange },
        { label: '签约时间', value: s.signDate },
        { label: '核验状态', value: this.labelOf('verifyStatus', s.verifyStatus) },
        { label: '是否专业对口', value: s.isMatchMajor ? '是' : '否' },
        { label: '是否实习转就业', value: s.fromInternship ? '是' : '否' },
        { label: '辅导员', value: s.counselor },
        { label: '就业老师', value: s.employmentTeacher },
        { label: '最近更新', value: s.updateTime }
      ]
    },
    toolbarActions() {
      const edit = this.perms['employment.record.edit']
      const voidP = this.perms['employment.record.void']
      const voided = this.detail?.student?.recordStatus === 'VOIDED'
      return [
        edit && !edit.visible
          ? null
          : { key: 'edit', label: '编辑就业信息', variant: 'primary', disabled: edit ? !edit.allowed : false, disabledReason: edit?.reason },
        voidP && !voidP.visible
          ? null
          : {
              key: 'void',
              label: '作废记录',
              disabled: (voidP ? !voidP.allowed : false) || voided,
              disabledReason: voided ? '该记录已作废' : voidP?.reason
            }
      ].filter(Boolean)
    },
    editFields() {
      return [
        { key: 'destinationType', label: '去向类型', type: 'select', options: this.statusOptions.destinationType || [], required: true },
        { key: 'companyName', label: '单位 / 院校', type: 'text' },
        { key: 'jobTitle', label: '岗位 / 专业', type: 'text' },
        { key: 'salaryRange', label: '薪资区间', type: 'text' },
        { key: 'signDate', label: '签约 / 确认时间', type: 'date' },
        { key: 'phone', label: '联系电话', type: 'text' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || value || '—'
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        // 核验工作区与主详情分开处理：核验接口故障不应让整个学生详情打不开，
        // 但也不能静默吞掉——拿不到就不渲染核验区块，而不是渲染一个空壳。
        const [ctx, status, detail, verification] = await Promise.all([
          api.getEmploymentContext(),
          api.getStatusOptions(),
          api.getEmploymentStudentDetail(this.$route.params.studentId),
          api.getDestinationVerification(this.$route.params.studentId)
        ])
        if (ctx.code === 0) this.ctx = ctx.data
        if (status.code === 0) this.statusOptions = status.data
        if (detail.code === 0) this.detail = detail.data
        else this.error = detail.message
        this.verification = verification.code === 0 ? verification.data : null
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    onToolbar(key) {
      if (key === 'edit') this.editVisible = true
      if (key === 'void') this.voidVisible = true
    },
    async submitVerification(action, comment) {
      this.submitting = true
      try {
        const res = await api.reviewDestinationVerification(this.detail.student.id, {
          action,
          comment,
          // 乐观锁版本必须来自服务端刚返回的核验工作区，不能自己攒——
          // 版本过期时服务端会 409，前端刷新后重试。
          expectedVersion: this.verification.expectedVersion
        })
        if (res.code === 0) {
          toast.success(action === 'VERIFY' ? '去向已核验，已写入留痕' : '已退回补正，原因已留痕')
          this.verifyVisible = false
          this.verifyReturnVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onEditSubmit(form) {
      this.submitting = true
      try {
        const res = await api.updateEmploymentRecord(this.detail.student.id, form)
        if (res.code === 0) {
          toast.success('就业信息已更新，已写入留痕')
          this.editVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onVoidConfirm({ reason }) {
      this.submitting = true
      try {
        const res = await api.voidEmploymentRecord(this.detail.student.id, { reason })
        if (res.code === 0) {
          toast.success('记录已作废（逻辑删除），原因已留痕')
          this.voidVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import './employment-page.css';

.emp-mat-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
.emp-mat-table th,
.emp-mat-table td {
  padding: var(--space-2);
  border-bottom: 1px solid var(--border-light);
  text-align: left;
}
.emp-mat-table th {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-section-blue);
}
.emp-follow {
  padding: var(--space-3) 0;
  border-bottom: 1px dashed var(--border-light);
}
.emp-follow:last-child {
  border-bottom: none;
}
.emp-follow__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.emp-follow__content {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
}
.emp-verify__evidence { margin: 0 0 var(--space-2); font-size: 13px; color: var(--text-2, #606266); }
.emp-verify__blocked { margin: 0 0 var(--space-2); font-size: 13px; color: var(--warning-6, #e6a23c); }
</style>
