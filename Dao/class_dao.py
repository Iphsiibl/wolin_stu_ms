"""
班级 + 班主任的数据访问层（DAO 层）。

统一返回约定：详见 stu_dao.py 顶部的详细说明。
    会失败的函数返回 (ok, result)；查列表的函数直接返回列表。

【这一模块的特别之处】
    业务失败统一用 422（"数据不合法 / 无法处理"）。
    你原来的班级模块就是这么定的，接口层也是这么写的，
    这里保持不变 —— 整个项目里班级模块的语义是"你的请求内容有问题"。
"""
import logging

from sqlalchemy.orm import Session

from model.class_model import Class, Class_teacher
from model.student_table import Student_info
from model.teacher import Teacher

logger = logging.getLogger(__name__)


# =====================================================================
# 一、班级
# =====================================================================

def add_class(db: Session, class_dict: dict):
    """
    新建班级。

    业务规则：
        1. 班级名不能重复（重名班会导致统计和就业查询对不上）-> 422
        2. 授课老师必须存在                               -> 422
        3. 班主任必须存在                                 -> 422
    """
    # ---- 1. 班级重名检查 ----
    result = db.query(Class).filter(
        Class.class_name == class_dict.get('class_name'),
        Class.is_del == 0,
    ).first()
    if result:
        return False, {
            'message': '该名字的班级已存在，创建失败',
            'status_code': 422,
        }

    # ---- 2. 授课老师存在性检查 ----
    result = db.query(Teacher).filter(
        Teacher.teacher_id == class_dict.get('teacher_id'),
        Teacher.is_delete == 0,
    ).first()
    if not result:
        return False, {
            'message': '没有该id的老师，创建失败',
            'status_code': 422,
        }

    # ---- 3. 班主任存在性检查 ----
    result = db.query(Class_teacher).filter(
        Class_teacher.class_teacher_id == class_dict.get('class_teacher_id'),
        Class_teacher.is_del == 0,
    ).first()
    if not result:
        return False, {
            'message': '没有该id的班主任，创建失败',
            'status_code': 422,
        }

    # ---- 4. 写入 ----
    # 修复记录：原来这里包了一层 try/except，把数据库异常也变成"创建失败"，
    # 真实报错被盖住了。现在数据库真出错就让异常往上冒，
    # 由全局异常处理器记完整堆栈并返回 500。
    new_class = Class(**class_dict)
    db.add(new_class)
    db.commit()

    return True, {'message': '创建成功'}


def put_class(db: Session, stu_class_id: int, class_dict: dict):
    """
    修改班级信息。班级不存在 -> 422。

    注意：老师 id 和班主任 id 只有在对方【存在】时才会被写进去，
    传了但不存在就整条请求失败，避免出现"班级指向一个不存在的老师"。
    """
    data_class = db.query(Class).filter(
        Class.stu_class_id == stu_class_id,
        Class.is_del == 0,
    ).first()
    if not data_class:
        return False, {
            'message': '更新失败，没有对应班级',
            'status_code': 422,
        }

    # 先改一定没问题的两个字段
    data_class.class_name = class_dict.get('class_name')
    data_class.start_date = class_dict.get('start_date')

    # 授课老师
    result1 = db.query(Teacher).filter(
        Teacher.teacher_id == class_dict.get('teacher_id'),
        Teacher.is_delete == 0,
    ).first()
    if not result1:
        db.rollback()
        return False, {
            'message': '没有该id的老师，修改失败',
            'status_code': 422,
        }
    data_class.teacher_id = class_dict.get('teacher_id')

    # 班主任
    # 修复记录：原来这里写的是 `Class.is_del == 0` ——
    # 查的是 Class_teacher 表，过滤的却是 Class 表的字段，
    # SQL 会多出一个毫无意义的 JOIN，
    # 而且这个条件根本没起到"排除已删除班主任"的作用。
    result2 = db.query(Class_teacher).filter(
        Class_teacher.class_teacher_id == class_dict.get('class_teacher_id'),
        Class_teacher.is_del == 0,
    ).first()
    if not result2:
        db.rollback()
        return False, {
            'message': '没有对应的班主任',
            'status_code': 422,
        }
    data_class.class_teacher_id = class_dict.get('class_teacher_id')

    db.commit()
    return True, {'message': '更新班级信息成功'}


def del_class(db: Session, stu_class_id: int):
    """
    软删除班级（is_del 置 1），并且把班级下的学员一起软删除。

    为什么要连学员一起删？
    班级解散了，学员就不再属于任何班级，
    如果留着他们，统计接口按班级分组时就会出现一堆"幽灵班级"。
    """
    target = db.query(Class).filter(
        Class.stu_class_id == stu_class_id,
        Class.is_del == 0,
    ).first()
    if not target:
        return False, {
            'message': '删除失败，没有对应班级',
            'status_code': 422,
        }

    target.is_del = 1

    # 班级解散，班级下的学员一起软删除
    del_stu = db.query(Student_info).filter(
        Student_info.stu_class_id == stu_class_id,
        Student_info.is_del == 0,
    ).all()
    for i in del_stu:
        i.is_del = 1

    db.commit()
    return True, {'message': '班级解散，班级学员全部删除成功'}


