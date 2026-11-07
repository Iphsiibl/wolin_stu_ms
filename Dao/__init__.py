"""
Dao 包：数据访问层。

【这一层是干什么的？】
    只和数据库打交道：查表、写表。
    不解析 HTTP 请求，不拼响应 JSON，不决定状态码。

    文件对应关系：
        stu_dao.py    学生 + 顾问
        score_Dao.py  成绩
        emp_dao.py    就业信息
        class_dao.py  班级 + 班主任
        teacher_dao.py 老师
        stat_dao.py   统计分析

【这一层的铁律 —— 记住这一条就够了】
    每个函数都返回 `(ok, result)`：
        ok=True  -> result 是业务数据
        ok=False -> result = {'message': '提示语', 'status_code': 404}

    · 不抛 HTTPException（那是接口层的活）
    · 不 try/except 吞掉异常（数据库真炸了让它往上冒，
      由 main.py 的全局处理器记完整堆栈并返回 500）

    详见 Dao/stu_dao.py 顶部的完整说明。
"""
