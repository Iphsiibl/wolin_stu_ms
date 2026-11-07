"""
小助手的单元测试。

【为什么这些测试最重要】
    小助手有两道防线直接关系到「能不能上线」：
      1. sql_guard —— 保证模型生成的 SQL 永远改不了数据；
      2. scope     —— 保证小助手只聊本系统。
    这两��必须有人盯着，改提示词的时候尤其容易把安全约束改松。

运行：
    cd kb_assistant
    pytest -q
"""

from __future__ import annotations

import pytest

from app import scope
from app.db import db
from app.knowledge import TABLES, render_knowledge, render_schema
from app.sql_guard import SqlRejected, extract_sql, validate


# ===========================================================================
#  SQL 安全闸门
# ===========================================================================
class TestSqlGuard:
    """SQL 只能读，不能写。"""

    def test_extract_from_code_fence(self):
        raw = '好的，这是查询：\n```sql\nSELECT stu_name FROM student_info LIMIT 10;\n```\n希望有帮助'
        sql = extract_sql(raw)
        assert 'SELECT' in sql.upper()
        assert 'student_info' in sql

    def test_extract_bare_sql(self):
        raw = 'SELECT COUNT(*) FROM student_info'
        assert extract_sql(raw).upper().startswith('SELECT')

    def test_extract_rejects_garbage(self):
        with pytest.raises(SqlRejected):
            extract_sql('我不知道这个问题该怎么查。')

    def test_rejects_insert(self):
        with pytest.raises(SqlRejected):
            validate("INSERT INTO student_info (stu_name) VALUES ('x')")

    def test_rejects_update(self):
        with pytest.raises(SqlRejected):
            validate("UPDATE student_info SET stu_name = 'x' WHERE stu_id = 1")

    def test_rejects_delete(self):
        with pytest.raises(SqlRejected):
            validate('DELETE FROM student_info')

    def test_rejects_drop(self):
        with pytest.raises(SqlRejected):
            validate('DROP TABLE student_info')

    def test_rejects_truncate(self):
        with pytest.raises(SqlRejected):
            validate('TRUNCATE TABLE scores')

    def test_rejects_multi_statement(self):
        with pytest.raises(SqlRejected):
            validate('SELECT 1; DROP TABLE student_info')

    def test_rejects_load_file(self):
        with pytest.raises(SqlRejected):
            validate("SELECT LOAD_FILE('/etc/passwd')")

    def test_rejects_outfile(self):
        with pytest.raises(SqlRejected):
            validate("SELECT 1 INTO OUTFILE '/tmp/x.txt'")

    def test_rejects_non_whitelisted_table(self):
        with pytest.raises(SqlRejected):
            validate('SELECT * FROM mysql.user')

    def test_rejects_system_table(self):
        with pytest.raises(SqlRejected):
            validate('SELECT * FROM information_schema.tables')

    def test_comment_cannot_hide_keyword(self):
        """
        注释里藏关键字也拦得住。

        这里期望的是「注释被剥掉后，危险语句不存在」——
        `SELECT 1 -- DROP TABLE student_info` 剥掉注释后就是无害的 SELECT 1。
        真正要防的是「注释让危险语句混进来」，所以断言结果里没有 DROP。
        """
        out = validate('SELECT 1 -- DROP TABLE student_info')
        assert 'DROP' not in out.upper()
        assert 'TABLE' not in out.upper()

    def test_block_comment_cannot_hide_keyword(self):
        out = validate('SELECT 1 /* DROP TABLE student_info */')
        assert 'DROP' not in out.upper()

    def test_adds_limit_when_missing(self):
        out = validate('SELECT stu_name FROM student_info', max_rows=50)
        assert out.upper().rstrip().endswith('LIMIT 50')

    def test_keeps_existing_limit(self):
        out = validate('SELECT stu_name FROM student_info LIMIT 10', max_rows=200)
        assert out.upper().count('LIMIT') == 1
        assert 'LIMIT 10' in out.upper()

    def test_accepts_valid_select(self):
        out = validate(
            'SELECT s.stu_name, c.class_name FROM student_info s '
            'JOIN clazz c ON s.stu_class_id = c.stu_class_id '
            'WHERE s.is_del = 0 AND c.is_del = 0 LIMIT 20'
        )
        assert out.upper().startswith('SELECT')
        assert 'LIMIT 20' in out.upper()

    def test_accepts_with_cte(self):
        out = validate(
            'WITH t AS (SELECT stu_id, AVG(score) a FROM scores WHERE is_del = 0 GROUP BY stu_id) '
            'SELECT * FROM t LIMIT 10'
        )
        assert out.upper().startswith('WITH')


