<template>
  <ModulePageShell
    :title="detail ? detail.student.name + ' · 服务详情' : '服务详情'"
    :subtitle="detail ? detail.student.className + ' · ' + maskNo(detail.student.studentNo) : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">服务画像</span>
            <span>
              <StatusTag
                :type="detail.student.careLevel === 'NORMAL' ? 'default' : detail.student.careLevel === 'FOCUS' ? 'warning' : 'danger'"
                :label="careLabel(detail.student.careLevel)"
                dot
              />
              <RiskTag v-if="detail.student.riskLevel !== 'LOW'" :level="detail.student.riskLevel" style="margin-left: var(--space-2)" />
            </span>
          </div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">学院 / 专业</span><span class="mp-kv__v">{{ detail.student.collegeName }} · {{ detail.student.majorName }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">宿舍</span><span class="mp-kv__v">{{ detail.student.building }} {{ detail.student.room }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">辅导员</span><span class="mp-kv__v">{{ detail.student.counselor }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">请假 / 工单</span><span class="mp-kv__v">{{ detail.student.leaveCount }} 次 / {{ detail.student.workOrderCount }} 单</span></div>
            <div class="mp-kv"><span class="mp-kv__k">奖助状态</span><span class="mp-kv__v">{{ detail.student.grantSummary }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">处分记录</span><span class="mp-kv__v">{{ detail.student.disciplineCount }} 条</span></div>
            <div class="mp-kv"><span class="mp-kv__k">联系电话</span><span class="mp-kv__v">{{ detail.student.phone || '未登记' }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">更新时间</span><span class="mp-kv__v">{{ detail.student.updateTime }}</span></div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">心理关怀（涉密收敛）</span></div>
          <div class="mp-card__body">
            <template v-if="detail.mentals.length">
              <div v-for="m in detail.mentals" :key="m.id" class="mp-kv">
                <span class="mp-kv__k">{{ m.levelLabel }} · {{ m.lastFollowTime }}</span>
                <span class="mp-kv__v">{{ m.summary }}</span>
              </div>
              <p class="mp-note">心理记录为涉密数据：仅心理老师可见完整内容，本次访问已写入审计日志。</p>
            </template>
            <EmptyState v-else title="无心理关怀记录" description="该学生当前没有心理关怀跟进，或当前角色无权查看" />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">违纪 / 处分</span></div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead><tr><th>编号</th><th>类型</th><th>事由</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="d in detail.disciplines" :key="d.id">
                  <td class="is-who">{{ d.code }}</td>
                  <td>{{ disciplineLabel(d.type) }}</td>
                  <td>{{ d.reason }}</td>
                  <td><StatusTag :type="d.status === 'EFFECTIVE' ? 'danger' : 'default'" :label="d.status === 'EFFECTIVE' ? '生效中' : '已解除'" /></td>
                </tr>
                <tr v-if="!detail.disciplines.length"><td colspan="4" class="mp-note">无处分记录</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-tabs" style="padding: 0 var(--space-4)">
            <button v-for="t in tabs" :key="t.key" class="mp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">
              {{ t.label }}
            </button>
          </div>
          <div class="mp-card__body">
            <table v-if="tab === 'leaves'" class="mp-audit">
              <thead><tr><th>编号</th><th>类型 / 时长</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="l in detail.leaves" :key="l.id">
                  <td class="is-who">{{ l.code }}<div class="mp-cell-sub">{{ l.applyTime }}</div></td>
                  <td>{{ leaveTypeLabel(l.type) }} · {{ l.duration }}</td>
                  <td><StatusTag :status="l.status" :label="leaveStatusLabel(l.status)" dot /></td>
                  <td><button class="mp-link" @click="$router.push('/admin/campus-service/leave?keyword=' + l.code)">去处理</button></td>
                </tr>
                <tr v-if="!detail.leaves.length"><td colspan="4" class="mp-note">无请假记录</td></tr>
              </tbody>
            </table>
            <table v-else-if="tab === 'grants'" class="mp-audit">
              <thead><tr><th>编号</th><th>类型 / 金额</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="g in detail.grants" :key="g.id">
                  <td class="is-who">{{ g.code }}<div class="mp-cell-sub">{{ g.applyTime }}</div></td>
                  <td>{{ grantTypeLabel(g.type) }} · {{ g.amountDisplay }}</td>
                  <td><StatusTag :status="g.status" :label="grantStatusLabel(g.status)" dot /></td>
                  <td><button class="mp-link" @click="$router.push('/admin/campus-service/grants?keyword=' + g.code)">去处理</button></td>
                </tr>
                <tr v-if="!detail.grants.length"><td colspan="4" class="mp-note">无资助申请</td></tr>
              </tbody>
            </table>
            <table v-else-if="tab === 'dorm'" class="mp-audit">
              <thead><tr><th>时间</th><th>类型</th><th>说明</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="e in detail.dormExceptions" :key="e.id">
                  <td>{{ e.happenTime }}</td>
                  <td class="is-who">{{ e.typeLabel }}</td>
                  <td>{{ e.detail }}</td>
                  <td><StatusTag :status="e.status" :label="dormStatusLabel(e.status)" dot /></td>
                </tr>
                <tr v-if="!detail.dormExceptions.length"><td colspan="4" class="mp-note">无宿舍异常记录</td></tr>
              </tbody>
            </table>
            <table v-else class="mp-audit">
              <thead><tr><th>编号 / 标题</th><th>类型</th><th>处理人</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="w in detail.workOrders" :key="w.id">
                  <td class="is-who">{{ w.code }}<div class="mp-cell-sub">{{ w.title }}</div></td>
                  <td>{{ orderTypeLabel(w.type) }}</td>
                  <td>{{ w.handler || '未分派' }}</td>
                  <td><StatusTag :status="w.status" :label="orderStatusLabel(w.status)" dot /></td>
                </tr>
                <tr v-if="!detail.workOrders.length"><td colspan="4" class="mp-note">无服务工单</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">审计留痕（本学生服务档案）</span></div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead><tr><th>操作人</th><th>时间</th><th>动作</th><th>明细</th></tr></thead>
              <tbody>
                <tr v-for="a in detail.auditLogs" :key="a.id">
                  <td class="is-who">{{ a.operator }}<div class="mp-cell-sub">{{ a.roleName }}</div></td>
                  <td>{{ a.time }}</td>
                  <td>{{ a.action }}</td>
                  <td>{{ a.detail }}</td>
                </tr>
                <tr v-if="!detail.auditLogs.length"><td colspan="4" class="mp-note">暂无审计记录</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学生服务详情（/admin/campus-service/students/:id）：服务画像 + 心理涉密收敛 + 处分 + 四页签（请假/资助/宿舍/工单）+ 审计。 */
import { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { getStudentServiceDetail, batchRemindServiceStudents } from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

export default {
  name: 'ServiceStudentDetailView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      detail: null,
      tab: 'leaves',
      tabs: [
        { key: 'leaves', label: '请假记录' },
        { key: 'grants', label: '资助申请' },
        { key: 'dorm', label: '宿舍异常' },
        { key: 'orders', label: '服务工单' }
      ]
    }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'remind', permission: 'campus.record.batchRemind', label: '发送提醒' },
        { key: 'order', permission: 'campus.workorder.create', label: '＋ 新建工单', variant: 'primary' }
      ]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
    },
    lbl(group, v) {
      return ((this.ctx.statusOptions[group] || []).find((o) => o.value === v) || {}).label || v
    },
    careLabel(v) {
      return this.lbl('careLevel', v)
    },
    leaveTypeLabel(v) {
      return this.lbl('leaveType', v)
    },
    leaveStatusLabel(v) {
      return this.lbl('leaveStatus', v)
    },
    grantTypeLabel(v) {
      return this.lbl('grantType', v)
    },
    grantStatusLabel(v) {
      return this.lbl('grantStatus', v)
    },
    dormStatusLabel(v) {
      return this.lbl('dormExceptionStatus', v)
    },
    disciplineLabel(v) {
      return this.lbl('disciplineType', v)
    },
    orderTypeLabel(v) {
      return this.lbl('workOrderType', v)
    },
    orderStatusLabel(v) {
      return this.lbl('workOrderStatus', v)
    },
    async onToolbar(key) {
      if (key === 'remind') {
        const res = await batchRemindServiceStudents([this.detail.student.id], '在校服务事项办理')
        if (res.code === 0) toast.success('提醒已发送（站内信 + 小程序），已写入审计日志')
        else toast.error(res.message)
      } else if (key === 'order') {
        this.$router.push('/admin/campus-service/work-orders?create=' + this.detail.student.id)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await getStudentServiceDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
