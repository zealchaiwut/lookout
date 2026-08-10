from db import CoachingSession
from models import Recommendation


class Router:
    """Minimal stand-in so this sample file is importable; the tracer
    reads it via AST, but pytest may still collect it as a module."""

    def get(self, path):
        def decorator(fn):
            return fn
        return decorator


coaching_router = Router()


@coaching_router.get('/api/recommendations')
def get_recommendations():
    sessions = CoachingSession.query()
    return Recommendation.from_sessions(sessions)
