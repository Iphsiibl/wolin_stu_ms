"""
班级 / 班主任的请求体校验模型（schema 层）。

【schema 层是干什么的？】
    校验"前端传过来的 JSON 长得对不对"。
    格式不对 -> FastAPI 自动返回 422，不用自己写 if 判断。
"""
from datetime import date

from pydantic import BaseModel, Field


class Class_Request(BaseModel):
    """
    新建 / 修改班级的请求体校验。

    这一个模型同时用于"新建"和"修改"两个接口，
    所以字段都是必填 —— 修改班级时也要把整个班级信息传一遍。
    """
    # 班级名称。数据库列长 varchar(20)。
    class_name: str = Field(..., max_length=20, description='班级名称')

    # 开课时间。
    start_date: date = Field(..., description='开课时间')

    # 班主任 id。gt=0 表示必须大于 0（0 和负数显然不是有效的 id）。
    # 这个 id 是不是真实存在的班主任，由 DAO 层检查（Dao/class_dao.py）。
    class_teacher_id: int = Field(..., gt=0, description='班主任id')

    # 授课老师 id。同上，真实性由 DAO 层检查。
    teacher_id: int = Field(..., gt=0, description='授课老师id')


class Class_teacher_Request(BaseModel):
    """
    新建 / 修改班主任的请求体校验。
    """
    # 班主任姓名。数据库列长 varchar(10)，最多 10 个字。
    class_teacher_name: str = Field(..., max_length=10, description='班主任名称')

    # 班主任性别。数据库列是 varchar(1)，只放一个字符。
    class_teacher_sex: str = Field(..., max_length=1, description='班主任性别')
