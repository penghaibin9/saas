<template>
  <div class="flow">
    <div v-for="(s, i) in steps" :key="i" class="flow__seg">
      <div class="flow__node">
        <span class="flow__circle" :style="circleStyle(s)">
          <svg v-if="s.state === 'done'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 5 5L20 6" /></svg>
          <template v-else>{{ i + 1 }}</template>
        </span>
        <span class="flow__name" :style="{ color: s.state === 'todo' ? '#A9B0BD' : 'var(--t1)', fontWeight: s.state === 'current' ? 600 : 500 }">{{ s.name }}</span>
        <span v-if="s.date" class="flow__date">{{ s.date }}</span>
      </div>
      <span v-if="i < steps.length - 1" class="flow__line" :style="{ background: s.state === 'done' ? 'var(--pri)' : '#E5E8EE' }" />
    </div>
  </div>
</template>

<script setup>
defineProps({ steps: { type: Array, default: () => [] } })
function circleStyle(s) {
  if (s.state === 'done') return { background: 'var(--pri)', border: '2px solid var(--pri)', color: '#fff' }
  if (s.state === 'current') return { background: '#fff', border: '2px solid var(--pri)', color: 'var(--pri)' }
  return { background: '#fff', border: '2px solid #DDE1E8', color: '#A9B0BD' }
}
</script>

<style scoped>
.flow { display: flex; align-items: flex-start; }
.flow__seg { display: flex; align-items: center; flex: 1; min-width: 0; }
.flow__node { display: flex; flex-direction: column; align-items: center; gap: 7px; flex: none; }
.flow__circle { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; }
.flow__name { font-size: 12px; white-space: nowrap; }
.flow__date { font-size: 10.5px; color: var(--t4); }
.flow__line { flex: 1; height: 2px; margin: 0 6px; margin-bottom: 22px; border-radius: 2px; }
</style>
