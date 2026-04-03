import traceback
try:
    from app.routes import router
    print("Import successful")
except Exception:
    traceback.print_exc()
except IndentationError:
    traceback.print_exc()
