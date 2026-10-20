"""Pure presentation classification, not a new business dictionary or region authority."""
from __future__ import annotations
from datetime import date

REGIONS = (('110000', '北京', '北京市'), ('120000', '天津', '天津市'), ('130000', '河北', '河北省'), ('140000', '山西', '山西省'), ('150000', '内蒙古', '内蒙古自治区'), ('210000', '辽宁', '辽宁省'), ('220000', '吉林', '吉林省'), ('230000', '黑龙江', '黑龙江省'), ('310000', '上海', '上海市'), ('320000', '江苏', '江苏省'), ('330000', '浙江', '浙江省'), ('340000', '安徽', '安徽省'), ('350000', '福建', '福建省'), ('360000', '江西', '江西省'), ('370000', '山东', '山东省'), ('410000', '河南', '河南省'), ('420000', '湖北', '湖北省'), ('430000', '湖南', '湖南省'), ('440000', '广东', '广东省'), ('450000', '广西', '广西壮族自治区'), ('460000', '海南', '海南省'), ('500000', '重庆', '重庆市'), ('510000', '四川', '四川省'), ('520000', '贵州', '贵州省'), ('530000', '云南', '云南省'), ('540000', '西藏', '西藏自治区'), ('610000', '陕西', '陕西省'), ('620000', '甘肃', '甘肃省'), ('630000', '青海', '青海省'), ('640000', '宁夏', '宁夏回族自治区'), ('650000', '新疆', '新疆维吾尔自治区'), ('710000', '台湾', '台湾省'), ('810000', '香港', '香港特别行政区'), ('820000', '澳门', '澳门特别行政区'))

def region_code(value):
    """Accept explicit province prefix/code only; never infer province from a city/address."""
    raw = str(value or "").strip()
    for code, short, full in REGIONS:
        if raw.startswith((code, full, short)):
            return code
    return "UNKNOWN"

def month_keys(day: date, months=6):
    if not 1 <= months <= 12:
        raise ValueError("months must be in 1..12")
    offset = day.year * 12 + day.month - 1
    return [f"{(offset-i)//12:04d}-{(offset-i)%12+1:02d}" for i in range(months-1, -1, -1)]
