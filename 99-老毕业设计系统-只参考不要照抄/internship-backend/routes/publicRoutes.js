const express = require('express');
const { enterpriseEvalController, enterprisePortalController } = require('../controllers');
const guardianController = require('../controllers/guardianController');
const schoolReadinessModel = require('../models/schoolReadinessModel');
const rateLimit = require('../utils/rateLimit');

// 免登录公开接口（凭 token）。仅放最小必要能力，避免越权。
const router = express.Router();

router.get('/enterprise-eval/:token',  enterpriseEvalController.publicGet);
router.post('/enterprise-eval/:token', enterpriseEvalController.publicSubmit);

// 企业入驻自助注册（公开，提交后待管理员审核）
router.post('/enterprise-register', enterprisePortalController.register);

// 公开销售演示接口：只用于返回演示聚合数据，不暴露真实学生个人信息。
router.get('/product-overview-demo', async (req, res, next) => {
  try {
    const overview = await schoolReadinessModel.overview({
      preferMockWhenEmpty: true,
      demoOnly: true
    });
    // 公开 API 使用显式字段白名单，防止模型未来新增诊断或内部字段时被连带暴露。
    const data = {
      source: overview.source,
      generatedAt: overview.generatedAt,
      kpis: overview.kpis,
      collegeRanking: overview.collegeRanking,
      demoFlow: overview.demoFlow
    };
    res.json({ success: true, message: '获取公开销售演示概览成功', data });
  } catch (err) {
    next(err);
  }
});

// 家长在线签署（公开，凭安全令牌）；提交侧限流，缓解滥用
const guardianLimiter = rateLimit({ windowMs: 10 * 60 * 1000, max: 30, message: '操作过于频繁，请稍后再试' });
router.get('/guardian/:token',  guardianController.publicGet);
router.post('/guardian/:token', guardianLimiter, guardianController.publicSign);

module.exports = router;
