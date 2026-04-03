# Google OAuth 2.0 Setup Guide

This guide provides step-by-step instructions to integrate Google OAuth 2.0 authentication into the UEBA platform.

## Prerequisites

- Google Account
- Google Cloud Console access
- Application already running with authentication framework in place
- `authlib` package installed (included in requirements.txt)

## Step 1: Create a Google Cloud Project

1. **Visit Google Cloud Console:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Sign in with your Google account

2. **Create a New Project:**
   - Click on the project dropdown at the top
   - Click "New Project"
   - Enter project name: `UEBA-Security-Hub`
   - Click "Create"
   - Wait for the project to be created (may take a minute)

3. **Select Your Project:**
   - Click on the project dropdown
   - Select `UEBA-Security-Hub`

## Step 2: Enable OAuth 2.0 API

1. **Enable the Google+ API:**
   - In the left sidebar, click "APIs & Services"
   - Click "Library"
   - Search for "Google+ API"
   - Click on it
   - Click "Enable"

2. **Enable the Google Identity API:**
   - Go back to Library
   - Search for "Google Identity APIs"
   - Click on "Google Identity API"
   - Click "Enable"

3. **Wait for APIs to initialize:**
   - The APIs are now active (may take a few moments)

## Step 3: Create OAuth 2.0 Credentials

1. **Navigate to Credentials:**
   - In the left sidebar, click "APIs & Services" > "Credentials"

2. **Create OAuth Consent Screen:**
   - If you see a warning about "Oauth consent screen", click "Create Consent Screen"
   - Select "External" as the user type
   - Click "Create"
   - Fill in the form:
     - **App name:** UEBA Security Hub
     - **User support email:** your-email@gmail.com
     - **Developer contact:** your-email@gmail.com
   - Click "Save and Continue"
   - On "Scopes" page, click "Add or Remove Scopes"
   - Search and select:
     - `openid`
     - `profile`
     - `email`
   - Click "Update"
   - Click "Save and Continue"
   - Review settings and click "Back to Dashboard"

3. **Create OAuth 2.0 Client ID:**
   - In "Credentials" page, click "Create Credentials"
   - Select "OAuth client ID"
   - Choose "Web application"
   - Configure:
     - **Name:** UEBA-Hub-OAuth-Client
     - **Authorized JavaScript origins:** 
       - `http://localhost:8000`  (for development)
       - `http://localhost` (optional)
       - `https://yourdomain.com` (for production)
     - **Authorized redirect URIs:**
       - `http://localhost:8000/auth/google/callback`
       
       - `https://yourdomain.com/auth/google/callback` (for production)
   - Click "Create"
   - Copy your Client ID and Client Secret (keep these secret!)

## Step 4: Configure Application

1. **Create `.env` file** (if not already created):
   ```bash
   # In your project root directory
   touch .env
   ```

2. **Add OAuth Credentials to `.env`:**
   ```env
   # Google OAuth Configuration
   GOOGLE_CLIENT_ID=your-client-id-from-step-3.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret-from-step-3
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
   
   # For production, use:
   # GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/google/callback
   ```

3. **Update `app/main.py` with OAuth handler:**

   Add imports at the top:
   ```python
   import os
   from authlib.integrations.starlette_client import OAuth, OAuthError
   from dotenv import load_dotenv
   
   load_dotenv()
   ```

   Initialize OAuth after FastAPI app creation:
   ```python
   app = FastAPI()
   
   oauth = OAuth()
   oauth.register(
       name='google',
       client_id=os.getenv('GOOGLE_CLIENT_ID'),
       client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
       server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
       client_kwargs={
           'scope': 'openid email profile'
       }
   )
   ```

4. **Implement OAuth Callback Route:**

   Replace the placeholder `/auth/google/callback` endpoint:
   ```python
   @app.get('/auth/google/callback')
   async def google_auth_callback(request: Request, db: Session = Depends(get_db)):
       """
       Handle Google OAuth 2.0 callback
       
       Advantages:
       - Automatic user creation on first login
       - Secure token exchange
       - Email-based user identification
       """
       try:
           token = await oauth.google.authorize_access_token(request)
       except OAuthError as error:
           error_msg = f'Invalid token: {error.description}'
           return RedirectResponse(url=f'/login?error={error_msg}')
       
       user_info = token.get('userinfo')
       if not user_info:
           return RedirectResponse(url='/login?error=Failed to get user info')
       
       email = user_info.get('email')
       google_id = user_info.get('sub')
       
       # Check if user exists
       user = db.query(User).filter(User.email == email).first()
       
       if not user:
           # Create new user from Google profile
           user = User(
               username=email.split('@')[0],  # Use email prefix as username
               email=email,
               google_id=google_id,
               is_active=True,
               email_verified=True,
               role='user'
           )
           db.add(user)
           db.commit()
           db.refresh(user)
       else:
           # Update existing user with Google ID if not set
           if not user.google_id:
               user.google_id = google_id
               db.commit()
       
       # Create session token
       access_token = create_access_token(data={'sub': user.email})
       
       # Set secure cookie
       response = RedirectResponse(url='/dashboard')
       response.set_cookie(
           key='access_token',
           value=access_token,
           httponly=True,
           secure=True,  # Set to False for localhost development
           samesite='lax'
       )
       
       return response
   ```

