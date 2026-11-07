"""
就业信息表的 ORM 模型。

"""
from sqlalchemy import (Column, DateTime, ForeignKey, Integer, Numeric,
                        String)
from sqlalchemy.orm import relationship
from database import Base, engine
class Emp(Base):
    """
    就业信息表。
    """
    __tablename__ = 'employment'
    __table_args__ = {'comment': '学生就业信息表'}

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键自增')
    stu_id = Column(Integer, ForeignKey('student_info.stu_id'), comment='关联学生表，外键')
    open_date = Column(DateTime, comment='简历开放日期')
    offer_date = Column(DateTime, comment='收到offer日期')
    company = Column(String(50), nullable=False, comment='就业公司')
    salary = Column(Numeric(10, 2), nullable=False, comment='薪资，单位：元/月')
    is_del = Column(Integer, default=0, comment='是否删除：0未删除，1已删除')

    # 指向学生信息（反向关系）。
    # 和 Student_info.employment 是配对的（back_populates="student"）。
    student = relationship("Student_info", back_populates="employment")

Base.metadata.create_all(engine)
