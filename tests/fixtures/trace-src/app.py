from routes import coaching_router


def create_app():
    app = App()
    app.include_router(coaching_router)
    return app
