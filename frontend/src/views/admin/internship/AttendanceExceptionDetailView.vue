<template>
  <ModulePageShell
    :title="detail ? detail.studentName + ' · 打卡异常处理' : '打卡异常处理'"
    :subtitle="detail ? detail.date + ' · ' + detail.typeLabel : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">异常打卡信息</span>
            <StatusTag :status="detail.status" :label="detail.status === 'COMPLETED' ? '已处理' : '待核实'" dot />
          </div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ detail.studentName }} · {{ detail.className }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">企业 / 岗位</span><span class="mp-kv__v">{{ detail.enterpriseName }} · {{ detail.positionName }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">打卡时间</span><span class="mp-kv__v">{{ detail.date }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">距打卡点</span><span class="mp-kv__v" style="color: var(--danger-600)">{{ detail.distance }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">定位精度</span><span class="mp-kv__v">{{ detail.accuracy }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">打卡地址</span><span class="mp-kv__v">{{ detail.address }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">设备</span><span class="mp-kv__v">{{ detail.device }}（{{ detail.deviceId }}）</span></div>
            <div class="mp-kv"><span class="mp-kv__k">模拟定位检测</span><span class="mp-kv__v" :style="detail.mockDetect.includes('命中') ? 'color: var(--danger-600)' : 'color: var(--success-600)'">{{ detail.mockDetect }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">系统风险评估</span><span class="mp-kv__v">{{ detail.systemRisk }}</span></div>
            <p class="mp-note" style="margin-top: var(--space-3)">定位仅在学生主动打卡瞬时采集（隐私冻结规则）。</p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">学生说明（来自小程序 P11）</span>
            <span v-if="detail.noteTime" class="mp-note">提交于 {{ detail.noteTime }}</span>
          </div>
          <div class="mp-card__body">
            <p style="margin: 0; font-size: var(--font-size-sm); color: var(--text-secondary)">{{ detail.studentNote }}</p>
            <div v-if="detail.attachments.length" style="margin-top: var(--space-3); display: flex; gap: var(--space-2)">
              <StatusTag v-for="a in detail.attachments" :key="a" type="info" :label="'📎 ' + a" />
            </div>
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">核实处理</span></div>
          <div class="mp-card__body">
            <template v-if="detail.status !== 'COMPLETED'">
              <div
                v-for="o in actionOptions"
                :key="o.value"
                class="mp-radio"
                :class="{ 'is-active': action === o.value }"
                @click="action = o.value"
              >
                <input type="radio" :checked="action === o.value" style="margin-top: 3px" />
                <div>
                  <div class="mp-radio__title">{{ o.title }}</div>
                  <div class="mp-radio__desc">{{ o.desc }}</div>
                </div>
              </div>
              <label class="mp-note" style="display: block; margin: var(--space-3) 0 var(--space-1)">处理意见（必填，≥5 字）</label>
              <textarea v-model="comment" class="mp-textarea" placeholder="例如：已电话企业导师核实，确为客户现场装机支持…"></textarea>
              <p v-if="formError" class="mp-form-err">{{ formError }}</p>
              <AppButton variant="primary" :loading="submitting" style="width: 100%; margin-top: var(--space-3)" @click="submit">
                提交处理结果
              </AppButton>
              <p class="mp-note" style="text-align: center; margin-top: var(--space-2)">提交后留痕，并实时同步学生小程序 P11 打卡状态</p>
            </template>
            <EmptyState v-else title="该异常已处理完成" description="处理结果已同步学生端，全部动作见下方处理留痕" />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">处理留痕</span></div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="(t, i) in detail.trail" :key="i" class="mp-timeline__item" :class="'is-' + (t.tone === 'processing' ? 'warning' : t.tone)">
                <div class="mp-timeline__title">{{ t.title }}</div>
                <div v-if="t.desc" class="mp-timeline__desc">{{ t.desc }}</div>
                <div class="mp-timeline__time">{{ t.time }}</div>
              </li>
            </ul>
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
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AttendanceExceptionDetailView',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppButton },
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
      actionOptions: [
        { value: 'REASONABLE', title: '标记合理', desc: '确认属正常外勤 / 客户现场，消除本条异常，不计入风险' },
        { value: 'ABNORMAL', title: '记为异常', desc: '核实不通过，计入异常统计，影响打卡率与考核' },
        { value: 'TO_RISK', title: '转风险跟进', desc: '生成风险单并指派责任人，进入风险闭环' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await internshipApi.getAttendanceExceptionDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    },
    async submit() {
      this.formError = ''
      if (!this.comment || this.comment.trim().length < 5) {
        this.formError = '处理意见必填且不少于 5 个字'
        return
      }
      this.submitting = true
      const res = await internshipApi.handleAttendanceException(this.detail.id, { action: this.action, comment: this.comment })
      this.submitting = false
      if (res.code === 0) {
        toast.success('处理完成：' + res.data.statusLabel + '，已留痕并同步学生端')
        this.comment = ''
        this.load()
      } else {
        this.formError = res.message
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
