<template>
  <picker
    mode="region"
    :value="pickerValue"
    :disabled="disabled"
    @change="onConfirm"
  >
    <view class="mrp" :class="{ 'is-disabled': disabled, 'is-empty': !modelValue }">
      <text class="mrp__text">{{ modelValue || placeholder }}</text>
      <text class="mrp__arrow">›</text>
    </view>
  </picker>
</template>

<script>
/**
 * MobileRegionPicker —— 省 / 市 / 区县三级联动选择（小程序端）。
 *
 * v-model 保持区划文本（如「浙江省 杭州市 西湖区」），与 PC 各端取值口径一致。
 * 小程序直接使用宿主原生 region picker，不再把完整全国区划数据打入主包；
 * 这样既保留原生滚动/无障碍体验，也避免地区数据挤占微信 2 MiB 主包预算。
 *
 * 历史自由文本仍原样展示。只有能可靠拆成省/市/区县三段时才回填给原生 picker，
 * 无法反解析的旧值不会被清空，用户重新选择后再写入规范化文本。
 */
export default {
  name: 'MobileRegionPicker',
  props: {
    modelValue: { type: String, default: '' },
    placeholder: { type: String, default: '请选择省 / 市 / 区县' },
    disabled: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    pickerValue() {
      const parts = String(this.modelValue || '')
        .trim()
        .split(/\s+/)
        .filter(Boolean)
      return parts.length >= 2 ? parts.slice(0, 3) : []
    }
  },
  methods: {
    onConfirm(e) {
      const names = Array.isArray(e && e.detail && e.detail.value) ? e.detail.value : []
      const codes = Array.isArray(e && e.detail && e.detail.code) ? e.detail.code : []
      const normalizedNames = names.filter((name, index) => name && name !== names[index - 1])
      const label = normalizedNames.join(' ')
      if (!label) return

      this.$emit('update:modelValue', label)
      this.$emit('change', {
        label,
        provinceCode: codes[0] || '',
        provinceName: names[0] || '',
        cityCode: codes[1] || '',
        cityName: names[1] || '',
        countyCode: codes[2] || '',
        countyName: names[2] || ''
      })
    }
  }
}
</script>

<style scoped>
.mrp {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  min-height: 80rpx;
  padding: 0 24rpx;
  border: 2rpx solid #e5e9f0;
  border-radius: 12rpx;
  background: #fff;
  box-sizing: border-box;
}
.mrp.is-disabled {
  background: #f6f8fb;
  opacity: 0.7;
}
.mrp__text {
  flex: 1;
  font-size: 28rpx;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mrp.is-empty .mrp__text {
  color: #9aa5b5;
}
.mrp__arrow {
  flex: none;
  font-size: 34rpx;
  color: #c4ccd8;
  line-height: 1;
}
</style>
