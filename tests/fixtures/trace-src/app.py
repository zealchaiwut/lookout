from routes import coaching_router
from db import CoachingSession


def create_app():
    app = App()
    app.include_router(coaching_router)
    return app
