
from sqlalchemy.orm import Session

from model.class_model import Class
from model.score_model import Score
from model.student_table import Student_info


# =====================================================================
# 成绩查询要一起带出来的字段
# ---------------------------------------------------------------------
# 【班级名是怎么来的】
#     scores 表里只有 stu_id，没有班级；
#     班级在 student_info.stu_class_id 上，而班级名在 clazz.class_name，
#     所以链路是：scores -> student_info -> clazz（JOIN 两次）。
#
# 【为什么用 outerjoin 而不是 join】
#     班级是 LEFT JOIN：万一某个学生没分班（stu_class_id 为 NULL），
#     或者班级被软删了，用内连接会把这条成绩【整行查不出来】 ——
#     成绩是硬数据，不该因为班级信息缺失就消失。
#     查不到班级时 class_name 为 None，接口层转成空串，页面显示「-」。
# =====================================================================
_SCORE_COLUMNS = (
    Score.stu_id,
    Score.test_id,
    Student_info.stu_name,
    Student_info.stu_class_id,
    Class.class_name,
    Score.score,
)


def _score_query(db: Session):
    """成绩 + 学生 + 班级的公共查询（各查询函数只管加自己的 filter）。"""
    return (
        db.query(*_SCORE_COLUMNS)
        .join(Student_info, Score.stu_id == Student_info.stu_id)
        .outerjoin(Class, Student_info.stu_class_id == Class.stu_class_id)
    )


# =====================================================================
# 一、录入成绩
# =====================================================================
def score_add(db: Session, score_dict: dict):
    # ---- 1. 学生存在性检查 ----
    student = db.query(Student_info).filter(
        Student_info.stu_id == score_dict.get('stu_id'),
        Student_info.is_del == 0,
    ).first()
    if not student:
        return False, {
            'message': f'成绩录入失败，没有该学生(id={score_dict.get("stu_id")})',
            'status_code': 404,
        }

    # ---- 2. 重复检查 ----
    exist = db.query(Score).filter(
        Score.stu_id == score_dict.get('stu_id'),
        Score.test_id == score_dict.get('test_id'),
        Score.is_del == 0,
    ).first()
    if exist:
        return False, {
            'message': (
                f'你添加学生编号为{score_dict.get("stu_id")}的学生的'
                f'第{score_dict.get("test_id")}次考试成绩已经存在'
            ),
            'status_code': 409,
        }

    # ---- 3. 写入 ----
    score = Score(**score_dict)
    db.add(score)
    db.commit()
    db.refresh(score)

    return True, {'id': score.id, 'message': '成绩录入成功'}


# =====================================================================
# 二、查询成绩
# =====================================================================
def get_stu_id_score(db: Session, stu_id: int):
    rows = (
        _score_query(db)
        .filter(Score.stu_id == stu_id, Score.is_del == 0,Student_info.is_del==0)
        .order_by(Score.test_id)
        .all()
    )
    return rows


def get_test_id_score(db: Session, test_id: int):
    rows = (
        _score_query(db)
        .filter(Score.test_id == test_id, Score.is_del == 0, Student_info.is_del==0)
        .order_by(Score.stu_id)
        .all()
    )
    return rows

def score_list(q: dict, test_id: int, db: Session):
    """
    按分数区间筛选某次考试的成绩。

    【q 里的分数边界是可选的】
        score_min 传了 -> 加 Score.score >= score_min
        score_max 传了 -> 加 Score.score <= score_max
        两个都不传     -> 就是查这场考试的全部成绩

    【为什么要改成可选】
        原来这里写死 `Score.score <= q.get('score1')`，
        而 score1 是必填字段，所以过滤条件永远存在。
        现在边界不传的时候【不能】拿 None 去比较 ——
        `Score.score <= None` 会生成 `score <= NULL`，
        在 SQL 里恒为 UNKNOWN，一行都查不出来。
        所以必须按"传了才加条件"的方式拼 filter。
    """
    filters = [
        Score.test_id == test_id,
        Score.is_del == 0,
        Student_info.is_del == 0,
    ]
    if q.get('score_min') is not None:
        filters.append(Score.score >= q['score_min'])
    if q.get('score_max') is not None:
        filters.append(Score.score <= q['score_max'])

    rows = (
        _score_query(db)
        .filter(*filters)
        .order_by(Score.stu_id)
        .all()
    )
    return rows



def get_stu_test_id_score(db: Session, stu_id: int, test_id: int):
    row = (
        _score_query(db)
        .filter(
            Score.stu_id == stu_id,
            Score.test_id == test_id,
            Score.is_del == 0,
             Student_info.is_del == 0
        )
        .first()
    )
    if not row:
        return False, {
            'message': f'未找到学生{stu_id}的第{test_id}次考试成绩',
            'status_code': 404,
        }
    return True, row


# =====================================================================
# 三、修改成绩
# =====================================================================
def put_score(db: Session, stu_id: int, test_id: int, score_dict: dict):
    row = (
        db.query(Score)
        .join(Student_info, Score.stu_id == Student_info.stu_id)
        .filter(Score.test_id == test_id, Score.stu_id == stu_id,
                Score.is_del == 0,Student_info.is_del==0)
        .first()
    )
    if not row:
        return False, {'status_code':404,'message': '学生考试信息不存在'}

    row.score = score_dict.get('score')
    db.commit()
    db.refresh(row)

    # 【返回的是值，不是 ORM 对象】
    # 原来这里 return {'score': row} —— row 是 Score 实体，
    # 序列化出去是 {"id": 601, "stu_id": ..., "score": 88.0, "is_del": 0, ...}
    # 这样一个字典，调用方要拿到分数得再钻一层（detail['score']['score']）。
    # 现在直接返回 {'stu_id', 'test_id', 'score'} 三个值，一层就够。
    return True, {
        'stu_id': row.stu_id,
        'test_id': row.test_id,
        'score': row.score,
    }


# =====================================================================
# 四、删除成绩
# =====================================================================
def del_score(db: Session, stu_id: int, test_id: int):
    score = (
        db.query(Score)
        .join(Student_info, Score.stu_id == Student_info.stu_id)
        .filter(Score.test_id == test_id, Score.stu_id == stu_id,
                Score.is_del == 0, Student_info.is_del == 0)
        .first()
    )
    if not score:
        return False, {'status_code':404,'message': '学生考试信息不存在'}

    score.is_del = 1
    db.commit()

    return True, {'message': '删除成功'}


# =====================================================================
# 五、查已删除的成绩
# =====================================================================
def get_del_score(db: Session):
    """
    查已软删除的成绩。

    【为什么要 JOIN 学生表】
        原来这里直接 `db.query(Score)`，返回的是 Score 实体对象，
        而实体上没有 stu_name 这一列 —— 接口层序列化时读 row.stu_name
        直接抛 AttributeError，/score/get_del 恒定 500。

        改成和上面几个查询一样的写法：显式列出需要的列，
        把学生姓名一起 JOIN 出来。查询结果的对象就同时带着 stu_name 了。

    这里【不过滤】Student_info.is_del —— 学生被软删除了，
    他那条已删除的成绩也应该在列表里看得到。
    """
    rows = (
        _score_query(db)
        .filter(Score.is_del == 1)
        .order_by(Score.stu_id)
        .all()
    )
    return rows
