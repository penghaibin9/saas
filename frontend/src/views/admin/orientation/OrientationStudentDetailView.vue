<template>
  <ModulePageShell title="新生报到详情" :subtitle="detail ? `${detail.student.className} · ${detail.student.admissionNo}` : ''" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="新生详情查阅">
    <template #actions>
      <button type="button" class="ori-back" @click="$router.back()">← 返回列表</button>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="detail">
      <ModuleToolbar :actions="toolbarActions" :hint="detail.student.recordStatus === 'VOIDED' ? `该记录已作废：${detail.student.voidReason}` : '编辑与作废操作全程留痕'" @action="onToolbar" />

      <!-- 报到环节进度 -->
      <section class="ori-section">
        <h3 class="ori-section__title">报到环节进度</h3>
        <div class="ori-steps">
          <div v-for="s in detail.steps" :key="s.key" class="ori-step" :class="`is-${(detail.student.steps[s.key] || 'TODO').toLowerCase()}`">
            <span class="ori-step__dot" />
            <span class="ori-step__label">{{ s.label }}</span>
            <span class="ori-step__state">{{ stepStateLabel(detail.student.steps[s.key]) }}</span>
          </div>
        </div>
        <div v-if="detail.student.blockedStep" class="ori-blocked-box">
          当前卡点：{{ stepLabel(detail.student.blockedStep) }} — {{ detail.student.blockedReason }}
        </div>
      </section>

      <div class="ori-detail-grid" style="margin-top: var(--space-4)">
        <div class="ori-col">
          <section class="ori-section">
            <div class="ori-section__head">
              <h3 class="ori-section__title">
                {{ detail.student.name }}
                <StatusTag :type="stageTagType[detail.student.stage] || 'default'" :label="labelOf('stage', detail.student.stage)" dot style="margin-left: 8px" />
                <RiskTag v-if="detail.student.riskLevel !== 'LOW'" :level="detail.student.riskLevel" style="margin-left: 6px" />
              </h3>
            </div>
            <div class="ori-kv">
              <div v-for="item in profileItems" :key="item.label" class="ori-kv__item">
                <span class="ori-kv__label">{{ item.label }}</span>
                <span class="ori-kv__value">{{ item.value || '—' }}</span>
              </div>
            </div>
          </section>

          <section class="ori-section" style="margin-top: var(--space-4)">
            <div class="ori-section__head">
              <h3 class="ori-section__title">缴费与绿色通道</h3>
              <button type="button" class="ori-section__more" @click="$router.push('/admin/orientation/payment')">前往缴费管理 →</button>
            </div>
            <div class="ori-kv">
              <div class="ori-kv__item"><span class="ori-kv__label">应缴金额</span><span class="ori-kv__value">¥{{ detail.student.payableAmount }}</span></div>
              <div class="ori-kv__item"><span class="ori-kv__label">已缴金额</span><span class="ori-kv__value">¥{{ detail.student.paidAmount }}</span></div>
              <div class="ori-kv__item">
                <span class="ori-kv__label">缴费状态</span>
                <StatusTag :type="paymentTagType[detail.student.paymentStatus] || 'default'" :label="labelOf('paymentStatus', detail.student.paymentStatus)" />
              </div>
              <div class="ori-kv__item">
                <span class="ori-kv__label">绿色通道</span>
                <StatusTag :type="greenTagType[detail.student.greenChannelStatus] || 'default'" :label="labelOf('greenChannelStatus', detail.student.greenChannelStatus)" />
              </div>
            </div>
            <div v-for="g in detail.greenChannels" :key="g.id" class="ori-green-item">
              <b>{{ g.applyType }}</b>（¥{{ g.applyAmount }}）· 提交于 {{ g.submitTime }}
              <StatusTag :type="greenTagType[g.status] || 'default'" :label="labelOf('greenChannelStatus', g.status)" />
              <div v-if="g.rejectReason" class="ori-inline-note">意见：{{ g.rejectReason }}</div>
            </div>
          </section>

          <section class="ori-section" style="margin-top: var(--space-4)">
            <div class="ori-section__head">
              <h3 class="ori-section__title">迎新材料</h3>
              <button type="button" class="ori-section__more" @click="$router.push('/admin/orientation/materials')">前往材料审核 →</button>
            </div>
            <EmptyState v-if="!detail.materials.length" title="暂无上传材料" />
            <table v-else class="ori-mat-table">
              <thead>
                <tr><th>材料类型</th><th>文件</th><th>提交时间</th><th>状态</th><th>审核意见</th></tr>
              </thead>
              <tbody>
                <tr v-for="m in detail.materials" :key="m.id">
                  <td>{{ labelOf('materialType', m.materialType) }}</td>
                  <td>{{ m.fileName }}</td>
                  <td>{{ m.submitTime }}</td>
                  <td><StatusTag :type="materialTagType[m.status] || 'default'" :label="labelOf('materialStatus', m.status)" /></td>
                  <td class="ori-inline-note">{{ m.returnReason || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>

        <div class="ori-col">
          <section class="ori-section">
            <h3 class="ori-section__title">宿舍信息</h3>
            <div class="ori-kv">
              <div class="ori-kv__item"><span class="ori-kv__label">楼栋</span><span class="ori-kv__value">{{ detail.student.building || '未分配' }}</span></div>
              <div class="ori-kv__item"><span class="ori-kv__label">房间 / 床位</span><span class="ori-kv__value">{{ detail.student.room || '未分配' }}</span></div>
              <div class="ori-kv__item">
                <span class="ori-kv__label">入住状态</span>
                <StatusTag :type="dormTagType[detail.student.dormStatus] || 'default'" :label="labelOf('dormStatus', detail.student.dormStatus)" />
              </div>
              <div class="ori-kv__item"><span class="ori-kv__label">入住时间</span><span class="ori-kv__value">{{ detail.student.checkinTime || '—' }}</span></div>
            </div>
            <div v-if="detail.student.exceptionNote" class="ori-blocked-box" style="margin-top: var(--space-3)">
              宿舍异常：{{ detail.student.exceptionNote }}
            </div>
          </section>

          <section v-if="detail.exceptions.length" class="ori-section" style="margin-top: var(--space-4)">
            <h3 class="ori-section__title">关联迎新异常</h3>
            <div v-for="e in detail.exceptions" :key="e.id" class="ori-green-item">
              <RiskTag :level="e.riskLevel" />
              <b style="margin-left: 6px">{{ labelOf('exceptionType', e.exceptionType) }}</b>
              <div class="ori-inline-note">{{ e.description }}</div>
            </div>
          </section>

          <section class="ori-section" style="margin-top: var(--space-4)">
            <h3 class="ori-section__title">操作留痕</h3>
            <AuditTrailPanel :logs="detail.auditLogs" />
          </section>
        </div>
      </div>

      <EditDrawer v-model:visible="editVisible" title="编辑报到信息" :fields="editFields" :model="detail.student" :submitting="submitting" @submit="onEditSubmit" />
      <DeleteConfirmDialog
        v-model:visible="voidVisible"
        title="作废报到记录"
        :message="`确认作废「${detail.student.name}」的报到记录？`"
        :submitting="submitting"
        @confirm="onVoidConfirm"
      />
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 3：/admin/orientation/students/:studentId 新生报到详情（环节进度 / 缴费 / 材料 / 宿舍 / 异常 / 留痕）。 */
import { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { EditDrawer, DeleteConfirmDialog, AuditTrailPanel } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import {
  STAGE_TAG_TYPE,
  PAYMENT_TAG_TYPE,
  GREEN_TAG_TYPE,
  MATERIAL_TAG_TYPE,
  DORM_TAG_TYPE,
  toLabelMap
} from '@/modules/orientation/constants/orientation.constants'
import { toast } from '@/utils/toast'

const STEP_STATE_LABEL = { DONE: '已完成', DOING: '进行中', BLOCKED: '卡点', TODO: '未开始' }

export default {
  name: 'OrientationStudentDetailView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, EmptyState, LoadingState, ErrorState, EditDrawer, DeleteConfirmDialog, AuditTrailPanel },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      submitting: false,
      detail: null,
      statusOptions: {},
      editVisible: false,
      voidVisible: false,
      stageTagType: STAGE_TAG_TYPE,
      paymentTagType: PAYMENT_TAG_TYPE,
      greenTagType: GREEN_TAG_TYPE,
      materialTagType: MATERIAL_TAG_TYPE,
      dormTagType: DORM_TAG_TYPE
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
        { label: '录取编号', value: s.admissionNo },
        { label: '学院 / 班级', value: `${s.collegeName} · ${s.className}` },
        { label: '录取专业', value: s.majorName },
        { label: '生源地', value: s.origin },
        { label: '联系电话（脱敏）', value: s.phone },
        { label: '身份证（脱敏）', value: s.idCard },
        { label: '报到状态', value: this.labelOf('reportStatus', s.reportStatus) },
        { label: '辅导员', value: s.counselor },
        { label: '最近更新', value: s.updateTime }
      ]
    },
    toolbarActions() {
      const edit = this.perms['orientation.student.edit']
      const voidP = this.perms['orientation.student.void']
      const voided = this.detail?.student?.recordStatus === 'VOIDED'
      return [
        edit && !edit.visible
          ? null
          : { key: 'edit', label: '编辑报到信息', variant: 'primary', disabled: edit ? !edit.allowed : false, disabledReason: edit?.reason },
        voidP && !voidP.visible
          ? null
          : { key: 'void', label: '作废记录', disabled: (voidP ? !voidP.allowed : false) || voided, disabledReason: voided ? '该记录已作废' : voidP?.reason }
      ].filter(Boolean)
    },
    editFields() {
      return [
        { key: 'reportStatus', label: '报到状态', type: 'select', options: this.statusOptions.reportStatus || [], required: true },
        { key: 'counselor', label: '辅导员', type: 'text' },
        { key: 'phone', label: '联系电话', type: 'text' },
        { key: 'origin', label: '生源地', type: 'text' }
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
    stepLabel(key) {
      return this.detail?.steps?.find((s) => s.key === key)?.label || key
    },
    stepStateLabel(state) {
      return STEP_STATE_LABEL[state || 'TODO']
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const [ctx, status, detail] = await Promise.all([
          api.getOrientationContext(),
          api.getStatusOptions(),
          api.getOrientationStudentDetail(this.$route.params.studentId)
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
        const res = await api.updateOrientationStudent(this.detail.student.id, form)
        if (res.code === 0) {
          toast.success('报到信息已更新，已写入留痕')
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
        const res = await api.voidOrientationStudent(this.detail.student.id, { reason })
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
@import './orientation-page.css';

.ori-steps {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.ori-step {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-full);
  border: 1px solid var(--border-light);
  background: var(--bg-card);
  font-size: var(--font-size-xs);
}
.ori-step__dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--gray-300);
}
.ori-step.is-done .ori-step__dot {
  background: var(--success-500);
}
.ori-step.is-doing .ori-step__dot {
  background: var(--primary-500);
}
.ori-step.is-blocked {
  border-color: var(--danger-100);
  background: var(--danger-50);
}
.ori-step.is-blocked .ori-step__dot {
  background: var(--danger-500);
}
.ori-step__state {
  color: var(--text-tertiary);
}
.ori-blocked-box {
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--danger-50);
  border: 1px solid var(--danger-100);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--danger-600);
}
.ori-mat-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}
.ori-mat-table th,
.ori-mat-table td {
  padding: var(--space-2);
  border-bottom: 1px solid var(--border-light);
  text-align: left;
}
.ori-mat-table th {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-section-blue);
}
.ori-green-item {
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--border-light);
  font-size: var(--font-size-sm);
}
.ori-green-item:last-child {
  border-bottom: none;
}
</style>
