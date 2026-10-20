<template><div class="steps" aria-label="办理步骤"><div v-for="(label, index) in labels" :key="label" class="step" :class="{ current: index === active, done: index < active }"><b>{{ index < active ? '✓' : index + 1 }}</b><span>{{ label }}</span></div></div></template>
<script setup>
defineProps({ labels: { type: Array, default: () => ['选择本人对象', '填写申请', '学校受理', '查看结果'] }, active: { type: Number, default: 1 } })
</script>
