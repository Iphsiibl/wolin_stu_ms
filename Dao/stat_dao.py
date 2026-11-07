
from sqlalchemy import case, func, text
from sqlalchemy.orm import Session

from model.class_model import Class
from model.employment import Emp
from model.score_model import Score
from model.student_table import Student_info
from schema.enums import Sex
from utils.company_cities import locate_company


# 2.6 统计分析模块
# 2.6.1 基本信息统计
# 查询所有超过30岁的学员的信息
def get_students_over_age(db: Session, age: int = 30):
    """查询年龄大于 age 的未删除学员。"""
    rows = (
        db.query(Student_info)
        .filter(
            Student_info.is_del == 0,
            Student_info.stu_age > age,
        )
        .all()
    )
    return [
        {
            "stu_id": r.stu_id,
            "stu_name": r.stu_name,
            "stu_age": r.stu_age,
            "stu_sex": r.stu_sex,
            "stu_class_id": r.stu_class_id,
            "stu_major": r.stu_major,
            "stu_school": r.stu_school,
            "edu_bg": r.edu_bg,
        }
        for r in rows
    ]


# 统计每个班级的人数以及男生女生的人数
def get_class_statistics(db: Session):
    """统计每个班级：总人数、男生数、女生数。"""
    male_count = func.sum(case((Student_info.stu_sex == Sex.MALE, 1), else_=0))
    female_count = func.sum(case((Student_info.stu_sex == Sex.FEMALE, 1), else_=0))
    total_count = func.count(Student_info.stu_id)

    rows = (
        db.query(
            Student_info.stu_class_id.label("stu_class_id"),
            total_count.label("total"),
            Class.class_name.label('class_name'),
            male_count.label("male_count"),
            female_count.label("female_count"),
        )
        .join(Class, Student_info.stu_class_id == Class.stu_class_id)
        .filter(Student_info.is_del == 0, Class.is_del == 0)
        .group_by(Student_info.stu_class_id, Class.stu_class_id)
        .all()
    )

    return [
        {
            "class_id": r.stu_class_id,
            "class_name": r.class_name,
            "total": r.total,
            "male_count": int(r.male_count or 0),      # sum 可能返回 None，兜底
            "female_count": int(r.female_count or 0),
        }
        for r in rows
    ]


# 2.6.2 成绩统计
# 查询每次考试成绩都在80分以上的学生的编号，姓名和成绩
def get_students_all_above_80(db: Session):
    """查询每次考试成绩都 >= 80 的学生编号、姓名、成绩（每次一行）。"""
    # 1. 子查询：先找出"最低分 >= 80"的学生
    subq = (
        db.query(Score.stu_id)
        .filter(Score.is_del == 0)
        .group_by(Score.stu_id)
        .having(func.min(Score.score) >= 80)
        .subquery()
    )

    # 2. 再查这些学生的每次成绩
    rows = (
        db.query(
            Student_info.stu_id,
            Student_info.stu_name,
            Score.test_id,
            Score.score,
        )
        .join(Score, Score.stu_id == Student_info.stu_id)
        .join(subq, subq.c.stu_id == Student_info.stu_id)
        .filter(Score.is_del == 0, Student_info.is_del == 0)
        .order_by(Student_info.stu_id, Score.test_id)
        .all()
    )

    return [
        {
            "stu_id": r.stu_id,
            "stu_name": r.stu_name,
            "test_id": r.test_id,
            "score": r.score,
        }
        for r in rows
    ]


# 查询有两次以上不及格的学生的姓名，班级和不及格成绩
def get_students_failed_twice(db: Session, pass_score: float = 60):
    """查询不及格次数 >= 2 的学生：姓名、班级、不及格成绩。"""
    # 1. 子查询：不及格次数 >= 2 的学生
    subq = (
        db.query(Score.stu_id)
        .filter(Score.is_del == 0, Score.score < pass_score)
        .group_by(Score.stu_id)
        .having(func.count() >= 2)
        .subquery()
    )

    # 2. 查这些学生的所有不及格成绩
    rows = (
        db.query(
            Student_info.stu_id,
            Student_info.stu_name,
            Student_info.stu_class_id,
            Score.test_id,
            Score.score,
        )
        .join(Score, Score.stu_id == Student_info.stu_id)
        .join(subq, subq.c.stu_id == Student_info.stu_id)
        .filter(
            Score.is_del == 0,
            Student_info.is_del == 0,
            Score.score < pass_score,      # 只列不及格的成绩
        )
        .order_by(Student_info.stu_id, Score.test_id)
        .all()
    )

    return [
        {
            "stu_id": r.stu_id,
            "stu_name": r.stu_name,
            "class_id": r.stu_class_id,
            "test_id": r.test_id,
            "score": r.score,
        }
        for r in rows
    ]


