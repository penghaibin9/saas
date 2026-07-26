from .base import authorize_student_action


def authorize(db, student, action="view"):
    codes = {
        "view": "graduationDesign.taskbook.view",
        "issue": "graduationDesign.taskbook.issue",
        "update": "graduationDesign.taskbook.update",
        "confirmOnBehalf": "graduationDesign.taskbook.confirmOnBehalf",
    }
    return authorize_student_action(db, student, action=f"taskbook.{action}", permission_code=codes[action])
