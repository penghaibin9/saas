<template>
  <ModulePageShell
    :title="detail ? detail.name + ' · 实习详情' : '实习详情'"
    :subtitle="detail ? detail.className + ' · ' + maskNo(detail.studentNo) : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
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
            <span class="mp-card__title">实习信息</span>
            <span>
              <StatusTag :status="detail.status" :label="detail.statusLabel" dot />
              <RiskTag v-if="detail.riskLevel !== 'NONE'" :level="detail.riskLevel" style="margin-left: var(--space-2)" />
            </span>
          </div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">实习企业</span><span class="mp-kv__v">{{ detail.enterpriseName }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">实习岗位</span><span class="mp-kv__v">{{ detail.positionName }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">校内导师</span><span class="mp-kv__v">{{ detail.advisorName }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">企业导师</span><span class="mp-kv__v">{{ detail.enterpriseMentor }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">实习起止</span><span class="mp-kv__v">{{ detail.internRange }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">保险</span><span class="mp-kv__v">{{ detail.insurance }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">三方协议</span><span class="mp-kv__v">{{ detail.agreement }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">联系电话</span><span class="mp-kv__v">{{ maskPhone(detail.phone) }}</span></div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">主状态进度</span></div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="s in detail.stateFlow" :key="s.title" class="mp-timeline__item" :class="'is-' + (s.tone === 'processing' ? 'warning' : s.tone)">
                <div class="mp-timeline__title">{{ s.title }}</div>
                <div class="mp-timeline__time">{{ s.time }}</div>
              </li>
            </ul>
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
            <table v-if="tab === 'checkins'" class="mp-audit">
              <thead><tr><th>日期 / 时段</th><th>结果</th><th>距打卡点</th><th>设备</th><th>学生说明</th><th>处理</th></tr></thead>
              <tbody>
                <tr v-for="c in detail.checkins" :key="c.id">
                  <td class="is-who">{{ c.date }}</td>
                  <td><StatusTag :type="c.tone" :label="c.result" /></td>
                  <td>{{ c.distance }}</td>
                  <td>{{ c.device }}</td>
                  <td>{{ c.note || '—' }}</td>
                  <td>{{ c.handle }}</td>
                </tr>
              </tbody>
            </table>
            <table v-else-if="tab === 'reports'" class="mp-audit">
              <thead><tr><th>周次</th><th>提交时间</th><th>版本</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="r in detail.reports" :key="r.id">
                  <td class="is-who">{{ r.week }}</td>
                  <td>{{ r.submitAt || '—' }}</td>
                  <td>{{ r.version }}</td>
                  <td><StatusTag :status="r.status" dot /></td>
                </tr>
              </tbody>
            </table>
            <table v-else-if="tab === 'leaves'" class="mp-audit">
              <thead><tr><th>类型</th><th>时间</th><th>状态</th><th>审批人</th></tr></thead>
              <tbody>
                <tr v-for="l in detail.leaves" :key="l.id">
                  <td class="is-who">{{ l.type }}</td>
                  <td>{{ l.range }}</td>
                  <td><StatusTag :status="l.status" dot /></td>
                  <td>{{ l.reviewer }}</td>
                </tr>
              </tbody>
            </table>
            <table v-else class="mp-audit">
              <thead><tr><th>编码 / 风险</th><th>等级</th><th>状态</th><th>责任人</th></tr></thead>
              <tbody>
                <tr v-for="r in detail.risks" :key="r.id">
                  <td class="is-who">{{ r.code }} · {{ r.title }}</td>
                  <td><RiskTag :level="r.level" /></td>
                  <td>{{ r.status }}</td>
                  <td>{{ r.owner }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">审计日志（本学生实习档案）</span></div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead><tr><th>操作人</th><th>时间</th><th>动作</th><th>影响数据</th></tr></thead>
              <tbody>
                <tr v-for="(a, i) in detail.auditTrail" :key="i">
                  <td class="is-who">{{ a.who }}</td>
                  <td>{{ a.time }}</td>
                  <td>{{ a.action }}</td>
                  <td>{{ a.affected }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/** 实习学生详情（/admin/internship/students/:id）：档案 + 四页签 + 审计日志。 */
import { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState } from '@/components/business'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

export default {
  name: 'InternshipStudentDetailView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      detail: null,
      tab: 'checkins',
      tabs: [
        { key: 'checkins', label: '打卡记录' },
        { key: 'reports', label: '周报记录' },
        { key: 'leaves', label: '请假记录' },
        { key: 'risks', label: '风险记录' }
      ]
    }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'batchRemind', label: '发送提醒' },
        { key: 'editStudent', label: '编辑实习信息', variant: 'primary' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    maskPhone(v) {
      return v ? v.slice(0, 3) + '****' + v.slice(-4) : '未登记'
    },
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
    },
    onToolbar(key) {
      if (key === 'batchRemind') toast.success('提醒已发送（站内信 + 小程序订阅消息），已写入审计日志')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await internshipApi.getStudentDetail(this.$route.params.id)
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
