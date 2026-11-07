"""
老师信息的请求体校验模型（schema 层）。

【三个模型的分工】
    Teacher_Create —— 新增老师（所有字段必填）
    Teacher_Update —— 修改老师（所有字段选填）
    Teacher_Out    —— 查出来的老师（比 Create 多一个 teacher_id）
"""
from pydantic import BaseModel, ConfigDict, Field


class Teacher_Create(BaseModel):
    """
    新增老师的请求体校验。
    """
    # 老师姓名，必填。
    teacher_name: str = Field(..., description='请输入姓名')

    # 修复记录：原来是 `teacher_tel : str = Field(None, ...)`。
    # 类型标成 str 却拿 None 当默认值，是自相矛盾的写法。
    # 正确写法是 `str | None = Field(default=None, ...)`：
    #   类型允许为空、默认值是 None、传了就校验格式。
    #
    # pattern 是正则：^1\d{10}$ 表示"1 开头 + 10 位数字"，也就是 11 位手机号。
    # 格式不对会被 Pydantic 拦下返回 422，不用自己写 if 判断。
    teacher_tel: str | None = Field(default=None, pattern=r'^1\d{10}$',
                                    description='手机号码，选填，需11位数字')

    # 老师岗位，必填。
    teacher_job: str = Field(..., description='请输入工作岗位')


class Teacher_Update(BaseModel):
    """
    修改老师的请求体校验。

    所有字段都是选填（default=None）：
    只传要改的字段，没传的保持原样。

    【新手最容易踩的坑】
    写成 `teacher_name: str | None = Field(max_length=20)`（没有 default）
    在 Pydantic v2 里会被当成【必填】！
    因为 v2 里 Field() 不带 default 时默认值是 PydanticUndefined。
    结果就是"只改个岗位"也会被 422 拦下：
        {"type": "missing", "loc": ["body", "teacher_name"], "msg": "Field required"}
    """
    teacher_name: str | None = Field(default=None, description='请输入姓名')
    teacher_tel: str | None = Field(default=None, pattern=r'^1\d{10}$',
                                    description='手机号码，选填，需11位数字')
    teacher_job: str | None = Field(default=None, description='请输入工作岗位')


class Teacher_Out(Teacher_Create):
    """
    老师信息输出模型。

    继承 Teacher_Create，所以姓名和岗位都是必填 ——
    也就是说返回的老师必须真的有这两个值，否则序列化会报错。

    多出来一个 teacher_id：这是查询接口要返回的（但新增时用户不用传）。
    """
    teacher_id: int

    # 修复：Pydantic v2 里 `orm_mode` 已经改名成 `from_attributes`。
    # 继续用 class Config: orm_mode = True 的话，Pydantic 会直接忽略它，
    # 启动时还会打印一条 UserWarning。
    # 这个开关的作用是：允许 from_attributes=True，把 SQLAlchemy 对象
    # 直接按属性名取值，而不是当成 dict 处理。
    # 接口上写了 response_model=Teacher_Out 之后，返回 ORM 对象就能自动转成 JSON。
    model_config = ConfigDict(from_attributes=True)
