const express = require('express');
const { gdAchievementController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 版本历史（须在 /:id 之前注册）
router.get('/versions', authMiddleware, gdAchievementController.versions);

router.get('/',    authMiddleware, gdAchievementController.list);
router.get('/:id', authMiddleware, gdAchievementController.detail);

// 学生：上传/重新提交/删除
router.post('/',      authMiddleware, requireRole(4), gdAchievementController.upload, gdAchievementController.create);
router.put('/:id',    authMiddleware, requireRole(4), gdAchievementController.upload, gdAchievementController.update);
router.delete('/:id', authMiddleware, requireRole(1, 2, 4), gdAchievementController.remove);

// 教师：审阅（通过/驳回/未完成）
router.put('/:id/review',   authMiddleware, requireRole(3), gdAchievementController.review);
// 教师：版本批注（不改变状态）
router.put('/:id/annotate', authMiddleware, requireRole(1, 2, 3), gdAchievementController.annotate);

module.exports = router;
