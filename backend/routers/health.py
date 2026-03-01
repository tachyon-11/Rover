from fastapi import APIRouter

router = APIRouter(
    prefix="/health",
    tags=["Health"]
)

@router.get("")
def health_check():
    return {
        "status": "healthy",
        "message": "Your applicatyion is running smoothly!",
        "version": "1.0.0"
    }