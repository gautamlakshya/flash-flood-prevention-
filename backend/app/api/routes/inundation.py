from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_inundation():
    return {"status": "ok", "module": "inundation"}
