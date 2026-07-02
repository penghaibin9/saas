const express = require('express');
const { defenseController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 答辩组：查看（管理员/评委教师）
router.get('/groups',      authMiddleware, requireRole(1, 2, 3), defenseController.listGroups);
router.get('/groups/:id',  authMiddleware, requireRole(1, 2, 3), defenseController.groupDetail);

// 管理员维护答辩组
router.post('/groups',         authMiddleware, requireRole(1, 2), defenseController.createGroup);
router.put('/groups/:id',      authMiddleware, requireRole(1, 2), defenseController.updateGroup);
router.delete('/groups/:id',   authMiddleware, requireRole(1, 2), defenseController.removeGroup);
router.post('/groups/:id/finalize', authMiddleware, requireRole(1, 2), defenseController.finalize);

// 评委
router.post('/groups/:id/committee', authMiddleware, requireRole(1, 2), defenseController.addCommittee);
router.delete('/committee/:cid',     authMiddleware, requireRole(1, 2), defenseController.removeCommittee);

// 答辩学生
router.post('/groups/:id/members', authMiddleware, requireRole(1, 2), defenseController.addMember);
router.delete('/members/:mid',     authMiddleware, requireRole(1, 2), defenseController.removeMember);
router.put('/members/:mid/recommend', authMiddleware, requireRole(1, 2), defenseController.setRecommend);

// 评分（评委教师或管理员）
router.put('/groups/:id/students/:sid/score', authMiddleware, requireRole(1, 2, 3), defenseController.score);

module.exports = router;
