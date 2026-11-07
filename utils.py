"""
通用小工具。

model_to_dict 是为了让 Pydantic 模型能安全地 **展开给 SQLAlchemy：

    new_obj = Student_info(**model_to_dict(stu_data))

直接用 model_dump() 会有个坑：如果字段类型是 Enum，
model_dump() 拿到的是枚举成员本身（Sex.MALE）而不是 '男'。
Enum 虽然继承 str，但某些序列化路径会把它打印成 'Sex.MALE'，
写进数据库就成了脏数据。这里统一把 Enum 拆成原始值。

修改类接口（update_xxx）记得传 exclude_unset=True，
这样 DAO 收到的就只有"用户真正传了的字段"，没传的字段一个都不会动。
"""
from enum import Enum

from pydantic import BaseModel


def model_to_dict(model: BaseModel, exclude_unset: bool = False) -> dict:
    """
    Pydantic 模型 -> 纯 dict（Enum 取 .value），可直接 ** 展开给 ORM。

    【exclude_unset 决定"没传的字段"要不要出现在结果里】

        False（默认）—— 模型的【全部】字段都出现在结果里，没填的是 None。
                         新增接口用这个：字段本来就全是必填的，
                         少传一个应该被 schema 层挡成 422。

        True        —— 只有【请求体里真正出现过】的字段才出现在结果里。
                         修改接口用这个：前端只传了要改的那几个字段，
                         没传的字段压根不会进结果，DAO 也就不会去动它们。

    两种模式的区别用一个例子说清楚：

        前端传 {"stu_school": "新大学"}

        exclude_unset=False -> {'stu_school': '新大学', 'stu_name': None,
                                'stu_tel': None, ... 一共 12 个 key}
        exclude_unset=True  -> {'stu_school': '新大学'}          只有 1 个 key

    注意：exclude_unset=True 时，用户【显式】传了 null 的字段
    依然会出现在结果里（值为 None）—— 因为"这个字段用户确实提到过"。
    至于要不要把它写进数据库，由 DAO 层按业务规则判断。
    """
    data = model.model_dump(exclude_unset=exclude_unset)
    return {
        key: (value.value if isinstance(value, Enum) else value)
        for key, value in data.items()
}
