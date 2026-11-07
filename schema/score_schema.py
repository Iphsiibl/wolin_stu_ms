"""
成绩的请求体校验模型（schema 层）。

【这个模型同时用于"录入成绩"和"修改成绩"两个接口】，
所以 stu_id / test_id / score 三个字段都是必填。

【字段名必须和 ORM 对齐 —— 这一条踩过坑】
    ORM（model/score_model.py）和数据库表（scores 表）都只有【一列】`score`，
    所以请求体里也只认 `score` 这一个字段。

    这里曾经写成 `score1` + `score2` 两个字段，于是：
        传 {"score": 88}      -> 422（schema 说缺 score1/score2）
        传 {"score1":88,...}  -> 500（Score(**dict) 报 'score1' is an invalid keyword）
    两种写法都进不去，等于整个成绩录入功能不可用。
    现在统一成单字段 `score`，和 ORM、数据库、前端 payload 三方一致。
"""
from pydantic import BaseModel, Field


class Score(BaseModel):
    """
    录入 / 修改成绩的请求体校验。

    一行成绩 = 一个学生 + 一次考试 + 一个分数。
    """
    # 学生编号。gt=0 = 必须大于 0。
    # 这个学生存不存在，由 DAO 层检查（Dao/score_Dao.py 的 score_add）。
    stu_id: int = Field(
        ...,
        gt=0,
        description='学生编号')

    # 考试序次：第几次考试。ge=1 = 大于等于 1（没有"第 0 次考试"）。
    test_id: int = Field(
        ...,
        ge=1,
        description='考试序次')

    # 分数。ge=0, le=100 = 0 到 100 之间。
    score: float = Field(
        ...,
        ge=0,
        le=100,
        description='分数')


class ScoreSearch(BaseModel):
    """
    按分数区间筛选成绩（GET /score/test_id1/{test_id} 用）。

    两个边界都是可选的：不传就是查全部，
    只传一个就是单向过滤（>= 下限 或 <= 上限）。
    """
    score_min: float | None = Field(default=None, ge=0, le=100, description='分数下限')
    score_max: float | None = Field(default=None, ge=0, le=100, description='分数上限')
