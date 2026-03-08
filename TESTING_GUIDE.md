# Authentication System Testing Guide

This guide provides comprehensive testing procedures for all authentication features in the UEBA platform.

## 📋 Pre-Testing Setup

### Requirements
1. Python 3.8+ installed
2. All dependencies installed: `pip install -r requirements.txt`
3. `.env` file created with configuration
4. Database initialized: `python create_db.py` (if needed)
5. Server running: `uvicorn app.main:app --reload --port 8000`

### Browser Setup
- Use a modern browser (Chrome, Firefox, Safari, Edge)
- Clear cookies before each test suite: Ctrl+Shift+Del (Windows) or Cmd+Shift+Del (Mac)
- Keep Developer Console open: F12
- Test on both desktop and mobile viewports

---

## ✅ Test Suite 1: Registration & Account Creation

### Test 1.1: Valid Registration
**Steps:**
1. Navigate to http://localhost:8000/signup
2. Fill in form:
   - **Username:** testuser123
   - **Email:** testuser@example.com
   - **Password:** Secure@Pass123
   - **Confirm Password:** Secure@Pass123
   - **Role:** user
3. Click "Sign Up"

**Expected Results:**
- ✓ Form submits without validation errors
- ✓ Redirected to dashboard
- ✓ User appears in database
- ✓ Welcome message displayed

**Verification:**
```sql
SELECT * FROM user WHERE email = 'testuser@example.com';
-- Should show: username=testuser123, is_active=True
```

### Test 1.2: Duplicate Email Registration
**Steps:**
1. Repeat Test 1.1 with same email
2. Try to sign up again

**Expected Results:**
- ✓ Registration form shows error
- ✓ Error message: "Email already registered"
- ✓ User not created (stays at signup page)

### Test 1.3: Weak Password Rejection
**Steps:**
1. Navigate to signup page
2. Fill form with weak password: `password`
3. Click "Sign Up"

**Expected Results:**
- ✓ Form validation shows errors
- ✓ Submit button disabled
- ✓ Error messages explain requirements

### Test 1.4: Missing Required Fields
**Steps:**
1. Navigate to signup page
2. Leave one field empty (e.g., username)
3. Try to submit

**Expected Results:**
- ✓ Browser validation prevents submission
- ✓ Field shows required indicator
- ✓ Error message displayed

### Test 1.5: Invalid Email Format
**Steps:**
1. Fill signup form with invalid email: `notanemail`
2. Try to submit

**Expected Results:**
- ✓ Validation error shown
- ✓ Form highlights email field
- ✓ Error: "Invalid email format"

---

## ✅ Test Suite 2: Login & Session Management

### Test 2.1: Valid Login
**Steps:**
1. Navigate to http://localhost:8000/login
2. Enter credentials:
   - **Email:** testuser@example.com
   - **Password:** Secure@Pass123
3. Click "Log In"

**Expected Results:**
- ✓ Login successful
- ✓ Redirected to dashboard
- ✓ Session cookie created (visible in DevTools)
- ✓ User name displayed in dashboard

### Test 2.2: Invalid Password
**Steps:**
1. Navigate to login page
2. Enter:
   - **Email:** testuser@example.com
   - **Password:** WrongPassword123
3. Click "Log In"

**Expected Results:**
- ✓ Login fails
- ✓ Error message shown
- ✓ Logged back at login page
- ✓ Cookie not set

### Test 2.3: Non-existent Email
**Steps:**
1. Navigate to login page
2. Enter:
   - **Email:** nonexistent@example.com
   - **Password:** Secure@Pass123
3. Click "Log In"

**Expected Results:**
- ✓ Login fails
- ✓ Generic error message (no email enumeration)
- ✓ Remains at login page

### Test 2.4: Empty Fields
**Steps:**
1. Leave email or password empty
2. Try to submit form

**Expected Results:**
- ✓ Browser validation prevents submission
- ✓ Required field indicator shown

