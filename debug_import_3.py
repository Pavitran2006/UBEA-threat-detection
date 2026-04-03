import sys
import traceback
import importlib

def trace_imports(module_name):
    print(f"Tracing imports for {module_name}...")
    try:
        importlib.import_module(module_name)
        print(f"Successfully imported {module_name}")
    except IndentationError:
        print(f"Caught IndentationError while importing {module_name}")
        traceback.print_exc()
    except Exception:
        print(f"Caught other error while importing {module_name}")
        traceback.print_exc()

if __name__ == "__main__":
    # Add project root to sys.path
    sys.path.append('.')
    trace_imports('app.main')
