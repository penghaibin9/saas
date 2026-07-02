const express = require('express');
const stipendController = require('../controllers/stipendController');
const { validate } = require('../middlewares/validate');
const { stipendCreate } = require('../validators/schemas');

const router = express.Router();

router.get('/stats',  stipendController.stats);
router.get('/',       stipendController.list);
router.get('/:id',    stipendController.detail);
router.post('/',      validate(stipendCreate), stipendController.create);
router.put('/:id',    stipendController.update);
router.delete('/:id', stipendController.remove);

module.exports = router;
