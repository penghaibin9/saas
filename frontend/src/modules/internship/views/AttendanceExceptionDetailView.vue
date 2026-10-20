<template>
  <ModulePageShell
    :title="detail ? detail.studentName + ' · 打卡异常处理' : '打卡异常处理'"
    :subtitle="detail ? detail.date + ' · ' + detail.typeLabel : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ReviewQueueBar
      ref="queueBar"
      :current-id="$route.params.id"
      kind="attendance-exception"
      :make-path="(id) => ({ path: '/admin/internship/exceptions/' + id, query: $route.query })"
      :list-fallback="$router.resolve({ path: '/admin/internship/exceptions', query: $route.query }).fullPath"
      style="margin-bottom: var(--space-3)"
    />
    <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />
    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">异常打卡信息</span>
            <AppStatusTag :status="detail.status" dot>{{ detail.status === 'COMPLETED' ? '已处理' : '待核实' }}</AppStatusTag>
          </div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ detail.studentName }} · {{ detail.className }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">企业 / 岗位</span><span class="mp-kv__v">{{ detail.enterpriseName }} · {{ detail.positionName }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">打卡时间</span><span class="mp-kv__v">{{ detail.date }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">距打卡点</span><span class="mp-kv__v" style="color: var(--danger-600)">{{ detail.distance }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">定位精度</span><span class="mp-kv__v">{{ detail.accuracy }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">打卡地址</span><span class="mp-kv__v">{{ detail.address }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">设备风险信号</span><span class="mp-kv__v">{{ deviceSignalLabel }}</span></div>
            <p class="mp-note" style="margin-top: var(--space-3)">定位仅在学生主动打卡瞬时采集（按隐私保护规则展示）。</p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">定位证据对照</span>
            <span class="mp-note">{{ ruleSourceLabel }}</span>
          </div>
          <div class="mp-card__body">
            <AppInlineAlert
              :type="detail.decisionFactsComplete ? 'info' : 'warning'"
              :title="detail.decisionFactsComplete ? '证据可供人工核验' : '证据不完整，请先补充核实'"
              :description="evidenceConclusion"
            />
            <div class="ae-evidence">
              <div class="ae-evidence__plot" aria-label="围栏与定位误差范围示意">
                <span class="ae-evidence__fence"><i class="ae-evidence__point" /></span>
                <span class="ae-evidence__accuracy" :style="accuracyStyle" />
              </div>
              <div class="ae-evidence__facts">
                <div><span>打卡坐标</span><strong>{{ coordinateText }}</strong></div>
                <div><span>围栏半径</span><strong>{{ evidence.radiusM != null ? `${evidence.radiusM} 米` : '未配置' }}</strong></div>
                <div><span>定位误差</span><strong>{{ evidence.accuracyM != null ? `±${evidence.accuracyM} 米` : '未上报' }}</strong></div>
                <div><span>批次误差上限</span><strong>{{ evidence.maxAccuracyM != null ? `${evidence.maxAccuracyM} 米` : '—' }}</strong></div>
              </div>
            </div>
            <p class="mp-note">图形用于比较围栏、距离与精度关系，不替代地图底图；教师应结合学生说明和企业核实后处理。</p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">学生说明（来自学生端）</span>
            <span v-if="detail.noteTime" class="mp-note">提交于 {{ detail.noteTime }}</span>
          </div>
          <div class="mp-card__body">
            <p style="margin: 0; font-size: var(--font-size-sm); color: var(--text-secondary)">{{ detail.studentNote }}</p>
            <div v-if="detail.attachments && detail.attachments.length" style="margin-top: var(--space-3); display: flex; gap: var(--space-2)">
              <AppStatusTag v-for="a in detail.attachments" :key="a" type="info">📎 {{ a }}</AppStatusTag>
            </div>
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">核实处理</span></div>
          <div class="mp-card__body">
            <!-- 同上：这条被别人核实完之后整块表单会消失，提示条必须在外层 -->
            <AppInlineAlert v-if="conflict.active" type="warning" title="记录已更新，本次处理已暂停" description="处理意见仍保留。请返回异常台账，重新打开记录并核对最新事实后再处理。">
              <p v-if="conflict.stale">最新记录读取失败，请返回台账重试。</p>
            </AppInlineAlert>
            <template v-if="detail.status !== 'COMPLETED'">
              <label
                v-for="o in actionOptions"
                :key="o.value"
                class="mp-radio"
                :class="{ 'is-active': action === o.value }"
              >
                <input v-model="action" type="radio" name="exception-action" :value="o.value" :disabled="submitting || conflict.active" style="margin-top: 3px" />
                <div>
                  <div class="mp-radio__title">{{ o.title }}</div>
                  <div class="mp-radio__desc">{{ o.desc }}</div>
                </div>
              </label>
              <label for="exception-comment" class="mp-note" style="display: block; margin: var(--space-3) 0 var(--space-1)">处理意见（必填，≥5 字）</label>
              <textarea id="exception-comment" v-model="comment" :disabled="submitting" class="mp-textarea" placeholder="例如：已电话企业导师核实，确为客户现场装机支持…"></textarea>
              <p v-if="formError" class="mp-form-err">{{ formError }}</p>
              <AppButton variant="primary" :loading="submitting" :disabled="conflict.active" style="width: 100%; margin-top: var(--space-3)" @click="submit">
                提交处理结果
              </AppButton>
              <p class="mp-note" style="text-align: center; margin-top: var(--space-2)">提交后留痕，并实时同步学生端打卡状态</p>
            </template>
            <EmptyState v-else title="该异常已处理完成" description="处理结果已同步学生端，全部动作见下方处理留痕" />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">处理留痕</span></div>
          <div class="mp-card__body">
            <AppAuditTrail :records="trailRecords" empty-text="暂无处理记录" />
          </div>
        </section>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 打卡异常处理详情（/admin/internship/exceptions/:id）。
 * 闭环：查看定位/设备/说明 → 标记合理 / 记为异常 / 转风险 → 留痕 → 学生端同步。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppAuditTrail, AppInlineAlert } from '@/components/common'
import { AppButton } from '@/components/ui'
import ReviewQueueBar from './components/ReviewQueueBar.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import ActionReceipt from './components/ActionReceipt.vue'
import { isConflict, captureConflict, emptyConflict } from '@/modules/internship/composables/conflictGuard'
import { toast } from '@/utils/toast'

export default {
  name: 'AttendanceExceptionDetailView',
  components: { ModulePageShell, AppStatusTag, AppAuditTrail, LoadingState, ErrorState, EmptyState,
    AppButton, ReviewQueueBar, AppInlineAlert, ActionReceipt },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      detail: null,
      action: 'REASONABLE',
      comment: '',
      formError: '',
      submitting: false,
      conflict: emptyConflict(),
      lastReceipt: null,
      actionOptions: [
        { value: 'REASONABLE', title: '标记合理', desc: '确认属正常外勤 / 客户现场，消除本条异常，不计入风险' },
        { value: 'ABNORMAL', title: '记为异常', desc: '核实不通过，计入异常统计，影响打卡率与考核' },
        { value: 'TO_RISK', title: '转风险跟进', desc: '生成风险单并指派责任人，进入风险闭环' }
      ]
    }
  },
  computed: {
    evidence() { return this.detail?.locationEvidence || {} },
    coordinateText() {
      if (!this.evidence.available) return '未取得定位'
      return `${Number(this.evidence.checkinLat).toFixed(6)}, ${Number(this.evidence.checkinLng).toFixed(6)} · ${this.evidence.coordinateSystem || 'GCJ-02'}`
    },
    deviceSignalLabel() {
      const value = this.evidence.deviceSignal || this.detail?.deviceRisk
      return ({ mock: '客户端报告模拟定位', rooted: '客户端报告设备风险', not_available: '当前客户端未提供可信检测' })[value] || '当前客户端未提供可信检测'
    },
    ruleSourceLabel() {
      return this.evidence.ruleSource === 'PLACEMENT_SNAPSHOT' ? '采用落岗时冻结规则' : '历史记录采用当前岗位规则'
    },
    evidenceConclusion() {
      if (!this.evidence.available) return '本次没有定位坐标，只能按无定位记录核实。'
      if (this.evidence.result === 'LOW_ACCURACY') return '定位误差超过批次阈值，系统未直接判断是否在围栏内。'
      if (this.evidence.result === 'LOCATION_UNCERTAIN') return '定位误差范围覆盖围栏边界，系统已交由教师核实。'
      if (this.evidence.result === 'OUT_OF_RANGE') return '定位点在围栏外；请结合精度、学生说明及企业现场情况核实。'
      return '系统已保留本次距离、精度和冻结规则。'
    },
    accuracyStyle() {
      const radius = Math.max(1, Number(this.evidence.radiusM || 1))
      const accuracy = Math.max(4, Math.min(42, Number(this.evidence.accuracyM || 8) / radius * 42))
      return { width: `${accuracy}px`, height: `${accuracy}px` }
    },
    trailRecords() {
      return (this.detail?.trail || []).map((t, i) => ({
        id: i,
        action: t.title,
        reason: t.desc,
        at: t.time,
        result: t.tone
      }))
    }
  },
  watch: {
    // 连续核实队列跳转（同组件复用）时必须重置本页状态并重新加载
    '$route.params.id'(id, oldId) {
      if (!id || id === oldId) return
      this.detail = null
      this.action = 'REASONABLE'
      this.comment = ''
      this.formError = ''
      this.conflict = emptyConflict()
      this.lastReceipt = null
      this.load()
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const id = this.$route.params.id
      const res = await internshipApi.getAttendanceExceptionDetail(id)
      if (id !== this.$route.params.id) return // 队列快速跳转时丢弃过期响应
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    },
    async submit() {
      if (this.submitting || this.loading || this.error || !this.detail || this.detail.status !== 'PENDING_HANDLE' || this.conflict.active) return
      const detailId = String(this.detail.id)
      const routeId = String(this.$route.params.id)
      this.formError = ''
      if (!this.comment || this.comment.trim().length < 5) {
        this.formError = '处理意见必填且不少于 5 个字'
        return
      }
      this.submitting = true
      const res = await internshipApi.handleAttendanceException(this.detail.id, {
        action: this.action, comment: this.comment, expectedVersion: this.detail.version
      })
      this.submitting = false
      if (String(this.$route.params.id) !== routeId || String(this.detail?.id) !== detailId) return
      if (res.code === 0) {
        this.lastReceipt = {
          id: res.data?.id, status: res.data?.status, statusLabel: res.data?.statusLabel,
          version: res.data?.version,
          actionLabel: ({ REASONABLE: '标记合理', ABNORMAL: '记为异常', TO_RISK: '转风险跟进' })[this.action],
          objectLabel: `${this.detail.studentName} · ${this.detail.date}`,
          auditText: '异常更新与处理留痕已同事务提交',
          nextStep: '可继续核对队列中的下一条异常'
        }
        toast.success('处理完成：' + res.data.statusLabel + '，已留痕并同步学生端')
        this.comment = ''
        this.load()
        // 连续核实：有下一条自动跳转，无则提示队列完成
        this.$refs.queueBar && this.$refs.queueBar.advance()
      } else if (isConflict(res)) {
        // 撞车：处理意见原样留着，只拉最新真值（含 version）让老师自己决定要不要重新提交
        this.conflict = { ...emptyConflict(), active: true }
        const captured = await captureConflict({
          res,
          kept: this.comment,
          refresh: async () => { await this.load(); if (this.error) throw new Error(this.error) },
          latest: () => {
            if (!this.detail) throw new Error('最新详情未拉回')
            // 异常详情不下发处理意见字段，只摆状态；不编造页面上没有的真值。
            return [{ label: '最新状态', value: this.detail.statusLabel || this.detail.status || '' }]
          }
        })
        if (String(this.$route.params.id) === routeId) this.conflict = captured
      } else {
        this.formError = res.message
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ae-evidence { display: grid; grid-template-columns: 180px 1fr; gap: var(--space-5); align-items: center; margin-top: var(--space-4); }
.ae-evidence__plot { height: 150px; border-radius: var(--radius-lg); background: linear-gradient(135deg, var(--primary-50), var(--bg-subtle)); display: grid; place-items: center; position: relative; overflow: hidden; }
.ae-evidence__fence { width: 104px; height: 104px; border: 2px solid var(--primary-500); border-radius: 50%; display: grid; place-items: center; }
.ae-evidence__point { width: 8px; height: 8px; border-radius: 50%; background: var(--primary-700); }
.ae-evidence__accuracy { position: absolute; border: 2px solid var(--warning-500); background: color-mix(in srgb, var(--warning-100) 65%, transparent); border-radius: 50%; transform: translate(30px, 4px); min-width: 8px; min-height: 8px; }
.ae-evidence__facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }
.ae-evidence__facts div { padding: var(--space-3); border: 1px solid var(--border-color); border-radius: var(--radius-md); }
.ae-evidence__facts span, .ae-evidence__facts strong { display: block; }
.ae-evidence__facts span { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-bottom: 4px; }
.ae-evidence__facts strong { color: var(--text-primary); font-size: var(--font-size-sm); }
@media (max-width: 900px) { .ae-evidence { grid-template-columns: 1fr; } }
</style>
