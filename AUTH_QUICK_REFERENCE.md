# Authentication System Quick Reference

## 🔐 Authentication Methods

### 1. Traditional Email/Password
- **Route:** POST `/login`
- **Requires:** Email and password
- **Returns:** JWT access token in secure cookie
- **Token Expiry:** 30 minutes (configurable)

### 2. Email/Password Registration
- **Route:** POST `/signup`
- **Requires:** Email, password, username, role
- **Returns:** Cookie redirect to dashboard

### 3. Password Reset
- **Forgot Password:** POST `/forgot-password` → Email with reset link
- **Reset Password:** POST `/reset-password/{token}` → New password
- **Token Expiry:** 15 minutes
- **Token Usage:** Single-use only

### 4. Google OAuth 2.0 (Ready to Configure)
- **Route:** GET `/auth/google/login/login` → Google consent → GET `/auth/google/callback`
- **Benefits:** No password management, faster login
- **Setup:** See `GOOGLE_OAUTH_SETUP.md`

### 5. GitHub OAuth (Framework Ready)
- **Route:** GET `/auth/github` → Placeholder
- **Status:** Ready for implementation

### 6. Microsoft OAuth (Framework Ready)
- **Route:** GET `/auth/microsoft` → Placeholder
- **Status:** Ready for implementation

---

## 📝 API Endpoints Reference

### Authentication Endpoints

| Method | Endpoint | Purpose | Protected | Returns |
|--------|----------|---------|-----------|---------|
| GET | `/` | Home page | ✗ | HTML |
| GET | `/login` | Login form | ✗ | HTML |
| POST | `/login` | Process login | ✗ | Cookie + Redirect |
| GET | `/signup` | Registration form | ✗ | HTML |
| POST | `/signup` | Create account | ✗ | Cookie + Redirect |
| GET | `/logout` | Logout user | ✓ | Redirect to login |
| GET | `/forgot-password` | Forgot password form | ✗ | HTML |
| POST | `/forgot-password` | Send reset email | ✗ | JSON response |
| GET | `/reset-password/{token}` | Reset password form | ✗ | HTML (if valid token) |
| POST | `/reset-password/{token}` | Process password reset | ✗ | JSON response |
| GET | `/auth/google/login` | Start Google OAuth | ✗ | Redirect to Google |
| GET | `/auth/google/callback` | Google OAuth callback | ✗ | Redirect to dashboard |
| GET | `/dashboard` | User dashboard | ✓ | HTML |

---

## 🔑 Password Requirements

