"""
老师信息表的 ORM 模型。
"""
from sqlalchemy import Column, Integer, String

from database import Base, engine


class Teacher(Base):
    """
    老师信息表。

    一行 = 一个老师。班级表(clazz)里有一个 teacher_id 指向这一行，
    表示"这个班是哪个老师上的"。
    """
    __tablename__ = 'teacher'

    # 老师编号，主键自增。
    teacher_id = Column(Integer, primary_key=True, autoincrement=True)

    # 老师姓名。nullable=False = 这一列不能为空（数据库层面也会拦）。
    teacher_name = Column(String(20), nullable=False)

    # 老师电话。选填，可以为空。
    teacher_tel = Column(String(20))

    # 老师岗位（比如"讲师"、"高级讲师"）。不能为空。
    teacher_job = Column(String(20), nullable=False)

    # 软删除标记：0 = 正常，1 = 已删除。
    # 【注意】这一列叫 is_delete，而其他表叫 is_del —— 名字不统一是历史遗留。
    is_delete = Column(Integer, default=0)

Base.metadata.create_all(engine)