### Test 2.5: Session Timeout
**Steps:**
1. Login successfully
2. Wait 30+ minutes (or modify token expiry in testing)
3. Try to access dashboard
4. Refresh page

**Expected Results:**
- ✓ Redirected to login page
- ✓ Old session token rejected
- ✓ Can login again with credentials

### Test 2.6: Logout
**Steps:**
1. Login successfully (Test 2.1)
2. Click "Logout" button on dashboard
3. Try to navigate to dashboard

**Expected Results:**
- ✓ Redirected to home page
- ✓ Session cookie cleared
- ✓ Cannot access protected pages

---

## ✅ Test Suite 3: Password Reset Flow

### Test 3.1: Forgot Password - Valid Email
**Steps:**
1. Navigate to http://localhost:8000/forgot-password
2. Enter email: testuser@example.com
3. Click "Send Reset Link"

**Expected Results:**
- ✓ Success message shown: "Check your email for reset link"
- ✓ Server logs show token: "Password reset token generated: ABC123XYZ..."
- ✓ PasswordResetToken created in database

**Verification:**
```sql
SELECT token, expires_at FROM password_reset_token 
WHERE user_id = (SELECT id FROM user WHERE email = 'testuser@example.com')
ORDER BY created_at DESC LIMIT 1;
```

### Test 3.2: Forgot Password - Non-existent Email
**Steps:**
1. Navigate to forgot_password page
2. Enter email: nonexistent@example.com
3. Click "Send Reset Link"

**Expected Results:**
- ✓ Same success message shown (no email enumeration)
- ✓ No token created in database
- ✓ Security: attacker can't detect valid emails

### Test 3.3: Reset Password - Valid Token
**Steps:**
1. Complete Test 3.1 to get token
2. Copy token from server logs
3. Navigate to: http://localhost:8000/reset-password/{token}
4. Verify page loads with form

**Expected Results:**
- ✓ Reset password form displayed
- ✓ Page shows "Token is valid"
- ✓ Password input field active

### Test 3.4: Reset Password - Invalid Token
**Steps:**
1. Navigate to: http://localhost:8000/reset-password/invalid_token_here
2. Try to view page

**Expected Results:**
- ✓ Error message: "Invalid or expired reset token"
- ✓ Form not displayed
- ✓ Link to request new token shown

### Test 3.5: Reset Password - Expired Token
**Steps:**
1. Generate a reset token (Test 3.1)
2. Wait 15+ minutes (or manually modify expires_at in database)
3. Try to use token

**Expected Results:**
- ✓ Error: "Reset token has expired"
- ✓ Prompt to request new reset link
- ✓ Cannot reset with expired token

### Test 3.6: Password Reset - Valid Token + Strong Password
**Steps:**
1. Complete Test 3.3 (valid token)
2. Fill in form:
   - **New Password:** NewSecure@Pass456
   - **Confirm Password:** NewSecure@Pass456
3. Click "Reset Password"

**Expected Results:**
- ✓ Success message: "Password successfully reset"
- ✓ Redirected to login page
- ✓ Old password no longer works
- ✓ New password logs in successfully
- ✓ Token marked as used in database

**Verification:**
```sql
-- Old password should fail login
-- New password should work

-- Check token marked as used
SELECT used FROM password_reset_token 
WHERE token = '{token_here}';
-- Should show: used = True
```

### Test 3.7: Password Reset - Weak Password
**Steps:**
1. Complete Test 3.3 (valid token)
2. Enter weak password: `password`
3. Try to submit

**Expected Results:**
- ✓ Form shows validation errors
- ✓ Submit button disabled
- ✓ Requirements checklist shows unmet criteria
- ✓ Password not changed

### Test 3.8: Password Reset - Mismatched Passwords
**Steps:**
1. Complete Test 3.3 (valid token)
2. Fill form:
   - **New Password:** NewSecure@Pass456
   - **Confirm Password:** Different@Pass789
3. Click "Reset Password"

**Expected Results:**
- ✓ Real-time validation shows mismatch
- ✓ Submit button disabled
- ✓ Error message: "Passwords do not match"
- ✓ Password not changed

