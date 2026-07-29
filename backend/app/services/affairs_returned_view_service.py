"""学生端退回状态投影修正。

困难认定核心退回状态为 DRAFT，资助核心退回状态为 RETURNED；移动端必须分别识别。
"""


def install() -> None:
    from app.services import mobile_affairs_service as affairs
    original = affairs.aid_my

    def aid_my(user):
        data = original(user)
        for item in data.get("items", []):
            if item.get("status") == "DRAFT":
                item["statusLabel"] = "已退回待修改"
                item["canResubmit"] = True
                item["allowedActions"] = ["EDIT_RETURNED", "RESUBMIT"]
        return data

    affairs.aid_my = aid_my
