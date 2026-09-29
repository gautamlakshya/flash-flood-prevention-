from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_observations():
    return {"status": "ok", "module": "observations"}
