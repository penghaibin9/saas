<template>
  <div class="app-region-picker" :class="{ 'is-disabled': disabled }">
    <div class="app-region-picker__cols">
      <AppSelect
        class="app-region-picker__col"
        :model-value="provinceCode"
        :options="provinceOptions"
        placeholder="省 / 直辖市"
        :disabled="disabled"
        :size="size"
        @update:model-value="onProvince"
      />
      <AppSelect
        class="app-region-picker__col"
        :model-value="cityCode"
        :options="cityOptions"
        :placeholder="provinceCode ? '市' : '请先选省'"
        :disabled="disabled || !provinceCode"
        :size="size"
        @update:model-value="onCity"
      />
      <AppSelect
        v-if="level === 'county'"
        class="app-region-picker__col"
        :model-value="countyCode"
        :options="countyOptions"
        :placeholder="cityCode ? '区 / 县（可选）' : '请先选市'"
        :disabled="disabled || !cityCode"
        :size="size"
        @update:model-value="onCounty"
      />
    </div>

    <div class="app-region-picker__foot">
      <span v-if="modelValue" class="app-region-picker__current">
        当前：{{ modelValue }}
        <button v-if="!disabled" type="button" class="app-region-picker__clear" @click="clear">清除</button>
      </span>
      <span v-else class="app-region-picker__hint">{{ placeholder }}</span>
      <span v-if="unresolved" class="app-region-picker__warn">
        已保存的「{{ modelValue }}」不在标准区划表中，重新选择后将被替换
      </span>
    </div>
  </div>
</template>

<script>
/**
 * AppChinaRegionPicker — 中国省 / 市 / 区县级联选择。
 *
 * 为什么 v-model 是「文本」而不是区划码：
 *   后端相关字段（岗位 work_location、企业 region、租户省市、生源地等）都是自由文本列，
 *   本组件只把「手打」换成「选择」，不改数据库结构，也不会让历史数据失效。
 *   历史自由文本在打开时会尽力反解析定位（resolveChinaRegion），解析不到就原样保留并提示，
 *   绝不因为解析失败就清空用户既有数据。
 *
 * Props:
 *  - modelValue: 选中地区文本，如「浙江省 杭州市 西湖区」（v-model）
 *  - level: 'county'(默认，省市区三级) | 'city'(仅到市)
 *  - disabled / size / placeholder
 * Emits: update:modelValue(labelString) / change({ provinceCode, cityCode, countyCode, label })
 */
import AppSelect from '../form/AppSelect.vue'
import {
  CHINA_PROVINCES,
  CHINA_CITIES,
  CHINA_COUNTIES,
  citiesForProvince,
  countiesForCity,
  regionLabel,
  resolveChinaRegion
} from '@/utils/chinaRegions'

export default {
  name: 'AppChinaRegionPicker',
  components: { AppSelect },
  props: {
    modelValue: { type: String, default: '' },
    level: {
      type: String,
      default: 'county',
      validator: (v) => ['county', 'city'].includes(v)
    },
    disabled: { type: Boolean, default: false },
    size: { type: String, default: 'normal' },
    placeholder: { type: String, default: '请选择省 / 市 / 区县' }
  },
  emits: ['update:modelValue', 'change'],
  data() {
    return { provinceCode: '', cityCode: '', countyCode: '', unresolved: false }
  },
  computed: {
    provinceOptions() {
      return CHINA_PROVINCES.map((p) => ({ value: p.code, label: p.name }))
    },
    cityOptions() {
      return citiesForProvince(this.provinceCode).map((c) => ({ value: c.code, label: c.name }))
    },
    countyOptions() {
      return countiesForCity(this.cityCode).map((c) => ({ value: c.code, label: c.name }))
    }
  },
  watch: {
    modelValue: { immediate: true, handler: 'syncFromValue' }
  },
  methods: {
    syncFromValue(value) {
      const text = String(value || '').trim()
      if (!text) {
        this.provinceCode = ''
        this.cityCode = ''
        this.countyCode = ''
        this.unresolved = false
        return
      }
      // 已由本组件选出的值不必重复反解析，避免把「北京市 北京市」这类去重后的展示文本解歪
      if (text === this.currentLabel()) return
      const resolved = resolveChinaRegion(text)
      this.provinceCode = resolved?.provinceCode || ''
      this.cityCode = resolved?.cityCode || ''
      this.countyCode = resolved?.countyCode || ''
      this.unresolved = !resolved
    },
    currentLabel() {
      return regionLabel(this.provinceCode, this.cityCode, this.countyCode)
    },
    /** 名称查表：供「省、市分列存两个字段」的调用方（如平台租户档案）拆分回填 */
    nameOf(list, code) {
      if (!code) return ''
      const hit = list.find((item) => item.code === code)
      return hit ? hit.name : ''
    },
    commit() {
      const label = this.currentLabel()
      this.unresolved = false
      this.$emit('update:modelValue', label)
      this.$emit('change', {
        provinceCode: this.provinceCode,
        cityCode: this.cityCode,
        countyCode: this.countyCode,
        provinceName: this.nameOf(CHINA_PROVINCES, this.provinceCode),
        cityName: this.nameOf(CHINA_CITIES, this.cityCode),
        countyName: this.nameOf(CHINA_COUNTIES, this.countyCode),
        label
      })
    },
    onProvince(code) {
      this.provinceCode = code || ''
      this.cityCode = ''
      this.countyCode = ''
      this.commit()
    },
    onCity(code) {
      this.cityCode = code || ''
      this.countyCode = ''
      this.commit()
    },
    onCounty(code) {
      this.countyCode = code || ''
      this.commit()
    },
    clear() {
      this.provinceCode = ''
      this.cityCode = ''
      this.countyCode = ''
      this.commit()
    }
  }
}
</script>

<style scoped>
.app-region-picker__cols {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
}
.app-region-picker__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 10px;
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
}
.app-region-picker__current {
  color: var(--t2, #4b5565);
}
.app-region-picker__hint {
  color: var(--t4, #98a2b3);
}
.app-region-picker__warn {
  color: var(--warning-600, #b54708);
}
.app-region-picker__clear {
  margin-left: 6px;
  padding: 0;
  border: 0;
  background: none;
  color: var(--pri, #2f6bff);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
.app-region-picker__clear:hover {
  text-decoration: underline;
}
.app-region-picker.is-disabled {
  opacity: 0.7;
}
</style>
