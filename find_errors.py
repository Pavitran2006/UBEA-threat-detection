import os
import py_compile

def find_indentation_errors(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    py_compile.compile(path, doraise=True)
                except py_compile.PyCompileError as e:
                    print(f"Error in {path}:")
                    print(e)
                except Exception as e:
                    print(f"Other error in {path}: {e}")

if __name__ == "__main__":
    find_indentation_errors('app')
    find_indentation_errors('models')
    find_indentation_errors('routes') # if there's a top level routes
    # check root files too
    for file in os.listdir('.'):
        if file.endswith('.py'):
            try:
                py_compile.compile(file, doraise=True)
            except py_compile.PyCompileError as e:
                print(f"Error in {file}:")
                print(e)