# ===========================================================================
#  领域边界
# ===========================================================================
class TestScope:
    """小助手只聊本系统。"""

    @pytest.mark.parametrize('question', [
        '今天天气怎么样',
        '帮我看看股票行情',
        '比特币现在多少钱',
        '写首关于春天的诗',
        '讲个笑话吧',
        '推荐几个武汉的餐厅',
        '帮我写个爬虫抓取豆瓣',
        '雅思口语怎么准备',
        '我头疼该吃什么药',
    ])
    def test_blocks_out_of_scope(self, question):
        assert scope.precheck(question) is not None

    @pytest.mark.parametrize('question', [
        '1 号班有多少学生',
        '这个系统有哪些功能模块',
        '数据库里有几张表',
        '就业薪资最高的 5 个人是谁',
        '哪些学生有两次以上不及格',
        '顾问和班主任有什么区别',
        '成绩表怎么设计',
        '帮我统计一下每个班的平均分',
        '学生信息接口在哪个路径',
        '什么是软删除',
        '我是谁',
    ])
    def test_allows_in_scope(self, question):
        assert scope.precheck(question) is None

    def test_empty_question_is_not_blocked(self):
        """空问题交给上层处理，不在这里拦。"""
        assert scope.precheck('') is None

    def test_detects_marker_in_answer(self):
        assert scope.is_out_of_scope_answer('abc [超出范围] def') is True
        assert scope.is_out_of_scope_answer('正常回答') is False

    def test_strip_marker(self):
        assert scope.strip_marker('[超出范围]') == ''
        assert scope.strip_marker('正常') == '正常'


# ===========================================================================
#  知识库
# ===========================================================================
class TestKnowledge:
    """知识库内容不能为空，也不能和真实表对不上。"""

    def test_all_tables_documented(self):
        names = {t.name for t in TABLES}
        assert names == {
            'student_info', 'clazz', 'agent', 'class_teacher',
            'teacher', 'scores', 'employment',
        }

    def test_every_table_has_columns(self):
        for table in TABLES:
            assert table.columns, f'{table.name} 没有字段定义'
            assert table.cn, f'{table.name} 没有中文名'
            assert table.desc, f'{table.name} 没有说明'

    def test_soft_delete_column_exists(self):
        """软删除字段必须真的在字段列表里，否则生成的 SQL 会引用不存在的列。"""
        for table in TABLES:
            if table.soft_delete:
                assert any(c.name == table.soft_delete for c in table.columns), \
                    f'{table.name} 声明了软删除字段 {table.soft_delete}，但字段列表里没有'

    def test_render_is_not_empty(self):
        assert len(render_schema()) > 500
        assert len(render_knowledge()) > 1000

    def test_class_naming_rule_is_documented(self):
        """
        班级名格式和「序号 = stu_class_id」的对应关系必须写进知识库。

        没有这条，模型问「1 号班」时会去猜 class_name = '1号班'，
        而库里实际叫「软件工程1班」，查出来是 0 人 —— 答案看着还挺自信。
        """
        text = render_knowledge()
        assert '软件工程1班' in text, '知识库里缺少班级名格式的说明'
        assert 'stu_class_id = N' in text, '知识库里缺少班级序号与 id 对应的说明'

    def test_sql_prompt_mentions_class_lookup_rule(self):
        """生成 SQL 的提示词里也要写死「不要臆造 class_name」。"""
        from app.prompts import SQL_SYSTEM

        assert 'class_name' in SQL_SYSTEM
        assert '臆造' in SQL_SYSTEM


# ===========================================================================
#  数据库
# ===========================================================================
class TestDatabase:
    """只读连接要能跑通真实查询。"""

    def test_ping(self):
        assert db.ping() is True

    def test_select_with_limit(self):
        result = db.run_sql('SELECT stu_id, stu_name FROM student_info WHERE is_del = 0 LIMIT 5')
        assert result.ok, result.error
        assert result.row_count == 5
        assert 'stu_name' in result.columns
        assert isinstance(result.rows[0], dict)

    def test_soft_delete_filter_works(self):
        """统计口径：过滤软删除后应该比不过滤少。"""
        with_filter = db.run_sql('SELECT COUNT(*) AS c FROM student_info WHERE is_del = 0')
        without = db.run_sql('SELECT COUNT(*) AS c FROM student_info')
        assert with_filter.ok and without.ok
        assert with_filter.rows[0]['c'] <= without.rows[0]['c']

    def test_row_cap(self):
        """即使 SQL 没写 LIMIT，也只能拿到 max_rows 行。"""
        result = db.run_sql('SELECT stu_id FROM student_info', max_rows=7)
        assert result.ok
        assert result.row_count == 7
        assert result.truncated is True

    def test_invalid_sql_returns_error_not_crash(self):
        result = db.run_sql('SELECT 不存在的列 FROM student_info')
        assert result.ok is False
        assert result.error
