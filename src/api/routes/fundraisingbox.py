from fastapi import APIRouter

fundraisingbox_router = APIRouter(prefix="/fnb")


@fundraisingbox_router.post("create")
async def create(): ...
