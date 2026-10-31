<template>
  <view class="card stack report-obligations">
    <button @click="toggle" :disabled="sending">{{ opened ? '收起应交与未交名单' : '查看应交与未交名单' }}</button>
    <template v-if="opened">
      <text class="t-sm">按当前批次应交篇数与已提交原单计算；退回仍计已交，重交不重复计数。未配置应交数时不计算缺交。</text>
      <picker :range="types" range-key="label" :value="typeIndex" :disabled="sending" @change="changeType">
        <view>报告类型：{{ types[typeIndex].label }} ▾</view>
      </picker>
      <view class="row">
        <button :disabled="sending || loading" @click="setMissing(true)">仅看未交</button>
        <button :disabled="sending || loading" @click="setSubmitted">仅看已交</button>
        <button :disabled="sending || loading" @click="setMissing(false)">全部学生</button>
      </view>
      <text>{{ missingOnly ? '未交名单' : submittedOnly ? '已交名单' : '全部学生' }} · 共 {{ total }} 人</text>
      <button v-if="canReview" :disabled="sending || loading || !!error || (missingOnly && total === 0)" @click="remindAll">{{ sending ? '正在逐人登记催交…' : '提醒该类型全部未交学生' }}</button>
      <text v-else class="t-sm">当前身份可查看名单，催交需报告批阅权限。</text>
      <view v-if="receipt" role="status" class="stack">
        <text>{{ receipt.text }}</text>
        <text v-for="item in receipt.failures" :key="item.id">{{ item.name }}：{{ item.message }}</text>
      </view>
      <view v-if="error" role="alert"><text>{{ error }}</text><button :disabled="sending" @click="load()">重新查询</button></view>
      <text v-else-if="loading">正在读取名单…</text>
      <text v-else-if="!rows.length">当前类型没有符合条件的学生。</text>
      <view v-for="row in rows" :key="row.recordId" class="stack report-obligations__student">
        <text class="t-bold">{{ row.studentName }} · {{ row.studentNo }}</text>
        <text>{{ metricText(row) }}</text>
      </view>
      <button v-if="rows.length < total" :disabled="loading || sending" @click="load(true)">加载更多学生</button>
    </template>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

export default {
  props: { batchId: { type: String, required: true }, canReview: Boolean, initialType: { type: String, default: 'DAILY' } },
  data() {
    return { opened: false, typeIndex: 0, missingOnly: true, submittedOnly: false, rows: [], total: 0, page: 1,
      loading: false, sending: false, error: '', receipt: null, sequence: 0,
      types: [{ label: '日报', value: 'DAILY' }, { label: '周报', value: 'WEEKLY' }, { label: '月报', value: 'MONTHLY' }, { label: '实习总结', value: 'SUMMARY' }] }
  },
  computed: { metricKey() { return this.types[this.typeIndex].value.toLowerCase() } },
  watch: { batchId() { this.sequence++; this.rows = []; this.total = 0; this.receipt = null; this.sending = false; if (this.opened) this.load() } },
  beforeUnmount() { this.sequence++ },
  methods: {
    current(command) { return command.sequence === this.sequence && command.batchId === this.batchId && command.generation === currentSessionGeneration() },
    command() { return { sequence: this.sequence, batchId: this.batchId, generation: currentSessionGeneration(), reportType: this.types[this.typeIndex].value } },
    toggle() {
      if (this.sending) return
      this.opened = !this.opened; this.sequence++
      if (this.opened) { this.typeIndex = Math.max(0, this.types.findIndex(type => type.value === this.initialType)); this.load() }
    },
    changeType(event) { if (!this.sending) { this.typeIndex = Number(event.detail.value); this.load() } },
    setMissing(value) { if (!this.sending) { this.missingOnly = value; this.submittedOnly = false; this.load() } },
    setSubmitted() { if (!this.sending) { this.missingOnly = false; this.submittedOnly = true; this.load() } },
    metricText(row) {
      const metric = row[this.metricKey]
      return metric?.configured ? `应交 ${metric.required} 篇 / 已交 ${metric.submitted} 篇 / 已通过 ${metric.approved} 篇 / 缺交 ${metric.missing} 篇` : `应交数未配置 / 已交 ${metric?.submitted || 0} 篇`
    },
    async load(more = false) {
      if (this.sending || (more && this.loading)) return
      this.sequence++
      const command = this.command(), page = more ? this.page + 1 : 1
      if (!more) { this.rows = []; this.total = 0; this.receipt = null }
      this.loading = true; this.error = ''
      try {
        const data = await teacherApi.getReportObligations({ ...command, missingOnly: this.missingOnly, submittedOnly: this.submittedOnly, page })
        if (!this.current(command)) return
        this.rows = more ? [...this.rows, ...data.items] : data.items; this.total = data.total; this.page = page
      } catch (error) { if (this.current(command)) this.error = normalizeError(error).text }
      finally { if (this.current(command)) this.loading = false }
    },
    async remindAll() {
      if (this.sending || this.loading || this.error || !this.canReview || !this.batchId) return
      const command = this.command(), targets = [], failures = []
      let registered = 0, attempted = 0, expectedTotal = null
      this.sending = true; this.receipt = null
      try {
        // Read every recipient page before sending; each command rechecks current scope and missing facts.
        for (let page = 1; ; page++) {
          const data = await teacherApi.getReportObligations({ ...command, missingOnly: true, page, pageSize: 200 })
          if (!this.current(command)) return
          if (expectedTotal !== null && data.total !== expectedTotal) throw { biz: true, bizCode: 'DATA_CONFLICT', message: '未交名单已变化，请重新查询后再催交' }
          expectedTotal = data.total
          if (!data.items.length && targets.length < data.total) throw new Error('incomplete recipients')
          targets.push(...data.items)
          if (targets.length >= data.total) break
        }
        const unique = [...new Map(targets.map(row => [row.recordId, row])).values()]
        if (unique.length !== expectedTotal) throw { biz: true, bizCode: 'DATA_CONFLICT', message: '未交名单已变化，请重新查询后再催交' }
        for (const row of unique) {
          if (!this.current(command) || !this.canReview) return
          attempted++
          try {
            await teacherApi.remindReportObligation(row.recordId, command.batchId, command.reportType)
            registered++
          } catch (error) {
            if (!this.current(command)) return
            const shown = normalizeError(error)
            failures.push({ id: row.recordId, name: row.studentName, message: shown.text })
            if (!['conflict', 'invalid', 'notfound'].includes(shown.kind)) {
              this.receipt = { text: `已登记 ${registered} 人；本次结果未全部确认，已停止后续 ${unique.length - attempted} 人。请先核对站内消息，勿重复发送。`, failures }
              return
            }
          }
        }
        if (this.current(command)) this.receipt = { text: `催交已登记 ${registered} 人，未登记 ${failures.length} 人。学生在站内消息接收，登记不代表已经送达。`, failures }
      } catch (error) { if (this.current(command)) this.receipt = { text: `名单读取失败，未发送催交。${normalizeError(error).text}`, failures } }
      finally { if (this.current(command)) this.sending = false }
    }
  }
}
</script>

<style scoped>
.report-obligations { margin: 12px 0; overflow-wrap: anywhere; }
.report-obligations__student { border-top: 1px solid #e5e7eb; padding-top: 12px; }
.report-obligations button { white-space: normal; }
</style>
