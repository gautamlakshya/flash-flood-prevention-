from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_hazards():
    return {"status": "ok", "module": "hazards"}
