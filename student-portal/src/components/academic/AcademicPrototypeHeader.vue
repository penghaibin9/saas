<template>
  <header ref="header" class="page-head">
    <div class="crumb">教务学业 / {{ academicPrototypeCopy[title]?.group || group }}{{ object ? ' / 对象办理' : '' }}</div>
    <div class="titleline">
      <div><h1>{{ title }}</h1><p>{{ academicPrototypeCopy[title]?.description || description }}</p></div>
      <div class="row"><span v-if="term" class="tag">{{ term }}</span><button class="btn small" type="button" :disabled="loading" @click="$emit('refresh')"><AcademicPrototypeIcon name="arrows-rotate" />{{ loading ? '读取中' : '刷新' }}</button></div>
    </div>
  </header>
</template>
<script setup>
import { ref, watch } from 'vue'
import AcademicPrototypeIcon from './AcademicPrototypeIcon.vue'
import { academicPrototypeCopy } from './studentAcademicPrototypeCopy'
const props = defineProps({ title: String, description: String, group: String, term: String, object: Boolean, loading: Boolean })
const header = ref(null)
watch(() => props.title, () => header.value?.scrollIntoView({ block: 'start', inline: 'nearest' }), { flush: 'post' })
defineEmits(['refresh'])
</script>
