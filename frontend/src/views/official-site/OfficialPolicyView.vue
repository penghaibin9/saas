<template>
  <div v-if="page && content" class="yk-site yk-story-site yk-policy-page">
    <header class="yk-header">
      <div class="yk-shell yk-nav">
        <router-link class="yk-brand" to="/" aria-label="返回跃科官网首页"><span class="yk-brand-dot" aria-hidden="true">跃</span><span class="yk-brand-copy"><strong>跃科</strong><small>职业院校学生全生命周期平台</small></span></router-link>
        <nav class="yk-nav-links" aria-label="政策与支持页面导航"><router-link to="/privacy">隐私政策</router-link><router-link to="/terms">用户协议</router-link><router-link to="/support">技术支持</router-link><router-link to="/contact">联系跃科</router-link></nav>
        <router-link class="yk-nav-home" to="/" aria-label="返回跃科官网首页"><span aria-hidden="true">⌂</span> 返回首页</router-link>
        <router-link class="yk-nav-cta" to="/contact">预约产品演示</router-link>
      </div>
    </header>

    <main>
      <section class="yk-policy-hero"><div class="yk-shell"><p class="yk-kicker">{{ page.eyebrow }}</p><h1>{{ page.navTitle }}</h1><p>{{ page.hero }}</p><small>最近更新：<time :datetime="page.contentUpdatedAt">{{ page.contentUpdatedAt }}</time></small></div></section>
      <section class="yk-section yk-policy-content"><div class="yk-shell yk-policy-layout">
        <aside><strong>本页目录</strong><a v-for="(section, index) in content.sections" :key="section.title" :href="`#policy-${index + 1}`">{{ section.title }}</a></aside>
        <article>
          <div v-for="(section, index) in content.sections" :id="`policy-${index + 1}`" :key="section.title" class="yk-policy-block">
            <span>0{{ index + 1 }}</span><h2>{{ section.title }}</h2><p v-for="paragraph in section.paragraphs" :key="paragraph">{{ paragraph }}</p>
            <ul v-if="section.items?.length"><li v-for="item in section.items" :key="item">{{ item }}</li></ul>
          </div>
          <div class="yk-policy-contact"><strong>需要进一步说明？</strong><p>请联系湖南跃科信息工程有限公司，我们会结合具体访问、咨询或项目场景答复。</p><a :href="contact.phoneHref">{{ contact.phone }}</a><router-link to="/contact">预约产品演示</router-link></div>
        </article>
      </div></section>
    </main>

    <footer class="yk-footer"><div class="yk-shell yk-footer-inner"><div><strong>{{ contact.company }}</strong><span>职业院校学生全生命周期数字化平台</span></div><div class="yk-footer-links"><router-link to="/">官网首页</router-link><router-link to="/privacy">隐私政策</router-link><router-link to="/terms">用户协议</router-link><router-link to="/support">技术支持</router-link><a :href="contact.phoneHref">{{ contact.phone }}</a><span>© {{ year }}</span></div></div></footer>
  </div>
</template>

<script>
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SITE_CONTACT } from '@/config/officialSalesPages'
import { syncOfficialSeo } from '@/services/officialSeoRuntime'
import '@/styles/official-site.css'
import '@/styles/official-site-story.css'

const POLICY_CONTENT = Object.freeze({
  '/privacy': {
    sections: [
      { title: '适用范围', paragraphs: ['本政策适用于跃科公开官网、预约产品演示表单和官网技术支持入口。学校正式业务系统中的学生、教师和业务数据处理，以项目合同、学校管理制度和对应系统配置为准。'] },
      { title: '我们处理的信息', paragraphs: ['当你主动预约产品演示时，我们会处理完成本次沟通所需的信息。'], items: ['学校名称', '联系人姓名（可选）', '联系电话', '意向产品', '主动填写的需求说明'] },
      { title: '使用目的与保存方式', paragraphs: ['上述信息仅用于响应本次咨询、确认需求和安排产品沟通。当前官网表单不会在跃科业务数据库中创建销售线索记录；系统会将必要摘要发送给商务联系人。基础设施可能按照安全配置产生必要的访问与错误日志。'] },
      { title: '共享、保护与保存', paragraphs: ['我们不会出售预约信息，也不会将其用于与本次咨询无关的营销。仅允许因沟通、运维和安全需要的授权人员接触必要信息，并通过访问控制、传输保护和日志审计降低风险。'] },
      { title: '你的权利', paragraphs: ['你可以联系我们查询、更正或要求停止使用本次咨询信息。涉及学校正式业务系统数据的请求，应通过学校授权管理员和项目约定渠道处理。'] }
    ]
  },
  '/terms': {
    sections: [
      { title: '协议适用', paragraphs: ['访问跃科官网或使用公开功能，即表示你同意遵守本页规则。学校正式系统的服务范围、账号权限、验收标准和持续服务，以双方合同及实施文件为准。'] },
      { title: '网站内容', paragraphs: ['官网用于介绍产品能力、解决方案和联系渠道。产品会持续迭代，具体模块、部署方式、系统集成和交付时间以正式方案为准。'] },
      { title: '账号与授权', paragraphs: ['系统账号仅限经学校或项目授权的人员使用。用户应妥善保管凭据，不得绕过权限、探测他人数据或以自动化方式影响系统正常运行。'] },
      { title: '知识产权', paragraphs: ['官网文案、界面、图形、产品名称和软件成果受相关法律保护。未经书面许可，不得复制、出售、反向工程或以误导方式对外使用。'] },
      { title: '责任边界', paragraphs: ['我们会持续维护公开信息的准确性，但不把官网介绍替代正式合同、招标参数、实施方案或验收文件。因不可抗力、第三方网络或未经授权使用造成的影响，按法律和双方约定处理。'] }
    ]
  },
  '/support': {
    sections: [
      { title: '支持范围', paragraphs: ['可通过本页联系产品咨询、账号访问、功能使用、数据导入、系统集成、部署交付和已上线项目问题。'] },
      { title: '提交问题前准备', paragraphs: ['为了更快定位问题，请尽量准备以下信息。'], items: ['学校或项目名称', '使用角色与所属模块', '发生时间和操作步骤', '页面提示或经过脱敏的截图', '影响范围与紧急程度'] },
      { title: '敏感信息提醒', paragraphs: ['请勿在公开留言中提交密码、验证码、访问令牌、完整身份证号或未经脱敏的学生隐私数据。需要传输业务材料时，请使用项目约定的安全渠道。'] },
      { title: '问题协同', paragraphs: ['收到问题后，我们会先确认现象、范围和必要上下文，再根据项目服务约定进入分析、处理和反馈流程。紧急生产问题请直接使用项目约定联系人或电话渠道。'] }
    ]
  }
})

export default {
  name: 'OfficialPolicyView',
  computed: {
    page() { return OFFICIAL_SALES_PAGE_MAP[this.$route.path] || null },
    content() { return POLICY_CONTENT[this.$route.path] || null },
    contact() { return OFFICIAL_SITE_CONTACT },
    year() { return new Date().getFullYear() }
  },
  watch: { '$route.path': { immediate: true, handler(path) { this.$nextTick(() => syncOfficialSeo(path)) } } }
}
</script>
