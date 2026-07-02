/**
 * 统一响应格式工具
 */
function success(res, data = null, message = '操作成功', code = 200) {
  return res.status(code).json({
    success: true,
    message,
    data
  });
}

function error(res, message = '操作失败', code = 500, data = null) {
  const payload = {
    success: false,
    message,
    code
  };

  if (data !== null) {
    payload.data = data;
  }

  return res.status(code).json(payload);
}

module.exports = {
  success,
  error
};
