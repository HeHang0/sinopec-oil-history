from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Province:
    code: int
    name: str
    slug: str


# The order mirrors the province list embedded in the source page.
PROVINCES: tuple[Province, ...] = (
    Province(11, "北京", "beijing"),
    Province(12, "天津", "tianjin"),
    Province(13, "河北", "hebei"),
    Province(14, "山西", "shanxi"),
    Province(41, "河南", "henan"),
    Province(37, "山东", "shandong"),
    Province(31, "上海", "shanghai"),
    Province(32, "江苏", "jiangsu"),
    Province(33, "浙江", "zhejiang"),
    Province(34, "安徽", "anhui"),
    Province(35, "福建", "fujian"),
    Province(36, "江西", "jiangxi"),
    Province(42, "湖北", "hubei"),
    Province(43, "湖南", "hunan"),
    Province(44, "广东", "guangdong"),
    Province(45, "广西", "guangxi"),
    Province(53, "云南", "yunnan"),
    Province(52, "贵州", "guizhou"),
    Province(46, "海南", "hainan"),
    Province(50, "重庆", "chongqing"),
    Province(51, "四川", "sichuan"),
    Province(65, "新疆", "xinjiang"),
    Province(15, "内蒙古", "neimenggu"),
    Province(21, "辽宁", "liaoning"),
    Province(22, "吉林", "jilin"),
    Province(64, "宁夏", "ningxia"),
    Province(61, "陕西", "shaanxi"),
    Province(23, "黑龙江", "heilongjiang"),
    Province(54, "西藏", "xizang"),
    Province(63, "青海", "qinghai"),
    Province(62, "甘肃", "gansu"),
)

BY_CODE = {province.code: province for province in PROVINCES}
BY_SLUG = {province.slug: province for province in PROVINCES}
BY_NAME = {province.name: province for province in PROVINCES}


def resolve_province(value: str) -> Province:
    """Resolve a numeric code, pinyin slug, or Chinese province name."""
    value = value.strip()
    if not value:
        raise ValueError("empty province selector")
    if value.isdigit():
        province = BY_CODE.get(int(value))
    else:
        province = BY_SLUG.get(value.lower()) or BY_NAME.get(value)
    if province is None:
        raise ValueError(f"unknown province: {value!r}")
    return province
