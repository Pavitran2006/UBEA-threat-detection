from flask import Flask, jsonify, render_template, session, redirect, url_for, request
from config import Config
from models import init_db, db
from services import bcrypt, init_auth
# Import models
from models.user import User
from models.activity import Activity
from models.alert import Alert
# Import Blueprints
from routes.auth_routes import auth_bp
from routes.dashboard_routes import dashboard_bp
from routes.risk_routes import risk_bp
from routes.ml_routes import ml_bp

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config.get('SECRET_KEY', 'cyberguard-super-secret-key')

# Initialize Database and Auth
init_db(app)
init_auth(app)

# Register Blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
app.register_blueprint(risk_bp, url_prefix='/api/risk')
app.register_blueprint(ml_bp, url_prefix='/api/ml')

# Web Interface Routes
@app.route('/')
@app.route('/login')
def login_page():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        print("[DEBUG] Unauthorized access attempt to Dashboard. Redirecting to Login.")
        return redirect(url_for('login_page'))
    
    # Fetch user data for the template
    user = User.query.filter_by(email=session['user']).first()
    if not user:
        # Fallback if user missing in DB but session persists
        session.pop('user', None)
        return redirect(url_for('login_page'))

    print(f"[DEBUG] Dashboard loaded for user: {user.username} ({user.email})")
    return render_template('dashboard.html', user=user)

@app.route('/logout')
def logout():
    user = session.pop('user', None)
    if user:
        print(f"[DEBUG] User {user} logged out.")
    return redirect(url_for('login_page'))

# General Health/Status
@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "service": "UEBA-Backend"}), 200

# Health Check Route
@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == '__main__':
    print("[DEBUG] Starting Flask Server on port 5000...")
    app.run(debug=True, port=5000)
