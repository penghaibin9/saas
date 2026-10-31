<template>
  <footer class="site-footer"><div class="footer-wrap"><div class="footer-top"><div><strong>跃科</strong><p>服务学生成长，成就教师发展。</p><small>{{ COMPANY_NAME }}</small></div><nav aria-label="页脚导航"><RouterLink to="/products">产品中心</RouterLink><RouterLink to="/solutions">解决方案</RouterLink><RouterLink to="/services/delivery">实施服务</RouterLink><a href="/news">新闻资讯</a><RouterLink to="/about">关于跃科</RouterLink><RouterLink to="/contact">联系我们</RouterLink><RouterLink to="/#login">系统登录</RouterLink></nav><div><span>产品咨询与服务</span><a class="phone" :href="contact.phoneHref">{{ contact.phone }}</a></div></div><div class="footer-bottom"><span>© {{ new Date().getFullYear() }} {{ COMPANY_NAME }}</span><div><a :href="ICP_QUERY_URL" rel="noopener noreferrer" target="_blank">{{ ICP_NUMBER }}</a><RouterLink to="/privacy">隐私政策</RouterLink><RouterLink to="/terms">用户协议</RouterLink><RouterLink to="/support">技术支持</RouterLink></div></div></div></footer>
</template>
<script setup>
import { COMPANY_NAME, ICP_NUMBER, ICP_QUERY_URL } from '../../config/portalConfig.js'
import { OFFICIAL_SITE_CONTACT as contact } from '../../config/officialSalesPages.js'
</script>

