from routes import coaching_router


def create_app():
    app = App()  # noqa: F821
    app.include_router(coaching_router)
    return app
