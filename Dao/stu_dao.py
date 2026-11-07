
from sqlalchemy.orm import Session, joinedload

from model.class_model import Class
from model.student_table import Agent, Student_info

# =====================================================================
# 允许被"修改接口"改动的字段白名单。
# 白名单把"能改什么"写死在这里，多余的 key 会被静默忽略。
# =====================================================================
STU_UPDATABLE_FIELDS = {
    'stu_name', 'stu_from', 'stu_school', 'stu_major',
    'enroll_date', 'gra_date', 'edu_bg', 'stu_sex',
    'stu_age', 'stu_class_id', 'agent_id', 'stu_tel',
}

AGENT_UPDATABLE_FIELDS = {
    'agent_name', 'agent_sex', 'agent_age',
}


# =====================================================================
# 内部小工具
# =====================================================================

def _check_agent_exists(db: Session, agent_id: int | None) -> str | None:
    """
    检查顾问是否真实存在。
    """
    if agent_id is None:
        # 没传顾问 id = 漏填了。业务上不允许每个学生都没有顾问。
        return '必须指定负责招生的顾问id'

    exists = db.query(Agent).filter(
        Agent.agent_id == agent_id,
        Agent.is_del == 0,          # 已删除的顾问不能再被选
    ).first()

    if not exists:
        return f'顾问不存在(id={agent_id})'
    return None


def _check_class_exists(db: Session, stu_class_id: int) -> str | None:
    """检查班级是否存在。返回 None 表示通过，返回 str 表示错误提示。"""
    exists = db.query(Class).filter(
        Class.stu_class_id == stu_class_id,
        Class.is_del == 0,
    ).first()
    if not exists:
        return f'班级不存在(id={stu_class_id})'
    return None


def _is_blank(value) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


# =====================================================================
# 一、顾问
# =====================================================================

def add_agent(db: Session, agent_data: dict):

    # 先查重名

    exists = db.query(Agent).filter(
        Agent.agent_name == agent_data.get('agent_name'),
        Agent.is_del == 0,
    ).first()
    if exists:
        return False, {
            'message': f'已存在同名顾问：{agent_data.get("agent_name")}',
            'status_code': 409,
        }

    # 没有 try/except 了：万一数据库真报错，异常会往上冒，
    # 由全局处理器记日志返回 500，而不是伪装成"新增失败"。
    new_agent = Agent(**agent_data)
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)     # 刷新一下，才能拿到数据库自增生成的 agent_id

    return True, {
        'message': '新增成功',
        'data': {'agent_id': new_agent.agent_id},
    }


def select_agent_list(db: Session):

    rows = (
        db.query(Agent)
        .filter(Agent.is_del == 0)
        .order_by(Agent.agent_id)
        .all()
    )
    return rows


def select_agent(db: Session, agent_id: int):
    """
    按 id 查询【单个】顾问。
    """
    row = (
        db.query(Agent)
        .filter(
            Agent.agent_id == agent_id,
            Agent.is_del == 0,
        )
        .first()
    )
    if not row:
        return False, {
            'message': f'无匹配顾问编号(id={agent_id})',
            'status_code': 404,
        }
    return True, row


def update_agent(db: Session, agent_id: int, agent_dict: dict):
    """
    修改顾问信息。只更新请求里真正带值的字段。
    """
    # 1. 先把要改的那一行查出来
    result = db.query(Agent).filter(
        Agent.agent_id == agent_id,
        Agent.is_del == 0,
    ).first()
    if not result:
        return False, {
            'message': f'无匹配顾问编号(id={agent_id})',
            'status_code': 404,
        }

    # 2. 遍历字典更新。注意：只改白名单里的字段、只改有值的字段
    for field, value in agent_dict.items():
        if value is not None and field in AGENT_UPDATABLE_FIELDS:
            setattr(result, field, value)
            # setattr(result, 'agent_name', '张三')
            # 等价于 result.agent_name = '张三'

    # 3. 循环【外面】统一提交一次 —— 这是本次修复的关键
    db.commit()
    db.refresh(result)

    return True, {
        'message': '更新成功',
        'data': {
            'agent_id': result.agent_id,
            'agent_name': result.agent_name,
            'agent_sex': result.agent_sex,
            'agent_age': result.agent_age,
        },
    }


def delete_agent(db: Session, agent_id: int):
    """
    删除顾问（软删除：把 is_del 置 1，不真的删行）。
    """
    result = db.query(Agent).filter(
        Agent.agent_id == agent_id,
        Agent.is_del == 0,
    ).first()
    if not result:
        return False, {
            'message': f'无匹配顾问编号(id={agent_id})',
            'status_code': 404,
        }

    result.is_del = 1
    db.commit()

    return True, {'message': '删除成功'}


# =====================================================================
# 二、学生信息
# =====================================================================

