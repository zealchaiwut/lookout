from db import CoachingSession
from models import Recommendation

coaching_router = Router()  # noqa: F821


@coaching_router.get('/api/recommendations')
def get_recommendations():
    sessions = CoachingSession.query()
    return Recommendation.from_sessions(sessions)
