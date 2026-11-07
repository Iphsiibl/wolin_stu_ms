
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from model.class_model import Class
from model.employment import Emp
from model.student_table import Student_info

# 就业信息要一起展示的字段。
_EMP_COLUMNS = (
    Emp.stu_id,
    Emp.company,
    Emp.salary,
    Emp.open_date,
    Emp.offer_date,
    Student_info.stu_name,
    Student_info.stu_class_id,
    Student_info.stu_major,
    Student_info.stu_school,
    Student_info.gra_date,
    Student_info.edu_bg,
    Student_info.stu_sex,
    Class.class_name,
)


def _emp_base_query(db: Session):
    """
    就业 + 学生 + 班级的公共查询。
    """
    return (
        db.query(*_EMP_COLUMNS)
        .join(Student_info, Emp.stu_id == Student_info.stu_id)
        .join(Class, Student_info.stu_class_id == Class.stu_class_id)
        .filter(Emp.is_del == 0, Student_info.is_del == 0, Class.is_del == 0)
    )


def _row_to_dict(row) -> dict:
    """查询结果行 -> 接口返回的 dict。"""
    return {
        "stu_id": row.stu_id,
        "stu_name": row.stu_name,
        "company": row.company,
        "salary": row.salary,
        "open_date": row.open_date,
        "offer_date": row.offer_date,
        "class_name": row.class_name,
        "stu_major": row.stu_major,
        "stu_school": row.stu_school,
        "gra_date": row.gra_date,
        "edu_bg": row.edu_bg,
        "stu_sex": row.stu_sex,
    }


# =====================================================================
# 一、新增
# =====================================================================
def add_emp(db: Session, emp_dict: dict):
    # ---- 1. 学生存在性检查 ----
    student = db.query(Student_info).filter(
        Student_info.stu_id == emp_dict['stu_id'],
        Student_info.is_del == 0,
    ).first()
    if not student:
        return False, {
            'message': '学生学籍不存在，不能添加就业信息。',
            'status_code': 404,
        }

    # ---- 2. 重复检查 ----
    emp = db.query(Emp).filter(
        Emp.stu_id == emp_dict['stu_id'],
        Emp.is_del == 0,
    ).first()
    if emp:
        return False, {
            'message': '该学生就业信息已经存在，不能重复添加。',
            'status_code': 409,
        }

    # ---- 3. 写入 ----
    # 【为什么这里要"复活"旧记录，而不是直接 INSERT】
    #   employment 表的 stu_id 上有唯一索引 uk_emp_stu_id，
    #   而删除走的是【软删除】（is_del=1）—— 软删除的行仍然占着这个唯一键。
    #   所以「先删掉旧的，再给同一个学生建一条新的」会直接撞唯一索引：
    #       IntegrityError: Duplicate entry 'xxx' for key 'uk_emp_stu_id'
    #   这个错误发生在 db.commit()，接口层接不住 -> 直接 500。
    #
    #   上面的重复检查只查 is_del=0 的记录，所以软删除的旧行能漏过去，
    #   然后在提交那一刻才炸。正确做法是：找到那条软删除的旧记录，
    #   把字段覆盖掉并把 is_del 改回 0 —— 对外表现就是"重新建了一条"。
    deleted_emp = db.query(Emp).filter(
        Emp.stu_id == emp_dict['stu_id'],
        Emp.is_del == 1,
    ).first()
    if deleted_emp:
        for field, value in emp_dict.items():
            setattr(deleted_emp, field, value)
        deleted_emp.is_del = 0
        db.commit()
        db.refresh(deleted_emp)
        return True, {'stu_id': deleted_emp.stu_id, 'message': '就业信息添加成功！'}

    new_emp = Emp(**emp_dict)
    db.add(new_emp)
    db.commit()
    db.refresh(new_emp)

    return True, {'stu_id': new_emp.stu_id, 'message': '就业信息添加成功！'}


# =====================================================================
# 二、条件查询
# =====================================================================
def get_emp_filter(db: Session, emp_dict: dict):
    stu_id = emp_dict.get('stu_id')
    stu_name = emp_dict.get('stu_name')
    company = emp_dict.get('company')
    salary_min = emp_dict.get('salary_min')
    salary_max = emp_dict.get('salary_max')
    class_name = emp_dict.get('class_name')
    edu_bg = emp_dict.get('edu_bg')
    stu_major = emp_dict.get('stu_major')
    stu_sex = emp_dict.get('stu_sex')

    # 薪资上下限颠倒 -> 400（参数错误）
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        return False, {
            'message': '薪资下限不能大于薪资上限',
            'status_code': 400,
        }

    query = _emp_base_query(db)

    if stu_id is not None:
        query = query.filter(Emp.stu_id == stu_id)
    if company:
        query = query.filter(Emp.company.like(f"%{company}%"))   # 模糊匹配
    if salary_min is not None:
        query = query.filter(Emp.salary >= salary_min)
    if salary_max is not None:
        query = query.filter(Emp.salary <= salary_max)
    if stu_name:
        query = query.filter(Student_info.stu_name.like(f"%{stu_name}%"))
    if class_name:
        query = query.filter(Class.class_name == class_name)
    if edu_bg:
        query = query.filter(Student_info.edu_bg == edu_bg)
    if stu_major:
        query = query.filter(Student_info.stu_major == stu_major)
    if stu_sex is not None:
        query = query.filter(Student_info.stu_sex == stu_sex)

    rows = query.all()
    return True, [_row_to_dict(r) for r in rows]


