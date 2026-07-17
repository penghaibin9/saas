<template>
  <ModulePageShell title="新生报到详情" :subtitle="detail ? `${detail.student.className} · ${detail.student.admissionNo}` : ''" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="新生详情查阅">
    <template #actions>
      <button v-if="wlHasQueue" type="button" class="ori-back" :disabled="!prevId" @click="goSibling(prevId)">← 上一个</button>
      <span v-if="wlHasQueue" class="ori-wl-pos">待办 {{ wlIndex + 1 }} / {{ wlTotal }}</span>
      <button v-if="wlHasQueue" type="button" class="ori-back" :disabled="!nextId" @click="goSibling(nextId)">下一个 →</button>
      <button type="button" class="ori-back" @click="$router.back()">返回列表</button>
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
        <!-- 就地动作：信息核验 + 卡点管理（无需跳转到其它页面） -->
        <div v-if="detail.student.recordStatus !== 'VOIDED'" class="ori-actbar">
          <button
            v-if="detail.student.steps.INFO !== 'DONE'"
            type="button"
            class="ori-act ori-act--primary"
            :disabled="submitting || isDenied('orientation.student.edit')"
            :title="isDenied('orientation.student.edit') ? '当前角色无信息核验权限' : ''"
            @click="verifyPass"
          >信息核验通过</button>
          <button
            v-if="detail.student.steps.INFO !== 'DONE'"
            type="button"
            class="ori-act"
            :disabled="submitting || isDenied('orientation.student.edit')"
            @click="verifyReturn"
          >核验退回</button>
          <button
            v-if="!detail.student.blockedStep"
            type="button"
            class="ori-act ori-act--danger"
            :disabled="submitting || isDenied('orientation.student.edit')"
            @click="markBlock"
          >标记卡点</button>
          <button
            v-else
            type="button"
            class="ori-act ori-act--primary"
            :disabled="submitting || isDenied('orientation.student.edit')"
            @click="resolveBlock"
          >解除卡点</button>
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
              <span
                v-if="detail.student.recordStatus !== 'VOIDED' && ['SUBMITTED', 'REVIEWING', 'RETURNED'].includes(g.status) && !isHidden('orientation.payment.view')"
                class="ori-rowact"
              >
                <button type="button" class="ori-act ori-act--primary" :disabled="submitting || isDenied('orientation.payment.view')" @click="approveGreen(g)">通过</button>
                <button type="button" class="ori-act" :disabled="submitting || isDenied('orientation.payment.view')" @click="returnGreen(g)">退回补充</button>
                <button type="button" class="ori-act ori-act--danger" :disabled="submitting || isDenied('orientation.payment.view')" @click="rejectGreen(g)">驳回</button>
              </span>
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
                <tr><th>材料类型</th><th>文件</th><th>提交时间</th><th>状态</th><th>审核意见</th><th v-if="showMaterialActions">操作</th></tr>
              </thead>
              <tbody>
                <tr v-for="m in detail.materials" :key="m.id">
                  <td>{{ labelOf('materialType', m.materialType) }}</td>
                  <td>{{ m.fileName }}</td>
                  <td>{{ m.submitTime }}</td>
                  <td><StatusTag :type="materialTagType[m.status] || 'default'" :label="labelOf('materialStatus', m.status)" /></td>
                  <td class="ori-inline-note">{{ m.returnReason || '—' }}</td>
                  <td v-if="showMaterialActions">
                    <span v-if="['UPLOADED', 'RETURNED'].includes(m.status)" class="ori-rowact">
                      <button type="button" class="ori-act ori-act--primary" :disabled="submitting || isDenied('orientation.material.review')" @click="approveMaterial(m)">通过</button>
                      <button type="button" class="ori-act" :disabled="submitting || isDenied('orientation.material.review')" @click="returnMaterial(m)">退回</button>
                    </span>
                    <span v-else class="ori-inline-note">—</span>
                  </td>
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
            <div v-if="detail.student.recordStatus !== 'VOIDED' && !isHidden('orientation.dorm.confirm')" class="ori-actbar" style="margin-top: var(--space-3)">
              <button
                v-if="detail.student.dormStatus === 'ASSIGNED'"
                type="button"
                class="ori-act ori-act--primary"
                :disabled="submitting || isDenied('orientation.dorm.confirm')"
                @click="confirmDorm"
              >确认入住</button>
              <button
                v-if="['ASSIGNED', 'CHECKED_IN'].includes(detail.student.dormStatus)"
                type="button"
                class="ori-act ori-act--danger"
                :disabled="submitting || isDenied('orientation.dorm.confirm')"
                @click="dormException"
              >标记入住异常</button>
              <button type="button" class="ori-act" @click="$router.push('/admin/orientation/dorm')">前往宿舍入住管理 →</button>
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
      <!-- 就地动作的填原因抽屉（退回/驳回/标记卡点等需理由的动作复用同一个抽屉） -->
      <EditDrawer
        v-model:visible="actionDrawer.visible"
        :title="actionDrawer.title"
        :fields="actionDrawer.fields"
        :model="null"
        :submitting="submitting"
        :submit-text="actionDrawer.submitText"
        @submit="onActionSubmit"
      />
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 3：/admin/orientation/students/:studentId 新生报到详情（环节进度 / 缴费 / 材料 / 宿舍 / 异常 / 留痕）。 */
import { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { EditDrawer, DeleteConfirmDialog, AuditTrailPanel } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { orientationWorklist } from '@/modules/orientation/constants/orientation.worklist'
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
      dormTagType: DORM_TAG_TYPE,
      actionDrawer: { visible: false, title: '', fields: [], submitText: '确认提交', handler: null }
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
    },
    showMaterialActions() {
      return this.detail?.student?.recordStatus !== 'VOIDED' && !this.isHidden('orientation.material.review')
    },
    /* ---------------- 待办队列：上一个/下一个流水线导航 ---------------- */
    wlIndex() {
      return orientationWorklist.ids.indexOf(String(this.$route.params.studentId))
    },
    wlTotal() {
      return orientationWorklist.ids.length
    },
    wlHasQueue() {
      return this.wlIndex >= 0 && this.wlTotal > 1
    },
    prevId() {
      return this.wlIndex > 0 ? orientationWorklist.ids[this.wlIndex - 1] : null
    },
    nextId() {
      return this.wlIndex >= 0 && this.wlIndex < this.wlTotal - 1 ? orientationWorklist.ids[this.wlIndex + 1] : null
    }
  },
  watch: {
    '$route.params.studentId'(id) {
      if (id) this.load()
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
    },
    /* ---------------- 就地动作：权限判断 ---------------- */
    isDenied(key) {
      const p = this.perms[key]
      return !!(p && p.allowed === false)
    },
    isHidden(key) {
      const p = this.perms[key]
      return !!(p && p.visible === false)
    },
    /* ---------------- 就地动作：统一执行 + 填原因抽屉 ---------------- */
    async runApi(fn, okMsg) {
      this.submitting = true
      try {
        const res = await fn()
        if (res.code === 0) {
          toast.success(okMsg)
          this.actionDrawer.visible = false
          this.load()
        } else toast.error(res.message)
      } catch (e) {
        toast.error(e.message || '操作失败')
      } finally {
        this.submitting = false
      }
    },
    openReason({ title, fields, submitText = '确认提交', handler }) {
      this.actionDrawer = { visible: true, title, fields, submitText, handler }
    },
    onActionSubmit(form) {
      if (this.actionDrawer.handler) this.actionDrawer.handler(form)
    },
    /* ---------------- 就地动作：信息核验 / 卡点 ---------------- */
    verifyPass() {
      this.runApi(() => api.verifyOrientationStudent(this.detail.student.id, { passed: true }), '信息核验已通过')
    },
    verifyReturn() {
      const id = this.detail.student.id
      this.openReason({
        title: '信息核验退回',
        submitText: '确认退回',
        fields: [{ key: 'reason', label: '退回原因', type: 'textarea', required: true, placeholder: '请说明需重新核对的内容（不少于5字）' }],
        handler: (f) => this.runApi(() => api.verifyOrientationStudent(id, { passed: false, reason: f.reason }), '已退回，学生需重新核对信息')
      })
    },
    markBlock() {
      const id = this.detail.student.id
      this.openReason({
        title: '标记报到卡点',
        submitText: '标记卡点',
        fields: [
          { key: 'blockedStep', label: '卡在哪个环节', type: 'select', required: true, options: (this.detail.steps || []).map((s) => ({ value: s.key, label: s.label })) },
          { key: 'blockedReason', label: '卡点原因', type: 'textarea', required: true, placeholder: '请说明卡点原因（不少于5字）' }
        ],
        handler: (f) => this.runApi(() => api.updateBlockedIssue(id, { blockedStep: f.blockedStep, blockedReason: f.blockedReason }), '已标记卡点')
      })
    },
    resolveBlock() {
      this.runApi(() => api.resolveBlockedIssue(this.detail.student.id, { note: '' }), '卡点已解除')
    },
    /* ---------------- 就地动作：材料审核 ---------------- */
    approveMaterial(m) {
      this.runApi(() => api.approveOrientationMaterial(m.id, { comment: '' }), '材料已通过')
    },
    returnMaterial(m) {
      this.openReason({
        title: '退回材料',
        submitText: '确认退回',
        fields: [{ key: 'reason', label: '退回原因', type: 'textarea', required: true, placeholder: '请说明需补充的内容（不少于5字）' }],
        handler: (f) => this.runApi(() => api.returnOrientationMaterial(m.id, { reason: f.reason }), '材料已退回')
      })
    },
    /* ---------------- 就地动作：绿色通道 ---------------- */
    approveGreen(g) {
      this.runApi(() => api.approveGreenChannel(g.id, { remark: '' }), '绿色通道已通过')
    },
    returnGreen(g) {
      this.openReason({
        title: '退回绿色通道申请',
        submitText: '确认退回',
        fields: [{ key: 'reason', label: '退回原因', type: 'textarea', required: true, placeholder: '请说明需补充的内容（不少于5字）' }],
        handler: (f) => this.runApi(() => api.returnGreenChannel(g.id, { reason: f.reason }), '已退回申请人补充')
      })
    },
    rejectGreen(g) {
      this.openReason({
        title: '驳回绿色通道申请',
        submitText: '确认驳回',
        fields: [{ key: 'reason', label: '驳回原因', type: 'textarea', required: true, placeholder: '请说明驳回理由（不少于5字）' }],
        handler: (f) => this.runApi(() => api.rejectGreenChannel(g.id, { reason: f.reason }), '已驳回该绿色通道申请')
      })
    },
    /* ---------------- 就地动作：宿舍入住 ---------------- */
    confirmDorm() {
      this.runApi(() => api.batchConfirmCheckin([this.detail.student.id]), '已确认入住')
    },
    dormException() {
      const id = this.detail.student.id
      this.openReason({
        title: '标记入住异常',
        submitText: '标记异常',
        fields: [{ key: 'note', label: '异常说明', type: 'textarea', required: true, placeholder: '请说明入住异常情况（不少于5字）' }],
        handler: (f) => this.runApi(() => api.markDormException(id, { note: f.note }), '已标记宿舍入住异常')
      })
    },
    /* ---------------- 待办队列：翻到相邻学生（同组件复用，靠 watch 重载） ---------------- */
    goSibling(id) {
      if (id && String(id) !== String(this.$route.params.studentId)) {
        this.$router.push(`/admin/orientation/students/${id}`)
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
.ori-actbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
.ori-rowact {
  display: inline-flex;
  gap: var(--space-1);
  margin-left: var(--space-2);
}
.ori-act {
  padding: 4px 10px;
  border-radius: var(--radius-base);
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all 0.12s;
}
.ori-act:hover:not(:disabled) {
  border-color: var(--primary-500);
  color: var(--primary-500);
}
.ori-act--primary {
  border-color: var(--primary-500);
  background: var(--primary-500);
  color: #fff;
}
.ori-act--primary:hover:not(:disabled) {
  color: #fff;
  box-shadow: 0 0 0 3px var(--primary-50);
}
.ori-act--danger {
  border-color: var(--danger-100);
  color: var(--danger-600);
}
.ori-act--danger:hover:not(:disabled) {
  background: var(--danger-50);
}
.ori-act:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ori-wl-pos {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  align-self: center;
  padding: 0 var(--space-1);
}
.ori-back:disabled {
  opacity: 0.45;
  cursor: not-allowed;
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
