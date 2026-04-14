from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "plane": "P01-Edge"}
