"""
老师信息的数据访问层（DAO 层）。

统一返回约定：详见 stu_dao.py 顶部的详细说明。
    会失败的函数返回 (ok, result)；查列表的函数直接返回列表。
"""
from collections import defaultdict

from sqlalchemy.orm import Session

from model.class_model import Class
from model.teacher import Teacher

# 允许被"修改接口"改动的字段白名单。
# 请求体里多余的 key 会被静默忽略，避免 setattr 出不存在的属性。
UPDATABLE_FIELDS = {
    'teacher_name', 'teacher_tel', 'teacher_job',
}


def create_teacher(db: Session, teacher_info):
    """
    新增老师。

    业务规则：不允许出现"同名 + 同电话"的老师 -> 409。

    注意这里的参数直接就是 Pydantic 模型对象（不是 dict），
    因为要用到 exclude_unset 这类只有模型才有的方法。
    """
    exists = db.query(Teacher).filter(
        Teacher.teacher_name == teacher_info.teacher_name,
        Teacher.teacher_tel == teacher_info.teacher_tel,
        Teacher.is_delete == 0,
    ).first()
    if exists:
        return False, {'message': '已存在该老师，添加失败', 'status_code': 409}

    db_teacher = Teacher(**teacher_info.model_dump())
    db.add(db_teacher)
    db.commit()
    db.refresh(db_teacher)

    return True, {
        'message': '添加成功',
        'data': {'teacher_id': db_teacher.teacher_id},
    }


def get_teacher_by_id(db: Session, teacher_id: int):
    """
    按 id 查老师。

    查到 -> (True, 老师对象)
    查不到 -> (False, {'message': ..., 'status_code': 404})
    """
    row = db.query(Teacher).filter(
        Teacher.teacher_id == teacher_id,
        Teacher.is_delete == 0,
    ).first()
    if not row:
        return False, {
            'message': f'该老师不存在(id={teacher_id})',
            'status_code': 404,
        }
    return True, row


def get_all_teacher(db: Session):
    """
    查询所有老师。

    【修复记录】原来的写法是 outerjoin(Class) 后把每一行都塞进列表，
    一个老师教 3 个班就会出现 3 条记录 —— "查询所有老师"却返回重复数据。
    现在改成：先查老师（1 条 SQL），再一次性查班级归属（1 条 SQL），
    在内存里拼起来。总共 2 条 SQL，不会出现 N+1。

    defaultdict(list) 的作用：
        class_map[teacher_id] 第一次访问时自动创建一个空列表，
        不用先判断 key 存不存在，代码更短。

    【不会失败】查不到就是空列表，所以直接返回列表，不返回 (ok, result)。
    """
    teachers = db.query(Teacher).filter(Teacher.is_delete == 0).all()

    class_map = defaultdict(list)
    for teacher_id, class_id in (
        db.query(Class.teacher_id, Class.stu_class_id)
        .filter(Class.is_del == 0, Class.teacher_id.isnot(None))
        .all()
    ):
        class_map[teacher_id].append(class_id)

    rows = [
        {
            'teacher_id': teacher.teacher_id,
            'teacher_name': teacher.teacher_name,
            'teacher_tel': teacher.teacher_tel,
            'teacher_job': teacher.teacher_job,
            'stu_class_ids': class_map.get(teacher.teacher_id, []),
        }
        for teacher in teachers
    ]
    return rows


def update_teacher(db: Session, teacher_id: int, update_info):
    """
    修改老师信息。老师不存在 -> 404。

    【修复记录】原来是 update_info.dict(exclude_unset=True)。
    .dict() 是 Pydantic v1 的写法，v2 里已经废弃（会打 DeprecationWarning），
    正确写法是 model_dump(exclude_unset=True)。

    exclude_unset=True 的含义：
        "只取用户在请求体里【真的写了】的字段"。
        如果用户只传了 teacher_job，那 name / tel 就不会被碰，
        也不会被 None 覆盖掉。
    """
    ok, db_teacher = get_teacher_by_id(db, teacher_id)
    if not ok:
        return False, db_teacher

    update_data = update_info.model_dump(exclude_unset=True)
    for field in UPDATABLE_FIELDS:
        if field in update_data:
            setattr(db_teacher, field, update_data[field])

    db.commit()
    db.refresh(db_teacher)

    return True, db_teacher


def delete_teacher(db: Session, teacher_id: int):
    """软删除老师（is_delete 置 1）。不存在 -> 404。"""
    ok, db_teacher = get_teacher_by_id(db, teacher_id)
    if not ok:
        return False, db_teacher

    db_teacher.is_delete = 1
    db.commit()
    db.refresh(db_teacher)

    return True, {'msg': '老师软删除成功'}