# 统计每次考试每个班级的平均分，按照从高到低排序
def get_avg_score_by_test_class(db: Session):
    """统计每次考试、每个班级的平均分，按平均分从高到低排序。"""
    avg_score = func.avg(Score.score)

    rows = (
        db.query(
            Score.test_id.label("test_id"),
            Student_info.stu_class_id.label("stu_class_id"),
            avg_score.label("avg_score"),
            Class.class_name.label("class_name"),
        )
        .join(Student_info, Student_info.stu_id == Score.stu_id)
        .join(Class, Class.stu_class_id == Student_info.stu_class_id)
        .filter(Score.is_del == 0, Student_info.is_del == 0, Class.is_del == 0)
        .group_by(Score.test_id, Student_info.stu_class_id)
        .order_by(avg_score.desc())
        .all()
    )

    return [
        {
            "test_id": r.test_id,
            "class_id": r.stu_class_id,
            "class_name": r.class_name,
            "avg_score": round(float(r.avg_score), 2) if r.avg_score is not None else None,
        }
        for r in rows
    ]


# 2.6.3 就业统计
# 统计就业薪资最高的前五名学生的姓名，班级和就业时间，就业公司
def get_top5_salary(db: Session):
    """薪资最高的前五名学生：姓名、班级、就业时间、就业公司。"""
    rows = (
        db.query(
            Student_info.stu_id,
            Student_info.stu_name,
            Student_info.stu_class_id.label("stu_class_id"),
            Emp.offer_date,               # 就业时间 = 收到 offer 的时间
            Emp.company,
            Emp.salary,
        )
        .join(Emp, Emp.stu_id == Student_info.stu_id)
        .join(Class, Class.stu_class_id == Student_info.stu_class_id)
        .filter(
            Emp.is_del == 0,
            Student_info.is_del == 0,
            Class.is_del == 0,
        )
        .order_by(Emp.salary.desc())
        .limit(5)
        .all()
    )

    return [
        {
            "stu_id": r.stu_id,
            "stu_name": r.stu_name,
            "class_id": r.stu_class_id,
            "offer_date": r.offer_date,
            "company": r.company,
            "salary": float(r.salary) if r.salary is not None else None,
        }
        for r in rows
    ]


# 统计每个学生的就业时长（offer下发时间-就业开放时间）
def get_employment_duration(db: Session):
    """每个学生的就业时长：offer_date - open_date。只算两个日期都有值的学生。"""
    duration = func.timestampdiff(
        text('second'),
        Emp.open_date,
        Emp.offer_date,
    )
    rows = (
        db.query(
            Student_info.stu_id,
            Student_info.stu_name,
            Student_info.stu_class_id.label("stu_class_id"),
            Emp.open_date,
            Emp.offer_date,
            duration.label("second"),
        )
        .join(Emp, Emp.stu_id == Student_info.stu_id)
        .filter(
            Emp.is_del == 0,
            Student_info.is_del == 0,
            Emp.open_date.isnot(None),     # 必须有开放时间
            Emp.offer_date.isnot(None),    # 必须有 offer 时间，否则算不出时长
        )
        .order_by(duration, Student_info.stu_id)
        .all()
    )

    data = []
    for r in rows:
        dhms = _seconds_to_dhms(r.second)  # 拆一份
        data.append({
            "stu_id": r.stu_id,
            "stu_name": r.stu_name,
            "class_id": r.stu_class_id,
            "open_date": r.open_date,
            "offer_date": r.offer_date,
            "duration_text": (
                f'{dhms["days"]}天{dhms["hours"]}小时{dhms["minutes"]}分{dhms["seconds"]}秒'
                if dhms else None
            ),
        })
    return data


