<template>
  <div class="aa-print">
    <div class="aa-print__bar">
      <span>{{ printTime }} · 操作人：{{ operator }}</span>
      <button class="mp-btn mp-btn--primary" @click="doPrint">打印</button>
    </div>

    <LoadingState v-if="loading" />
    <div v-else-if="error" class="aa-print__err">{{ error }}</div>
    <div v-else-if="change" class="aa-print__sheet">
      <h1 class="aa-print__title">{{ schoolName }}</h1>
      <h2 class="aa-print__subtitle">学籍异动审批表</h2>
      <table class="aa-print__table">
        <tbody>
          <tr><th>学生姓名</th><td>{{ change.realName }}</td><th>学生ID</th><td>{{ change.studentId }}</td></tr>
          <tr><th>异动类型</th><td>{{ change.changeTypeLabel }}</td><th>状态变化</th><td>{{ change.fromStatus }} → {{ change.toStatus }}</td></tr>
          <tr><th>当前状态</th><td>{{ statusLabel(change.status) }}</td><th>当前节点</th><td>{{ nodeLabel(change.currentNode) }}</td></tr>
          <tr v-if="change.expireDate"><th>休学到期</th><td>{{ change.expireDate }}</td><th>生效日期</th><td>{{ change.effectiveDate || '—' }}</td></tr>
          <tr><th>申请原因</th><td colspan="3">{{ change.reason || '（无）' }}</td></tr>
        </tbody>
      </table>
      <div class="aa-print__flow">
        <div class="aa-print__flow-title">审批流程</div>
        <div v-for="(n, i) in flowNodes" :key="n" class="aa-print__flow-node">
          <span>{{ i + 1 }}. {{ nodeLabel(n) }}</span>
          <span class="aa-print__sign">签字 / 日期：____________</span>
        </div>
      </div>
      <div class="aa-print__seal">教务处（盖章）：____________　　日期：__________</div>
    </div>
  </div>
</template>

<script>
/** 学籍异动审批表打印页（/admin/academic-affairs/print/status-change/:id）：D7 独立打印路由，无导航布局。 */
import { LoadingState } from '@/components/business'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { STATUS_LABEL, NODE_LABEL, CHANGE_FLOW_NODES } from '@/modules/academicAffairs/constants/status-change'

export default {
  name: 'AaStatusChangePrintView',
  components: { LoadingState },
  data() {
    return { loading: true, error: '', change: null, schoolName: '职业院校', operator: '', printTime: '' }
  },
  computed: {
    flowNodes() { return this.change ? (CHANGE_FLOW_NODES[this.change.changeType] || []) : [] }
  },
  created() {
    // new Date() 在浏览器运行时可用（非 workflow 沙箱）；仅用于打印抬头展示
    const d = new Date()
    this.printTime = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
    this.load()
  },
  methods: {
    statusLabel(s) { return STATUS_LABEL[s] || s || '' },
    nodeLabel(n) { return n ? (NODE_LABEL[n] || n) : '—' },
    doPrint() { window.print() },
    async load() {
      const [ctxRes, chgRes] = await Promise.all([
        academicAffairsApi.getContext(),
        academicAffairsApi.getStatusChange(this.$route.params.id)
      ])
      if (ctxRes.code === 0) {
        this.schoolName = ctxRes.data.tenantBrandConfig.schoolName || '职业院校'
        this.operator = ctxRes.data.currentRole.roleName || ''
      }
      if (chgRes.code === 0) {
        this.change = chgRes.data
      } else {
        this.error = chgRes.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-print { padding: 24px; max-width: 800px; margin: 0 auto; color: #000; background: #fff; }
.aa-print__bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; font-size: 12px; color: #666; }
.aa-print__err { color: var(--danger-600, #f53f3f); }
.aa-print__title { text-align: center; font-size: 22px; margin: 0 0 4px; }
.aa-print__subtitle { text-align: center; font-size: 16px; font-weight: 500; margin: 0 0 20px; }
.aa-print__table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
.aa-print__table th, .aa-print__table td { border: 1px solid #333; padding: 8px 12px; font-size: 14px; text-align: left; }
.aa-print__table th { background: #f5f5f5; width: 100px; font-weight: 500; }
.aa-print__flow-title { font-weight: 600; margin-bottom: 8px; }
.aa-print__flow-node { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px dashed #999; font-size: 14px; }
.aa-print__sign { color: #666; }
.aa-print__seal { margin-top: 32px; text-align: right; font-size: 14px; }
@media print {
  .aa-print__bar { display: none; }
  .aa-print { padding: 0; }
  @page { size: A4; margin: 1.5cm; }
}
</style>
