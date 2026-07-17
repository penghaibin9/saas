"""学生 PC 门户后端包（/api/v1/portal/*）。

定位：承接微信小程序做不了、必须上电脑的重活（长文档、大附件、大表、打印、电子签、家长代理），
与老师 PC 端同一个 MySQL、同一套账号/权限。读复用 /api/v1/mobile/*；PC 重活写用本包 /portal/*。
复用公用底座：auth（get_current_user）、file、audit、approval、notification、models、alembic，不另起一套。

见规划：student-portal/docs/01-学生PC门户-生产级施工包(总纲与5期规划).md
"""
