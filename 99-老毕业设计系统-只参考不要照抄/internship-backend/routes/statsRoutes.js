const express = require('express');
const { statsController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');
const schoolReadinessModel = require('../models/schoolReadinessModel');

const router = express.Router();

router.get('/overview', authMiddleware, statsController.overview);

router.get('/product-overview', authMiddleware, requireRole(1, 2), async (req, res, next) => {
  try {
    const data = await schoolReadinessModel.overview({
      preferMockWhenEmpty: String(req.query.demo || '') === '1'
    });
    res.json({ success: true, message: '获取产品销售概览成功', data });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
