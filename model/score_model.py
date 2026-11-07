"""
成绩表的 ORM 模型。

【业务含义】
    一行 = 一个学生某一次考试的分数。
"""
from sqlalchemy import Column, Float, Integer

from database import Base, engine


class Score(Base):
    """
    成绩表。
    """
    __tablename__ = 'scores'

    # 主键自增。一行 = 一条成绩记录。
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 学生 id。
    stu_id = Column(Integer)

    # 考试序次：第几次考试。第 1 次、第 2 次……
    test_id = Column(Integer)

    # 分数。用 Float 就行 —— 成绩不需要精确到分。
    score = Column(Float)

    # 软删除标记：0 = 正常，1 = 已删除。
    # nullable=False 表示这列一定要有值（默认值 0 就算）。
    is_del = Column(Integer, default=0, nullable=False)

    def __repr__(self):
        return f'Score< 学生编号{self.stu_id} 考核序次{self.test_id} 分数{self.score}>'

Base.metadata.create_all(engine)
