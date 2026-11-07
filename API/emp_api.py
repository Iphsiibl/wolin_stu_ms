
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from Dao.emp_dao import (add_emp, delete_emp, get_emp_filter, get_emp_page,
                          get_unemployed_students, update_emp)
from database import get_db
from schema.emp_request import EmpRequest, EmpSearch, EmpUpdate
from utils import model_to_dict

router03 = APIRouter()


# =====================================================================
# 一、新增
# =====================================================================
@router03.post("/create", status_code=status.HTTP_201_CREATED, summary='添加一条学生的就业信息')
def create_emp(emp: EmpRequest, db: Session = Depends(get_db)):
    """
    新增就业信息。
    失败原因和状态码：
        学生不存在        -> 404
        就业信息已存在    -> 409
    """
    ok, result = add_emp(db, model_to_dict(emp))
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


# =====================================================================
# 二、条件查询
# =====================================================================
@router03.get("/search", summary='依据条件查询就业信息')
def search_emp_detail(
    search: Annotated[EmpSearch, Query()],
    db: Session = Depends(get_db),
):
    """
    按条件查询就业信息：学号、姓名、公司、薪资区间、班级、学历、专业、性别。
    薪资上下限颠倒 -> 400。
    查不到 -> 返回空列表 []。
    """
    ok, result = get_emp_filter(db, model_to_dict(search))
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


# =====================================================================
# 三、分页查询
# =====================================================================
@router03.get("/page", summary='分页查询就业信息')
def search_emp_page(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    size: int = Query(20, ge=1, le=100, description="每页条数，最大100"),
    sort: str | None = Query(
        None,
        max_length=120,
        description="排序，格式 '字段:方向'，多段用逗号分隔，如 salary:desc,stu_id:asc",
    ),
    db: Session = Depends(get_db),
):
    """
    分页查询就业信息。

    sort 支持的字段：salary / stu_id / company / open_date / offer_date。
    字段不在白名单里的整段忽略，所以传脏参数也不会影响查询。
    """
    # 【不会失败】查不到就是空列表，所以没有 if not ok 分支。
    return get_emp_page(db, page, size, sort)


# 五、查询未就业的学生
# =====================================================================
@router03.get("/unemployed", summary='查询当前未就业的学生信息')
def search_unemployed_students(db: Session = Depends(get_db)):
    """
    查询当前还没就业的学生。
    "未就业" = 在 employment 表里没有一条【未删除】的就业记录。
    就业记录被软删除（is_del=1）的学生，也算未就业。

    返回格式和学生模块保持一致：{'code', 'message', 'total', 'Data'}。
    """
    return get_unemployed_students(db)

# =====================================================================
# 四、修改
# =====================================================================
@router03.put("/put/{stu_id}", summary='根据学号修改学生的就业信息')
def put_emp(
    stu_id: int,
    emp: EmpUpdate,
    db: Session = Depends(get_db),
):
    """
    修改就业信息。
    只取用户真正传了的字段（排除 None）。
    一个字段都没传，提示用户 —— 否则接口会返回"更新成功"但什么都没改。
    """
    emp_dict = model_to_dict(emp)
    emp_dict = {k: v for k, v in emp_dict.items() if v is not None}
    if not emp_dict:
        raise HTTPException(status_code=400, detail='请至少提供一个要修改的字段')

    ok, result = update_emp(db, stu_id, emp_dict)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result

# =====================================================================
# 六、删除
# =====================================================================
@router03.delete("/delete/{stu_id}", summary='删除用户信息')
def delete_employment(stu_id: int, db: Session = Depends(get_db)):
    """软删除就业信息。不存在 -> 404。"""
    ok, result = delete_emp(db, stu_id)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result
