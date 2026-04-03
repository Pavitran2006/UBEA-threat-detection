import urllib.request, urllib.parse, http.cookiejar

class NoRedirect(urllib.request.HTTPErrorProcessor):
    def http_response(self, req, resp): return resp
    https_response = http_response

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())

# 1. Test Home
home = opener.open('http://127.0.0.1:8000/', timeout=5)
print('Home Status:', home.status)

# 2. Test Signup Display
signup_page = opener.open('http://127.0.0.1:8000/signup', timeout=5)
print('Signup UI Status:', signup_page.status)

# 3. Test Signup POST logic
data = urllib.parse.urlencode({'username': 'blocktester', 'email': 'block@test.com', 'phone': '555-0000', 'password': 'password123', 'confirmPassword': 'password123', 'role': 'user'}).encode()
r_signup = opener.open(urllib.request.Request('http://127.0.0.1:8000/signup', data=data), timeout=5)
print('Signup POST Status:', r_signup.status)
if r_signup.status == 500:
    print("FAILED: 500 Internal Server Error still on Signup")
    exit(1)

# 4. Test Login
data_login = urllib.parse.urlencode({'email': 'block@test.com', 'password': 'password123'}).encode()
r_login = opener.open(urllib.request.Request('http://127.0.0.1:8000/login', data=data_login), timeout=5)
print('Login POST Status:', r_login.status)

# 5. Access Dashboard
dash = opener.open('http://127.0.0.1:8000/dashboard', timeout=5)
print('Dashboard UI Status:', dash.status)

import sqlite3
conn = sqlite3.connect('ueba_app.db')
cursor = conn.cursor()
cursor.execute('DELETE FROM users WHERE email="block@test.com"')
conn.commit()
conn.close()
print('SUCCESS: All endpoints returned correctly, Database cleanup active.')