### Test 3.9: Token Single-Use (Reuse Prevention)
**Steps:**
1. Complete Test 3.6 (use token successfully)
2. Get the same token from server logs
3. Try to use token again: http://localhost:8000/reset-password/{same_token}

**Expected Results:**
- ✓ Error: "Token has already been used"
- ✓ Security: prevents token reuse attack

### Test 3.10: Password Strength Indicator
**Steps:**
1. Visit http://localhost:8000/reset-password/{valid_token}
2. Type different passwords and observe indicator

**Test Cases:**
| Password | Expected Strength | Bar Color |
|----------|-------------------|-----------|
| `p` | Weak | Red (0/4 requirements) |
| `password` | Weak | Red (no uppercase) |
| `Password1` | Fair | Yellow (no special char) |
| `Password1!` | Good | Blue (8 chars + requirements) |
| `MyVerySecure@Pass123` | Strong | Green (all requirements + length) |

**Expected Results:**
- ✓ Real-time strength updates as typing
- ✓ Correct colors for each strength level
- ✓ Requirements checklist updates dynamically

---

## ✅ Test Suite 4: Password Strength Validation

### Test 4.1: Registration Password Strength
**Steps:**
1. Visit signup page
2. Test each password strength scenario
3. Observe real-time validation

**Test Cases:**
| Input | Valid | Issue |
|-------|-------|-------|
| `short` | ✗ | Less than 8 chars |
| `nogoodchars` | ✗ | No uppercase or numbers |
| `NoNumbers!` | ✗ | No numbers |
| `NoSpecial123` | ✗ | No special character |
| `Good@Pass1` | ✓ | All requirements met |

**Expected Results:**
- ✓ Each requirement highlighted as met/unmet
- ✓ Submit button disabled until all met
- ✓ Green checkmarks appear as requirements met

### Test 4.2: Reset Password Strength
**Steps:**
1. Complete Test 3.3 (valid reset token)
2. Repeat Test 4.1 password tests on reset form

**Expected Results:**
- ✓ Same validation behavior as signup
- ✓ Real-time feedback
- ✓ Submit disabled for weak passwords

### Test 4.3: Special Characters Coverage
**Steps:**
1. Test each special character: !@#$%^&*()_+-=[]{}
2. Try password with each character

**Expected Results:**
- ✓ Each special character passes validation
- ✓ Requirement shows as met
- ✓ No validation errors

---

## ✅ Test Suite 5: OAuth Integration (When Configured)

### Test 5.1: Google OAuth Button Display
**Steps:**
1. Navigate to http://localhost:8000/login
2. Look for "Continue with Google" button

**Expected Results:**
- ✓ Button visible with Google colors
- ✓ Button clickable
- ✓ Google logo displayed

### Test 5.2: Google OAuth Redirect
**Steps:**
1. Click "Continue with Google" button
2. Observe redirect

**Expected Results:**
- ✓ Redirected to Google login page
- ✓ Correct consent scope requested
- ✓ No error messages

### Test 5.3: Google OAuth Callback Success
**Steps:**
1. Complete Google OAuth flow
2. Allow permissions
3. Observe redirect back to app

**Expected Results:**
- ✓ Redirected to dashboard
- ✓ New user created if first login
- ✓ Existing user logged in if account exists
- ✓ google_id field populated in database

**Verification:**
```sql
SELECT email, google_id, created_at FROM user 
WHERE google_id IS NOT NULL;
```

### Test 5.4: OAuth Account Linking
**Steps:**
1. Create account with email: oauth-test@example.com (password method)
2. Logout
3. Try to login with Google using same email
4. Allow permissions

**Expected Results:**
- ✓ Existing account linked to Google
- ✓ No duplicate account created
- ✓ Both login methods work (password + Google)

### Test 5.5: OAuth Failure Handling
**Steps:**
1. Click "Continue with Google"
2. Deny permissions
3. Observe error handling

**Expected Results:**
- ✓ Redirected with error message
- ✓ Back at login page
- ✓ Clear error explanation
- ✓ Can retry

