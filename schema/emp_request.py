from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from decimal import Decimal

from schema.enums import SexField


# 新建用户输入时的数据校验模型
class EmpRequest(BaseModel):
    """新建用户输入时的数据校验模型。"""
    stu_id: int = Field(..., gt=0, description='学生id')
    company: str = Field(..., max_length=50, description='学生入职公司')
    # 薪资。【单位：元/月】—— 全项目统一用"元"，不混用"千元"。
    # 填 25000 = 25000 元/月。
    # （曾经踩过的坑：种子数据里写成了 27.74，意思其实是"27.74 千"，
    #   结果库里出现"月薪 27 块 7 毛"这种荒谬数字，
    #   而且和另一个接口写进去的 25000 混成了两种量级，没人说得清。）
    salary: Decimal = Field(..., gt=0, description='薪资，单位：元/月')
    # 这两个日期是必填的。
    # 一条就业信息从"简历开放"到"收到 offer"是一段完整的业务过程，
    # 缺了任何一端，"就业时长"这个核心指标就算不出来
    # （stat_dao 的 get_employment_duration / get_avg_duration_by_class
    #   都得专门过滤掉日期不全的行）。
    # 既然两个日期都有，那它们的先后关系就是一条明确的业务规则，
    # 应该在入口就校验掉，而不是等统计接口算出负数时长才发现。
    open_date: datetime = Field(..., description='简历开放时间')
    offer_date: datetime = Field(..., description='收到offer时间')

    @model_validator(mode='after')
    def check_date_order(self):
        """收到 offer 的时间不能早于简历开放时间。"""
        if self.offer_date < self.open_date:
            raise ValueError('收到offer的时间不能早于简历开放时间')
        return self


# 学生编号，公司名字，工资范围查询学生就业信息
class EmpSearch(BaseModel):
    stu_id: int | None = Field(default=None, gt=0, description='学生ID')
    company: str | None = Field(default=None, description='公司名')
    salary_min: Decimal | None = Field(default=None, gt=0, description='薪资下限')
    salary_max: Decimal | None = Field(default=None, gt=0, description='薪资上限')
    stu_name: str | None = Field(default=None, description='学生姓名')
    class_name: str | None = Field(default=None, description='班级名称')
    edu_bg: str | None = Field(default=None, description='学历：大专/本科/硕士')
    stu_major: str | None = Field(default=None, description='专业')
    stu_sex: SexField | None = Field(default=None, description='性别：男/女')


# 更新数据时的数据校验模型
class EmpUpdate(BaseModel):
    open_date: datetime | None = Field(default=None, description='简历开放日期')
    offer_date: datetime | None = Field(default=None, description='收到offer日期')
    company: str | None = Field(default=None, max_length=50, description='就业公司')
    salary: Decimal | None = Field(default=None, gt=0, description='薪资，单位：元/月')
