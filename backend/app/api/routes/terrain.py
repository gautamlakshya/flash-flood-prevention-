from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_terrain():
    return {"status": "ok", "module": "terrain"}
