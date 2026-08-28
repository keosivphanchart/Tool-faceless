from fastapi import APIRouter

from faceless_pipeline.modules.automation.cost import spend_summary

router = APIRouter()


@router.get("/spend")
def get_spend_summary():
    return spend_summary()