def add_stu(db: Session, stu_dict: dict):
    """
    新增学生。
    """
    # ---- 1. 姓名 + 电话 重复检查 ----

    duplicated = db.query(Student_info).filter(
        Student_info.stu_name == stu_dict.get('stu_name'),
        Student_info.stu_tel == stu_dict.get('stu_tel'),
        Student_info.is_del == 0,
    ).first()
    if duplicated:
        return False, {
            'message': (
                f'学生姓名{stu_dict.get("stu_name")}和电话'
                f'{stu_dict.get("stu_tel")}已经存在'
            ),
            'status_code': 409,
        }

    # ---- 2. 班级存在性检查 ----
    class_error = _check_class_exists(db, stu_dict.get('stu_class_id'))
    if class_error:
        return False, {'message': class_error, 'status_code': 404}

    # ---- 3. 顾问存在性检查 ----
    agent_error = _check_agent_exists(db, stu_dict.get('agent_id'))
    if agent_error:
        return False, {'message': agent_error, 'status_code': 404}

    # ---- 4. 全部通过，正式写入 ----
    new_stu = Student_info(**stu_dict)
    db.add(new_stu)
    db.commit()
    db.refresh(new_stu)     # 拿到自增生成的 stu_id

    return True, {
        'message': '添加成功',
        'data': {'stu_id': new_stu.stu_id},
    }


def select_stu_id(db: Session, stu_id: int):
    """
    按学生 id 查询【单个】学生。
    """
    row = (
        db.query(Student_info)
        .filter(
            Student_info.stu_id == stu_id,
            Student_info.is_del == 0,
        )
        # 顺手把顾问一起查出来，序列化时就不用再单独发一次 SELECT
        .options(joinedload(Student_info.agent))
        .first()
    )
    if not row:
        return False, {
            'message': f'无匹配学生编号(id={stu_id})',
            'status_code': 404,
        }
    return True, row


def skip_stu(db: Session, skip: int = 0, limit: int = 100):
    """
    分页查询学生列表。
    """
    rows = (
        db.query(Student_info)
        .filter(Student_info.is_del == 0)
        .order_by(Student_info.stu_id)
        .offset(skip)
        .limit(limit)
        # joinedload：一次 JOIN 把顾问也带出来。
        .options(joinedload(Student_info.agent))
        .all()
    )
    return rows
def select_stu_class(db: Session, stu_class_id: int):
    """
    按班级查询学生。

    【不会失败】查不到就是空列表 []，直接返回列表，不返回 (ok, result)。
    （接口层会自己把"空列表"变成 404。）
    """
    rows = (
        db.query(Student_info)
        .filter(
            Student_info.stu_class_id == stu_class_id,
            Student_info.is_del == 0,
        )
        .options(joinedload(Student_info.agent))
        .all()
    )
    return rows

def select_stu_name(db: Session, stu_name: str):
    """
    按学生姓名查询（可能查到多个，因为允许重名）。
    """
    rows = (
        db.query(Student_info)
        .filter(
            Student_info.stu_name == stu_name,
            Student_info.is_del == 0,
        )
        .options(joinedload(Student_info.agent))
        .all()
    )
    return rows




def select_stu_agent(db: Session, agent_id: int):
    """
    按顾问查询学生（这个顾问招来的学生）。
    """
    rows = (
        db.query(Student_info)
        .filter(
            Student_info.agent_id == agent_id,
            Student_info.is_del == 0,
        )
        .options(joinedload(Student_info.agent))
        .all()
    )
    return rows


def update_stu_info(db: Session, stu_dict: dict, stu_id: int):
    """
    修改学生信息 —— 【只改用户真正传了的字段】。
    """
    # 1. 先查出要改的那一行
    result = db.query(Student_info).filter(
        Student_info.stu_id == stu_id,
        Student_info.is_del == 0,
    ).options(joinedload(Student_info.agent)).first()
    if not result:
        return False, {
            'message': f'无匹配学生编号(id={stu_id})',
            'status_code': 404,
        }

    # 2. 挑出真正要改的字段
    #    没传的、传了 null 的、传了空字符串的，一律当成"这个字段不动"。
    update_fields = {
        field: value
        for field, value in stu_dict.items()
        if field in STU_UPDATABLE_FIELDS and not _is_blank(value)
    }

    # 3. 一个有效字段都没有 -> 400
    if not update_fields:
        return False, {
            'message': '没有需要更新的字段（请求体里没有可修改的非空字段）',
            'status_code': 400,
        }

    # 4. 换了班级要检查新班级是否存在，否则会写进一个不存在的 stu_class_id
    if 'stu_class_id' in update_fields:
        class_error = _check_class_exists(db, update_fields['stu_class_id'])
        if class_error:
            return False, {'message': class_error, 'status_code': 404}

    # 5. 换顾问同理。
    #    只有【真的要改 agent_id】才检查。
    #    因为"修改学生"是部分更新，没传 agent_id 表示"这个字段不动"，
    #    而不是"把顾问清空"。
    if 'agent_id' in update_fields:
        agent_error = _check_agent_exists(db, update_fields['agent_id'])
        if agent_error:
            return False, {'message': agent_error, 'status_code': 404}

    # 6. 真正的更新 —— 循环外面统一提交一次
    for field, value in update_fields.items():
        setattr(result, field, value)

    db.commit()
    db.refresh(result)

    return True, {
        'message': '更新成功',
        'data': result,        # 接口层会用它拼响应
    }


def delete_stu(db: Session, stu_id: int):
    """
    软删除学生（is_del 置 1）。
    """
    result = db.query(Student_info).filter(
        Student_info.stu_id == stu_id,
        Student_info.is_del == 0,
    ).first()
    if not result:
        return False, {
            'message': f'删除失败，没有该学员(id={stu_id})',
            'status_code': 404,
        }

    result.is_del = 1
    db.commit()

    return True, {
        'message': '删除成功',
        'data': {'stu_id': stu_id},
    }