---

## ✅ Test Suite 6: Security & Edge Cases

### Test 6.1: SQL Injection Prevention
**Steps:**
1. Try to login with SQL injection in email field:
   - `' OR '1'='1' --`
   - `admin'--`
   - `" OR 1=1; DROP TABLE users; --`

**Expected Results:**
- ✓ All attempts treated as invalid email
- ✓ No SQL errors shown
- ✓ Login fails gracefully
- ✓ Database unaffected

### Test 6.2: XSS Prevention (Signup)
**Steps:**
1. Enter in username field: `<script>alert('XSS')</script>`
2. Complete signup

**Expected Results:**
- ✓ Script not executed
- ✓ Username stored as plain text
- ✓ No alerts shown
- ✓ Displayed safely in dashboard

### Test 6.3: CSRF Protection (If Cookie Session)
**Steps:**
1. Create malicious form on different domain
2. Try to auto-submit to password reset endpoint
3. Check if request rejected

**Expected Results:**
- ✓ Request fails without valid CSRF token
- ✓ Or SameSite cookie prevents cross-site
- ✓ Action not performed

### Test 6.4: Rate Limiting (If Implemented)
**Steps:**
1. Make multiple rapid login attempts (5+ in 1 minute)
2. Try to login again immediately

**Expected Results:**
- ✓ Requests throttled after threshold
- ✓ Error: "Too many attempts"
- ✓ Can retry after cooldown period

### Test 6.5: Brute Force Protection
**Steps:**
1. Attempt multiple wrong passwords for same account
2. Try 10+ attempts in short time
3. Check if account locked

**Expected Results:**
- ✓ Account remains accessible (good UX)
- ✓ IP/account rate-limited
- ✓ Error after N attempts
- ✓ Can still reset password

---

## ✅ Test Suite 7: Database & Data Integrity

### Test 7.1: User Data Storage Verification
**Queries to Run:**
```sql
-- Check all users
SELECT id, username, email, is_active, created_at FROM user;

-- Verify password is hashed (not plain text)
SELECT LENGTH(hashed_password) FROM user WHERE id = 1;
-- Should be ~60 characters (bcrypt hash)

-- Check password is bcrypt format
SELECT hashed_password FROM user WHERE id = 1;
-- Should start with $2b$12$ (bcrypt identifier)
```

**Expected Results:**
- ✓ All passwords hashed, never plain text
- ✓ Bcrypt format confirmed
- ✓ Email verified for OAuth users
- ✓ Created/updated timestamps present

### Test 7.2: Password Reset Token Storage
**Queries to Run:**
```sql
-- Check all reset tokens
SELECT id, user_id, token, expires_at, used FROM password_reset_token;

-- Verify token is 64 characters
SELECT LENGTH(token) FROM password_reset_token;
-- Should be 64

-- Check expiry in future
SELECT expires_at > CURRENT_TIMESTAMP as is_valid FROM password_reset_token;
```

**Expected Results:**
- ✓ Tokens are 64 random characters
- ✓ Expiry times are UTC datetime
- ✓ Used flag properly updated
- ✓ Old tokens can be cleaned up

### Test 7.3: Data Consistency
**Queries to Run:**
```sql
-- Verify foreign key constraints
-- These should not return passwords reset tokens for non-existent users
SELECT prt.* FROM password_reset_token prt
LEFT JOIN user u ON prt.user_id = u.id
WHERE u.id IS NULL;
-- Should return 0 rows

-- Check duplicate entries
SELECT email, COUNT(*) as count FROM user GROUP BY email HAVING count > 1;
-- Should return 0 rows (unique constraint)

SELECT username, COUNT(*) as count FROM user GROUP BY username HAVING count > 1;
-- Should return 0 rows (unique constraint)
```

**Expected Results:**
- ✓ No orphaned password reset tokens
- ✓ No duplicate emails
- ✓ No duplicate usernames
- ✓ Referential integrity maintained

---

## ✅ Test Suite 8: Cross-Browser & Responsive Testing

