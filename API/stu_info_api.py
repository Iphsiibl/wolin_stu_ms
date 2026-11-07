
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from Dao.stu_dao import (add_agent, add_stu, delete_agent, delete_stu,
                          select_agent, select_agent_list,
                          select_stu_agent, select_stu_class, select_stu_id,
                          select_stu_name, skip_stu, update_agent,
                          update_stu_info)
from database import get_db
from schema.student_request import (Agent_request, Student_request,
                                    UpdateAgent, UpdateStudent)
from utils import model_to_dict

# APIRouter = 路由器的"空壳"。真正的路径前缀和分组标签在 main.py 里
# 通过 app.include_router(router01, prefix='/student') 挂上去。
router01 = APIRouter()
router07 = APIRouter()


# =====================================================================
# 内部工具：把一行学生记录变成接口要返回的 dict
# =====================================================================

def _stu_to_dict(row) -> dict:
    """
    学生信息输出格式。
    """
    return {
        'stu_id': row.stu_id,
        'stu_name': row.stu_name,
        'stu_age': row.stu_age,
        'stu_sex': row.stu_sex,
        'stu_tel': row.stu_tel,
        'stu_class_id': row.stu_class_id,
        # 顾问信息。顾问可能为空（不是每个学生都有顾问），
        # 所以这里要用 row.agent 的判空，不能直接 row.agent.agent_name。
        'agent_id': row.agent_id,
        'agent_name': row.agent.agent_name if row.agent else None,
        'stu_from': row.stu_from,
        'stu_school': row.stu_school,
        'stu_major': row.stu_major,
        'enroll_date': row.enroll_date,
        'gra_date': row.gra_date,
        'edu_bg': row.edu_bg,
    }


def _agent_to_dict(row) -> dict:
    """顾问信息输出格式。"""
    return {
        'agent_id': row.agent_id,
        'agent_name': row.agent_name,
        'agent_sex': row.agent_sex,
        'agent_age': row.agent_age,
    }


# =====================================================================
# 一、顾问
# =====================================================================

@router07.post('/add_agent', status_code=status.HTTP_201_CREATED, summary='新增顾问')
def add_agent_api(agent_data: Agent_request, db: Session = Depends(get_db)):
    """
    新增顾问。
    重名 -> 409（DAO 返回的 status_code 就是 409）。
    """
    ok, result = add_agent(db, model_to_dict(agent_data))
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


@router07.get('/agent', summary='查询所有顾问')
def list_agent_api(db: Session = Depends(get_db)):
    """
    查询所有【未被删除】的顾问。

    新增/修改学生时要选顾问，前端得先能拿到顾问列表 —— 光有 agent_id 字段是没法用的。
    """
    rows = select_agent_list(db)

    return {
        'code': 200,
        'message': '查询成功',
        'total': len(rows),
        'Data': [_agent_to_dict(r) for r in rows],
    }


@router07.get('/select_agent', summary='按id查询单个顾问')
def select_agent_api(agent_id: int, db: Session = Depends(get_db)):
    """
    按 id 查询【单个】顾问。

    查不到 -> 404（原来你写的是 422，而且文案写的是"无匹配学生编号"，
    明明查的是顾问，这里一并修正）。
    """
    ok, row = select_agent(db, agent_id)
    if not ok:
        raise HTTPException(status_code=row['status_code'], detail=row['message'])

    return {
        'code': 200,
        'message': '查询成功',
        'Data': _agent_to_dict(row),
    }


@router07.put('/update_agent', summary='修改顾问')
def update_agent_api(
    agent_id: int,
    agent_data: UpdateAgent,
    db: Session = Depends(get_db),
):
    """
    修改顾问。

    用 UpdateAgent（所有字段可选），而不是 Agent_request（所有字段必填）——
    否则"只改个名字"也得把姓名/性别/年龄全传一遍。
    """
    ok, result = update_agent(db, agent_id, model_to_dict(agent_data))
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return {
        'code': 200,
        'message': '更新成功',
        'Data': result.get('data'),
    }


