const express = require('express');
const { internLogController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 模板 / 批量批阅（须在 /:id 动态路由之前注册,避免被误匹配）
router.get('/template',     authMiddleware, internLogController.getTemplate);
router.put('/template',     authMiddleware, requireRole(1, 2), internLogController.setTemplate);
router.put('/batch-review', authMiddleware, requireRole(3), internLogController.batchReview);

router.get('/',    authMiddleware, internLogController.list);
router.get('/:id', authMiddleware, internLogController.detail);

// 学生：创建/修改/提交/删除（支持附件）
router.post('/',          authMiddleware, requireRole(4), internLogController.upload, internLogController.create);
router.put('/:id',        authMiddleware, requireRole(4), internLogController.upload, internLogController.update);
router.put('/:id/submit', authMiddleware, requireRole(4), internLogController.submit);
router.delete('/:id',     authMiddleware, requireRole(4), internLogController.remove);

// 教师：批阅
router.put('/:id/review', authMiddleware, requireRole(3), internLogController.review);

module.exports = router;
