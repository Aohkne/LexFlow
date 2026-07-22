from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.schemas import GraphData

router = APIRouter(tags=["graph"])


@router.get("/graph", response_model=GraphData)
def graph_endpoint() -> GraphData:
    if not settings.neo4j_enabled:
        raise HTTPException(status_code=503, detail="Neo4j chưa được cấu hình.")
    try:
        from app.knowledge.graph import get_graph

        return get_graph()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
