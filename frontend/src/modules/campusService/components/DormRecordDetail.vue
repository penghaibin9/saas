<template>
  <div class="drd">
    <div class="mp-card">
      <div class="mp-card__head"><div class="mp-card__title">学生摘要</div></div>
      <div class="mp-card__body">
        <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ record.name }}（{{ record.className }}）</span></div>
        <div class="mp-kv"><span class="mp-kv__k">近30天异常</span><span class="mp-kv__v">{{ record.exceptionCount || 0 }} 次</span></div>
      </div>
    </div>

    <div class="mp-card">
      <div class="mp-card__head"><div class="mp-card__title">当前住宿信息</div></div>
      <div class="mp-card__body">
        <div class="mp-kv"><span class="mp-kv__k">楼栋</span><span class="mp-kv__v">{{ record.building || record.buildingId || '未设置' }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">房间 / 床位</span><span class="mp-kv__v">{{ record.room }}-{{ record.bed }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">入住时间</span><span class="mp-kv__v">{{ record.checkinDate || '未设置' }}</span></div>
        <div class="mp-kv">
          <span class="mp-kv__k">住宿状态</span>
          <span class="mp-kv__v"><StatusTag :type="record.status === 'IN' ? 'success' : 'default'" :label="statusLabel(record.status)" dot /></span>
        </div>
      </div>
    </div>

    <div class="mp-card">
      <div class="mp-card__head"><div class="mp-card__title">调宿 / 退宿历史</div></div>
      <div class="mp-card__body">
        <p class="mp-note">暂无相关数据（调宿 / 退宿流程随「宿舍与公寓」模块施工接入，本页不展示推测数据）。</p>
      </div>
    </div>

    <div class="mp-card">
      <div class="mp-card__head"><div class="mp-card__title">住宿异常记录</div></div>
      <div class="mp-card__body">
        <LoadingState v-if="exceptionsLoading" />
        <template v-else-if="exceptions.length">
          <table class="mp-audit">
            <thead><tr><th>编号</th><th>类型</th><th>发生时间</th><th>情况说明</th><th>状态</th></tr></thead>
            <tbody>
              <tr v-for="e in exceptions" :key="e.id">
                <td>{{ e.code }}</td>
                <td>{{ e.typeLabel }}</td>
                <td>{{ e.happenTime }}</td>
                <td>{{ e.detail }}</td>
                <td>{{ exStatusLabel(e.status) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <p v-else class="mp-note">暂无异常记录</p>
      </div>
    </div>

    <div class="drd__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script>
/**
 * DormRecordDetail — 单条住宿记录业务详情区块（学生摘要 / 住宿信息 / 调宿退宿历史 / 异常记录）。
 * 被 DormitoryView 双栏右栏与 DormRecordDetailView 独立深链接页共同复用，避免两套逻辑。
 * 无接口的数据（调宿/退宿历史）明确显示「暂无相关数据」，不虚构。
 */
import { StatusTag, LoadingState } from '@/components/business'

export default {
  name: 'DormRecordDetail',
  components: { StatusTag, LoadingState },
  props: {
    record: { type: Object, required: true },
    exceptions: { type: Array, default: () => [] },
    exceptionsLoading: { type: Boolean, default: false },
    ctx: { type: Object, required: true }
  },
  methods: {
    statusLabel(v) {
      return (this.ctx.statusOptions.dormStatus.find((o) => o.value === v) || {}).label || v
    },
    exStatusLabel(v) {
      return (this.ctx.statusOptions.dormExceptionStatus.find((o) => o.value === v) || {}).label || v
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.drd .mp-card + .mp-card {
  margin-top: var(--space-3);
}
.drd__actions {
  margin-top: var(--space-3);
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
</style>
