"""
演示数据重置的接口层（API 层）。

====================================================================
【这个接口解决什么问题？】
====================================================================
系统部署到公网后，任何拿到网址的人都能增删改数据。
被软删了、被改坏了字段、被塞了垃圾行 —— 都需要一个「一键回到初始状态」的出口。

====================================================================
【安全设计：三道闸门，缺一不可】
====================================================================
    ① 口令 —— 必须带正确的 RESET_TOKEN（环境变量，绝不写死在代码里）
    ② 确认短语 —— 必须传 confirm='RESET'，防手滑
    ③ 未配置即关闭 —— 没配 RESET_TOKEN 时，接口返回 404 而不是放行

    为什么第 ③ 条最重要：
    公开部署时如果忘了配口令，正确的行为是「这个功能用不了」，
    而不是「任何人都能重置你的库」。默认必须是安全的那个。

    另外：这个接口【不在 Swagger 里暴露】——
    include_in_schema=False 让它不出现在 /docs 页面，
    避免给扫描器递刀。知道路径的人照样能用（靠口令保护）。
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from utils.reset_service import (get_baseline_info, get_reset_token,
                                is_reset_enabled, reset_to_baseline,
                                verify_token, write_audit)

router09 = APIRouter()


# =====================================================================
# 请求体
# =====================================================================
class ResetRequest(BaseModel):
    """
    重置请求。

    口令放在【请求体】而不是 query 参数：
    query 参数会进 Nginx / 网关的访问日志，口令会跟着日志一起被记下来。
    放请求体里不会。
    """
    token: str = Field(..., description='重置口令（对应环境变量 RESET_TOKEN）')
    confirm: str = Field(..., description='确认短语，必须是 RESET')


# =====================================================================
# 一、查询重置状态与当前基线
# =====================================================================
@router09.get('/status', summary='查询重置功能状态与当前数据量')
def get_reset_status(request: Request):
    """
    看看重置功能有没有开、现在库里是什么状态。

    前端「重置演示数据」弹窗打开时先调它，
    让用户看清「重置前有多少行 → 重置后会变成多少行」。
    """
    enabled = is_reset_enabled()

    if not enabled:
        return {
            'enabled': False,
            'message': '重置功能未启用（服务器未配置 RESET_TOKEN）',
        }

    info = get_baseline_info()
    return {
        'enabled': True,
        'message': '重置功能已启用',
        'current_counts': info['current_counts'],
        'baseline_counts': info['baseline_counts'],
        'total_current': info['total_current'],
        'total_baseline': info['total_baseline'],
        'is_at_baseline': info['is_at_baseline'],
    }


# =====================================================================
# 二、执行重置
# =====================================================================
@router09.post('/execute', include_in_schema=False)
def execute_reset(payload: ResetRequest, request: Request, db: Session = Depends(get_db)):
    """
    把数据库恢复到种子基线（删表重建 + 灌 1018 条种子数据）。

    ⚠️ 这会【删掉当前库里的全部数据】，包括你自己新加的记录。
    """
    # ---- 闸门 0：功能是否启用 ----
    if not is_reset_enabled():
        # 用 404 而不是 403：这个接口在未配置的部署里【根本不该存在】，
        # 返回 404 让外部看不出这里有个可调用的东西。
        write_audit({
            'action': 'reset',
            'result': 'rejected',
            'operator': 'unknown',
            'ip': _client_ip(request),
            'client': request.headers.get('user-agent', '')[:120],
            'duration_ms': 0,
            'detail': '功能未启用（无 RESET_TOKEN）',
        })
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail='重置功能未启用')

    # ---- 闸门 1：确认短语 ----
    if payload.confirm != 'RESET':
        write_audit({
            'action': 'reset',
            'result': 'rejected',
            'operator': 'unknown',
            'ip': _client_ip(request),
            'client': request.headers.get('user-agent', '')[:120],
            'duration_ms': 0,
            'detail': '确认短语错误',
        })
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='确认短语不正确，需要填写 RESET')

    # ---- 闸门 2：口令 ----
    if not verify_token(payload.token):
        write_audit({
            'action': 'reset',
            'result': 'rejected',
            'operator': 'unknown',
            'ip': _client_ip(request),
            'client': request.headers.get('user-agent', '')[:120],
            'duration_ms': 0,
            'detail': '口令错误',
        })
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='重置口令不正确')

    # ---- 通过所有闸门，执行重置 ----
    result = reset_to_baseline(db)

    write_audit({
        'action': 'reset',
        'result': 'success' if result['ok'] else 'partial',
        'operator': 'admin',
        'ip': _client_ip(request),
        'client': request.headers.get('user-agent', '')[:120],
        'duration_ms': result.get('duration_ms', 0),
        'detail': result.get('message', ''),
    })

    if not result['ok']:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=result['message'])

    return result


# =====================================================================
# 工具
# =====================================================================
def _client_ip(request: Request) -> str:
    """
    取真实客户端 IP。

    反向代理（Nginx）后面，request.client.host 拿到的是代理的 IP。
    真实 IP 在 X-Forwarded-For 的第一个位置。
    """
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.client.host if request.client else 'unknown'
