from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_prediction():
    return {"status": "ok", "module": "prediction"}
