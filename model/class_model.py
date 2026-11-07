"""
班级 + 班主任的 ORM 模型。
"""
from sqlalchemy import Column, Date, Integer, String
from sqlalchemy.orm import relationship

from database import Base, engine


class Class_teacher(Base):
    __tablename__ = 'class_teacher'

    # 班主任编号，主键自增。
    class_teacher_id = Column(Integer, primary_key=True, autoincrement=True)

    # 班主任姓名。数据库列长 varchar(10)，所以最多 10 个字。
    class_teacher_name = Column(String(10))

    # 班主任性别。varchar(1)，只存一个字符（'男' / '女'）。
    # 这一列是后来补上的（迁移 004），以前这张表根本没有性别。
    class_teacher_sex = Column(String(1))

    # 软删除标记：0 = 正常，1 = 已删除。
    is_del = Column(Integer, default=0)

class Class(Base):
    """
    班级表。
    一行 = 一个班级。注意表名是 clazz（不是 class），
    """
    __tablename__ = 'clazz'

    # 班级编号。主键不自增 —— 班级 id 是人工指定的（比如 1 号班就是 1）。
    stu_class_id = Column(Integer, primary_key=True)

    # 班级名称。
    class_name = Column(String(20))

    # 开课时间。
    start_date = Column(Date)

    # 班主任 id。
    # 这里【没有】写 ForeignKey('class_teacher.class_teacher_id')，
    # 原因：数据库里的 clazz 表本来就没有这个外键约束，
    # 写了 ORM 里的外键会和真实表结构对不上，迁移脚本会误判。
    # 业务上的"班主任必须存在"由 DAO 层检查（见 Dao/class_dao.py）。
    class_teacher_id = Column(Integer)

    # 授课老师 id，指向 teacher 表。
    # 同样没有写 ForeignKey，原因同上。
    teacher_id = Column(Integer)

    # 软删除标记：0 = 正常，1 = 已删除。
    is_del = Column(Integer, default=0)

    # 这个班里的所有学生（反向关系）。
    # 和 Student_info.clazz 是配对的（back_populates="students"），
    students = relationship("Student_info", back_populates="clazz")

Base.metadata.create_all(engine)
