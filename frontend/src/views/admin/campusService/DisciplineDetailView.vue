<template>
  <ModulePageShell
    :title="record ? '违纪详情 · ' + record.code : '违纪详情'"
    :subtitle="record ? record.name + '（' + record.className + '）' : '按编号定位处分记录'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <AppButton variant="ghost" @click="backToList">← 返回列表</AppButton>
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!record"
        title="未找到该处分记录"
        description="记录可能不存在、已超出当前数据范围，或链接缺少编号参数；请从违纪处分列表重新进入"
      />
      <template v-else>
        <div class="mp-card">
          <div class="mp-card__head"><div class="mp-card__title">学生摘要</div></div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ record.name }}（{{ record.className }}）</span></div>
            <div class="mp-kv">
              <span class="mp-kv__k">快捷入口</span>
              <span class="mp-kv__v">
                <button class="mp-link" @click="$router.push('/admin/campus-service/students/' + record.studentId)">学生服务</button>
                <button class="mp-link" @click="$router.push('/admin/student/' + record.studentId)">学生360</button>
              </span>
            </div>
          </div>
        </div>

        <div class="mp-card">
          <div class="mp-card__head"><div class="mp-card__title">违纪基本信息</div></div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">编号 / 文号</span><span class="mp-kv__v">{{ record.code }}{{ record.docNo ? ' · ' + record.docNo : '' }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">处分类型</span><span class="mp-kv__v"><StatusTag :type="record.type === 'WARNING' ? 'warning' : 'danger'" :label="typeLabel(record.type)" /></span></div>
            <div class="mp-kv"><span class="mp-kv__k">决定日期</span><span class="mp-kv__v">{{ record.decideDate || '未设置' }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">经办人 / 更新时间</span><span class="mp-kv__v">{{ record.operator || '—' }} · {{ record.updateTime || '—' }}</span></div>
          </div>
        </div>

        <div class="mp-card">
          <div class="mp-card__head"><div class="mp-card__title">违纪事实</div></div>
          <div class="mp-card__body"><p class="ddv-reason">{{ record.reason }}</p></div>
        </div>

        <div class="mp-card">
          <div class="mp-card__head"><div class="mp-card__title">处分状态</div></div>
          <div class="mp-card__body">
            <div class="mp-kv">
              <span class="mp-kv__k">当前状态</span>
              <span class="mp-kv__v">
                <StatusTag :type="record.status === 'EFFECTIVE' ? 'danger' : 'default'" :label="record.status === 'EFFECTIVE' ? '生效中' : '已解除'" dot />
                <StatusTag v-if="record.recordStatus === 'VOIDED'" type="default" label="已作废" />
              </span>
            </div>
            <div v-if="record.status === 'REVOKED'" class="mp-kv"><span class="mp-kv__k">解除日期 / 说明</span><span class="mp-kv__v">{{ record.revokeDate || '—' }} · {{ record.revokeReason || '—' }}</span></div>
            <div v-if="record.recordStatus === 'VOIDED'" class="mp-kv"><span class="mp-kv__k">作废原因</span><span class="mp-kv__v">{{ record.voidReason || '—' }}</span></div>
          </div>
        </div>

        <div class="mp-card">
          <div class="mp-card__head"><div class="mp-card__title">材料附件</div></div>
          <div class="mp-card__body">
            <p class="mp-note">暂无相关数据（处分材料附件随「违纪处分」模块流程链施工接入，本页不展示推测数据）。</p>
          </div>
        </div>

        <div class="mp-card">
          <div class="mp-card__head"><div class="mp-card__title">操作历史（审计留痕）</div></div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead><tr><th>时间</th><th>操作人</th><th>动作</th></tr></thead>
              <tbody>
                <tr v-for="a in auditLogs" :key="a.id">
                  <td>{{ a.time }}</td>
                  <td class="is-who">{{ a.operator }}</td>
                  <td>{{ a.detail }}</td>
                </tr>
                <tr v-if="!auditLogs.length"><td colspan="3" class="mp-note">暂无操作记录</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="ddv-actions">
          <AppButton
            v-if="record.status === 'EFFECTIVE' && record.recordStatus === 'ACTIVE'"
            variant="primary"
            :disabled="!can('campus.discipline.edit')"
            :title="reason('campus.discipline.edit')"
            @click="revokeDialog = { visible: true, submitting: false }"
          >解除处分</AppButton>
          <AppButton
            v-if="visiblePerm('campus.discipline.void') && record.recordStatus === 'ACTIVE'"
            variant="danger"
            :disabled="!can('campus.discipline.void')"
            :title="reason('campus.discipline.void')"
            @click="voidDialog = { visible: true, submitting: false }"
          >作废记录</AppButton>
        </div>
        <p class="mp-note">审批、决定送达、申诉、解除流程链随「违纪处分」模块施工接入后在本页扩展，当前仅提供已实现的解除 / 作废操作。</p>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="revokeDialog.visible"
      type="primary"
      title="解除处分"
      :message="'确认解除「' + (record ? record.code + ' · ' + record.name : '') + '」的处分？解除后记录保留，状态置为已解除。'"
      confirm-text="确认解除"
      require-reason
      reason-label="解除说明"
      reason-placeholder="请说明解除依据（如察看期内表现良好，按程序解除），不少于 5 个字"
      :submitting="revokeDialog.submitting"
      @confirm="submitRevoke"
    />
    <AppConfirmDialog
      v-model:visible="voidDialog.visible"
      type="danger"
      title="作废处分记录"
      :message="'确认作废「' + (record ? record.code : '') + '」？作废仅用于录入错误，为逻辑删除并留痕。'"
      confirm-text="确认作废"
      require-reason
      reason-label="作废原因"
      reason-placeholder="请说明作废原因（如重复录入、信息错误），不少于 5 个字"
      :submitting="voidDialog.submitting"
      @confirm="submitVoid"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 违纪详情独立页（/admin/campus-service/discipline/:recordId?code=…）— 第一批交互改造。
 * 完整违纪业务不再放右侧抽屉：学生摘要 / 基本信息 / 违纪事实 / 处分状态 / 材料 / 操作历史 / 可执行操作。
 * 现无单条查询接口：按 ?code= 走既有列表接口 keyword 定位（刷新可用）；无 code 时翻前几页兜底；
 * 材料附件等未实现能力明确显示「暂无相关数据」，不造假 Tab。权限与数据范围沿用列表页原 key，越权仍被拦截。
 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppButton } from '@/components/ui'
