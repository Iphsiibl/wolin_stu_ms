"""
schema 包：请求体校验模型的集合。

【这一层是干什么的？】
    校验"前端传过来的 JSON 长得对不对"。

    六个模块的请求体模型都在这里：
        student_request.py  学生 / 顾问
        class_schema.py     班级 / 班主任
        teacher_request.py  老师
        emp_request.py      就业信息
        score_schema.py     成绩
        enums.py            全局枚举（性别）

【为什么单独抽一个 schema 包？】
    把"校验"和"业务"、"数据库"分开：
        schema 层 —— 只管数据长什么样
        Dao 层   —— 只管怎么查库怎么写库
        API 层   —— 只管怎么跟 HTTP 打交道
    三层各干各的，改一层不会牵连另外两层。

    另外，FastAPI 会自动读取这些模型生成 Swagger 文档（访问 /docs），
    前端同学不用看代码就知道每个接口要传哪些字段。
"""
