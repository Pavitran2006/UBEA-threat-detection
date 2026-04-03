from flask import Blueprint, request, jsonify, session, redirect, url_for
from flask import render_template
from app.database import SessionLocal
from sqlalchemy import func
from services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    db = SessionLocal()
    try:
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
            db, username, email, password, role
        )
        
        if status_code == 201:
            print(f"[DEBUG] Signup successful for: {email}")
            session['user'] = email
            print("[DEBUG] Redirecting to Dashboard...")
            return redirect(url_for('dashboard'))
        
        if request.is_json:
            return jsonify(response), status_code
        return redirect(url_for('signup_page', error=response.get('error', 'Registration failed')))
    finally:
        db.close()

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
        
    db = SessionLocal()
    try:
        client_ip = request.remote_addr or 'Unknown'
        user_agent = request.headers.get('User-Agent', 'Unknown')

        response, status_code = AuthService.login_user(
            db=db,
            identifier=username,
            password=password,
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        if status_code == 200:
            email = response.get('user', {}).get('email', username)
            print(f"[DEBUG] Login successful for: {email} from {client_ip}")
            session['user'] = email
            print("[DEBUG] Redirecting to Dashboard...")
            return redirect(url_for('dashboard'))
    finally:
        db.close()
    
    if request.is_json:
        return jsonify(response), status_code
    return redirect(url_for('login_page', error=response.get('error', 'Invalid credentials')))
