<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="p">
        <!-- 顶部身份卡 -->
        <view class="pf__id card">
          <view class="pf__avatar">{{ p.base.name.slice(0,1) }}</view>
          <view class="flex-1">
            <text class="t-lg t-bold">{{ p.base.name }}</text>
            <text class="pf__id-sub">{{ p.org.className }} · 学号 {{ p.base.studentNo }}</text>
            <view class="pf__id-tags">
              <MobileStatusTag :label="p.status.stageText" type="processing" />
              <MobileStatusTag :label="p.status.statusText" type="success" />
            </view>
          </view>
        </view>

        <MobileInlineAlert type="info" description="姓名、身份证号、学号、学籍状态不可自行修改；手机号、地址、紧急联系人可申请更正。" />

        <!-- 基础信息 -->
        <view class="card">
          <text class="card-title">基础信息</text>
          <view class="divider" />
          <view class="pf__row"><text class="pf__k">姓名</text><text class="pf__v">{{ p.base.name }}<text class="pf__lock">🔒</text></text></view>
          <view class="pf__row"><text class="pf__k">性别 / 民族</text><text class="pf__v">{{ p.base.gender }} · {{ p.base.nation }}</text></view>
          <view class="pf__row"><text class="pf__k">出生日期</text><text class="pf__v">{{ p.base.birth }}</text></view>
          <view class="pf__row"><text class="pf__k">政治面貌</text><text class="pf__v">{{ p.base.political }}</text></view>
          <view class="pf__row"><text class="pf__k">身份证号</text>
            <view class="pf__v"><MobileSensitiveText :value="p.base.idCard" type="idcard" /><text class="pf__lock">🔒</text></view>
          </view>
        </view>

        <!-- 联系方式（可更正） -->
        <view class="card">
          <view class="row-between"><text class="card-title">联系方式</text><text class="pf__editable">可申请更正</text></view>
          <view class="divider" />
          <view class="pf__row"><text class="pf__k">手机号</text>
            <view class="pf__v"><MobileSensitiveText :value="p.contact.phone" type="phone" /><text class="pf__edit" @click="correct('手机号')">更正</text></view>
          </view>
          <view class="pf__row"><text class="pf__k">邮箱</text><text class="pf__v">{{ p.contact.email }}</text></view>
          <view class="pf__row"><text class="pf__k">家庭住址</text>
            <view class="pf__v"><MobileSensitiveText :value="p.contact.address" type="address" /><text class="pf__edit" @click="correct('家庭住址')">更正</text></view>
          </view>
          <view class="pf__row"><text class="pf__k">紧急联系人</text><text class="pf__v flex-1 ellipsis">{{ p.contact.emergency }}<text class="pf__edit" @click="correct('紧急联系人')">更正</text></text></view>
        </view>

        <!-- 学籍组织 -->
        <view class="card">
          <text class="card-title">学籍组织</text>
          <view class="divider" />
          <view class="pf__row"><text class="pf__k">学院 / 专业</text><text class="pf__v">{{ p.org.college }} · {{ p.org.major }}</text></view>
          <view class="pf__row"><text class="pf__k">年级 / 学制</text><text class="pf__v">{{ p.org.grade }} · {{ p.org.system }}</text></view>
          <view class="pf__row"><text class="pf__k">入学时间</text><text class="pf__v">{{ p.org.enrollDate }}</text></view>
          <view class="pf__row"><text class="pf__k">注册状态</text><text class="pf__v">{{ p.status.enrollStatus }}</text></view>
        </view>

        <!-- 材料证照 -->
        <view class="card">
          <text class="card-title">材料证照</text>
          <view class="divider" />
          <view v-for="c in p.credentials" :key="c.id" class="pf__cred">
            <text class="pf__cred-name">{{ c.name }}</text>
            <MobileStatusTag :status="c.status" />
            <text class="pf__cred-time">{{ c.updated }}</text>
          </view>
        </view>

        <!-- 各中心摘要 -->
        <view class="card">
          <text class="card-title">我的全周期摘要</text>
          <view class="divider" />
          <view class="pf__row"><text class="pf__k">服务记录</text><text class="pf__v flex-1 ellipsis">{{ p.summaries.service }}</text></view>
          <view class="pf__row"><text class="pf__k">岗位实习</text><text class="pf__v flex-1 ellipsis">{{ p.summaries.internship }}</text></view>
          <view class="pf__row"><text class="pf__k">毕业设计</text><text class="pf__v flex-1 ellipsis">{{ p.summaries.graduation }}</text></view>
          <view class="pf__row"><text class="pf__k">就业去向</text><text class="pf__v flex-1 ellipsis">{{ p.summaries.employment }}</text></view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'
export default {
  data() { return { p: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getProfile().then((d) => { this.p = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    correct(field) {
      // 走真实服务申请（信息更正工单），不做假成功
      uni.navigateTo({ url: '/pages/student/service-apply/index?name=' +
        encodeURIComponent('信息更正申请（' + field + '）') + '&dept=' + encodeURIComponent('学籍管理') })
    }
  }
}
</script>

<style scoped>
.pf__id { display: flex; align-items: center; gap: var(--space-3); }
.pf__avatar { width: 52px; height: 52px; border-radius: var(--radius-full); background: var(--brand-gradient); color: #fff; display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xl); }
.pf__id-sub { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.pf__id-tags { display: flex; gap: var(--space-2); margin-top: var(--space-2); }
.pf__row { display: flex; align-items: center; justify-content: space-between; padding: 9px 0; }
.pf__k { font-size: var(--font-size-base); color: var(--text-tertiary); }
.pf__v { font-size: var(--font-size-base); color: var(--text-primary); display: inline-flex; align-items: center; gap: 6px; }
.pf__lock { font-size: 11px; }
.pf__edit { color: var(--text-link); font-size: var(--font-size-sm); margin-left: var(--space-3); }
.pf__editable { font-size: var(--font-size-xs); color: var(--success-600); }
.pf__cred { display: flex; align-items: center; gap: var(--space-3); padding: 8px 0; }
.pf__cred-name { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); }
.pf__cred-time { font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
