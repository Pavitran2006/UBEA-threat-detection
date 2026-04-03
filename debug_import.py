import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("Attempting to import app.main...")
    import app.main
    print("Import successful!")
    
    # Check if app is defined
    if hasattr(app.main, 'app'):
        print("FastAPI app found!")
    else:
        print("FastAPI app NOT found!")

    # Check if models are imported and working
    from app.models import User
    print(f"User model: {User}")
    print(f"User tablename: {getattr(User, '__tablename__', 'MISSING')}")

except Exception as e:
    import traceback
    print("Import failed!")
    traceback.print_exc()
    sys.exit(1)
