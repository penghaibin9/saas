"""教务中心服务包。

本包不在导入阶段替换模块、不执行 monkey patch，也不依赖导入顺序安装业务规则。
调用方必须显式导入所需 Service；兼容逻辑应合并回对应原 Service 或由其显式调用纯策略/校验器。
"""

# 各域最终公开入口。均为普通模块别名，不改写其它模块函数对象。
from . import academic_affairs_selection_final_service as academic_affairs_selection_service
from . import academic_affairs_scheduling_public_service as academic_affairs_scheduling_service
from . import academic_affairs_autoschedule_final_service as academic_affairs_autoschedule_service
from . import academic_affairs_schedule_final_service as academic_affairs_schedule_service
from . import academic_affairs_exam_facade as academic_affairs_exam_service
from . import academic_affairs_textbook_final_facade as academic_affairs_textbook_service
