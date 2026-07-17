<template>
  <div class="wiz">
    <div v-for="(s, i) in steps" :key="i" class="wiz__seg">
      <div class="wiz__node">
        <span class="wiz__c" :class="cls(i + 1)">
          <svg v-if="current > i + 1" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 5 5L20 6" /></svg>
          <template v-else>{{ i + 1 }}</template>
        </span>
        <span class="wiz__t" :class="{ on: current >= i + 1 }">{{ s }}</span>
      </div>
      <span v-if="i < steps.length - 1" class="wiz__line" :style="{ background: current > i + 1 ? 'var(--pri)' : '#E5E8EE' }" />
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ steps: { type: Array, default: () => [] }, current: { type: Number, default: 1 } })
function cls(n) { return props.current > n ? 'done' : props.current === n ? 'cur' : 'todo' }
</script>

<style scoped>
.wiz { display: flex; align-items: center; }
.wiz__seg { display: flex; align-items: center; flex: 1; }
.wiz__node { display: flex; align-items: center; gap: 8px; flex: none; }
.wiz__c { width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; background: #fff; border: 2px solid #DDE1E8; color: #A9B0BD; }
.wiz__c.cur { border-color: var(--pri); color: var(--pri); }
.wiz__c.done { background: var(--pri); border-color: var(--pri); color: #fff; }
.wiz__t { font-size: 13px; color: #A9B0BD; white-space: nowrap; }
.wiz__t.on { color: var(--t1); font-weight: 600; }
.wiz__line { flex: 1; height: 2px; margin: 0 10px; }
</style>
