"""道路设施接口：维护道路设施，并提供按等级、管养单位聚合的路况总览。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.road import RoadService

router = APIRouter(prefix="/api/road", tags=["道路设施"])

service = RoadService()

LIST_FIELDS = ["设施编码", "道路名称", "道路等级", "起止桩号", "路面结构", "管养单位", "建成年份", "设施状态"]
STATUSES = ["待移交", "正常养护", "重点观测", "封闭施工"]


@router.get("/overview", response_model=dict)
def road_condition_overview() -> dict[str, Any]:
    """路况总览：按道路等级和管养单位成排汇总病害与未闭环计划。"""
    return service.road_overview()


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按设施编码或道路名称检索"),
    name: str | None = Query(default=None, description="按道路名称检索"),
    level: str | None = Query(default=None, description="按道路等级检索"),
    unit: str | None = Query(default=None, description="按管养单位检索"),
    status: str | None = Query(default=None, description="待移交、正常养护、重点观测、封闭施工"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按设施编码、名称、等级、管养单位与状态过滤道路设施列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword,
        name=name,
        level=level,
        unit=unit,
        status=status,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出道路设施清单：返回当前全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "road", "total": total, "items": items}


@router.get("/{entry_id}/condition", response_model=dict)
def get_entry_condition(entry_id: int) -> dict:
    """读取单条道路设施关联病害、养护计划与施工进度。"""
    detail = service.road_detail(entry_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"道路设施 {entry_id} 不存在或已归档")
    return detail


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条道路设施明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"道路设施 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条道路设施，缺字段时说明原因而不是静默丢弃。"""
    entry, result = service.create_entry(payload.values)
    if isinstance(result, str):
        return ActionResult(ok=False, message=result)
    if result:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(result)}")
    return ActionResult(ok=True, message="道路设施已登记", entry=entry)


@router.patch("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """在总览中修改道路设施基础信息，保存后与台账使用同一份数据。"""
    entry, message = service.update_entry(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条道路设施执行办理移交、标记观测、封闭设施；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
