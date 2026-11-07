"""
成绩信息的接口层（API 层）。

统一失败写法（只有会失败的接口才写）：
    ok, result = xxx(db, ...)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])

查列表的接口（/stu_id/{id}、/test_id/{id}、/get_del）不会失败，
它们的 DAO 直接返回列表，所以接口层没有 if not ok 分支，
只在"查到的列表是空的"时，用 if not rows 抛 404。
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from Dao.score_Dao import (del_score, get_del_score, get_stu_id_score,
                            get_stu_test_id_score, get_test_id_score,
                            put_score, score_add,score_list)
from database import get_db
from schema.score_schema import Score, ScoreSearch

router02 = APIRouter()


def _score_to_dict(row) -> dict:
    """
    成绩输出格式，不暴露 is_del（那是内部软删除标记）。

    「班级名称」是 JOIN 班级表带出来的（scores -> student_info -> clazz），
    成绩列表要显示班级，不用前端再查一次班级表。
    学生没分班 / 班级被软删时这里是 None，转成空串，页面显示「-」。
    """
    return {
        '学生编号': row.stu_id,
        '考试序次': row.test_id,
        '学生姓名':row.stu_name,
        '班级名称': row.class_name if row.class_name else '',
        '分数': row.score
    }


# =====================================================================
# 一、录入成绩
# =====================================================================
@router02.post('/score', status_code=status.HTTP_201_CREATED, summary='录入成绩')
def post_score_api(score_data: Score, db: Session = Depends(get_db)):
    """
    录入成绩。

    业务规则（学生存不存在、成绩有没有重复录）已经下沉到 DAO 层，
    这里只负责把失败结果翻译成 HTTP 异常：
        学生不存在      -> 404
        同一场次已录过  -> 409
    """
    ok, result = score_add(db, score_data.model_dump())
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return {'msg': '成绩录入成功', 'detail': result}


# =====================================================================
# 二、查询成绩
# =====================================================================
@router02.get('/stu_id/{stu_id}', summary='查询单个学生的考试成绩')
def get_stu_id_score_api(stu_id: int, db: Session = Depends(get_db)):
    """查某个学生的所有场次成绩。查不到 -> 404。"""
    rows = get_stu_id_score(db, stu_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f'未找到该{stu_id}学生')

    return {'msg': '查询成功', 'detail': [_score_to_dict(r) for r in rows]}


@router02.get('/test_id/{test_id}', summary='查询单次考试次序的学生成绩')
def get_test_id_score_api(test_id: int, db: Session = Depends(get_db)):
    """查某次考试所有学生的成绩。查不到 -> 404。"""
    rows = get_test_id_score(db, test_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f'未找到{test_id}考试序次')

    return {'msg': '查询成功', 'detail': [_score_to_dict(r) for r in rows]}


@router02.get('/test_id1/{test_id}',summary='按分数区间查询单次考试次序的学生成绩')
def get_test_id_score_api(
    test_id: int,
    q: Annotated[ScoreSearch, Query()],
    db: Session = Depends(get_db),
):
    """
    查某次考试里【分数落在指定区间】的学生成绩。

    【为什么改成 query 参数】
        原来这里是 `def get_test_id_score_api(s: Score, test_id: int, ...)` ——
        一个 GET 请求却带着【必填的请求体】。这类请求在浏览器里发不出去
        （fetch/axios 发 GET 不带 body），Swagger 也要先填 body 才让点。
        现在改成 `?score_min=60&score_max=90` 这种标准 query 参数。

    【另一个改动：参数顺序】
        原来调用写的是 `score_list(q, db, test_id)`，
        而 DAO 的签名是 `score_list(q, test_id, db)` ——
        test_id 和 db 被传反了，DAO 里拿 db 当 test_id 去比较，直接炸。
        现在顺序对齐。

    两个边界都不传 = 查这场考试的全部成绩。
    查不到 -> 404。
    """
    result = score_list(q.model_dump(), test_id, db)

    if not result:
        raise HTTPException(status_code=404, detail=f'未找到{test_id}考试序次')

    return {'msg': '查询成功', 'detail': [_score_to_dict(r) for r in result]}

@router02.get('/stu_id/{stu_id}/test_id/{test_id}', summary='查询单个学生的单一考试序次的考试成绩')
def get_test_id_test_score_api(stu_id: int, test_id: int, db: Session = Depends(get_db)):
    """查某个学生某一场考试的成绩。查不到 -> 404。"""
    ok, result = get_stu_test_id_score(db, stu_id, test_id)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])

    return {'msg': '查询成功', 'detail': _score_to_dict(result)}


# =====================================================================
# 三、修改成绩
# =====================================================================
@router02.put('/put', summary='修改学生考试成绩')
def put_score_api(score_data: Score, db: Session = Depends(get_db)):
    """
    修改成绩。

    修复记录：原来返回的是 {'detail': True}，"detail" 里塞了个布尔值，
    前端拿到只能猜。改成返回真实的成绩数据。
    """
    ok, result = put_score(db, score_data.stu_id, score_data.test_id, score_data.model_dump())
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return {'msg': '成绩修改成功', 'detail': result}


# =====================================================================
# 四、删除成绩
# =====================================================================
@router02.delete('/del/stu_id/{stu_id}/test_id/{test_id}', summary='删除学生的考试成绩')
def remove_score_api(stu_id: int, test_id: int, db: Session = Depends(get_db)):
    """软删除某个学生的某次成绩。不存在 -> 404。"""
    ok, result = del_score(db, stu_id, test_id)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


# =====================================================================
# 五、查已删除的成绩
# =====================================================================
@router02.get('/get_del', summary='查询已删除的学生成绩')
def get_delete_score(db: Session = Depends(get_db)):
    """查询已软删除的成绩。查不到 -> 404。"""
    rows = get_del_score(db)
    if not rows:
        raise HTTPException(status_code=404, detail='未找到当前信息')

    return {'msg': '查询成功', 'detail': [_score_to_dict(r) for r in rows]}
