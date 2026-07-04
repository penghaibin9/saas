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
                  <td>{{ m.fileName }}</td>
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
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 3：/admin/employment/students/:id 学生就业详情（材料 / 跟进 / 留痕一体）。 */
import { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { EditDrawer, DeleteConfirmDialog, AuditTrailPanel } from '@/modules/employment/components'
import * as api from '@/modules/employment/api/employment.api'
import { DESTINATION_TAG_TYPE, MATERIAL_TAG_TYPE, FOLLOWUP_TAG_TYPE, toLabelMap } from '@/modules/employment/constants/employment.constants'
import { toast } from '@/utils/toast'

export default {
  name: 'EmploymentStudentDetailView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, EmptyState, LoadingState, ErrorState, EditDrawer, DeleteConfirmDialog, AuditTrailPanel },
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
      destinationTagType: DESTINATION_TAG_TYPE,
      materialTagType: MATERIAL_TAG_TYPE,
      followTagType: FOLLOWUP_TAG_TYPE
    }
  },
  computed: {
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
        const [ctx, status, detail] = await Promise.all([
          api.getEmploymentContext(),
          api.getStatusOptions(),
          api.getEmploymentStudentDetail(this.$route.params.studentId)
        ])
        if (ctx.code === 0) this.ctx = ctx.data
        if (status.code === 0) this.statusOptions = status.data
        if (detail.code === 0) this.detail = detail.data
        else this.error = detail.message
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
</style>