### Test 8.1: Desktop Browser Compatibility
**Browsers to Test:**
- [ ] Google Chrome (latest)
- [ ] Mozilla Firefox (latest)
- [ ] Safari (latest)
- [ ] Microsoft Edge (latest)

**Pages to Test:**
- signup, login, forgot_password, reset_password

**For Each Browser:**
1. Check form layouts render correctly
2. Test password strength indicator
3. Test visibility toggles
4. Submit forms successfully

**Expected Results:**
- ✓ Pages render identically
- ✓ All fields aligned properly
- ✓ Colors display correctly
- ✓ Animations smooth
- ✓ Forms submit successfully

### Test 8.2: Mobile Responsive (320px - 768px)
**Steps:**
1. Open DevTools (F12)
2. Enable Device Toolbar
3. Test with devices: iPhone SE (375px), iPad (768px)

**Pages to Test:**
- All authentication pages

**For Each Breakpoint:**
1. Check layout adapts
2. Fields stack vertically
3. Buttons remain clickable
4. Text remains readable

**Expected Results:**
- ✓ 100% responsive design
- ✓ Touch-friendly button sizes
- ✓ No content overflow
- ✓ Readable text sizes
- ✓ Forms fully functional

### Test 8.3: Dark Mode (If Applicable)
**Steps:**
1. Enable dark mode in OS settings
2. Reload application
3. Check if theme adjusts or stays consistent

**Expected Results:**
- ✓ Page visible in dark mode
- ✓ Text readable (good contrast)
- ✓ Form inputs accessible
- ✓ Colors appropriate

---

## ✅ Test Suite 9: Performance Testing

### Test 9.1: Form Responsiveness
**Steps:**
1. Type rapidly in password field
2. Observe strength indicator update
3. Check for lag or delays

**Expected Results:**
- ✓ Real-time validation without lag
- ✓ Strength bar updates instantly
- ✓ No JavaScript errors
- ✓ Smooth animations

### Test 9.2: Page Load Time
**Steps:**
1. Open DevTools Network tab
2. Navigate to each page
3. Record load time

**Expected Results:**
- ✓ Each page loads in <2 seconds
- ✓ No slow HTTP requests
- ✓ CSS/JS optimized

---

## 🐛 Debugging Tips

### Enable Debug Mode
```env
DEBUG=True
```

### View Server Logs
```bash
# Watch logs in real-time
tail -f app.log

# Check for password reset tokens
grep "password reset token" app.log
```

### Browser DevTools Inspection

**Check Cookies:**
1. Open DevTools (F12)
2. Application → Cookies
3. Look for `access_token` cookie
4. Verify it's HTTP-only and Secure (HTTPS only)

**Check Network:**
1. Network tab
2. Login and watch requests
3. Verify POST request succeeds
4. Check response status (200)

**Check Console:**
1. Console tab
2. Look for JavaScript errors
3. Verify no failed API calls

### Database Inspection
```bash
# Access SQLite
sqlite3 instance/ueba_app.db

# List all tables
.tables

# Query users
SELECT * FROM user;

# Exit
.exit
```

---

## 📊 Test Results Template

```
Test Suite: _________________
Date: _____________________
Tester: ___________________
Browser: __________________
OS: ______________________

Test Name | Status | Notes | Timestamp
-----------|--------|-------|----------
1.1        | PASS   |       | 
1.2        | PASS   |       |
...

Issues Found:
1. 
2.
3.

Sign-Off: _________________ Date: _______
```

---

## ✅ Acceptance Criteria

All tests in this suite must PASS before:
- [ ] Deployment to staging
- [ ] Deployment to production
- [ ] Release to beta users
- [ ] Public launch

---

## 📞 Support & Escalation

If tests fail:
1. Check error messages in browser console (F12)
2. Review server logs for exceptions
3. Verify database schema is correct
4. Check environment variables (.env)
5. Review recent code changes
6. Consult troubleshooting guides in AUTHENTICATION_GUIDE.md

---
