const express = require('express');
const { assignmentChangeController } = require('../controllers');
const { requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/', assignmentChangeController.list);
router.post('/', requireRole(3, 4, 1, 2), assignmentChangeController.create);
router.put('/:id/teacher-review', requireRole(1, 2, 3), assignmentChangeController.teacherReview);
router.put('/:id/admin-review', requireRole(1, 2), assignmentChangeController.adminReview);

module.exports = router;
