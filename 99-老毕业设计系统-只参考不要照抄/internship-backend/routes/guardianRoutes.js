const express = require('express');
const guardianController = require('../controllers/guardianController');

const router = express.Router();

router.get('/',       guardianController.list);
router.get('/:id',    guardianController.detail);
router.post('/',      guardianController.create);
router.delete('/:id', guardianController.remove);

module.exports = router;
