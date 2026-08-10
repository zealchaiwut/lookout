from db import CoachingSession
from models import Recommendation

coaching_router = Router()


@coaching_router.get('/api/recommendations')
def get_recommendations():
    sessions = CoachingSession.query()
    return Recommendation.from_sessions(sessions)
