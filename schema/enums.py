"""
全局枚举。
数据库里 student_info.stu_sex 现在存的就是 '男'/'女' 字符串。
继承 str 之后，Sex.MALE == '男' 为 True，
"""
from enum import Enum
from typing import Annotated, Any

from pydantic import BeforeValidator


class Sex(str, Enum):
    """性别。与数据库 student_info.stu_sex 列的取值一一对应。"""
    MALE = "男"
    FEMALE = "女"

    # 必须覆写 __str__！
    #   Python 3.10 里，class Sex(str, Enum) 的 str(Sex.MALE) 返回的是
    #   'Sex.MALE' 而不是 '男'。
    #   而 pymysql 在把参数写进 SQL 时会先做 str(value)：
    #       def escape_str(value, mapping=None):
    #           return "'" + escape_string(str(value)) + "'"
    #   于是性别这一列会被存成字符串 'Sex.MALE' —— 不报错，但数据全废了。
    #   覆写之后 str(Sex.MALE) == '男'，和 Sex.MALE == '男' 同时成立。
    def __str__(self) -> str:
        return self.value


# 历史包袱兼容表：老接口一直传的是 1/0，现在改成字符串了，
# 但不能因为改了存储格式就让老前端直接 422。这里做一次兼容转换。
_SEX_ALIASES = {
    1: Sex.MALE, 0: Sex.FEMALE,
    "1": Sex.MALE, "0": Sex.FEMALE,
    "男": Sex.MALE, "女": Sex.FEMALE,
    "male": Sex.MALE, "female": Sex.FEMALE,
    "M": Sex.MALE, "F": Sex.FEMALE,
}

from typing import Any, Annotated
from pydantic import BeforeValidator


def _to_sex(value: Any) -> Any:
    """
    BeforeValidator：在 Pydantic 正式校验之前，先把“各种写法”统一成 Sex 枚举。
    为什么需要它？
    接口里用户可能传 "男" / "女" / 1 / 0 / "1" / "0" 好几种写法，
    """
    # ① 已经是 None 或已经是 Sex 枚举，不用翻译，直接放行
    if value is None or isinstance(value, Sex):
        return value

    # ② 如果是字符串，先去掉首尾空格："  男  " → "男"
    #    防止用户手滑多打了空格，导致 "男 " 匹配不上
    if isinstance(value, str):
        value = value.strip()

    # ③ 去映射字典里查：
    #    _SEX_ALIASES = {"男": Sex.male, "女": Sex.female, 1: Sex.male, 0: Sex.female, ...}
    #    .get(value, value) 的意思是：
    #      - 查到了 → 返回对应的 Sex 枚举
    #      - 查不到 → 返回原值（让 Pydantic 去报"类型不对"的错）
    try:
        return _SEX_ALIASES.get(value, value)
    except TypeError:
        # ④ 如果 value 是 list/dict 这种“不可哈希”的值，
        #    .get() 会直接抛 TypeError，这里兜住，原样返回，
        #    同样交给 Pydantic 去报错，别在这里崩掉
        return value


# 用 Annotated 把“类型 Sex” 和“转换器 _to_sex”绑在一起。
# 以后接口里写 stu_sex: SexField，Pydantic 就会：
#   1. 先跑 _to_sex，把 "男" / 1 / "1" 统一成 Sex 枚举
#   2. 再做正式校验，确认最终是 Sex 类型
# 效果：一个字段，同时接受 "男" / "女" / 1 / 0 四种写法
SexField = Annotated[Sex, BeforeValidator(_to_sex)]