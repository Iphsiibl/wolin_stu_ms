"""
班级 + 班主任的接口层（API 层）。

统一失败写法（只有会失败的接口才写）：
    ok, result = xxx(db, ...)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])

查列表的接口（/all_class、/all_class_teacher）不会失败，
它们的 DAO 直接返回列表，所以接口层没有 if not ok 分支。

【这个模块的返回体格式是你自己定的】
    查询单个   -> {'message': ..., '班级id': ..., ...}
    查询所有   -> [ {...}, {...} ]
    新增/修改 -> {'message': '创建成功'}
    这里保持原样，不改成别的模块那种 {'code','message','Data'} 的格式。
"""
from fastapi import APIRouter, Depends, HTTPException, status

from Dao.class_dao import (add_class, add_class_teacher, del_class,
                            del_class_teacher, get_all_class,
                            get_all_class_teacher, get_class,
                            get_class_teacher, put_class, put_class_teacher,get_class_students)
from database import get_db
from schema.class_schema import Class_Request, Class_teacher_Request

router04 = APIRouter()


# ============================================================================
# 班级
# ============================================================================

# 定义新增班级信息接口
@router04.post('/', status_code=status.HTTP_201_CREATED, summary='新建班级')
def creat_class1(clazz: Class_Request, db=Depends(get_db)):
    """
    新建班级。

    失败（重名 / 老师不存在 / 班主任不存在）-> 422。

    修复记录：原来失败时也是 `return result`，HTTP 状态码还是 200，
    只有 body 里写着"创建失败"。前端只能靠猜 body 判断成功与否。
    现在失败一律抛 HTTPException，让状态码说真话。
    """
    ok, result = add_class(db, clazz.model_dump())
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


# 定义修改班级信息接口
@router04.put('/update_class/{stu_class_id}', summary='修改班级信息')
def update_class1(stu_class_id: int, clazz: Class_Request, db=Depends(get_db)):
    """修改班级信息。班级不存在 / 老师或班主任不存在 -> 422。"""
    ok, result = put_class(db, stu_class_id, clazz.model_dump())
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


# 定义软删除班级信息接口
@router04.delete('/delete_class/{stu_class_id}', summary='删除班级以及班级学员')
def del_class1(stu_class_id: int, db=Depends(get_db)):
    """软删除班级，班级下的学员也一起软删除。不存在 -> 422。"""
    ok, result = del_class(db, stu_class_id)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])
    return result


# 定义查询班级信息接口
@router04.get('/get_class/{stu_class_id}', summary='查询班级信息')
def get_class1(stu_class_id: int, db=Depends(get_db)):
    """按 id 查询单个班级。查不到 -> 404。"""
    ok, result = get_class(db, stu_class_id)
    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])

    return {'message': '查询成功',
            '班级id': result.stu_class_id,
            '班级名字': result.class_name,
            '开课时间': result.start_date,
            '班主任id': result.class_teacher_id,
            '班主任姓名': result.class_teacher_name,
            '授课老师id': result.teacher_id,
            '授课老师姓名': result.teacher_name,
            }



@router04.get('/get_class/{stu_class_id}/students', summary='查询班级所有学生信息')
def get_class_students1(stu_class_id: int, db=Depends(get_db)):
    ok, result = get_class_students(db, stu_class_id)

    if not ok:
        raise HTTPException(status_code=result['status_code'], detail=result['message'])

    # 此时 result 是学生对象的列表
    return [{
        'stu_class_id': row.stu_class_id,
        'stu_id': row.stu_id,
        'stu_name': row.stu_name,
        'stu_age': row.stu_age,
        'stu_sex': row.stu_sex,
        'stu_tel': row.stu_tel,
        # 顾问信息。顾问可能为空（不是每个学生都有顾问），
        # 所以这里要用 row.agent 的判空，不能直接 row.agent.agent_name。
        'agent_id': row.agent_id,
        'agent_name': row.agent.agent_name if row.agent else None,
        'stu_from': row.stu_from,
        'stu_school': row.stu_school,
        'stu_major': row.stu_major,
        'enroll_date': row.enroll_date,
        'gra_date': row.gra_date,
        'edu_bg': row.edu_bg
    } for row in result]


