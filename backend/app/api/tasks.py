"""
Task status route — lets clients poll Celery task results.
"""

from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult
from app.queue.celery_app import celery_app

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}", summary="Poll async task status")
async def get_task_status(task_id: str):
    """
    Returns the current state and result of a Celery task.
    States: PENDING → STARTED → SUCCESS | FAILURE
    """
    result: AsyncResult = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "status": result.state,
        "result": None,
        "error": None,
    }

    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.result)
    elif result.state == "STARTED":
        response["result"] = {"info": result.info}

    return response