5. **Update Initiate OAuth Route:**

   Replace the placeholder `/auth/google/login` endpoint:
   ```python
   @app.get('/auth/google/login')
   async def google_login(request: Request):
       """
       Initiate Google OAuth 2.0 authentication flow (route `/auth/google/login`)
       
       Advantages:
       - Seamless OAuth integration
       - Secure state parameter generation
       - Automatic redirect to Google consent screen
       """
       redirect_uri = request.url_for('google_auth_callback')
       return await oauth.google.authorize_redirect(request, redirect_uri)
   ```

## Step 5: Update Requirements (if needed)

Verify these packages are installed:
```bash
pip install -r requirements.txt
```

The following packages should be present:
- `authlib>=1.2.0`
- `python-dotenv>=0.19.0` (for loading .env files)
- `starlette>=0.26.0` (included with FastAPI)

## Step 6: Test Google OAuth

1. **Start your application:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

2. **Navigate to login page:**
   - Open http://localhost:8000/login
   - Look for "Continue with Google" button

3. **Click the Google OAuth button:**
   - You'll be redirected to Google's login page
   - Sign in with your Google account
   - Grant permissions when prompted

4. **Verify successful login:**
   - You should be redirected to `/dashboard`
   - Check the database for new user with `google_id` field populated

## Step 7: Environment-Specific Configuration

### Development Environment
```env
DEBUG=True
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
# Secure cookie disabled for localhost
```

### Production Environment
```env
DEBUG=False
GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/google/callback
SECURE_COOKIES=True
# Requires HTTPS
```

## Troubleshooting

### Issue: "Invalid redirect_uri"
**Solution:** Ensure the redirect URI in `.env` exactly matches the one configured in Google Cloud Console.

### Issue: "Client authentication failed"
**Solution:** Verify your Client ID and Client Secret are correct in the `.env` file.

### Issue: "Redirect URL Mismatch"
**Solution:** 
1. Go to Google Cloud Console
2. Edit the OAuth credentials
3. Add `http://localhost:8000/auth/google/callback` to "Authorized redirect URIs"

### Issue: CORS errors
**Solution:** Google OAuth doesn't use CORS for backend communication, so this shouldn't occur. If it does, it may be a proxy issue.

### Issue: User not created
**Solution:** Check that `email_verified=True` is set. Google OAuth automatically verifies emails.

## Security Best Practices for Production

1. **HTTPS Only:**
   - Always use HTTPS in production
   - Set `secure=True` in cookies
   - Use HTTPS redirect URIs in Google Cloud

2. **State Parameter:**
   - Authlib automatically handles CSRF state parameter
   - Never allow requests without valid state

3. **Client Secret:**
   - Never commit `.env` to version control
   - Use environment variables in production
   - Store secrets in secure secret management (AWS Secrets Manager, Azure Key Vault, etc.)

4. **Token Expiry:**
   - Set reasonable token expiry times
   - Implement token refresh mechanism for long sessions
   - Revoke tokens on logout

5. **Scope Limitation:**
   - Only request necessary scopes: `openid`, `email`, `profile`
   - Minimize user data collection

6. **Rate Limiting:**
   - Implement rate limiting on `/auth/google` endpoint
   - Prevent login brute force attacks

## Multi-Account Support

The application supports users authenticating with:
- Traditional email/password
- Google OAuth
- GitHub OAuth (configure similarly)
- Microsoft OAuth (configure similarly)

A single email can be linked to multiple authentication methods. Users can:
1. Create account with email/password
2. Later link their Google account using the same email
3. Use either method to log in

## Advantages of Google OAuth Integration

### For Users:
- **No password to remember** - Use existing Google account
- **Faster login** - One click instead of typing credentials
- **Automatic account creation** - No need for registration page
- **Increased security** - Google's security replaces user-managed passwords
- **Email pre-verified** - Google verifies user emails

### For the Application:
- **Reduced support burden** - No password reset requests
- **Stronger security** - OAuth tokens instead of stored passwords
- **Trusted identity provider** - Google's authentication
- **Access to user data** - Email and profile information
- **Lower development cost** - Third-party authentication replaces custom auth

### For Security:
- **No password storage** - Reduces breach risk
- **OAuth 2.0 standard** - Compliant with industry standards
- **Token-based authentication** - Shorter-lived than passwords
- **Automatic scope limitation** - Users grant specific permissions
- **Auditability** - Can track OAuth logins separately

## Next Steps

1. ✅ Google OAuth configured and tested
2. **Optional:** Set up GitHub OAuth (similar process)
3. **Optional:** Set up Microsoft OAuth for enterprise
4. **Optional:** Implement email-based password reset
5. **Optional:** Add 2FA (Two-Factor Authentication)
6. **Deploy:** Move to production with HTTPS

## Additional Resources

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Authlib Documentation](https://docs.authlib.org/)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP OAuth 2.0 Security](https://owasp.org/www-community/attacks/oauth)

## Support

For issues with this setup, check:
1. Google Cloud Console credentials configuration
2. `.env` file values match console configuration
3. Server error logs for detailed error messages
4. Firewall/network access to Google OAuth servers

For application issues, refer to the main `AUTHENTICATION_GUIDE.md`.