✓ **Validation Checklist:**
1. Minimum 8 characters
2. At least one uppercase letter (A-Z)
3. At least one number (0-9)
4. At least one special character (!@#$%^&*)

**Example Valid Passwords:**
- `Secure@Password123`
- `MySecure#Pass99`
- `Admin!2024Pass`

**Example Invalid Passwords:**
- `password` ✗ (no uppercase, numbers, or special chars)
- `PASSWORD123` ✗ (no special characters)
- `Pass1!` ✗ (only 6 characters)

---

## 🗄️ Database Tables

### User Table
```sql
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(500),  -- NULL for OAuth-only users
    role VARCHAR(50) DEFAULT 'user',
    google_id VARCHAR(500) UNIQUE,  -- OAuth provider
    github_id VARCHAR(500) UNIQUE,  -- OAuth provider
    microsoft_id VARCHAR(500) UNIQUE,  -- OAuth provider
    is_active BOOLEAN DEFAULT True,
    email_verified BOOLEAN DEFAULT False,
    risk_score FLOAT DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### PasswordResetToken Table
```sql
CREATE TABLE password_reset_token (
    id INTEGER PRIMARY KEY,
    user_id INTEGER FOREIGN KEY REFERENCES user(id),
    token VARCHAR(500) UNIQUE NOT NULL,
    expires_at DATETIME NOT NULL,
    used BOOLEAN DEFAULT False,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔒 Security Features

| Feature | Implementation | Details |
|---------|-----------------|---------|
| Password Hashing | bcrypt | Automatic salt generation |
| Session Tokens | JWT | 30-minute expiry + refresh |
| Reset Tokens | Secure Random | 64-character cryptographic token |
| Token Expiry | UTC datetime | 15 minutes for reset tokens |
| Single-Use Tokens | Boolean flag | Tokens marked "used" after reset |
| Cookie Security | HTTP-only | Prevents JavaScript access |
| CSRF Protection | State parameter | OAuth 2.0 state for CSRF prevention |
| Email Enumeration | Hidden | Same response for found/not-found |
| Input Validation | Pydantic | Server-side validation required |

---

## 🛠️ Development Setup

### Quick Start
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env file
cp .env.example .env  # Edit with your values

# 3. Initialize database
python create_db.py

# 4. Run server
uvicorn app.main:app --reload --port 8000

# 5. Visit application
# http://localhost:8000
```

### Testing Endpoints

**Test Password Reset:**
```bash
# 1. Visit http://localhost:8000/forgot-password
# 2. Enter your test email
# 3. Check server logs for token
# 4. Visit http://localhost:8000/reset-password/{token}
# 5. Enter new password
```

**Test Login:**
```bash
# 1. Register account at http://localhost:8000/signup
# 2. Login at http://localhost:8000/login
# 3. Verify dashboard loads
```

---

## 📧 Email Configuration (Optional)

For production password resets via email:

```python
# app/auth.py - Add email sending
import aiosmtplib
from email.mime.text import MIMEText

async def send_reset_email(email: str, reset_link: str):
    message = MIMEText(f'Reset your password: {reset_link}')
    message['Subject'] = 'Password Reset Request'
    
    async with aiosmtplib.SMTP(hostname=SMTP_SERVER, port=SMTP_PORT) as smtp:
        await smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        await smtp.send_message(message)
```

**Environment Variables Required:**
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

---

## 🔄 OAuth 2.0 Integration Status

### Google OAuth ✅ Ready to Configure
- **Files to Update:** `app/main.py`
- **Setup Time:** 15-20 minutes
- **Guide:** [GOOGLE_OAUTH_SETUP.md](GOOGLE_OAUTH_SETUP.md)

### GitHub OAuth 🟡 Framework Ready
- **Files to Update:** `app/main.py`
- **Implementation Time:** 15 minutes
- **Process:** Similar to Google OAuth

### Microsoft OAuth 🟡 Framework Ready
- **Files to Update:** `app/main.py`
- **Implementation Time:** 15 minutes
- **Note:** Requires Azure tenant configuration

---

## 🚀 Deployment Checklist

Before deploying to production:

- [ ] Change SECRET_KEY in environment variables
- [ ] Set DEBUG=False
- [ ] Configure HTTPS/SSL certificates
- [ ] Set up email service (SMTP or cloud provider)
- [ ] Configure Google OAuth credentials
- [ ] Update redirect URIs to production domain
- [ ] Enable secure cookies (secure=True)
- [ ] Set up database backups
- [ ] Configure rate limiting
- [ ] Enable CORS properly
- [ ] Set up monitoring/logging
- [ ] Create admin account
- [ ] Test password reset workflow
- [ ] Test OAuth login flow
- [ ] Review security headers

---

## 📚 File Structure

```
app/
├── main.py              ← Routes and endpoint definitions
├── auth.py              ← Authentication utilities
│   ├── verify_password()
│   ├── get_password_hash()
│   ├── create_access_token()
│   ├── generate_password_reset_token()
│   └── get_password_reset_token_expiry()
├── models.py            ← Database models
│   ├── User
│   └── PasswordResetToken
├── database.py          ← Database configuration
└── __init__.py

templates/
├── login.html           ← Login form + OAuth buttons
├── signup.html          ← Registration form
├── forgot_password.html ← Password reset request
├── reset_password.html  ← New password form
└── dashboard.html       ← Protected user dashboard
```

---

## 🔍 Monitoring & Logs

### Check for Errors
```bash
# Server logs show password reset tokens in development
# Look for: "Password reset token generated: ABC123..."
```

### User Account Status
```python
# Check if user exists
SELECT * FROM user WHERE email = 'user@example.com';

# Check password reset tokens
SELECT * FROM password_reset_token WHERE user_id = 1;

# View OAuth linked accounts
SELECT google_id, github_id, microsoft_id FROM user WHERE id = 1;
```

---

## ⚠️ Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "Invalid credentials" on login | Wrong password | Ensure password is correct, verify CAPS LOCK |
| "Email already exists" on signup | Duplicate email | Use different email or reset password |
| "Token expired" on reset | Token >15 mins old | Request new password reset link |
| "Invalid token" on reset | Wrong/malformed token | Check URL matches email link |
| OAuth redirect fails | Client ID/Secret wrong | Verify .env values match app credentials |
| Password too weak | Doesn't meet requirements | Add uppercase, number, and special character |
| Forget Password Email | Not sent (dev mode) | Check server logs for token instead |
| Session cookie not set | Secure=True on localhost | Use http://localhost:8000 not https |

---

## 🎯 Next Steps After Setup

1. **Test the System:**
   - Register a test account
   - Login with credentials
   - Test password reset flow
   - Verify tokens in database

2. **Configure Google OAuth:**
   - Follow [GOOGLE_OAUTH_SETUP.md](GOOGLE_OAUTH_SETUP.md)
   - Test Google login button
   - Verify user creation

3. **Add Email Service:**
   - Configure SMTP settings
   - Test password reset emails
   - Monitor email delivery

4. **Implement GitHub OAuth:**
   - Create GitHub OAuth App
   - Add client ID/secret to .env
   - Implement callback handler

5. **Deploy to Production:**
   - Follow deployment checklist
   - Configure domain and HTTPS
   - Update OAuth redirect URIs
   - Monitor login attempts

---

## 📖 Detailed Guides

- **[AUTHENTICATION_GUIDE.md](AUTHENTICATION_GUIDE.md)** - Complete authentication system documentation
- **[GOOGLE_OAUTH_SETUP.md](GOOGLE_OAUTH_SETUP.md)** - Step-by-step Google OAuth configuration
- **[README.md](README.md)** - Project overview and installation

---

## 🤝 Support & Resources

- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Authlib Docs:** https://docs.authlib.org/
- **OAuth 2.0 Spec:** https://tools.ietf.org/html/rfc6749
- **JWT Tokens:** https://jwt.io/
- **OWASP Auth:** https://owasp.org/www-community/attacks/
