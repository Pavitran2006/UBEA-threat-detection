from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List
from datetime import datetime, timedelta
import jwt

# dummy in-memory store as example
class User(BaseModel):
    id: int
    name: str
    email: str
    role: str
    last_login: datetime
    status: str

fake_users = [
    User(id=1, name="Alice", email="alice@example.com", role="User", last_login=datetime.utcnow(), status="Active"),
    User(id=2, name="Bob", email="bob@example.com", role="Admin", last_login=datetime.utcnow(), status="Disabled"),
]

SECRET_KEY = "supersecret"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
app = FastAPI()

# JWT helpers

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    # in real app, query DB
    user = next((u for u in fake_users if u.id == user_id), None)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # dummy authentication
    user = next((u for u in fake_users if u.email == form_data.username), None)
    if not user or form_data.password != "password":
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users", response_model=List[User])
def list_users(current: User = Depends(get_current_user)):
    return fake_users

@app.post("/users/disable/{id}")
def disable_user(id: int, current: User = Depends(get_current_user)):
    u = next((u for u in fake_users if u.id == id), None)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    u.status = "Disabled"
    return {"status": "ok"}

@app.post("/users/enable/{id}")
def enable_user(id: int, current: User = Depends(get_current_user)):
    u = next((u for u in fake_users if u.id == id), None)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    u.status = "Active"
    return {"status": "ok"}

@app.delete("/users/{id}")
def delete_user(id: int, current: User = Depends(get_current_user)):
    global fake_users
    fake_users = [u for u in fake_users if u.id != id]
    return {"status": "deleted"}

# additional endpoints for logs/alerts (placeholders)  

class LogEntry(BaseModel):
    timestamp: datetime
    username: str
    action: str
    risk_level: str

@app.get("/logs", response_model=List[LogEntry])
def get_logs(current: User = Depends(get_current_user)):
    # return dummy data
    return [
        LogEntry(timestamp=datetime.utcnow(), username="alice", action="login", risk_level="Low"),
        LogEntry(timestamp=datetime.utcnow(), username="bob", action="failed_attempt", risk_level="Medium"),
    ]

@app.get("/alerts")
def get_alerts(current: User = Depends(get_current_user)):
    return [
        {"user":"alice","message":"Suspicious access","time":"12:01","level":"High"},
        {"user":"bob","message":"Multiple failed logins","time":"13:22","level":"Medium"}
    ]
