"""教务中心服务包。

本包不在导入阶段替换模块、不执行 monkey patch，也不依赖导入顺序安装业务规则。
调用方必须显式导入所需 Service；兼容逻辑应合并回对应原 Service 或由其显式调用纯策略/校验器。
"""

# 选课域在整文件收口后的最终契约入口。该别名是普通模块引用，不改写任何函数对象。
from . import academic_affairs_selection_final_service as academic_affairs_selection_service
