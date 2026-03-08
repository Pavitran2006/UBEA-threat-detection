import requests

print('registering user')
r = requests.post('http://127.0.0.1:8000/api/register', json={
    'email':'testuser@example.com',
    'password':'Password1',
    'confirmPassword':'Password1',
    'username':'testuser'
})
print(r.status_code, r.text)

print('logging in')
r2 = requests.post('http://127.0.0.1:8000/api/login', json={
    'username':'testuser',
    'password':'Password1'
})
print('login', r2.status_code, r2.text)
print('cookies', r2.cookies.get_dict())
print('fetch dashboard', requests.get('http://127.0.0.1:8000/dashboard', cookies=r2.cookies).status_code)
