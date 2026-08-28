from fastapi import APIRouter

from faceless_pipeline.modules.analytics.api import router as analytics_router
from faceless_pipeline.modules.publisher.accounts_api import router as accounts_router
from faceless_pipeline.modules.publisher.api import router as publisher_router
from faceless_pipeline.modules.publisher.slots_api import router as slots_router
from faceless_pipeline.modules.review.api import router as review_router
from faceless_pipeline.modules.scripts.api import router as scripts_router
from faceless_pipeline.modules.trends.api import router as trends_router
from faceless_pipeline.api.pipeline import router as pipeline_router
from faceless_pipeline.api.settings_status import router as settings_router

api_router = APIRouter(prefix="/api")
api_router.include_router(pipeline_router, prefix="/pipeline", tags=["pipeline"])
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])
api_router.include_router(trends_router, prefix="/trends", tags=["trends"])
api_router.include_router(scripts_router, prefix="/scripts", tags=["scripts"])
api_router.include_router(review_router, prefix="/videos", tags=["review"])
# accounts/slots must be registered before publisher_router: publisher_router
# has POST /publish/{video_id}, a single-segment catch-all that would
# otherwise match POST /publish/slots first (with "slots" parsed as
# video_id) since routes are matched in registration order.
api_router.include_router(accounts_router, prefix="/publish/accounts", tags=["accounts"])
api_router.include_router(slots_router, prefix="/publish/slots", tags=["slots"])
api_router.include_router(publisher_router, prefix="/publish", tags=["publisher"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
