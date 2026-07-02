const express = require('express');
const { provinceController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 省厅数据：仅院校管理员
router.get('/',         authMiddleware, requireRole(1), provinceController.list);
router.get('/template', authMiddleware, requireRole(1), provinceController.downloadTemplate);
router.post('/fetch',   authMiddleware, requireRole(1), provinceController.uploadMiddleware, provinceController.fetchList);
router.get('/verify',   authMiddleware, requireRole(1), provinceController.verify);
router.put('/:id/upload', authMiddleware, requireRole(1), provinceController.uploadAchievement);

module.exports = router;
