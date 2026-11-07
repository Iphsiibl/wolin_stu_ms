"""
学生模块的请求体校验模型（schema 层）。

====================================================================
【schema 层是干什么的？】
====================================================================
校验"前端传过来的 JSON 长得对不对"。

FastAPI 收到一个 POST 请求后，会先把 JSON 按这里的类转成 Python 对象，
并且自动做三件事：
    1. 检查必填字段有没有传        —— 少了 -> 422
    2. 检查类型对不对              —— "abc" 传给 int -> 422
    3. 检查格式/范围对不对          —— 手机号不像手机号 -> 422

只要这里写对了，DAO 层拿到的就一定是干净数据，
DAO 里就不用再写一遍 `if not isinstance(x, int): ...`。

【为什么不把校验写在接口函数里？】
    那样每个接口都要重复写，而且返回的错误格式不统一。
    放在 schema 里，FastAPI 会自动生成统一的错误提示，
    而且 Swagger 文档（/docs）会自动带上字段说明。

【Field(...) 和 Field(default=None) 的区别 —— 新手最容易踩的坑】
    Field(...)          省略号 = 必填。少传这个字段 -> 422
    Field(default=None) 有默认值 = 选填。不传就是 None
    Field(max_length=10)  ← 【没有 default！这种写法在 Pydantic v2 里
                             等于"必填"，不是"可选"】
    以前的 UpdateStudent 就是这么写的，结果"只改一个名字"也会被 422 拦下：
        {"type": "missing", "loc": ["body", "stu_from"], "msg": "Field required"}
    现在统一写成 `Field(default=None, max_length=10)` 才是真的可选。
"""
from datetime import date

from pydantic import BaseModel, Field, model_validator

from schema.enums import SexField


class Student_request(BaseModel):
    """
    新增学生的请求体校验。

    下面每个字段对应 student_info 表的一列。
    """
    # 学生姓名。数据库列是 varchar(10)，所以最多 10 个字。
    stu_name: str = Field(..., max_length=10, description='学生姓名')

    # 年龄。大于 18 是业务规则（招的是大学生/成年学员）。
    stu_age: int = Field(..., gt=18, description='年龄，必须大于18')

    # 性别。用 SexField 而不是裸的 int / str。
    #   SexField 能同时接受："男" / "女" / 1 / 0 四种写法，
    #   内部统一转成 Sex 枚举，存进数据库的就是 '男' / '女'。
    # 修复记录：你原来的附件写的是 `stu_sex: int = Field(...)`，
    #   但数据库这一列存的是字符串，int 写进去会变成 '1'，
    #   和统计接口里按 '男'/'女' 统计的口径对不上。
    stu_sex: SexField = Field(..., description='性别：男/女（兼容老的 1/0）')

    # 所在班级 id。
    #   ge=1 而不是 gt=1 —— gt=1 会把 1 号班挡在门外，
    #   而库里实实在在有 1 号班（软件1班），那个 Bug 让它形同虚设。
    stu_class_id: int = Field(..., ge=1, description='班级id')

    # 学生联系电话（你本轮新加的业务规则）。
    #   pattern 是正则：^1[3-9]\d{9}$ 表示
    #   以 1 开头、第二位是 3~9、后面 9 位数字 —— 标准手机号格式。
    #   写错格式会被 Pydantic 直接拦下返回 422，不用自己写 if 判断。
    stu_tel: str = Field(
        ...,
        pattern=r'^1[3-9]\d{9}$',
        description='手机号码，11位，1开头',
    )

    # 生源地。数据库列是 varchar(20)，校验也按 20 走，
    # 两边一致才不会出现"校验通过但数据库截断"的怪事。
    stu_from: str = Field(..., max_length=20, description='生源地')

    # 毕业院校
    stu_school: str = Field(..., max_length=20, description='毕业院校')

    # 专业
    stu_major: str = Field(..., max_length=20, description='专业')

    # 入学时间
    enroll_date: date = Field(..., description='入学时间')

    # 毕业时间
    gra_date: date = Field(..., description='毕业时间')

    # 学历
    edu_bg: str = Field(..., description='学历：大专/本科/硕士')

    # 顾问 id（负责招生的那个顾问）。
    #   【业务规则】每个学生都必须有顾问 —— 所以这里是【必填】。
    #   Field(..., ge=1) 里的省略号 = 必填，少传会直接 422：
    #       {"type": "missing", "loc": ["body", "agent_id"], "msg": "Field required"}
    #   ge=1 表示必须是 1 或更大的整数。
    #   DAO 层还会再校验一次"这个顾问 id 是不是真实存在"，
    #   避免写出指向不存在顾问的孤儿数据（见 Dao/stu_dao.py 的 _check_agent_exists）。
    agent_id: int = Field(..., ge=1, description='顾问id')


class Agent_request(BaseModel):
    """
    新增 / 修改顾问的请求体校验。
    """
    # 顾问姓名
    agent_name: str = Field(..., max_length=20, description='顾问姓名')

    # 顾问性别。这里暂时用普通字符串，等 Sex 枚举要覆盖全部表的时候
    # 再换成 SexField（换成 SexField 现在就能用，只是多传一个值）。
    agent_sex: str = Field(..., max_length=10, description='顾问性别：男/女')

    # 顾问年龄，和数据库的 Integer 列保持一致。
    agent_age: int = Field(..., gt=18, description='顾问年龄，必须大于18')


