<template>
  <div class="sp-dropzone" :class="{ 'is-disabled': disabled }">
    <template v-if="disabled">
      <span class="sp-dropzone__hint">「大文件上传」功能未开通，请联系学校管理员</span>
    </template>
    <template v-else>
      <span class="sp-dropzone__icon">⬆️</span>
      <span class="sp-dropzone__hint">拖拽或点击选择文件（学生 PC 门户支持大文件上传）</span>
      <input type="file" class="sp-dropzone__input" @change="onPick" />
    </template>
  </div>
</template>

<script setup>
const props = defineProps({ disabled: { type: Boolean, default: false } })
const emit = defineEmits(['pick'])
function onPick(e) {
  if (props.disabled) return
  const f = e.target.files && e.target.files[0]
  if (f) emit('pick', f)
}
</script>