# 定义查询所有班级的信息接口
@router04.get('/all_class', summary='查询所有班级信息')
def get_all_class1(db=Depends(get_db)):
    """
    查询所有班级。

    列表接口查不到数据返回 200 + [] 是正常状态，不是 404。
    （原来这里写的是 `if result is None`，而 .all() 只会返回 []，
      永远不会返回 None —— 那段判断是死代码。）
    """
    result = get_all_class(db)

    return [{'message': '查询成功',
            '班级id': i.stu_class_id,
            '班级名字': i.class_name,
            '开课时间': i.start_date,
            '班主任id': i.class_teacher_id,
            '班主任姓名': i.class_teacher_name,
            '授课老师id': i.teacher_id,
            '授课老师姓名': i.teacher_name,
             } for i in result]





# # ============================================================================
# # 班主任
# # ============================================================================
#
# # 定义新增班主任信息接口
# @router04.post('/class_teacher', status_code=status.HTTP_201_CREATED, summary='新增班主任')
# def creat_class_teacher1(class_teacher: Class_teacher_Request, db=Depends(get_db)):
#     """
#     新增班主任。
#
#     这张表以前【没有任何接口能写】，但"新建班级"又要求班主任必须存在，
#     班级模块因此陷入死锁 —— 现在补上了。
#     """
#     ok, result = add_class_teacher(db, class_teacher.model_dump())
#     if not ok:
#         raise HTTPException(status_code=result['status_code'], detail=result['message'])
#     return result
#
#
# # 定义修改班主任信息接口
# @router04.put('/update_class_teacher/{class_teacher_id}', summary='修改班主任信息')
# def update_class_teacher1(class_teacher_id: int, class_teacher: Class_teacher_Request, db=Depends(get_db)):
#     """修改班主任信息。班主任不存在 -> 422。"""
#     ok, result = put_class_teacher(db, class_teacher_id, class_teacher.model_dump())
#     if not ok:
#         raise HTTPException(status_code=result['status_code'], detail=result['message'])
#     return result
#
#
# # 定义软删除班主任信息接口
# @router04.delete('/delete_class_teacher/{class_teacher_id}', summary='删除班主任')
# def del_class_teacher1(class_teacher_id: int, db=Depends(get_db)):
#     """
#     软删除班主任。不存在 -> 422。
#
#     修复记录：原来函数参数写的是 teacher_id，但路径是 {class_teacher_id}。
#     FastAPI 找不到路径参数，就把 teacher_id 当成了【必填的 query 参数】，
#     于是这个接口永远返回 422：
#         {"detail": [{"type": "missing", "loc": ["query", "teacher_id"], ...}]}
#
#     记住这条规则：路径 {xxx} 里的名字必须和函数参数名【完全一致】。
#     """
#     ok, result = del_class_teacher(db, class_teacher_id)
#     if not ok:
#         raise HTTPException(status_code=result['status_code'], detail=result['message'])
#     return result
#
#
# # 定义查询班主任信息接口
# @router04.get('/get_class_teacher/{class_teacher_id}', summary='查询班主任信息')
# def get_class_teacher1(class_teacher_id: int, db=Depends(get_db)):
#     """按 id 查询单个班主任。查不到 -> 404。"""
#     ok, result = get_class_teacher(db, class_teacher_id)
#     if not ok:
#         raise HTTPException(status_code=result['status_code'], detail=result['message'])
#
#     return {'message': '查询成功',
#             '班主任id': result.class_teacher_id,
#             '班主任名字': result.class_teacher_name,
#             '班主任性别': result.class_teacher_sex}
#
#
# # 定义查询所有班主任的信息接口
# @router04.get('/all_class_teacher', summary='查询所有班主任信息')
# def get_all_class_teacher1(db=Depends(get_db)):
#     """
#     查询所有班主任。
#
#     新建班级的接口要填"班主任id"，
#     前端得先能拿到班主任列表才填得出来 —— 这就是补这个接口的原因。
#     """
#     rows = get_all_class_teacher(db)
#
#     return [{'message': '查询成功',
#              '班主任id': i.class_teacher_id,
#              '班主任名字': i.class_teacher_name,
#              '班主任性别': i.class_teacher_sex}
#             for i in rows]
