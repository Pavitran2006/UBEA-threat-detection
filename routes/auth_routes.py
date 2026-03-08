from flask import Blueprint, request, jsonify, session, redirect, url_for
from services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    # Handle both JSON and Form data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
    
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'user')

    if not username or not password or not email:
        if request.is_json:
            return jsonify({"error": "Missing required fields"}), 400
        return redirect(url_for('signup_page', error="Missing required fields"))
        
    response, status_code = AuthService.register_user(
        username=username,
        email=email,
        password=password,
        role=role
    )
    
    if status_code == 201:
        print(f"[DEBUG] Signup successful for: {email}")
        session['user'] = email
        print("[DEBUG] Redirecting to Dashboard...")
        return redirect(url_for('dashboard'))
    
    if request.is_json:
        return jsonify(response), status_code
    return redirect(url_for('signup_page', error=response.get('error', 'Registration failed')))

@auth_bp.route('/login', methods=['POST'])
def login():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
        
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        if request.is_json:
            return jsonify({"error": "Missing username or password"}), 400
        return redirect(url_for('login_page', error="Missing username or password"))
        
    response, status_code = AuthService.login_user(
        username=username,
        password=password
    )
    
    if status_code == 200:
        email = response.get('user', {}).get('email', username)
        print(f"[DEBUG] Login successful for: {email}")
        session['user'] = email
        print("[DEBUG] Redirecting to Dashboard...")
        return redirect(url_for('dashboard'))
    
    if request.is_json:
        return jsonify(response), status_code
    return redirect(url_for('login_page', error=response.get('error', 'Invalid credentials')))
