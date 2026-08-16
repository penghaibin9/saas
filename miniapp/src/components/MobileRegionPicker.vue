<template>
  <picker
    mode="multiSelector"
    :range="range"
    :value="indexes"
    :disabled="disabled"
    @columnchange="onColumnChange"
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
 * v-model 为区划文本（如「浙江省 杭州市 西湖区」），与 PC 各端保持同一取值口径：
 * 后端相关字段都是自由文本列，本组件只是把「手打」换成「选择」，不改数据库结构；
 * 历史自由文本会尽力反解析定位，解析不到也原样保留展示，不清空用户既有数据。
 *
 * 用 uni-app 原生 multiSelector 而非自绘浮层：原生选择器在各家小程序宿主里
 * 滚动手感、无障碍与键盘避让都是宿主保证的，自绘容易在真机上出问题。
 */
import {
  CHINA_PROVINCES,
  citiesForProvince,
  countiesForCity,
  labelFromIndex,
  rangeFromIndex,
  resolveRegionIndex
} from '@/utils/chinaRegions'

export default {
  name: 'MobileRegionPicker',
  props: {
    modelValue: { type: String, default: '' },
    placeholder: { type: String, default: '请选择省 / 市 / 区县' },
    disabled: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change'],
  data() {
    const indexes = resolveRegionIndex(this.modelValue)
    return { indexes, range: rangeFromIndex(indexes) }
  },
  watch: {
    modelValue(value) {
      // 只在外部值与当前选中不一致时重算，避免用户滚动过程中被回填打断
      if (value === labelFromIndex(this.indexes)) return
      this.indexes = resolveRegionIndex(value)
      this.range = rangeFromIndex(this.indexes)
    }
  },
  methods: {
    /** 滚动某一列时联动刷新右侧列，并把右侧下标归零 */
    onColumnChange(e) {
      const column = e.detail.column
      const value = e.detail.value
      const next = [...this.indexes]
      next[column] = value
      if (column === 0) {
        next[1] = 0
        next[2] = 0
      } else if (column === 1) {
        next[2] = 0
      }
      this.indexes = next
      this.range = rangeFromIndex(next)
    },
    onConfirm(e) {
      const next = e.detail.value
      this.indexes = next
      this.range = rangeFromIndex(next)
      const label = labelFromIndex(next)
      this.$emit('update:modelValue', label)
      this.$emit('change', { label, ...this.codesOf(next) })
    },
    /** 供需要分列存省/市的调用方取区划码与名称 */
    codesOf(indexes) {
      const [pi = 0, ci = 0, di = 0] = indexes || []
      const province = CHINA_PROVINCES[pi]
      const cities = province ? citiesForProvince(province.code) : []
      const city = cities[ci]
      const counties = city ? countiesForCity(city.code) : []
      const county = counties[di]
      return {
        provinceCode: province ? province.code : '',
        provinceName: province ? province.name : '',
        cityCode: city ? city.code : '',
        cityName: city ? city.name : '',
        countyCode: county ? county.code : '',
        countyName: county ? county.name : ''
      }
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
