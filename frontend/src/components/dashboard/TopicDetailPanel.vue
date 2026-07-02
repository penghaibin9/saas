<template>
  <div class="topic-detail-panel">
    <div class="dash-topic-tabs" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="dash-topic-tab"
        :class="{ 'is-active': activeTab === tab.key }"
        role="tab"
        :aria-selected="activeTab === tab.key"
        @click="$emit('update:activeTab', tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>
    <div v-show="activeTab === 'practice'" class="dash-metric-grid">
      <MetricCard
        v-for="m in practiceMetrics"
        :key="m.id"
        v-bind="m"
        :accent="accent(m)"
        @drill="$emit('drill', $event)"
      />
    </div>
    <div v-show="activeTab === 'graduation'" class="dash-metric-grid dash-metric-grid--gd">
      <MetricCard
        v-for="m in graduationMetrics"
        :key="m.id"
        v-bind="m"
        :accent="accent(m)"
        @drill="$emit('drill', $event)"
      />
    </div>
    <div v-show="activeTab === 'internship'" class="dash-metric-grid">
      <MetricCard
        v-for="m in internshipMetrics"
        :key="m.id"
        v-bind="m"
        :accent="accent(m)"
        @drill="$emit('drill', $event)"
      />
    </div>
  </div>
</template>

<script>
import MetricCard from './MetricCard.vue'
import { metricAccent } from '@/modules/dashboard/adapter/dashboard.adapter.js'

const TABS = [
  { key: 'internship', label: '岗位实习' },
  { key: 'practice', label: '实践教学' },
  { key: 'graduation', label: '毕业设计' }
]

export default {
  name: 'TopicDetailPanel',
  components: { MetricCard },
  props: {
    activeTab: { type: String, default: 'internship' },
    practiceMetrics: { type: Array, default: () => [] },
    graduationMetrics: { type: Array, default: () => [] },
    internshipMetrics: { type: Array, default: () => [] }
  },
  emits: ['update:activeTab', 'drill'],
  data() {
    return { tabs: TABS }
  },
  methods: {
    accent: metricAccent
  }
}
</script>
