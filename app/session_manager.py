import time
import uuid
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from passlib.context import CryptContext

# Configure logging for security events
logger = logging.getLogger("session_manager")
logging.basicConfig(level=logging.INFO)

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class SecureSessionManager:
    """
    Manages active user sessions using an in-memory Map (dictionary).
    Implements secure login, global reset, and session timeout behaviors.
    """
    
    def __init__(self, session_timeout_minutes: int = 30):
        # 1. Maintain login data using a Map
        self._user_sessions: Dict[str, Dict[str, Any]] = {}  # sessionId -> sessionData
        self._session_timeout = timedelta(minutes=session_timeout_minutes)
        self._dummy_db = {
            "pavitran": pwd_context.hash("SecurePass123!"),
            "system_admin": pwd_context.hash("AdminAccess99")
        }
        logger.info("Session Manager Initialized.")

    # 2. Implement resetLogin() function
    def resetLogin(self) -> str:
        """
        Completely clear all stored login information from the Map.
        Ensure no previous session, token, or credential remains.
        """
        old_count = len(self._user_sessions)
        
        # Use clear() method as requested
        self._user_sessions.clear()
        
        logger.warning(f"SECURITY EVENT: Global Login Reset triggered. {old_count} sessions purged.")
        
        # 3. After clearing return message for redirect/prompt logic
        return "Session expired. Please log in again."

    # 4. Implement login flow
    def login(self, username: str, password: str) -> Optional[str]:
        """
        Accept username/password, validate, and store new session data.
        """
        # Validate credentials
        hashed_pwd = self._dummy_db.get(username)
        if not hashed_pwd or not pwd_context.verify(password, hashed_pwd):
            logger.warning(f"FAILED LOGIN: Invalid credentials for user '{username}'")
            return None

        # If valid: Generate unique sessionId
        session_id = str(uuid.uuid4())
        
        # Store new login data in the Map
        self._user_sessions[session_id] = {
            "username": username,
            "login_time": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "logged_in": True
        }
        
        logger.info(f"SUCCESSFUL LOGIN: User '{username}' authenticated. Session: {session_id[:8]}...")
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves session data and checks for timeout / inactivity.
        """
        session = self._user_sessions.get(session_id)
        if not session:
            return None

        # 5. Add security improvements: Session timeout check
        now = datetime.utcnow()
        if now - session["last_activity"] > self._session_timeout:
            logger.info(f"SESSION EXPIRED: Session {session_id[:8]}... timed out due to inactivity.")
            del self._user_sessions[session_id]
            return None

        # Update last activity timestamp
        session["last_activity"] = now
        return session

    # 6. Optional: Logout functionality calling resetLogin logic
    def logout_user(self, session_id: str):
        """
        Explicit logout for a single user.
        """
        if session_id in self._user_sessions:
            user = self._user_sessions[session_id].get("username")
            del self._user_sessions[session_id]
            logger.info(f"USER LOGOUT: Session for '{user}' terminated.")

# Example Usage Demonstration
if __name__ == "__main__":
    manager = SecureSessionManager(session_timeout_minutes=1)
    
    # Simulate Login
    print("--- 1. Attempting Login ---")
    sid = manager.login("pavitran", "SecurePass123!")
    if sid:
        print(f"Login Success! Session ID: {sid}")
    
    # Verify Session
    session = manager.get_session(sid)
    print(f"Session Active: {session['username'] if session else 'No'}")

    # Simulate Global Reset
    print("\n--- 2. Performing Global Reset ---")
    message = manager.resetLogin()
    print(f"Manager Response: {message}")

    # Verify sessions are cleared
    session_after = manager.get_session(sid)
    if not session_after:
        print("Verification: No session remains for previous session ID.")
    else:
        print("Error: Session still exists!")

    # Check Logout
    sid2 = manager.login("system_admin", "AdminAccess99")
    print(f"\n--- 3. Single User Logout ---")
    manager.logout_user(sid2)
    print(f"Session for admin exists: {sid2 in manager._user_sessions}")
