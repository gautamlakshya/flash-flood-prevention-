from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_rainfall():
    return {"status": "ok", "module": "rainfall"}
