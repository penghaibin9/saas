"""教务中心服务层公开入口。

大文件服务采用兼容 facade 做低风险增量收口；调用方继续使用原模块名，避免同时改动千行 router。
"""

from . import academic_affairs_archive_facade as academic_affairs_archive_service
