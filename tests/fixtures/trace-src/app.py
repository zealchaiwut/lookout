from routes import coaching_router


class App:
    """Minimal stand-in so this sample file is importable; the tracer
    reads it via AST, but pytest may still collect it as a module."""

    def include_router(self, router):
        pass


def create_app():
    app = App()
    app.include_router(coaching_router)
    return app
