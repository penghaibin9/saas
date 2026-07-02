<template>
  <div class="app-risk-student-card" :class="`is-${normalizedRisk}`">
    <div class="app-risk-student-card__header">
      <div class="app-risk-student-card__avatar">{{ avatarText }}</div>
      <div class="app-risk-student-card__identity">
        <div class="app-risk-student-card__name-row">
          <span class="app-risk-student-card__name">{{ name }}</span>
          <span class="app-risk-student-card__no">{{ studentNo }}</span>
          <AppRiskTag :level="riskLevel" />
        </div>
        <div class="app-risk-student-card__org">{{ orgText }}</div>
        <div class="app-risk-student-card__stage">当前环节：{{ stage }}</div>
      </div>
    </div>

    <div class="app-risk-student-card__risk-block">
      <span class="app-risk-student-card__risk-icon" aria-hidden="true">⚠</span>
      <div>
        <div class="app-risk-student-card__risk-label">风险原因</div>
        <div class="app-risk-student-card__risk-text">{{ riskReason }}</div>
      </div>
    </div>

    <div class="app-risk-student-card__info-row">
      <span
        >责任老师 <strong>{{ responsibleTeacher }}</strong></span
      >
      <span
        >处理时限 <strong>{{ deadline }}</strong></span
      >
    </div>

    <div class="app-risk-student-card__suggestions">
      <div class="app-risk-student-card__suggestions-title">系统建议</div>
      <ul>
        <li v-for="(s, i) in suggestions" :key="i">{{ s }}</li>
      </ul>
    </div>

    <div class="app-risk-student-card__actions">
      <button type="button" class="app-risk-student-card__btn" @click="$emit('contact')">
        联系学生
      </button>
      <button type="button" class="app-risk-student-card__btn" @click="$emit('remind')">
        发起提醒
      </button>
      <button type="button" class="app-risk-student-card__btn" @click="$emit('follow')">
        填写跟进
      </button>
      <button
        type="button"
        class="app-risk-student-card__btn app-risk-student-card__btn--primary"
        @click="$emit('resolve')"
      >
        标记已处理
      </button>
    </div>
  </div>
</template>

<script>
import AppRiskTag from '../common/AppRiskTag.vue'

export default {
  name: 'AppRiskStudentCard',
  components: { AppRiskTag },
  props: {
    name: { type: String, required: true },
    studentNo: { type: String, default: '' },
    college: { type: String, default: '' },
    major: { type: String, default: '' },
    className: { type: String, default: '' },
    stage: { type: String, default: '' },
    riskLevel: { type: String, required: true },
    riskReason: { type: String, default: '' },
    responsibleTeacher: { type: String, default: '' },
    deadline: { type: String, default: '' },
    suggestions: { type: Array, default: () => [] }
  },
  emits: ['contact', 'remind', 'follow', 'resolve'],
  computed: {
    normalizedRisk() {
      return String(this.riskLevel).toUpperCase()
    },
    avatarText() {
      return this.name ? this.name.slice(0, 1) : '生'
    },
    orgText() {
      return [this.college, this.major, this.className].filter(Boolean).join(' · ')
    }
  }
}
</script>

<style scoped>
.app-risk-student-card {
  background: var(--bg-card);
  border: 1px solid var(--danger-100);
  border-radius: var(--radius-card-sm);
  padding: var(--space-4);
  box-shadow: var(--shadow-card);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}
.app-risk-student-card.is-HIGH,
.app-risk-student-card.is-CRITICAL {
  background: linear-gradient(180deg, var(--danger-50) 0%, var(--bg-card) 40%);
}
.app-risk-student-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-card-hover);
}
.app-risk-student-card__header {
  display: flex;
  gap: var(--space-3);
}
.app-risk-student-card__avatar {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: var(--radius-full);
  background: var(--danger-100);
  color: var(--danger-600);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-bold);
  display: grid;
  place-items: center;
}
.app-risk-student-card__identity {
  flex: 1;
  min-width: 0;
}
.app-risk-student-card__name-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.app-risk-student-card__name {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
}
.app-risk-student-card__no {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.app-risk-student-card__org {
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.app-risk-student-card__stage {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--primary-600);
  font-weight: var(--font-weight-medium);
}
.app-risk-student-card__risk-block {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--danger-50);
  border: 1px solid var(--danger-100);
}
.app-risk-student-card__risk-icon {
  color: var(--danger-500);
  font-size: 16px;
  line-height: 1.4;
}
.app-risk-student-card__risk-label {
  font-size: var(--font-size-xs);
  color: var(--danger-600);
  font-weight: var(--font-weight-semibold);
  margin-bottom: 2px;
}
.app-risk-student-card__risk-text {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  line-height: 1.5;
}
.app-risk-student-card__info-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  margin-top: var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.app-risk-student-card__info-row strong {
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);
}
.app-risk-student-card__suggestions {
  margin-top: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
}
.app-risk-student-card__suggestions-title {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--warning-700);
  margin-bottom: var(--space-1);
}
.app-risk-student-card__suggestions ul {
  margin: 0;
  padding-left: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.7;
}
.app-risk-student-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-4);
}
.app-risk-student-card__btn {
  height: 36px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all 0.2s ease;
}
.app-risk-student-card__btn:hover {
  border-color: var(--primary-100);
  color: var(--primary-600);
  background: var(--primary-50);
}
.app-risk-student-card__btn--primary {
  border-color: var(--primary-600);
  background: var(--primary-600);
  color: var(--text-inverse);
}
.app-risk-student-card__btn--primary:hover {
  background: var(--primary-700);
  border-color: var(--primary-700);
  color: var(--text-inverse);
}
</style>
