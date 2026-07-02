<template>
  <AppCard class="stu-panel">
    <AppSectionHeader title="监护人 / 联系人" compact>
      <template #extra>
        <span class="stu-guardian__count">{{ guardians.length }} 位</span>
      </template>
    </AppSectionHeader>
    <div v-if="guardians.length" class="stu-guardian__list">
      <div v-for="g in maskedList" :key="g.guardianId" class="stu-guardian__item">
        <div class="stu-guardian__head">
          <span class="stu-guardian__name">{{ g.guardianName }}</span>
          <span class="stu-guardian__rel">{{ g.relationship }}</span>
          <AppBadge v-if="g.isPrimaryGuardian" type="info">主要监护人</AppBadge>
          <AppBadge v-if="g.isEmergencyContact" type="warning">紧急联系人</AppBadge>
        </div>
        <dl class="stu-kv">
          <dt>联系电话</dt><dd>{{ g.guardianPhone || '未登记' }}</dd>
          <dt>证件号码</dt><dd>{{ g.guardianIdCard || '未登记' }}</dd>
          <dt>住址</dt><dd>{{ g.guardianAddress || '—' }}</dd>
        </dl>
      </div>
    </div>
    <div v-else class="stu-guardian__empty">暂无监护人/联系人信息</div>
  </AppCard>
</template>

<script>
/** StudentGuardianPanel — 监护人展示（电话/证件/住址全部脱敏） */
import { AppCard, AppBadge, AppSectionHeader } from '@/components/ui'
import { maskGuardianForDisplay } from '../helpers/student-security.helper'

export default {
  name: 'StudentGuardianPanel',
  components: { AppCard, AppBadge, AppSectionHeader },
  props: { guardians: { type: Array, default: () => [] } },
  computed: {
    maskedList() {
      return this.guardians.map(maskGuardianForDisplay)
    }
  }
}
</script>

<style scoped>
@import './student-panel.css';
.stu-guardian__count { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.stu-guardian__list { display: flex; flex-direction: column; gap: var(--space-3); }
.stu-guardian__item { border: 1px solid var(--border-light); border-radius: var(--radius-base); padding: var(--space-3); }
.stu-guardian__head { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2); flex-wrap: wrap; }
.stu-guardian__name { font-weight: var(--font-weight-medium); color: var(--text-primary); }
.stu-guardian__rel { font-size: var(--font-size-sm); color: var(--text-secondary); }
.stu-guardian__empty { color: var(--text-tertiary); font-size: var(--font-size-sm); }
</style>
