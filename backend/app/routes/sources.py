import json
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import SOURCES_FILE

router = APIRouter(prefix="/api/sources", tags=["Sources"])


class SourceItem(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., description="订阅源名称")
    url: str = Field(..., description="订阅链接")
    notes: Optional[str] = Field(default="", description="备注说明")


def load_sources() -> List[Dict[str, Any]]:
    if not SOURCES_FILE.exists():
        return []
    try:
        with open(SOURCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_sources(sources: List[Dict[str, Any]]) -> None:
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)


@router.get("", response_model=List[Dict[str, Any]])
def get_sources():
    """获取所有已保存的上游订阅源"""
    return load_sources()


@router.post("", response_model=Dict[str, Any])
def add_source(source: SourceItem):
    """添加新的上游订阅源"""
    sources = load_sources()
    new_item = source.model_dump()
    new_item["id"] = str(uuid.uuid4())[:8]
    sources.append(new_item)
    save_sources(sources)
    return new_item


@router.put("/{source_id}", response_model=Dict[str, Any])
def update_source(source_id: str, source: SourceItem):
    """更新上游订阅源"""
    sources = load_sources()
    for idx, item in enumerate(sources):
        if item.get("id") == source_id:
            updated = source.model_dump()
            updated["id"] = source_id
            sources[idx] = updated
            save_sources(sources)
            return updated
    raise HTTPException(status_code=404, detail="订阅源未找到")


@router.delete("/{source_id}")
def delete_source(source_id: str):
    """删除指定的上游订阅源"""
    sources = load_sources()
    new_sources = [s for s in sources if s.get("id") != source_id]
    if len(new_sources) == len(sources):
        raise HTTPException(status_code=404, detail="订阅源未找到")
    save_sources(new_sources)
    return {"success": True, "message": "删除成功"}
