from flask import Flask, render_template_string, request, redirect, url_for, session
import requests
from urllib.parse import urlencode
import secrets
import os
from dotenv import load_dotenv

# --- Load env ---
load_dotenv()

def require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val

# --- Flask app + secret ---
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(16)

# --- Google OAuth configuration (from env where appropriate) ---
GOOGLE_CLIENT_ID = require("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = require("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = require("GOOGLE_REDIRECT_URI")  # e.g., http://localhost:3000

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Scopes for accessing user info
SCOPES = ["openid", "email", "profile"]

# Allowed email domain (configurable)
ALLOWED_EMAIL_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "student.monash.edu")

# ---------------- HTML templates (unchanged) ----------------
LOGIN_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>NilouVoter Login - Google OAuth Demo</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }
        .login-btn { background-color: #4285f4; color: white; border: none; padding: 12px 24px; border-radius: 4px; cursor: pointer; font-size: 16px; text-decoration: none; display: inline-block; margin: 20px 0; }
        .login-btn:hover { background-color: #357ae8; }
        .error { color: #d93025; background-color: #fce8e6; border: 1px solid #d93025; border-radius: 4px; padding: 10px; margin: 20px 0; }
        .restriction-notice { background-color: #fff3cd; color: #856404; border: 1px solid #ffeaa7; border-radius: 4px; padding: 15px; margin: 20px 0; }
    </style>
</head>
<body>
    <h1>NilouVoter Login</h1>
    <p>Sign in with your Monash student Google account</p>
    <div class="restriction-notice">
        <strong>⚠️ Welcome to NilouVoter</strong><br>
        Only work with <strong>@student.monash.edu</strong> else rejected L.
        <br><br>
        <img src="https://media.tenor.com/v96jmNd3sr8AAAAd/nilou-genshin-impact.gif" alt="Nilou Dance" style="display: block; margin: 15px auto; max-width: 100%; height: auto;">
    </div>
    {% if error %}
    <div class="error"><strong>Error:</strong> {{ error }}</div>
    {% endif %}
    <a href="{{ auth_url }}" class="login-btn">Sign in with Monash Student Account</a>
    <div style="margin-top: 40px; font-size: 12px; color: #666;">
        <p>This application will access your basic profile information (name, email, profile picture)</p>
        <p>Please use your @student.monash.edu email address</p>
    </div>
</body>
</html>
"""

PROFILE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>User Profile - Google OAuth Demo</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
        .profile-card { border: 1px solid #ddd; border-radius: 8px; padding: 20px; text-align: center; background-color: #f9f9f9; }
        .profile-picture { border-radius: 50%; width: 100px; height: 100px; margin-bottom: 20px; }
        .logout-btn { background-color: #ea4335; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 14px; text-decoration: none; display: inline-block; margin-top: 20px; }
        .logout-btn:hover { background-color: #d33b2c; }
        .info-item { margin: 10px 0; text-align: left; }
        .info-label { font-weight: bold; color: #333; }
        .success-message { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 4px; padding: 15px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>LETS FUCKING GO IT WORKED!</h1>
    <div class="success-message"><strong>✅ Successfully logged in!</strong><br>Welcome, <strong>{{ user_info.name }}</strong>!</div>
    <div class="profile-card">
        {% if user_info.picture %}<img src="{{ user_info.picture }}" alt="Profile Picture" class="profile-picture">{% endif %}
        <h2>{{ user_info.name }}</h2>
        <div class="info-item"><span class="info-label">Student Email:</span> {{ user_info.email }}</div>
        {% if user_info.given_name %}<div class="info-item"><span class="info-label">First Name:</span> {{ user_info.given_name }}</div>{% endif %}
        {% if user_info.family_name %}<div class="info-item"><span class="info-label">Last Name:</span> {{ user_info.family_name }}</div>{% endif %}
        <div class="info-item"><span class="info-label">Google ID:</span> {{ user_info.id }}</div>
        {% if user_info.verified_email %}<div class="info-item"><span class="info-label">Email Verified:</span> ✅ Yes</div>{% endif %}
        <a href="{{ url_for('logout') }}" class="logout-btn">Logout</a>
    </div>
    <div style="margin-top: 20px; font-size: 12px; color: #666;">
        <h3>Raw User Data (for debugging):</h3>
        <pre style="background-color: #f0f0f0; padding: 10px; border-radius: 4px; text-align: left; overflow-x: auto;">{{ user_info | tojson(indent=2) }}</pre>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    # OAuth callback return?
    if 'code' in request.args:
        return handle_oauth_callback()

    if 'user_info' in session:
        return redirect(url_for('profile'))

    # CSRF state
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state

    # Build Google OAuth URL
    auth_params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'scope': ' '.join(SCOPES),
        'response_type': 'code',
        'state': state,
        'access_type': 'offline',
        'prompt': 'consent'
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(auth_params)}"
    error = request.args.get('error')

    return render_template_string(LOGIN_TEMPLATE, auth_url=auth_url, error=error)

def handle_oauth_callback():
    # CSRF check
    if request.args.get('state') != session.get('oauth_state'):
        return redirect(url_for('index', error='Invalid state parameter'))

    if 'error' in request.args:
        return redirect(url_for('index', error=request.args.get('error_description', 'Authorization failed')))

    code = request.args.get('code')
    if not code:
        return redirect(url_for('index', error='No authorization code received'))

    try:
        # Exchange code for token
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code',
            'code': code
        }
        token_response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
        token_response.raise_for_status()
        token_info = token_response.json()

        if 'access_token' not in token_info:
            return redirect(url_for('index', error='Failed to obtain access token'))

        # Fetch user info
        headers = {'Authorization': f"Bearer {token_info['access_token']}"}
        user_response = requests.get(GOOGLE_USERINFO_URL, headers=headers)
        user_response.raise_for_status()
        user_info = user_response.json()

        # Domain restriction
        user_email = user_info.get('email', '')
        if not user_email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
            return redirect(url_for('index', error=f'Access denied. Only @{ALLOWED_EMAIL_DOMAIN} emails are allowed.'))

        print(f"✅ Successful login: {user_info.get('name', 'Unknown User')} ({user_email})")

        # Session
        session['user_info'] = user_info
        session['access_token'] = token_info['access_token']

        return redirect(url_for('profile'))

    except requests.exceptions.RequestException as e:
        return redirect(url_for('index', error=f'API request failed: {str(e)}'))
    except Exception as e:
        return redirect(url_for('index', error=f'Authentication failed: {str(e)}'))

@app.route('/callback')
def callback():
    # Keep for compatibility
    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    if 'user_info' not in session:
        return redirect(url_for('index'))
    return render_template_string(PROFILE_TEMPLATE, user_info=session['user_info'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    print("Starting Google OAuth Demo...")
    print("Open your browser and go to:", GOOGLE_REDIRECT_URI)
    print("Press Ctrl+C to stop the server")
    app.run(host='localhost', port=int(GOOGLE_REDIRECT_URI.split(':')[-1]), debug=True)
