from app import app
from models import db
from models.user import User
from models.activity import Activity
from models.alert import Alert
import os

db_path = os.path.join('instance', 'ueba.db')
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"Removed existing database at {db_path}")

if not os.path.exists('instance'):
    os.makedirs('instance')

with app.app_context():
    print("Creating all tables...")
    db.create_all()
    print("Database initialized successfully.")