@router07.delete('/delete_agent', summary='删除顾问')
def delete_agent_api(agent_id: int, db: Session = Depends(get_db)):
    """
    删除顾问（软删除）。
    """
    ok, result = delete_agent(db, agent_id)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return {'code': 200, 'message': '删除成功'}


# =====================================================================
# 二、学生信息
# =====================================================================

@router01.post('/add_stu', status_code=status.HTTP_201_CREATED, summary='新增学生')
def create_student_api(stu_data: Student_request, db: Session = Depends(get_db)):
    """
    新增学生。
    校验分工：
        · 字段格式（手机号、年龄、性别）-> Pydantic 层，422
    接口层只负责把 DAO 的失败结果翻译成 HTTP 异常。
    """
    ok, result = add_stu(db, model_to_dict(stu_data))
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


@router01.get('/select_stu_id', summary='按照学生id查询')
def query_stu_id_api(stu_id: int, db: Session = Depends(get_db)):
    """
    按学生 id 查询。
    注意参数要有类型标注（stu_id: int）
    """
    ok, student = select_stu_id(db, stu_id)
    if not ok:
        raise HTTPException(status_code=student['status_code'], detail=student['message'])

    return {'code': 200, 'message': '查询成功', 'Data': _stu_to_dict(student)}

@router07.get('/select_stu_agent', summary='按顾问查询学生')
def query_stu_agent_api(agent_id: int, db: Session = Depends(get_db)):
    """
    查某个顾问招来的学生。
    """
    rows = select_stu_agent(db, agent_id)
    if not rows:
        raise HTTPException(status_code=404, detail='该顾问名下没有学生')

    return {
        'code': 200,
        'message': '查询成功',
        'Data': [_stu_to_dict(r) for r in rows],
    }



@router01.get('/select_stu_skip', summary='分页查询学生')
def query_stu_skip_api(
    skip: int = Query(0, ge=0, description='跳过前几条（第几页从 0 开始数）'),
    limit: int = Query(100, ge=0, description='这一页最多返回几条'),
    db: Session = Depends(get_db),
):
    """
    分页查询学生列表。

    skip  = 跳过几条（第几页从 0 开始数）
    limit = 最多返回几条
    【不会失败】查不到就是空列表 []，所以没有 if not ok 分支。
    """
    rows = skip_stu(db, skip, limit)

    return {
        'code': 200,
        'message': '查询成功',
        'total': len(rows),
        'Data': [_stu_to_dict(r) for r in rows],
    }


@router01.get('/select_stu_name', summary='按姓名查询学生')
def query_stu_name_api(stu_name: str, db: Session = Depends(get_db)):
    """
    按姓名查询学生（可能查到多个）。

    查不到 -> 404。
    """
    rows = select_stu_name(db, stu_name)
    if not rows:
        raise HTTPException(status_code=404, detail='没有匹配学生姓名')

    return {
        'code': 200,
        'message': '查询成功',
        'Data': [_stu_to_dict(r) for r in rows],
    }


@router01.get('/select_stu_class', summary='按班级查询学生')
def query_stu_class_api(stu_class_id: int, db: Session = Depends(get_db)):
    """
    按班级查询学生。
    """
    rows = select_stu_class(db, stu_class_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f'无匹配班级编号(id={stu_class_id})')

    return {
        'code': 200,
        'message': '查询成功',
        'Data': [_stu_to_dict(r) for r in rows],
    }


@router01.put('/update_stu_class', summary='更改学生信息')
def update_stu_info_api(
    stu_id: int,
    stu_info: UpdateStudent,
    db: Session = Depends(get_db),
):
    """
    修改学生信息 —— 【只改用户传了的字段】。
    """
    update_dict = model_to_dict(stu_info, exclude_unset=True)

    ok, result = update_stu_info(db, update_dict, stu_id)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])

    return {
        'code': 200,
        'message': '更新成功',
        'Data': _stu_to_dict(result['data']),
    }


@router01.delete('/delete_stu', summary='删除学生')
def delete_stu_api(stu_id: int, db: Session = Depends(get_db)):
    """
    删除学生（软删除）。
    """
    ok, result = delete_stu(db, stu_id)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])

    return {'code': 200, 'message': '删除成功'}
