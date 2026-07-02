const path = require('path');
const multer = require('multer');
const storage = require('./storage');

const UPLOADS_DIR = storage.UPLOADS_DIR;
const DEFAULT_EXT = ['.pdf', '.doc', '.docx', '.zip', '.jpg', '.jpeg', '.png'];

/**
 * 创建一个 multer 上传器（经对象存储抽象层）：
 * - 文件名加密随机，避免枚举
 * - 扩展名白名单
 * - 默认大小上限 20MB
 * - STORAGE_DRIVER=local 写本地（默认）；=oss/s3 自动落对象存储（多实例共享）
 *   控制器统一用 require('../utils/storage').keyToUrl(req.file.filename) 取访问 URL
 */
function createUploader({ prefix = 'file', allowedExt = DEFAULT_EXT, maxSize = 20 * 1024 * 1024 } = {}) {
  return multer({
    storage: storage.multerStorage({ prefix, allowedExt }),
    limits: { fileSize: maxSize },
    fileFilter: (req, file, cb) => {
      if (allowedExt.includes(path.extname(file.originalname).toLowerCase())) cb(null, true);
      else cb(new Error('不支持的文件格式：' + path.extname(file.originalname)));
    }
  });
}

module.exports = { createUploader, UPLOADS_DIR, DEFAULT_EXT, keyToUrl: storage.keyToUrl };
