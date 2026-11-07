"""
API 包：六个模块的接口层。

【这一层是干什么的？】
    收 HTTP 请求 -> 调 DAO -> 拼 JSON 返回 / 抛 HTTPException。

    文件对应关系：
        stu_info_api.py  学生 + 顾问   （router01, 前缀 /student）
        score_api.py     成绩             （router02, 前缀 /score）
        emp_api.py       就业信息         （router03, 前缀 /employment）
        class_api.py     班级 + 班主任    （router04, 前缀 /class）
        teacher_api.py   老师             （router05, 前缀 /teacher）
        stat_api.py      统计分析         （router06, 前缀 /stat）

    各个 router 的前缀和分组标签不在这里写，
    而是在 main.py 里用 app.include_router(router, prefix=..., tags=...) 挂上去。

【这一层的铁律】
    业务失败一律 `raise HTTPException(status_code=..., detail=...)`，
    不自己 return 一个带 "失败" 字样的 200 响应。
    状态码要能说真话，前端才不用去猜 body。
"""
