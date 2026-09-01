<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="o">
        <view class="card oq__ticket is-invalid">
          <text class="oq__ticket-label">正式电子报到凭证</text>
          <view class="oq__code-box">
            <text class="oq__code">尚未签发</text>
          </view>
          <text class="oq__note">{{ o.reportCode.note }}</text>
        </view>

        <view class="card oq__identity">
          <text class="card-title">身份信息</text>
          <view class="oq__row"><text class="oq__k">姓名</text><text class="oq__v">{{ o.identity.name }}</text></view>
          <view class="oq__row"><text class="oq__k">录取编号</text><text class="oq__v">{{ o.identity.admissionNo || '—' }}</text></view>
          <view class="oq__row"><text class="oq__k">学院</text><text class="oq__v">{{ o.identity.collegeName || '—' }}</text></view>
          <view class="oq__row"><text class="oq__k">专业</text><text class="oq__v">{{ o.identity.majorName || '—' }}</text></view>
          <view class="oq__row"><text class="oq__k">班级</text><text class="oq__v">{{ o.identity.className || '待分班' }}</text></view>
        </view>

        <MobileInlineAlert type="info" description="正式报到凭证将在资格校验通过后由学校签发。录取编号不是核验凭证，请勿截图冒用。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
export default {
  data() { return { o: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getOrientation().then((d) => {
        this.o = d
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.oq__ticket {
  position: relative; text-align: center; padding: var(--space-6) var(--space-5);
  background: linear-gradient(180deg, #fff, var(--primary-50));
  border: 1px dashed var(--brand-primary);
}
.oq__ticket.is-invalid { border-color: var(--border-dark); background: var(--gray-50); }
.oq__ticket-label { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.oq__code-box { margin: var(--space-4) 0; padding: var(--space-4); background: #fff; border-radius: var(--radius-md); box-shadow: var(--shadow-card); }
.oq__code { font-size: 28px; font-weight: var(--font-weight-semibold); color: var(--text-primary); letter-spacing: 4px; font-family: monospace; }
.oq__ticket.is-invalid .oq__code { color: var(--text-disabled); }
.oq__note { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); }
.oq__done-badge { position: absolute; top: var(--space-3); right: var(--space-3); font-size: var(--font-size-xs); color: #fff; background: var(--success-500); padding: 3px 10px; border-radius: var(--radius-full); }
.oq__identity { margin: var(--card-gap-mobile) 0; }
.oq__row { display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
.oq__row:last-child { border-bottom: none; }
.oq__k { width: 76px; flex-shrink: 0; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.oq__v { font-size: var(--font-size-base); color: var(--text-primary); }
</style>
