from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# try health check
print('health ->', client.get('/api/health').json())

# attempt to register a new user
resp = client.post('/api/register', json={'email':'test@example.com','password':'secret','confirmPassword':'secret','username':'testuser'})
print('register status', resp.status_code, resp.text)

# try login
resp2 = client.post('/api/login', json={'email':'test@example.com','password':'secret'})
print('login status', resp2.status_code, resp2.text)
