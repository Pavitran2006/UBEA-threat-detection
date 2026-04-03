# OTP-Based Forgot Password Implementation
Approved plan execution steps:

## Step 1: Update services/auth_service.py [PENDING]
- Add forgot_password(email)
- Add verify_reset_otp(email, otp)  
- Add reset_password(email, new_password)

## Step 2: Update app/otp_service.py [PENDING]
- Add reset_otp_verify(email, otp)

## Step 3: Update routes/auth_routes.py [PENDING]
- Add /forgot-password GET/POST
- Add /verify-otp POST
- Add /reset-password GET/POST (OTP-based)

## Step 4: Update templates [PENDING]
- templates/forgot_password.html (OTP messaging)
- Repurpose templates/reset_password.html
- Create templates/verify_otp.html

## Step 5: Test [PENDING]
- Configure .env SMTP
- python run_server.py
- Test flow: forgot → OTP email → verify → reset

## Step 6: Complete [PENDING]
- attempt_completion

