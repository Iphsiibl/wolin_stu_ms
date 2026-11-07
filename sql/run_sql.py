"""
一键执行 sql/ 目录下的建库 + 灌数据脚本。

====================================================================
【为什么需要这个脚本？】
====================================================================
Windows 的 PowerShell 不支持 `mysql < xxx.sql` 这种重定向写法
（那是 Linux/macOS 的 bash 语法），在 PowerShell 里直接跑会报错。

Navicat / MySQL Workbench / DBeaver 这些图形化工具可以直接打开 .sql 文件
点"运行"，不需要这个脚本。但如果你只想在终端里敲一行命令，就用这个。

====================================================================
【怎么用】
====================================================================
    python sql/run_sql.py                 # 建 student_ms_demo 库 + 灌数据
    python sql/run_sql.py student_ms_test # 换一个库名（库会被先删掉重建！）

====================================================================
【注意：它会先 DROP DATABASE】
====================================================================
    建库脚本里有 `DROP DATABASE IF EXISTS`，
    所以目标库里的东西会被全部清空、然后重建。

    默认目标是 student_ms_demo —— 一个全新的、专供测试的库，
    不会碰到你正在用的 student_ms。
    但如果你手动把库名改成 student_ms，那就会把你现有的数据清掉！
"""
import io
import os
import sys

from dotenv import load_dotenv
import pymysql

# 让脚本不管从哪个目录运行，都能找到项目根目录（.env 和 sql/ 都在那儿）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(ROOT, 'sql')

# 默认目标库
DEFAULT_DB = 'student_ms_demo'

# 要按顺序执行的文件
FILES = ['01_create_schema.sql', '02_seed_demo_data.sql']


def split_sql_statements(text: str):
    """
    把一个 .sql 文件拆成一条条独立的语句。

    【为什么要自己拆？】
    试过让 PyMySQL 一次执行整个文件（client_flag=MULTI_STATEMENTS），
    结果是：文件中间的 `SET NAMES utf8mb4;` 会改变连接字符集，
    PyMySQL 解析后面的结果包时对不上，
    后面的 INSERT 被【静默跳过】—— 不报错，但数据一行都没插进去。
    这种"不报错但没生效"最坑，所以改成一条一条执行。

    拆分时必须跳过这些地方里的分号，否则会切错：
        '字符串里的分号;'      —— 单引号
        "字符串里的分号;"      —— 双引号
        `表名;`                —— 反引号
        -- 行注释里的分号;     —— 双减号注释
        /* 块注释里的分号; */  —— 块注释
    """
    statements = []
    buf = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ''

        # ---- 注释 ----
        if ch == '-' and nxt == '-':
            # 行注释：一直跳到行尾
            while i < n and text[i] != '\n':
                i += 1
            continue

        if ch == '/' and nxt == '*':
            # 块注释：找到 */
            end = text.find('*/', i + 2)
            i = n if end == -1 else end + 2
            continue

        # ---- 引号 ----
        if ch in ("'", '"', '`'):
            quote = ch
            buf.append(ch)
            i += 1
            while i < n:
                buf.append(text[i])
                if text[i] == '\\' and i + 1 < n:
                    # 反斜杠转义：把下一个字符原样带过去
                    i += 1
                    buf.append(text[i])
                    i += 1
                    continue
                if text[i] == quote:
                    i += 1
                    break
                i += 1
            continue

        # ---- 分号：一条语句结束 ----
        if ch == ';':
            stmt = ''.join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    # 文件最后可能有一条不带分号的语句
    tail = ''.join(buf).strip()
    if tail:
        statements.append(tail)

    return statements


def read_sql(path: str) -> str:
    """读一个 .sql 文件（UTF-8）。"""
    with io.open(path, 'r', encoding='utf-8') as f:
        return f.read()


def run() -> int:
    # 读 .env 拿数据库账号密码
    load_dotenv(os.path.join(ROOT, '.env'))

    host = os.getenv('DB_HOST', '127.0.0.1')
    port = int(os.getenv('DB_PORT', '3306'))
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')

    if not user or not password:
        print('✗ 读不到数据库账号密码。')
        print('  请检查项目根目录的 .env 文件，里面应该有：')
        print('      DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD')
        return 1

    # 目标库名：命令行参数优先
    target_db = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB

    print('=' * 70)
    print('目标数据库: %s' % target_db)
    print('=' * 70)

    try:
        # 这里【不指定 database】：第一个脚本自己要 CREATE DATABASE
        conn = pymysql.connect(
            host=host, port=port, user=user, password=password,
            charset='utf8mb4',
        )
    except pymysql.Error as e:
        print('✗ 连不上数据库：%s' % e)
        print('  请确认 MySQL 服务已启动，.env 里的账号密码是对的。')
        return 1

    total_rows = 0
    try:
        with conn.cursor() as cur:
            for name in FILES:
                path = os.path.join(SQL_DIR, name)
                if not os.path.exists(path):
                    print('✗ 找不到文件: %s' % path)
                    return 1

                sql = read_sql(path)
                # 把脚本里写死的库名换成命令行指定的库名
                if target_db != DEFAULT_DB:
                    sql = sql.replace(DEFAULT_DB, target_db)

                statements = split_sql_statements(sql)
                print('\n>>> 执行 %s（%d 条语句）...' % (name, len(statements)))

                for index, stmt in enumerate(statements, 1):
                    head = stmt.split('\n')[0][:60]
                    try:
                        cur.execute(stmt)
                        affected = cur.rowcount
                        if affected and affected > 0:
                            total_rows += affected
                            print('    [%2d] 写入 %5d 行   %s' % (index, affected, head))
                        else:
                            print('    [%2d] ok            %s' % (index, head))
                    except pymysql.Error as e:
                        print('\n✗ 第 %d 条语句失败：\n   %s\n   原因：%s'
                              % (index, head, e))
                        return 1
                print('    ✓ %s 完成' % name)

                # 【关键】提交事务。
                #
                # PyMySQL 默认 autocommit=False，也就是说 execute() 只是把语句
                # 发给数据库、放在一个"还没存盘"的事务里。
                # 如果不 commit，连接一关闭事务就被【回滚】了 ——
                # 表现是：每条 INSERT 都显示"写入 N 行"，
                #         但换个连接一查，行数全是 0。
                # 这个坑特别坑，因为它【不报错】。
                conn.commit()
    except pymysql.Error as e:
        print('\n✗ 执行失败：%s' % e)
        return 1
    finally:
        conn.close()

    # ---------- 最后统计一下插了多少行 ----------
    try:
        conn2 = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=target_db, charset='utf8mb4',
        )
        with conn2.cursor() as cur:
            cur.execute('SHOW TABLES')
            tables = [r[0] for r in cur.fetchall()]
            print('\n' + '=' * 70)
            print('%s 建好了，数据统计：' % target_db)
            print('=' * 70)
            total = 0
            for t in tables:
                cur.execute('SELECT COUNT(*) FROM `%s`' % t)
                n = cur.fetchone()[0]
                total += n
                print('    %-16s %5d 行' % (t, n))
            print('    %-16s %5d 行' % ('合计', total))
        conn2.close()
    except pymysql.Error as e:
        print('（统计行数时出错，不影响建库结果：%s）' % e)

    print('\n下一步：把 .env 里的 DB_NAME 改成 %s，然后启动服务' % target_db)
    print('    python main.py')
    print('    然后打开 http://127.0.0.1:8002/docs 逐个接口试')
    return 0


if __name__ == '__main__':
    sys.exit(run())
