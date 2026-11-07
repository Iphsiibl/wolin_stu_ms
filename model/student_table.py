"""
学生信息表 + 顾问表的 ORM 模型。

====================================================================
【本文件里的两个表】
====================================================================
agent        顾问。负责把学生招进来。
student_info 学生信息。有一个 agent_id 指向他招来的那个顾问。
注意 agent 和 student_info 是【一对多】：
一个顾问可以招很多学生，一个学生只属于一个顾问。
所以 student_info.agent_id 这一列允许为 NULL ——
有些学生是校方直招的、没有顾问。
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base, engine


class Agent(Base):
    """
    顾问表。
    """
    __tablename__ = "agent"

    # 主键。顾问编号，由数据库自增分配。
    agent_id = Column(Integer, primary_key=True, autoincrement=True)

    # 顾问姓名
    agent_name = Column(String(20))

    # 顾问性别，和 student_info.stu_sex 一样存字符串（'男' / '女'），
    # 统一用 schema/enums.py 里的 Sex 枚举，别再搞 int / 字符串两套写法。
    agent_sex = Column(String(20))

    # 顾问年龄。
    agent_age = Column(Integer)

    # 软删除标记：0 = 正常，1 = 已删除。
    is_del = Column(Integer, default=0)
    # 反向关系：这个顾问名下的所有学生。
    # 有了它，查顾问时可以顺手把学生带出来（配合 joinedload 避免 N+1）。
    students = relationship("Student_info", back_populates="agent")


class Student_info(Base):
    """
    学生信息表。
    """
    __tablename__ = "student_info"

    # 学生编号，主键自增。
    stu_id = Column(Integer, primary_key=True, autoincrement=True)

    # 学生姓名，数据库列长 varchar(10)，所以最多 10 个字。
    # （schema 里也做了 max_length=10 的校验，两边保持一致）
    stu_name = Column(String(10))

    # 年龄。用 Integer 不用 String —— 年龄是用来做数值比较和统计的
    #（比如"查询所有超过30岁的学员"），字符串没法直接比较大小。
    stu_age = Column(Integer)

    # 性别。存 '男' / '女' 字符串，和 schema/enums.py 的 Sex 枚举一一对应。
    stu_sex = Column(String(10))

    # 学生联系电话。
    stu_tel = Column(String(20))

    # 所在班级 id，外键指向 clazz.stu_class_id。
    stu_class_id = Column(Integer, ForeignKey('clazz.stu_class_id'))

    # 顾问id，外键指向 agent.agent_id。
    # 可以为 NULL：不是每个学生都有顾问，也可能是校方直招。
    agent_id = Column(Integer, ForeignKey('agent.agent_id'))

    # 生源地
    stu_from = Column(String(20))

    # 毕业院校
    stu_school = Column(String(20))

    # 专业
    stu_major = Column(String(20))

    # 入学时间
    enroll_date = Column(DateTime)

    # 毕业时间
    gra_date = Column(DateTime)

    # 学历
    edu_bg = Column(String(20))

    # 软删除标记：0 = 正常，1 = 已删除。
    is_del = Column(Integer, default=0)


    # 就业信息（一对一）：一个学生最多一条就业记录。
    employment = relationship('Emp', back_populates="student")

    # 所在班级（多对一）：多个学生属于同一个班级。
    clazz = relationship("Class", back_populates="students")

    # 顾问（多对一）：多个学生可以是同一个顾问招来的。
    agent = relationship("Agent", back_populates="students")

Base.metadata.create_all(engine)