import { getDisciplineRecords, updateDisciplineRecord, voidDisciplineRecord, getAuditLogs } from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

export default {
  name: 'DisciplineDetailView',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      record: null,
      auditLogs: [],
      revokeDialog: { visible: false, submitting: false },
      voidDialog: { visible: false, submitting: false }
    }
  },
  created() {
    this.load()
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    visiblePerm(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    typeLabel(v) {
      return (this.ctx.statusOptions.disciplineType.find((o) => o.value === v) || {}).label || v
    },
    backToList() {
      /* 优先历史返回（保留列表筛选/页码 query）；无来源时回列表首页 */
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (back && String(back).startsWith('/admin/campus-service/discipline')) this.$router.back()
      else this.$router.push('/admin/campus-service/discipline')
    },
    async load() {
      this.loading = true
      this.error = ''
      this.record = null
      const id = String(this.$route.params.recordId || '')
      const code = String(this.$route.query.code || '')
      try {
        /* 无单条接口：先按编号 keyword 精确检索，未命中时翻前 5 页兜底（既有接口，零后端改动） */
        if (code) {
          const res = await getDisciplineRecords({ keyword: code, page: 1, pageSize: 50 })
          if (res.code !== 0) throw new Error(res.message)
          this.record = (res.data.list || []).find((r) => r.id === id || r.code === code) || null
        }
        if (!this.record) {
          for (let page = 1; page <= 5 && !this.record; page++) {
            const res = await getDisciplineRecords({ page, pageSize: 100 })
            if (res.code !== 0) throw new Error(res.message)
            this.record = (res.data.list || []).find((r) => r.id === id) || null
            if ((res.data.list || []).length < 100) break
          }
        }
        if (this.record) this.loadAudit()
      } catch (e) {
        this.error = e.message || '加载失败'
      }
      this.loading = false
    },
    async loadAudit() {
      const res = await getAuditLogs({ bizType: 'DISCIPLINE', keyword: this.record.name, pageSize: 20 })
      this.auditLogs = res.code === 0 ? res.data.list : []
    },
    async submitRevoke({ reason }) {
      this.revokeDialog.submitting = true
      const res = await updateDisciplineRecord(this.record.id, { status: 'REVOKED', reason })
      this.revokeDialog.submitting = false
      this.revokeDialog.visible = false
      if (res.code === 0) {
        toast.success('处分已解除，解除说明已留痕并同步学生360')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async submitVoid({ reason }) {
      this.voidDialog.submitting = true
      const res = await voidDisciplineRecord(this.record.id, { reason })
      this.voidDialog.submitting = false
      this.voidDialog.visible = false
      if (res.code === 0) {
        toast.success('处分记录已作废（逻辑删除），原因已留痕')
        this.load()
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-stack .mp-card + .mp-card {
  margin-top: var(--space-3);
}
.ddv-reason {
  margin: 0;
  font-size: var(--font-size-sm);
  line-height: 1.7;
  white-space: pre-wrap;
}
.ddv-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
</style>
