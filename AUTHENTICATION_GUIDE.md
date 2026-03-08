# Secure Authentication System - Implementation Guide

This document explains the comprehensive authentication system implemented for the UEBA Security Intelligence Platform.

## Features Implemented

### 1. Password Reset / Forgot Password System

**Flow:**
1. User visits `/forgot-password` page
2. Enters their email address
3. System sends reset link via email (placeholder in current implementation)
4. Link points to `/reset-password/{token}`
5. User enters new password (must meet strength requirements)
6. System validates token expiry (15 minutes)
7. Password is updated using bcrypt hashing
8. Token marked as used to prevent reuse

**Security Features:**
- Cryptographically secure token generation (64 characters)
- 15-minute token expiry for prevent abuse
- One-time use tokens (marked as used after reset)
- Password strength validation:
  - Minimum 8 characters
  - At least one uppercase letter
  - At least one number
  - At least one special character (! @ # $ % ^ & *)
- Token expiry validation before password reset
- No email existence leakage (same message for existing/non-existing emails)

**Database Schema:**
```sql
-- PasswordResetToken table
- id (Primary Key)
- user_id (Foreign Key to User)
- token (64-character secure random string)
- expires_at (UTC timestamp, 15 minutes from creation)
- used (Boolean flag to prevent reuse)
- created_at (Timestamp of token creation)
```

### 2. Google OAuth 2.0 Authentication

This section walks through every step required to add "Sign in with Google" to the application.

#### 2.1. Create credentials in Google Cloud Console

1. **Open the Cloud Console:** https://console.cloud.google.com/
2. **Create or select a project** (e.g. `ueba-security-hub`).
3. **Enable APIs & Services:**
   - Navigate to "APIs & Services > Library".
   - Enable **Google Identity Services** (and "Google+ API" if shown).
4. **Configure OAuth consent screen:**
   - In "APIs & Services > OAuth consent screen", choose "External".
   - Fill in app name (UEBA Security Hub), support email, developer contact.
   - Add scopes: `openid`, `email`, `profile`.
   - Save and continue through the wizard.
5. **Create OAuth 2.0 Client ID:**
   - Go to "Credentials" tab, click "Create Credentials" → "OAuth client ID".
   - Select "Web application".
   - Name: `UEBA Web Client`.
   - **Authorized JavaScript origins:**
     - `http://localhost:8000` (and `https://yourdomain.com` for prod).
   - **Authorized redirect URIs:**
     - `http://localhost:8000/auth/google/callback`
     - Add production URI later (`https://yourdomain.com/auth/google/callback`).
   - Click "Create" and copy the **Client ID** and **Client Secret**.

  > ⚠️ The redirect URI must match exactly – trailing slashes matter.

6. **Store credentials securely:**
   - Add to your `.env` file (never commit it):
     ```env
     GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
     GOOGLE_CLIENT_SECRET=your-client-secret
     GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
     ```
   - In production, update the URI and set `DEBUG=False`.

#### 2.2. Required Python libraries

Add the following to `requirements.txt` (already included earlier):

```txt
authlib>=1.2.0        # OAuth2/OIDC client
python-dotenv>=0.19.0 # load .env variables
```

Install with:
```bash
pip install -r requirements.txt
```

#### 2.3. FastAPI backend changes

At the top of `app/main.py` import and initialize OAuth:

```python
import os
from authlib.integrations.starlette_client import OAuth, OAuthError
from dotenv import load_dotenv

load_dotenv()

oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)
```

##### Routes

```python
# initiates the flow
@app.get('/auth/google/login')
async def auth_google(request: Request):
    redirect_uri = request.url_for('auth_google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)

# handles callback
@app.get('/auth/google/callback')
async def auth_google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        return RedirectResponse(url=f'/login?error={error.description}')
    user_info = token.get('userinfo')
    email = user_info.get('email')
    google_id = user_info.get('sub')
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(username=email.split('@')[0],
                    email=email,
                    google_id=google_id,
                    is_active=True,
                    email_verified=True,
                    role='user')
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if not user.google_id:
            user.google_id = google_id
            db.commit()
    access_token = create_access_token(data={'sub': user.email})
    response = RedirectResponse(url='/dashboard')
    _set_auth_cookie(response, access_token)
    return response
```

These routes perform tasks 6–9 from your list: exchanging the code, looking up/creating a user, storing data, and returning a JWT session token.

> Note: we renamed the initiate route to `/auth/google/login` for clarity; update any front‑end links accordingly.

#### 2.4. Front‑end button

On your login page (`templates/login.html`):

```html
<a href="/auth/google/login" class="oauth-btn oauth-google">
  <svg ...>  <!-- Google logo svg -->
  </svg>
  Continue with Google
</a>
```

You already have this button styled with `.oauth-google` in the CSS; the `href` is now `/auth/google/login`.

#### 2.5. Security best practices

* Never commit client secrets; use environment variables or a secret manager.
* Use HTTPS in production; set `secure=True` on cookies when deploying.
* Validate the `state` parameter – Authlib handles this automatically.
* Only request scopes you need (`openid email profile`).
* Limit authorized redirect URIs in Google Console to known domains.
* Rotate OAuth credentials if you suspect compromise.

#### 2.6. Testing the flow

1. Restart the server: `uvicorn app.main:app --reload --port 8000`.
2. Open `http://localhost:8000/login` and click "Continue with Google".
3. Authenticate with Google; grant permissions.
4. You should be redirected to `/dashboard` and a new user record appears with `google_id` populated.
5. Log out and repeat; the same account should be reused.

If an error occurs, check console output for messages; common issues include
mismatched redirect URI or incorrect client ID/secret.

#### 2.7. Environment variables recap

Ensure the following are defined (in `.env` or your deployment platform):

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

Reload the environment or restart your process to pick them up.

---

The above steps satisfy all tasks in your request: console configuration, client ID creation, redirect URI, placement of credentials, backend routes, account creation/login logic, JWT issuance, and front‑end button code.  With `authlib` installed and `dotenv` loaded, the integration is complete.

Continue by following the testing procedures in `TESTING_GUIDE.md` (see OAuth section), and remember to update the authorized redirect URI when you deploy to production.
### 3. GitHub OAuth (Ready for Implementation)

**Status:** Placeholder endpoint in place

**Configuration needed:**
```python
GITHUB_CLIENT_ID=your_github_app_id
GITHUB_CLIENT_SECRET=your_github_app_secret
GITHUB_REDIRECT_URI=http://localhost:8000/auth/github/callback
```

### 4. Microsoft OAuth (Ready for Implementation)

**Status:** Placeholder endpoint in place

**Configuration needed:**
```python
MICROSOFT_CLIENT_ID=your_azure_app_id
MICROSOFT_CLIENT_SECRET=your_azure_app_secret
MICROSOFT_TENANT_ID=your_tenant_id
MICROSOFT_REDIRECT_URI=http://localhost:8000/auth/microsoft/callback
```

## User Model Updates

**New Fields Added:**
```python
# OAuth Integration
google_id: String (unique, nullable)
github_id: String (unique, nullable)
microsoft_id: String (unique, nullable)

# Account Management
is_active: Boolean (default: True)
email_verified: Boolean (default: False)

# Timestamps
updated_at: DateTime (on update)

# Password Security
hashed_password: Now nullable (OAuth users don't need passwords)
```

## Frontend Pages

### 1. Forgot Password Page (`/forgot-password`)

**Features:**
- Dark cybersecurity theme matching platform
- Email input field with validation
- Clear instructions about reset link
- Success/error notifications
- Link back to login
- Information about security

**Design Elements:**
- Card-based layout with glassmorphism
- Cyan glow accent (#06b6d4)
- Animated background with gradient
- Loading spinner on submit
- Responsive design for mobile

### 2. Reset Password Page (`/reset-password/{token}`)

**Features:**
- Password input with visibility toggle
- Confirm password field
- Real-time password strength indicator (4 levels: Weak, Fair, Good, Strong)
- Password requirements checklist (dynamic validation)
- Token expiry validation
- Error messages for expired/invalid tokens

**Password Requirements:**
- ✓ At least 8 characters
- ✓ One uppercase letter
- ✓ One number
- ✓ One special character

**Design Elements:**
- Color-coded strength bars
- Dynamic requirement checklist with checkmarks
- Matching password validation
- Visual feedback for all interactions
- Disabled submit button until all requirements met

## Email Configuration (To be Implemented)

Currently, password reset emails are logged to console (development mode).

**To enable email sending, add to backend:**

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

async def send_reset_email(email: str, token: str):
    """Send password reset email with secure link"""
    
    reset_link = f"http://your-domain.com/reset-password/{token}"
    
    message = MIMEMultipart()
    message["From"] = os.getenv("SMTP_FROM_EMAIL")
    message["To"] = email
    message["Subject"] = "Reset Your Password - UEBA Security Platform"
    
    body = f"""
    Hello,
    
    You requested to reset your password. Click the link below to proceed:
    
    {reset_link}
    
    This link expires in 15 minutes for security purposes.
    
    If you did not request this, please ignore this email.
    
    Best regards,
    UEBA Security Intelligence Team
    """
    
    message.attach(MIMEText(body, "plain"))
    
    # Send via SMTP
    server = smtplib.SMTP(os.getenv("SMTP_SERVER"), os.getenv("SMTP_PORT"))
    server.starttls()
    server.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD"))
    server.send_message(message)
    server.quit()
```

**Environment Variables Needed:**
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@your-domain.com
```

## Security Best Practices Implemented

1. **Password Hashing:**
   - Using bcrypt with automatic salt generation
   - Passwords never stored in plain text
   - Password requirements enforced on frontend and backend

2. **Token Security:**
   - Cryptographically secure random generation
   - 64-character tokens (2^384 possible values)
   - Short expiry windows (15 minutes)
   - One-time use tokens

3. **OAuth Security:**
   - CSRF protection via state parameter (to be implemented)
   - Secure HTTPS redirects
   - Client secret never exposed to frontend
   - Minimal permissions requested

4. **Email Security:**
   - No email existence leakage (same message for found/not found)
   - Links include tokens only (no user ID visible)
   - Links expire quickly
   - One-time use only

## API Endpoints Reference

### Password Reset Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/forgot-password` | Display forgot password form |
| POST | `/forgot-password` | Send password reset email |
| GET | `/reset-password/{token}` | Display reset password form |
| POST | `/reset-password/{token}` | Process password reset |

### OAuth Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/auth/google/login` | Initiate Google OAuth |
| GET | `/auth/google/callback` | Handle Google callback |
| GET | `/auth/github` | Initiate GitHub OAuth (ready) |
| GET | `/auth/microsoft` | Initiate Microsoft OAuth (ready) |

## Testing the Features

### Test Forgot Password Flow:

1. **Access forgot password page:**
   ```
   http://localhost:8000/forgot-password
   ```

2. **Submit email:**
   Enter any email address and click "Send Reset Link"

3. **Check console for token:**
   Look in server console for logged token (dev mode)

4. **Access reset page:**
   ```
   http://localhost:8000/reset-password/{token}
   ```

5. **Reset password:**
   Enter new password meeting all requirements

## Future Enhancements

1. **Email Service Integration:**
   - Implement SendGrid, AWS SES, or SMTP
   - HTML email templates
   - Internationalization (multiple languages)

2. **OAuth Providers:**
   - Complete Google OAuth implementation
   - Add GitHub OAuth integration
   - Add Microsoft/Azure AD integration
   - Add SAML support for enterprise

3. **Two-Factor Authentication:**
   - TOTP (Time-based One-Time Password)
   - SMS verification
   - Backup codes

4. **Account Security:**
   - Password change history
   - Login attempt tracking
   - Suspicious activity alerts
   - Device management console

5. **Audit Logging:**
   - Log all authentication events
   - Track password reset requests
   - Monitor OAuth token exchanges
   - Alert on failed attempts

## Advantages of This System

### For Users:
- **Easy Recovery:** Forgot password? Reset in 15 minutes
- **Multiple Login Options:** Choose how to authenticate
- **Security:** Strong password requirements protect accounts
- **Privacy:** No tracking of email existence
- **Mobile Friendly:** Works on all devices

### For Security:
- **Secure Defaults:** bcrypt hashing, HTTPS, token expiry
- **Audit Trail:** All auth events can be logged
- **Enterprise Ready:** OAuth supports corporate logins
- **OWASP Compliant:** Follows security best practices
- **Scalable:** Ready for multi-tenancy

### For Developers:
- **Well Documented:** Clear code comments and docstrings
- **Modular Design:** Easy to extend with more OAuth providers
- **Error Handling:** Proper HTTP status codes and messages
- **Testing Ready:** Clear endpoints for manual testing
- **Framework Agnostic:** Can be adapted to other frameworks

## Requirements

### Python Packages (To Add):
```bash
pip install authlib              # OAuth 2.0 implementation
pip install google-auth          # Google OAuth support
pip install aiosmtplib          # Async email sending
pip install python-multipart     # Form data parsing
```

### Update `requirements.txt`:
Add the following lines:
```
authlib==1.2.0
google-auth==2.25.0
google-auth-oauthlib==1.1.0
google-auth-httplib2==0.2.0
aiosmtplib==3.0.0
python-dotenv==1.0.0
```

## Conclusion

This authentication system provides enterprise-grade security while maintaining ease of use. The modular design allows for easy extension with additional OAuth providers and authentication methods as needed.
