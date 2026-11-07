"""
统计分析的接口层（API 层）。

====================================================================
【这一层的统一写法】
====================================================================
    rows = xxx(db, ...)
    return rows

统计类查询【不会失败】：查不到就是空列表 []，那是正常业务状态，
所以 200 + [] 就够了，接口层没有 if not ok 分支
（它们的 DAO 直接返回数据，没有 ok 标志可判断）。

真正出错了（比如数据库连不上），异常会直接往上冒，变成 500。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from Dao.stat_dao import (get_avg_duration_by_class, get_avg_score_by_test_class,
                          get_class_statistics, get_employment_destination,
                          get_employment_duration,
                          get_students_all_above_80, get_students_failed_twice,
                          get_students_over_age, get_top5_salary)
from database import get_db

router06 = APIRouter()


# =====================================================================
# 2.6.1 基本信息统计
# =====================================================================

# 查询所有超过30岁的学员的信息
@router06.get("/students/over_age", summary='查询所有超过指定年龄的学员的信息')
def students_over_age(age: int = Query(30, ge=0, description='年龄下限'), db: Session = Depends(get_db)):
    """查询年龄【大于】age 的未删除学员。"""
    rows = get_students_over_age(db, age)
    return rows


@router06.get("/class/statistics", summary='统计每个班级的人数以及男生女生的人数')
def class_statistics(db: Session = Depends(get_db)):
    """
    统计每个班级：总人数、男生数、女生数。

    修复记录：以前代码拿字符串 '男'/'女' 去比一个 int 列，
    MySQL 会把 '男' 隐式转成 0，
    于是"男生数"和"女生数"统计到的是同一批人（两个数字永远相等）。
    """
    rows = get_class_statistics(db)
    return rows


# =====================================================================
# 2.6.2 成绩统计
# =====================================================================

# 查询每次考试成绩都在80分以上的学生的编号，姓名和成绩
@router06.get("/score/all_above_80", summary='查询每次考试成绩都在80分以上的学生的编号，姓名和成绩')
def students_all_above_80(db: Session = Depends(get_db)):
    """查询【每次】考试都 >= 80 分的学生（每个考试场次一行）。"""
    rows = get_students_all_above_80(db)
    return rows


# 查询有两次以上不及格的学生的姓名，班级和不及格成绩
@router06.get("/score/failed_twice", summary='查询有两次以上不及格的学生的姓名，班级和不及格成绩')
def students_failed_twice(
    pass_score: float = Query(60, ge=0, le=100, description='及格线'),
    db: Session = Depends(get_db),
):
    """查询不及格次数 >= 2 的学生，列出他们的每一门不及格成绩。"""
    rows = get_students_failed_twice(db, pass_score)
    return rows


# 统计每次考试每个班级的平均分，按照从高到低排序
@router06.get("/score/avg_by_class", summary='统计每次考试每个班级的平均分，按照从高到低排序')
def avg_score_by_class(db: Session = Depends(get_db)):
    """每次考试、每个班级的平均分，按平均分从高到低排序。"""
    rows = get_avg_score_by_test_class(db)
    return rows


# =====================================================================
# 2.6.3 就业统计
# =====================================================================

# 统计就业薪资最高的前五名学生的姓名，班级和就业时间，就业公司
@router06.get("/emp/top5_salary", summary='统计就业薪资最高的前五名学生的姓名，班级和就业时间，就业公司')
def top5_salary(db: Session = Depends(get_db)):
    """薪资最高的前五名学生。"""
    rows = get_top5_salary(db)
    return rows


# 统计每个学生的就业时长（offer下发时间-就业开放时间）
@router06.get("/emp/duration", summary='统计每个学生的就业时长（offer下发时间-就业开放时间）')
def employment_duration(db: Session = Depends(get_db)):
    """每个学生的就业时长 = 收到 offer 的时间 - 简历开放的时间。"""
    rows = get_employment_duration(db)
    return rows


# 统计每个班级的平均就业时长（只统计进入就业阶段的学生，也就是有就业开放时间）
@router06.get("/emp/avg_duration_by_class", summary='统计每个班级的平均就业时长（只统计进入就业阶段的学生，也就是有就业开放时间）')
def avg_duration_by_class(db: Session = Depends(get_db)):
    """每个班级的平均就业时长，精确到天/时/分/秒。"""
    rows = get_avg_duration_by_class(db)
    return rows


# 按省份统计就业去向（就业热力地图的数据源）
@router06.get("/emp/destination", summary='按省份统计就业去向（就业热力地图的数据源）')
def employment_destination(db: Session = Depends(get_db)):
    """
    按省份聚合就业去向：人数、平均薪资、最高薪资、去向公司。

    employment 表没有地区字段，省份是拿公司名反查公司总部所在地得到的
    （映射表在 utils/company_cities.py），
    查不到归属的公司统一归到「其他」。
    """
    rows = get_employment_destination(db)
    return rows
