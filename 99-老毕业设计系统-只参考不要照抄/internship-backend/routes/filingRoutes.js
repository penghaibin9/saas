const express = require('express');
const { filingController } = require('../controllers');
const { requireRole } = require('../middlewares/auth');

const router = express.Router();

router.get('/overview', requireRole(1, 2), filingController.overview);
router.get('/export', requireRole(1, 2), filingController.exportPack);
router.get('/', requireRole(1, 2), filingController.list);
router.post('/generate', requireRole(1, 2), filingController.generate);
router.post('/:id/submit', requireRole(1, 2), filingController.submit);
router.put('/:id/filed', requireRole(1, 2), filingController.markFiled);
router.put('/:id/reject', requireRole(1, 2), filingController.reject);

module.exports = router;
