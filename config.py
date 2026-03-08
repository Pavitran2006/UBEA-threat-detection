import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-secret-key')
    
    # Check if we should use MySQL or SQLite
    # Default to SQLite if DB_TYPE is not set or MySQL connection fails
    DB_TYPE = os.environ.get('DB_TYPE', 'sqlite')
    
    if DB_TYPE == 'mysql':
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+mysqlconnector://{os.environ.get('DB_USERNAME')}:"
            f"{os.environ.get('DB_PASSWORD')}@{os.environ.get('DB_HOST')}/"
            f"{os.environ.get('DB_NAME')}"
        )
    else:
        # SQLite database file in the project directory
        SQLALCHEMY_DATABASE_URI = 'sqlite:///ueba.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get('FLASK_ENV') == 'development'
