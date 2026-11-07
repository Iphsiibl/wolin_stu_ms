"""
老师信息的接口层（API 层）。

统一失败写法（只有会失败的接口才写）：
    ok, result = xxx(db, 数据)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])

查列表的接口（/）不会失败，它的 DAO 直接返回列表，所以接口层没有 if not ok 分支。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from Dao.teacher_dao import (create_teacher, delete_teacher, get_all_teacher,
                              get_teacher_by_id, update_teacher)
from database import get_db
from schema.teacher_request import Teacher_Create, Teacher_Out, Teacher_Update

router05 = APIRouter()


# =====================================================================
# 一、新增
# =====================================================================
@router05.post("/", status_code=status.HTTP_201_CREATED, summary="新增老师")
def add_teacher(
    teacher_info: Teacher_Create,
    db: Session = Depends(get_db),
):
    """
    新增老师。

    修复记录：原来重复添加老师时返回的是 200 + {"message": "已存在该老师，添加失败"}，
    状态码骗人。现在重复 -> 409。
    """
    ok, result = create_teacher(db, teacher_info)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


# =====================================================================
# 二、查询
# =====================================================================
@router05.get("/{teacher_id}", response_model=Teacher_Out, summary="根据ID查询单个老师")
def get_one_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
):
    """
    按 id 查询单个老师。查不到 -> 404。

    response_model=Teacher_Out 的作用：
        告诉 FastAPI"返回的数据要按这个模型的字段过滤一遍"。
        好处是：模型里没写的字段（比如 is_delete）不会漏给前端，
        而且 Swagger 文档里会直接显示返回结构。

        Teacher_Out 继承了 Teacher_Create，所以它的字段都是必填的 ——
        这也意味着返回的老师必须真的有姓名和岗位，否则序列化会报错。
    """
    ok, teacher_data = get_teacher_by_id(db, teacher_id)
    if not ok:
        raise HTTPException(status_code=teacher_data['status_code'],
                            detail=teacher_data['message'])
    return teacher_data


@router05.get("/", summary="查询所有老师")
def get_teacher_list(
    db: Session = Depends(get_db),
):
    """查询所有老师（带每个老师带的班级 id 列表）。"""
    rows = get_all_teacher(db)
    return rows


# =====================================================================
# 三、修改
# =====================================================================
@router05.put("/{teacher_id}", response_model=Teacher_Out, summary="修改老师信息")
def edit_teacher(
    teacher_id: int,
    update_info: Teacher_Update,
    db: Session = Depends(get_db),
):
    """
    修改老师信息。

    用 Teacher_Update（全字段可选）而不是 Teacher_Create，
    否则改个岗位也得把姓名电话全传一遍。
    """
    ok, teacher_data = update_teacher(db, teacher_id, update_info)
    if not ok:
        raise HTTPException(status_code=teacher_data['status_code'],
                            detail=teacher_data['message'])
    return teacher_data


# =====================================================================
# 四、删除
# =====================================================================
@router05.delete("/{teacher_id}", summary="删除老师")
def remove_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
):
    """软删除老师（is_delete 置 1）。不存在 -> 404。"""
    ok, result = delete_teacher(db, teacher_id)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result