# =====================================================================
# 三、分页查询
# =====================================================================
# 可排序字段白名单。
# 前端只能排这几列 —— 字段名不经过白名单直接拼进 order_by，
# 等于把 SQL 片段的口子开给前端，所以这里先卡死。
_SORTABLE_COLUMNS = {
    'salary': Emp.salary,
    'stu_id': Emp.stu_id,
    'company': Emp.company,
    'open_date': Emp.open_date,
    'offer_date': Emp.offer_date,
}


def _apply_sort(query, sort: str | None):
    """
    把 'salary:desc,stu_id:asc' 翻译成 order_by。

    规则：
      - 字段必须命中白名单，命中不了就整段忽略；
      - 方向只认 asc / desc，其它一律按升序；
      - 多段按写的先后依次比较（等价 ORDER BY a, b）。
    """
    if not sort:
        return query

    orders = []
    for part in sort.split(','):
        bits = part.split(':')
        if len(bits) != 2:
            continue
        field = bits[0].strip()
        direction = bits[1].strip().lower()
        column = _SORTABLE_COLUMNS.get(field)
        if column is None:
            continue
        orders.append(column.desc() if direction == 'desc' else column.asc())

    return query.order_by(*orders) if orders else query


def get_emp_page(db: Session, page: int = 1, size: int = 20, sort: str | None = None):
    query = _emp_base_query(db)
    total = query.count()          # 总条数
    offset = (page - 1) * size     # 跳过前几条
    # 排序在分页【之前】做：先排好再切页，翻页之后依然是有序的
    query = _apply_sort(query, sort)
    rows = query.offset(offset).limit(size).all()

    # 总页数：比如 total=21, size=10 -> 3 页（21/10 向上取整）
    # 写成 total // size + (1 if total % size else 0) 比用 math.ceil 更直白
    total_pages = total // size + (1 if total % size else 0)

    return {
        "total": total,             # 总条数
        "page": page,               # 第几页
        "size": size,               # 每页多少条
        "total_pages": total_pages, # 总页数
        "items": [_row_to_dict(r) for r in rows],
    }


# =====================================================================
# 四、修改
# =====================================================================
def update_emp(db: Session, stu_id: int, emp_dict: dict):
    emp = db.query(Emp).filter(Emp.stu_id == stu_id, Emp.is_del == 0).first()
    if not emp:
        return False, {'message': '就业信息不存在', 'status_code': 404}

    for field, value in emp_dict.items():
        if value is not None:           # 没传（None）的字段跳过
            setattr(emp, field, value)  # 等价于 emp.company = "新公司"

    # 日期先后校验放在这里，而不是只在 schema 里。
    # 因为修改接口可能只传了其中一个日期，
    # 只有拿到库里的另一个日期，才知道顺序对不对。
    if emp.open_date and emp.offer_date and emp.offer_date < emp.open_date:
        db.rollback()      # 把刚才改的撤回去，不能半改半留
        return False, {
            'message': '收到offer的时间不能早于简历开放时间',
            'status_code': 400,
        }

    db.commit()
    db.refresh(emp)

    return True, {
        "stu_id": emp.stu_id,
        "company": emp.company,
        "salary": emp.salary,
        "open_date": emp.open_date,
        "offer_date": emp.offer_date,
    }


# =====================================================================
# 六、查询未就业的学生
# =====================================================================
def get_unemployed_students(db: Session):
    rows = (
        db.query(Student_info)
        # LEFT JOIN：就业表里没有匹配行时，左边的学生行照样保留
        .outerjoin(
            Emp,
            and_(Emp.stu_id == Student_info.stu_id, Emp.is_del == 0),
        )
        .filter(
            Student_info.is_del == 0,   # 删掉的学生不算
            Emp.id.is_(None),          # 没 JOIN 上 = 没有未删除的就业记录
        )
        .options(
            joinedload(Student_info.agent),   # 顾问名
            joinedload(Student_info.clazz),   # 班级名
        )#“查学生的时候，顺手把班级和顾问一起查回来，别等到用的时候再跑一趟”。
        .order_by(Student_info.stu_id)
        .all()
    )

    result = [
            {
            'stu_id': r.stu_id,
            'stu_name': r.stu_name,
            'stu_age': r.stu_age,
            'stu_sex': r.stu_sex,
            'stu_tel': r.stu_tel,
            # 班级名。class_teacher_id 那一列存的是班级 id，
            # 班级名要通过 clazz 关系拿。
            'stu_class_id': r.stu_class_id,
            'class_name': r.clazz.class_name if r.clazz else None,
            # 顾问
            'agent_id': r.agent_id,
            'agent_name': r.agent.agent_name if r.agent else None,
            'stu_from': r.stu_from,
            'stu_school': r.stu_school,
            'stu_major': r.stu_major,
            'enroll_date': r.enroll_date,
            'gra_date': r.gra_date,
            'edu_bg': r.edu_bg,
        }
        for r in rows
    ]

    # 【返回结构和其他模块保持一致】
    #   原来这里返回 {"total": N, "result": [...]} —— 少了一层壳，
    #   和接口层 docstring 里承诺的 {'code', 'message', 'total', 'Data'} 对不上，
    #   也和其他模块（学生 / 就业列表）不统一，前端适配层不得不为它
    #   单独加一个特判分支。现在统一成标准形状。
    return {
        'code': 200,
        'message': '查询成功',
        'total': len(result),
        'Data': result,
    }


# =====================================================================
# 七、删除
# =====================================================================
def delete_emp(db: Session, stu_id: int):
    emp = db.query(Emp).filter(Emp.stu_id == stu_id, Emp.is_del == 0).first()
    if not emp:
        return False, {'message': '就业信息不存在', 'status_code': 404}

    emp.is_del = 1
    db.commit()
    return True, {'stu_id': stu_id, 'message': '删除成功'}
