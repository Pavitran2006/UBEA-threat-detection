import requests

def test_login():
    url = "http://127.0.0.1:8000/login"
    data = {
        "email": "analyst@ueba.sec", # Typical user, we can try with bad password first
        "password": "wrongpassword"
    }
    headers = {
        "X-Requested-With": "XMLHttpRequest"
    }
    try:
        response = requests.post(url, data=data, headers=headers)
        print("Status Code:", response.status_code)
        print("Response Headers:", response.headers)
        print("Response Text:", response.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_login()
