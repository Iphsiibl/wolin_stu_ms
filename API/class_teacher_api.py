from fastapi import APIRouter, Depends, HTTPException, status

from Dao.class_dao import (add_class, add_class_teacher, del_class,
                            del_class_teacher, get_all_class,
                            get_all_class_teacher, get_class,
                            get_class_teacher, put_class, put_class_teacher,get_class_students)
from database import get_db
from schema.class_schema import Class_Request, Class_teacher_Request

router08 = APIRouter()

# ============================================================================
# 班主任
# ============================================================================

# 定义新增班主任信息接口
@router08.post('/class_teacher', status_code=status.HTTP_201_CREATED, summary='新增班主任')
def creat_class_teacher1(class_teacher: Class_teacher_Request, db=Depends(get_db)):
    """
    新增班主任。

    这张表以前【没有任何接口能写】，但"新建班级"又要求班主任必须存在，
    班级模块因此陷入死锁 —— 现在补上了。
    """
    ok, result = add_class_teacher(db, class_teacher.model_dump())
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


# 定义修改班主任信息接口
@router08.put('/update_class_teacher/{class_teacher_id}', summary='修改班主任信息')
def update_class_teacher1(class_teacher_id: int, class_teacher: Class_teacher_Request, db=Depends(get_db)):
    """修改班主任信息。班主任不存在 -> 422。"""
    ok, result = put_class_teacher(db, class_teacher_id, class_teacher.model_dump())
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


# 定义软删除班主任信息接口
@router08.delete('/delete_class_teacher/{class_teacher_id}', summary='删除班主任')
def del_class_teacher1(class_teacher_id: int, db=Depends(get_db)):
    """
    软删除班主任。不存在 -> 422。

    修复记录：原来函数参数写的是 teacher_id，但路径是 {class_teacher_id}。
    FastAPI 找不到路径参数，就把 teacher_id 当成了【必填的 query 参数】，
    于是这个接口永远返回 422：
        {"detail": [{"type": "missing", "loc": ["query", "teacher_id"], ...}]}

    记住这条规则：路径 {xxx} 里的名字必须和函数参数名【完全一致】。
    """
    ok, result = del_class_teacher(db, class_teacher_id)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


# 定义查询班主任信息接口
@router08.get('/get_class_teacher/{class_teacher_id}', summary='查询班主任信息')
def get_class_teacher1(class_teacher_id: int, db=Depends(get_db)):
    """按 id 查询单个班主任。查不到 -> 404。"""
    ok, result = get_class_teacher(db, class_teacher_id)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])

    return {'message': '查询成功',
            '班主任id': result.class_teacher_id,
            '班主任名字': result.class_teacher_name,
            '班主任性别': result.class_teacher_sex}


# 定义查询所有班主任的信息接口
@router08.get('/all_class_teacher', summary='查询所有班主任信息')
def get_all_class_teacher1(db=Depends(get_db)):
    """
    查询所有班主任。

    新建班级的接口要填"班主任id"，
    前端得先能拿到班主任列表才填得出来 —— 这就是补这个接口的原因。
    """
    rows = get_all_class_teacher(db)

    return [{'message': '查询成功',
             '班主任id': i.class_teacher_id,
             '班主任名字': i.class_teacher_name,
             '班主任性别': i.class_teacher_sex}
            for i in rows]