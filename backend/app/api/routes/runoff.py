from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_runoff():
    return {"status": "ok", "module": "runoff"}