def get_class(db: Session, stu_class_id: int):
    """按 id 查询单个班级。查不到 -> (False, {...404})。"""
    row = (db.query(Class.stu_class_id,Class.class_name,Class.start_date,Class.class_teacher_id
                   ,Class_teacher.class_teacher_name,Class.teacher_id,Teacher.teacher_name)
           .join(Class_teacher,Class.class_teacher_id == Class_teacher.class_teacher_id)
           .join(Teacher,Teacher.teacher_id == Class.teacher_id).filter(Class.stu_class_id == stu_class_id,
        Class.is_del == 0,Class_teacher.is_del==0,Teacher.is_delete == 0).first())
    if not row:
        return False, {
            'message': f'班级不存在(id={stu_class_id})',
            'status_code': 404,
        }
    return True, row


def get_class_students(db: Session, stu_class_id: int):
    """按 id 查询单个班级。查不到 -> (False, {...404})。"""

    # 【为什么要显式 JOIN】
    #   原来的写法是：
    #       db.query(Student_info).filter(
    #           Student_info.stu_class_id == stu_class_id,
    #           Student_info.is_del == 0, Class.is_del == 0)
    #   filter 里出现了 Class.is_del，但 Class 从来没被 JOIN 过 ——
    #   SQLAlchemy 只能把 clazz 整张表塞进 FROM，于是变成
    #   student_info × clazz 的【笛卡尔积】：
    #       查 6 个学生，数据库实际吐出 6 × 36 = 216 行。
    #   （结果凑巧没错，因为 Query.all() 会按主键去重，
    #     但每次请求都在白跑几十倍的数据量，而且 SQLAlchemy 每次都告警。
    #     更糟的是：如果所有班级都被软删了，笛卡尔积为空，
    #     明明有学生却会返回 404。）
    #
    #   现在补上真正的 JOIN 条件：学生所在的班级就是被查的这个班级。
    row = (
        db.query(Student_info)
        .join(Class, Student_info.stu_class_id == Class.stu_class_id)
        .filter(
            Student_info.stu_class_id == stu_class_id,
            Student_info.is_del == 0,
            Class.is_del == 0,
        )
        .all()
    )
    if not row:
        return False, {
            'message': f'班级不存在(id={stu_class_id})',
            'status_code': 404,
        }

    return True, row


def get_all_class(db: Session):
    """
    查询所有未删除的班级。

    【不会失败】查不到就是空列表，不是错误。
    所以直接返回列表，不返回 (ok, result)。
    """
    rows = (db.query(Class.stu_class_id,Class.class_name,Class.start_date,Class.class_teacher_id
                   ,Class_teacher.class_teacher_name,Class.teacher_id,Teacher.teacher_name)
           .join(Class_teacher,Class.class_teacher_id == Class_teacher.class_teacher_id)
           .join(Teacher,Teacher.teacher_id == Class.teacher_id).filter(
        Class.is_del == 0,Class_teacher.is_del==0,Teacher.is_delete == 0).all())
    # rows = db.query(Class).filter(Class.is_del == 0).all()
    return rows


# =====================================================================
# 二、班主任
# =====================================================================

def add_class_teacher(db: Session, class_teacher_dict: dict):
    """新增班主任。班主任名不能重复 -> 422。"""
    result = db.query(Class_teacher).filter(
        Class_teacher.class_teacher_name == class_teacher_dict.get('class_teacher_name'),
        Class_teacher.is_del == 0,
    ).first()
    if result:
        return False, {
            'message': '该名字的班主任已存在，新增失败',
            'status_code': 422,
        }

    new_class_teacher = Class_teacher(**class_teacher_dict)
    db.add(new_class_teacher)
    db.commit()

    return True, {'message': '新增班主任成功'}


def put_class_teacher(db: Session, class_teacher_id: int, class_teacher_dict: dict):
    """修改班主任信息。班主任不存在 -> 422。"""
    data_class_teacher = db.query(Class_teacher).filter(
        Class_teacher.class_teacher_id == class_teacher_id,
        Class_teacher.is_del == 0,
    ).first()
    if not data_class_teacher:
        return False, {
            'message': '更新失败，没有对应班主任',
            'status_code': 422,
        }

    data_class_teacher.class_teacher_name = class_teacher_dict.get('class_teacher_name')
    data_class_teacher.class_teacher_sex = class_teacher_dict.get('class_teacher_sex')

    db.commit()
    return True, {'message': '更新班主任信息成功'}


def del_class_teacher(db: Session, class_teacher_id: int):
    """软删除班主任（is_del 置 1）。不存在 -> 422。"""
    class_teacher = db.query(Class_teacher).filter(
        Class_teacher.class_teacher_id == class_teacher_id,
        Class_teacher.is_del == 0,
    ).first()
    if not class_teacher:
        return False, {
            'message': '删除失败，没有对应班主任',
            'status_code': 422,
        }

    class_teacher.is_del = 1
    db.commit()
    return True, {'message': '班主任删除成功'}


def get_class_teacher(db: Session, class_teacher_id: int):
    """按 id 查询单个班主任。查不到 -> (False, {...404})。"""
    row = db.query(Class_teacher).filter(
        Class_teacher.class_teacher_id == class_teacher_id,
        Class_teacher.is_del == 0,
    ).first()
    if not row:
        return False, {
            'message': f'班主任不存在(id={class_teacher_id})',
            'status_code': 404,
        }
    return True, row


def get_all_class_teacher(db: Session):
    """
    查询所有未删除的班主任。

    【不会失败】查不到就是空列表，不是错误。
    所以直接返回列表，不返回 (ok, result)。
    """
    rows = db.query(Class_teacher).filter(Class_teacher.is_del == 0).all()
    return rows