# 统计每个班级的平均就业时长（只统计进入就业阶段的学生，也就是有就业开放时间）
def get_avg_duration_by_class(db: Session):
    """每个班级的平均就业时长，精确到天/时/分/秒。"""
    duration_seconds = func.timestampdiff(
        text('SECOND'), Emp.open_date, Emp.offer_date
    )
    avg_seconds = func.avg(duration_seconds)

    rows = (
        db.query(
            Student_info.stu_class_id.label("stu_class_id"),
            avg_seconds.label("avg_seconds"),
            func.count(Emp.stu_id).label("student_count"),
        )
        .join(Emp, Emp.stu_id == Student_info.stu_id)
        .join(Class, Class.stu_class_id == Student_info.stu_class_id)
        .filter(
            Emp.is_del == 0,
            Student_info.is_del == 0,
            Class.is_del == 0,
            Emp.open_date.isnot(None),
            Emp.offer_date.isnot(None),
        )
        .group_by(Student_info.stu_class_id)
        .order_by(avg_seconds.asc())
        .all()
    )

    data = []
    for r in rows:
        # avg 返回 float/Decimal，四舍五入成整数秒再拆
        avg_total = round(float(r.avg_seconds)) if r.avg_seconds is not None else None
        dhms = _seconds_to_dhms(avg_total)
        data.append({
            "class_id": r.stu_class_id,
            "student_count": r.student_count,
            "duration_text": (
                f'{dhms["days"]}天{dhms["hours"]}小时{dhms["minutes"]}分{dhms["seconds"]}秒'
                if dhms else None
            ),
        })
    return data


# 按省份统计就业去向（就业热力地图的数据源）
def get_employment_destination(db: Session):
    """按省份聚合就业去向：人数、平均/最高薪资、去向公司。

    employment 表里没有地区字段，所以省份是拿公司名反查出来的
    （见 utils/company_cities.py）。查不到归属的公司统一算到「其他」，
    前端不会把它画到地图上，但人数照样统计得到，不会丢人。
    """
    rows = (
        db.query(
            Emp.company,
            Emp.salary,
            Student_info.stu_id,
            Student_info.stu_name,
        )
        .join(Student_info, Student_info.stu_id == Emp.stu_id)
        .filter(
            Emp.is_del == 0,
            Student_info.is_del == 0,
        )
        .all()
    )

    # 省份 -> 聚合数据
    provinces: dict[str, dict] = {}
    for r in rows:
        city, province = locate_company(r.company)
        salary = float(r.salary) if r.salary is not None else 0.0

        p = provinces.setdefault(province, {
            'count': 0,
            'salary_sum': 0.0,
            'max_salary': 0.0,
            'cities': {},      # 城市 -> 人数
            'companies': {},   # 公司名 -> {city, count, salary_sum, max_salary}
        })
        p['count'] += 1
        p['salary_sum'] += salary
        p['max_salary'] = max(p['max_salary'], salary)
        p['cities'][city] = p['cities'].get(city, 0) + 1

        c = p['companies'].setdefault(r.company, {
            'city': city,
            'count': 0,
            'salary_sum': 0.0,
            'max_salary': 0.0,
        })
        c['count'] += 1
        c['salary_sum'] += salary
        c['max_salary'] = max(c['max_salary'], salary)

    data = []
    for province, p in provinces.items():
        # 该省人数最多的城市（人数一样时按城市名排，保证结果稳定）
        main_city = sorted(p['cities'].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

        # 去向公司：人数多的排前面，人数一样看最高薪资，再一样按公司名
        companies = sorted(
            p['companies'].items(),
            key=lambda kv: (-kv[1]['count'], -kv[1]['max_salary'], kv[0]),
        )

        data.append({
            "province": province,
            "city": main_city,
            "count": p['count'],
            "avg_salary": round(p['salary_sum'] / p['count'], 2) if p['count'] else 0.0,
            "max_salary": round(p['max_salary'], 2),
            "companies": [
                {
                    "company": name,
                    "city": info['city'],
                    "count": info['count'],
                    "avg_salary": round(info['salary_sum'] / info['count'], 2) if info['count'] else 0.0,
                    "max_salary": round(info['max_salary'], 2),
                }
                for name, info in companies
            ],
        })

    # 人数多的省排前面
    data.sort(key=lambda d: (-d['count'], d['province']))
    return data


def _seconds_to_dhms(total_seconds):
    """把总秒数拆成 天/时/分/秒。例：90061 秒 -> {'days': 1, 'hours': 1, ...}"""
    if total_seconds is None:
        return None

    negative = total_seconds < 0          # offer_date 比 open_date 还早，数据异常
    total_seconds = abs(total_seconds)

    days, rem = divmod(total_seconds, 86400)      # 1 天 = 86400 秒
    hours, rem = divmod(rem, 3600)                # 1 小时 = 3600 秒
    minutes, seconds = divmod(rem, 60)

    return {
        "days": -days if negative else days,
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds,
        "total_seconds": -abs(total_seconds) if negative else total_seconds,
    }
