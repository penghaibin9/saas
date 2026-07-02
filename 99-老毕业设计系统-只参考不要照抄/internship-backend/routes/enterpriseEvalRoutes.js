const express = require('express');
const { enterpriseEvalController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/',     authMiddleware, requireRole(1, 2, 3), enterpriseEvalController.list);
router.post('/',    authMiddleware, requireRole(1, 2, 3), enterpriseEvalController.create);
router.delete('/:id', authMiddleware, requireRole(1, 2, 3), enterpriseEvalController.remove);

module.exports = router;
