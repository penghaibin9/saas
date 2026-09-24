<template>
  <!-- #ifdef H5 -->
  <view class="mrp mrp--web" :class="{ 'is-disabled': disabled }">
    <select aria-label="省份" :disabled="disabled" :value="provinceCode" @change="chooseProvince($event.target.value)"><option value="">请选择省份</option><option v-for="item in provinces" :key="item.code" :value="item.code">{{ item.name }}</option></select>
    <select aria-label="城市" :disabled="disabled || !provinceCode" :value="cityCode" @change="chooseCity($event.target.value)"><option value="">请选择城市</option><option v-for="item in cities" :key="item.code" :value="item.code">{{ item.name }}</option></select>
    <select aria-label="区县" :disabled="disabled || !cityCode" :value="countyCode" @change="chooseCounty($event.target.value)"><option value="">请选择区县</option><option v-for="item in counties" :key="item.code" :value="item.code">{{ item.name }}</option></select>
    <text v-if="modelValue" class="mrp__saved">{{ modelValue }}</text>
  </view>
  <!-- #endif -->
  <!-- #ifndef H5 -->
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
  <!-- #endif -->
</template>

<script>
// #ifdef H5
import { areaList } from '@vant/area-data'
const entries = source => Object.entries(source).map(([code, name]) => ({ code, name }))
// #endif
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
  // #ifdef H5
  data() { return { provinceCode: '', cityCode: '', countyCode: '', pendingSelectionClear: false } },
  watch: { modelValue: { immediate: true, handler(value) {
    if (!value) {
      if (this.pendingSelectionClear) { this.pendingSelectionClear = false; return }
      this.provinceCode = ''; this.cityCode = ''; this.countyCode = ''
      return
    }
    this.pendingSelectionClear = false
    const names = String(value).trim().split(/\s+/)
    this.provinceCode = this.provinces.find(item => item.name === names[0])?.code || ''
    this.cityCode = this.cities.find(item => names.includes(item.name))?.code || ''
    this.countyCode = this.counties.find(item => names.includes(item.name))?.code || ''
  } } },
  // #endif
  computed: {
    // #ifdef H5
    provinces() { return entries(areaList.province_list) },
    cities() { return this.provinceCode ? entries(areaList.city_list).filter(item => item.code.startsWith(this.provinceCode.slice(0, 2))) : [] },
    counties() { return this.cityCode ? entries(areaList.county_list).filter(item => item.code.startsWith(this.cityCode.slice(0, 4))) : [] },
    // #endif
    pickerValue() {
      const parts = String(this.modelValue || '')
        .trim()
        .split(/\s+/)
        .filter(Boolean)
      return parts.length >= 2 ? parts.slice(0, 3) : []
    }
  },
  methods: {
    // #ifdef H5
    clearModelForSelection() {
      // Internal cascade edits clear the submitted value, not the new selection.
      // The marker lasts through Vue's prop update, never through a later reset.
      this.pendingSelectionClear = true
      this.$emit('update:modelValue', '')
      this.$nextTick?.(() => { this.pendingSelectionClear = false })
    },
    chooseProvince(code) { if (this.disabled) return; this.provinceCode = code; this.cityCode = ''; this.countyCode = ''; this.clearModelForSelection() },
    chooseCity(code) { if (this.disabled) return; this.cityCode = code; this.countyCode = ''; this.clearModelForSelection() },
    chooseCounty(code) {
      if (this.disabled) return
      this.countyCode = code
      if (!code) { this.clearModelForSelection(); return }
      const codes = [this.provinceCode, this.cityCode, code]
      const names = [areaList.province_list[codes[0]], areaList.city_list[codes[1]], areaList.county_list[codes[2]]]
      this.onConfirm({ detail: { value: names, code: codes } })
    },
    // #endif
    onConfirm(e) {
      if (this.disabled) return
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
.mrp--web { flex-wrap: wrap; padding: 8px; }
.mrp--web select { flex: 1 1 90px; min-width: 0; max-width: 100%; padding: 8px 2px; border: 0; background: transparent; color: #1f2937; font-size: 14px; }
.mrp__saved { width: 100%; font-size: 12px; color: #64748b; }
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