class UpdateAgent(BaseModel):
    """
    修改顾问的请求体校验。

    和 UpdateStudent 一样的道理：所有字段都带 default=None，
    表示"只改我传了的字段，没传的保持原样"。
    如果写成 `Field(max_length=20)`（不带 default），
    Pydantic v2 会当成必填，接口会直接 422。
    """
    agent_name: str | None = Field(default=None, max_length=20, description='顾问姓名')
    agent_sex: str | None = Field(default=None, max_length=10, description='顾问性别：男/女')
    agent_age: int | None = Field(default=None, gt=18, description='顾问年龄')


class UpdateStudent(BaseModel):
    """
    修改学生信息的请求体校验。

    【本模型最重要的约定】
    每一个字段都是 default=None 的"选填"字段。
    接口层用 `model_dump(exclude_unset=True)`，
    只把用户真正传了的字段交给 DAO 去改，
    没传的字段保持数据库里的原值不变。

    【"空值"的定义 —— 本次调整的核心】
    在这个模型里，下面三种写法统统表示【"这个字段用户没改，别动它"】：

        1. 这个 key 根本没出现在请求体里        -> 没传
        2. 传了 null                            -> 显式传空
        3. 传了 "" 或 "   "（空白字符串）        -> 前端表单没填的输入框

    第 3 种为什么必须单独处理？
    前端表单里用户没碰过的输入框，提交上来是空字符串 ""，不是 null。
    如果直接丢给 Pydantic 校验：
        stu_tel: ""   -> 422 手机号格式不对（正则拦下）
        stu_age: ""   -> 422 不是合法整数
        stu_sex: ""   -> 422 不是合法性别
        enroll_date: "" -> 422 不是合法日期
    整个请求直接挂掉 —— 用户明明只想改个学校，结果一个字段都改不了。
    所以下面那个 _blank_to_none 校验器会在【校验之前】统一把空白字符串转成 None。

    修复记录：原来的写法是
        stu_name: str | None = Field(max_length=10)
    没有 default，Pydantic v2 里默认值是 PydanticUndefined，
    字段会被当成【必填】！结果就是"只改一个名字"也会被 422 拦下来：
        {"type": "missing", "loc": ["body", "stu_from"], "msg": "Field required"}
    改成 `Field(default=None, ...)` 后才是真正的"可选字段"。
    """
    stu_name: str | None = Field(default=None, max_length=10, description='学生姓名')
    stu_from: str | None = Field(default=None, max_length=20, description='生源地')
    stu_school: str | None = Field(default=None, max_length=20, description='毕业院校')
    stu_major: str | None = Field(default=None, max_length=20, description='专业')
    enroll_date: date | None = Field(default=None, description='入学时间')
    gra_date: date | None = Field(default=None, description='毕业时间')
    edu_bg: str | None = Field(default=None, description='学历')
    stu_sex: SexField | None = Field(default=None, description='性别：男/女')
    # 补上原来漏掉的字段：接口签名叫 update_stu_class，不改班级名不副实
    stu_age: int | None = Field(default=None, gt=18, description='年龄')
    stu_class_id: int | None = Field(default=None, ge=1, description='班级id')
    # 改绑顾问
    agent_id: int | None = Field(default=None, gt=0, description='顾问id')
    # 补上你本轮新加的联系电话
    stu_tel: str | None = Field(
        default=None,
        pattern=r'^1[3-9]\d{9}$',
        description='手机号码，11位，1开头',
    )

    @model_validator(mode='before')
    @classmethod
    def _blank_to_none(cls, data):
        """
        把空白字符串（"" / "   "）统一转成 None。

        mode='before' = 在【字段校验之前】执行。
        这一步很关键：只有先转成 None，后面的 pattern / gt / 日期解析
        才不会再拿空字符串去比，接口也就不会 422。

        为什么不能放在 mode='after'？
        after 跑的时候字段已经校验过了，空字符串早就被 pattern 拦成 422 了。

        转成 None 而不是删掉这个 key，是有意的：
        删掉 key = "这个字段用户压根没提过"；
        留着 None = "用户提到了这个字段，但给的是空值"。
        两种情况在 DAO 层都按"不改这个字段"处理，但保留 key
        可以让接口层清楚地知道前端【提过】这个字段，
        从而在"一个有效字段都没有"时给出 400 而不是静默成功。

        非字典输入（比如前端传了个数组）原样放行，
        交给 Pydantic 自己报"模型类型不对"。
        """
        if not isinstance(data, dict):
            return data
        return {
            key: (None if isinstance(value, str) and not value.strip() else value)
            for key, value in data.items()
        }


# =====================================================================
# 【已删除】Student_request2
#
# 这是你原附件里的一个"第 2 版"模型，但它从来没有任何地方 import 过，
# 属于死代码。它自己还有个 bug：
#     enroll_date: date      （必填）
#     gra_date: date         （必填）
# 放在"修改学生"的场景里完全用不上。
# 死代码的坏处：改错的时候不知道有没有人在用；读代码的时候要多花时间看。
# 需要的时候再从 git 历史里翻出来就行。
# =====================================================================
