from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import requests
from urllib.parse import urlencode
import secrets
import os
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta
import json

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

# JWT secret for API tokens
JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_hex(32)

# Backend API URL
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

# --- Google OAuth configuration ---
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

# Admin emails (can be configured in .env)
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "admin@student.monash.edu").split(",")

# ---------------- HTML templates ----------------
LOGIN_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>NilouVoter Login - Monash Voting System</title>
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
        Only works with <strong>@student.monash.edu</strong> emails.
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

VOTING_DASHBOARD = """<!DOCTYPE html>
<html>
<head>
    <title>NilouVoter - Voting Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background-color: #4285f4; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .user-info { background-color: #f0f0f0; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .user-info img { border-radius: 50%; width: 50px; height: 50px; vertical-align: middle; margin-right: 10px; }
        .elections-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .election-card { border: 1px solid #ddd; border-radius: 8px; padding: 20px; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .election-card h3 { margin-top: 0; color: #333; }
        .status-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; }
        .status-active { background-color: #d4edda; color: #155724; }
        .status-closed { background-color: #f8d7da; color: #721c24; }
        .status-scheduled { background-color: #fff3cd; color: #856404; }
        .btn { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
        .btn-primary { background-color: #4285f4; color: white; }
        .btn-primary:hover { background-color: #357ae8; }
        .btn-secondary { background-color: #6c757d; color: white; }
        .btn-secondary:hover { background-color: #5a6268; }
        .btn-danger { background-color: #ea4335; color: white; }
        .btn-danger:hover { background-color: #d33b2c; }
        .admin-panel { background-color: #e3f2fd; border: 2px solid #2196f3; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        .loading { text-align: center; padding: 20px; }
        .error-msg { color: #d93025; background-color: #fce8e6; border: 1px solid #d93025; border-radius: 4px; padding: 10px; margin: 10px 0; }
        .success-msg { color: #155724; background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 4px; padding: 10px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="header">
        <h1>NilouVoter - Voting Dashboard</h1>
        <p>Monash Student Council Electronic Voting System</p>
    </div>
    
    <div class="user-info">
        {% if user_info.picture %}<img src="{{ user_info.picture }}" alt="Profile Picture">{% endif %}
        <strong>{{ user_info.name }}</strong> ({{ user_info.email }})
        {% if is_admin %}<span class="status-badge" style="background: #e91e63; color: white; margin-left: 10px;">ADMIN</span>{% endif %}
        <a href="{{ url_for('logout') }}" class="btn btn-danger" style="float: right;">Logout</a>
    </div>
    
    {% if is_admin %}
    <div class="admin-panel">
        <h2>Admin Panel</h2>
        <a href="{{ url_for('create_election_page') }}" class="btn btn-primary">Create New Election</a>
        <a href="{{ url_for('view_audit_logs') }}" class="btn btn-secondary">View Audit Logs</a>
        <a href="{{ url_for('manage_templates') }}" class="btn btn-secondary">Manage Templates</a>
    </div>
    {% endif %}
    
    <h2>Available Elections</h2>
    <div id="elections-container" class="loading">Loading elections...</div>
    
    <script>
        // Store user info and API token
        const userInfo = {{ user_info | tojson }};
        const apiToken = '{{ api_token }}';
        const apiUrl = '{{ api_url }}';
        
        // Fetch elections
        async function loadElections() {
            try {
                const response = await fetch(`${apiUrl}/api/elections`);
                const elections = await response.json();
                
                const container = document.getElementById('elections-container');
                container.classList.remove('loading');
                
                if (elections.length === 0) {
                    container.innerHTML = '<p>No elections available at this time.</p>';
                    return;
                }
                
                container.innerHTML = '<div class="elections-grid">' + 
                    elections.map(election => `
                        <div class="election-card">
                            <h3>${election.title}</h3>
                            <p>${election.description || 'No description available'}</p>
                            <p><strong>Start:</strong> ${new Date(election.start_time).toLocaleString()}</p>
                            <p><strong>End:</strong> ${new Date(election.end_time).toLocaleString()}</p>
                            <p>
                                <span class="status-badge status-${election.status}">
                                    ${election.status.toUpperCase()}
                                </span>
                                ${election.is_frozen ? '<span class="status-badge" style="background: #ff9800; color: white; margin-left: 5px;">FROZEN</span>' : ''}
                            </p>
                            ${election.status === 'active' && !election.is_frozen ? 
                                `<a href="/vote/${election.id}" class="btn btn-primary">Vote Now</a>` : 
                                election.status === 'closed' ? 
                                `<a href="/results/${election.id}" class="btn btn-secondary">View Results</a>` :
                                '<span style="color: #666;">Voting not available</span>'
                            }
                        </div>
                    `).join('') + '</div>';
            } catch (error) {
                document.getElementById('elections-container').innerHTML = 
                    '<div class="error-msg">Failed to load elections. Please try again later.</div>';
            }
        }
        
        // Load elections on page load
        loadElections();
        
        // Refresh every 30 seconds
        setInterval(loadElections, 30000);
    </script>
</body>
</html>
"""

VOTING_PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>Vote - NilouVoter</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .header { background-color: #4285f4; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .candidate { border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px 0; background: white; }
        .candidate h3 { margin-top: 0; }
        .rank-selector { width: 60px; padding: 5px; font-size: 16px; }
        .voter-info { background-color: #f0f0f0; padding: 15px; border-radius: 8px; margin: 20px 0; }
        .btn { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }
        .btn-submit { background-color: #4caf50; color: white; font-size: 18px; padding: 15px 30px; }
        .btn-submit:hover { background-color: #45a049; }
        .btn-back { background-color: #6c757d; color: white; }
        .error { color: #d93025; }
        .form-group { margin: 15px 0; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group select, .form-group input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Cast Your Vote</h1>
        <p id="election-title">Loading...</p>
    </div>
    
    <a href="/dashboard" class="btn btn-back">← Back to Dashboard</a>
    
    <div class="voter-info">
        <h3>Voter Information</h3>
        <p>Please provide your details for demographic analysis (your vote remains secret):</p>
        
        <div class="form-group">
            <label for="faculty">Faculty:</label>
            <select id="faculty" required>
                <option value="">Select Faculty</option>
                <option value="Engineering">Engineering</option>
                <option value="Business">Business</option>
                <option value="Arts">Arts</option>
                <option value="Science">Science</option>
                <option value="Medicine">Medicine</option>
                <option value="Law">Law</option>
                <option value="Education">Education</option>
                <option value="IT">Information Technology</option>
            </select>
        </div>
        
        <div class="form-group">
            <label for="gender">Gender:</label>
            <select id="gender" required>
                <option value="">Select Gender</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Non-binary">Non-binary</option>
                <option value="Prefer not to say">Prefer not to say</option>
            </select>
        </div>
        
        <div class="form-group">
            <label for="study_level">Study Level:</label>
            <select id="study_level" required>
                <option value="">Select Study Level</option>
                <option value="Undergraduate">Undergraduate</option>
                <option value="Postgraduate">Postgraduate</option>
                <option value="PhD">PhD</option>
            </select>
        </div>
        
        <div class="form-group">
            <label for="year_level">Year Level:</label>
            <select id="year_level" required>
                <option value="">Select Year</option>
                <option value="1">1st Year</option>
                <option value="2">2nd Year</option>
                <option value="3">3rd Year</option>
                <option value="4">4th Year</option>
                <option value="5">5+ Year</option>
            </select>
        </div>
    </div>
    
    <h2>Rank Candidates (1 = Most Preferred)</h2>
    <div id="candidates-container">Loading candidates...</div>
    
    <button class="btn btn-submit" onclick="submitVote()">Submit Vote</button>
    
    <div id="message"></div>
    
    <script>
        const electionId = {{ election_id }};
        const userInfo = {{ user_info | tojson }};
        const apiUrl = '{{ api_url }}';
        let candidates = [];
        
        async function loadElection() {
            try {
                // Load election details
                const electionResponse = await fetch(`${apiUrl}/api/elections`);
                const elections = await electionResponse.json();
                const election = elections.find(e => e.id === electionId);
                
                if (election) {
                    document.getElementById('election-title').textContent = election.title;
                }
                
                // Load candidates
                const candidatesResponse = await fetch(`${apiUrl}/api/elections/${electionId}/candidates`);
                candidates = await candidatesResponse.json();
                
                const container = document.getElementById('candidates-container');
                container.innerHTML = candidates.map((candidate, index) => `
                    <div class="candidate">
                        <h3>${candidate.name}</h3>
                        <p><strong>Faculty:</strong> ${candidate.faculty || 'Not specified'}</p>
                        <p><strong>Manifesto:</strong> ${candidate.manifesto || 'No manifesto provided'}</p>
                        <label>Preference Rank: 
                            <select class="rank-selector" data-candidate-id="${candidate.id}">
                                ${candidates.map((_, i) => 
                                    `<option value="${i+1}" ${i === index ? 'selected' : ''}>${i+1}</option>`
                                ).join('')}
                            </select>
                        </label>
                    </div>
                `).join('');
                
                // Add change listeners to prevent duplicate ranks
                document.querySelectorAll('.rank-selector').forEach(selector => {
                    selector.addEventListener('change', validateRanks);
                });
                
            } catch (error) {
                document.getElementById('candidates-container').innerHTML = 
                    '<div class="error">Failed to load candidates. Please try again.</div>';
            }
        }
        
        function validateRanks() {
            const selectors = document.querySelectorAll('.rank-selector');
            const ranks = Array.from(selectors).map(s => parseInt(s.value));
            const uniqueRanks = new Set(ranks);
            
            if (uniqueRanks.size !== ranks.length) {
                alert('Each candidate must have a unique rank!');
                return false;
            }
            return true;
        }
        
        async function submitVote() {
            if (!validateRanks()) return;
            
            // Get voter traits
            const faculty = document.getElementById('faculty').value;
            const gender = document.getElementById('gender').value;
            const studyLevel = document.getElementById('study_level').value;
            const yearLevel = document.getElementById('year_level').value;
            
            if (!faculty || !gender || !studyLevel || !yearLevel) {
                alert('Please fill in all voter information fields');
                return;
            }
            
            // Collect preferences
            const preferences = {};
            document.querySelectorAll('.rank-selector').forEach(selector => {
                const candidateId = selector.dataset.candidateId;
                const rank = parseInt(selector.value);
                preferences[candidateId] = rank;
            });
            
            // Prepare vote data
            const voteData = {
                google_user_info: {
                    id: userInfo.id,
                    email: userInfo.email,
                    name: userInfo.name,
                    picture: userInfo.picture
                },
                election_id: electionId,
                preferences: preferences,
                voter_traits: {
                    faculty: faculty,
                    gender: gender,
                    study_level: studyLevel,
                    year_level: parseInt(yearLevel)
                }
            };
            
            try {
                const response = await fetch(`${apiUrl}/api/vote`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(voteData)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    document.getElementById('message').innerHTML = `
                        <div style="background: #d4edda; color: #155724; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h2>✓ Vote Submitted Successfully!</h2>
                            <p><strong>Confirmation Code:</strong> ${result.confirmation_code}</p>
                            <p><strong>Receipt Number:</strong> ${result.receipt_number}</p>
                            <p>Keep these codes for your records. You can verify your vote was counted using the confirmation code.</p>
                            <a href="/receipt/${result.receipt_number}" class="btn btn-primary" target="_blank">View Receipt</a>
                            <a href="/dashboard" class="btn btn-secondary">Back to Dashboard</a>
                        </div>
                    `;
                    
                    // Disable submit button
                    document.querySelector('.btn-submit').disabled = true;
                } else {
                    throw new Error(result.detail || 'Failed to submit vote');
                }
            } catch (error) {
                document.getElementById('message').innerHTML = 
                    `<div class="error">Error: ${error.message}</div>`;
            }
        }
        
        // Load election data on page load
        loadElection();
    </script>
</body>
</html>
"""

# Helper function to generate JWT token
def generate_api_token(user_info):
    """Generate JWT token for API authentication"""
    payload = {
        'google_id': user_info.get('id'),
        'email': user_info.get('email'),
        'name': user_info.get('name'),
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

# Routes
@app.route('/')
def index():
    # OAuth callback return?
    if 'code' in request.args:
        return handle_oauth_callback()

    if 'user_info' in session:
        return redirect(url_for('dashboard'))

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

        # Store in session
        session['user_info'] = user_info
        session['access_token'] = token_info['access_token']
        session['api_token'] = generate_api_token(user_info)
        session['is_admin'] = user_email in ADMIN_EMAILS

        return redirect(url_for('dashboard'))

    except requests.exceptions.RequestException as e:
        return redirect(url_for('index', error=f'API request failed: {str(e)}'))
    except Exception as e:
        return redirect(url_for('index', error=f'Authentication failed: {str(e)}'))

@app.route('/dashboard')
def dashboard():
    """Main dashboard showing available elections"""
    if 'user_info' not in session:
        return redirect(url_for('index'))
    
    return render_template_string(
        VOTING_DASHBOARD,
        user_info=session['user_info'],
        is_admin=session.get('is_admin', False),
        api_token=session.get('api_token'),
        api_url=BACKEND_API_URL
    )

@app.route('/vote/<int:election_id>')
def vote_page(election_id):
    """Voting page for a specific election"""
    if 'user_info' not in session:
        return redirect(url_for('index'))
    
    return render_template_string(
        VOTING_PAGE,
        user_info=session['user_info'],
        election_id=election_id,
        api_url=BACKEND_API_URL
    )

@app.route('/receipt/<receipt_number>')
def view_receipt(receipt_number):
    """View vote receipt"""
    if 'user_info' not in session:
        return redirect(url_for('index'))
    
    try:
        response = requests.get(f"{BACKEND_API_URL}/api/receipts/{receipt_number}")
        if response.ok:
            return response.text
        else:
            return "Receipt not found", 404
    except:
        return "Error retrieving receipt", 500

@app.route('/verify-vote', methods=['GET', 'POST'])
def verify_vote():
    """Vote verification page"""
    if 'user_info' not in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        confirmation_code = request.form.get('confirmation_code')
        verification_data = {
            'confirmation_code': confirmation_code,
            'google_id': session['user_info']['id']
        }
        
        try:
            response = requests.post(
                f"{BACKEND_API_URL}/api/verify-vote",
                json=verification_data
            )
            return jsonify(response.json()), response.status_code
        except:
            return jsonify({'error': 'Verification failed'}), 500
    
    # Show verification form
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Verify Vote</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            .form-group { margin: 20px 0; }
            .form-group input { width: 100%; padding: 10px; font-size: 16px; }
            .btn { padding: 10px 20px; background: #4285f4; color: white; border: none; border-radius: 4px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>Verify Your Vote</h1>
        <form method="POST">
            <div class="form-group">
                <label>Enter your confirmation code:</label>
                <input type="text" name="confirmation_code" required>
            </div>
            <button type="submit" class="btn">Verify</button>
        </form>
        <a href="/dashboard">Back to Dashboard</a>
    </body>
    </html>
    """

@app.route('/results/<int:election_id>')
def view_results(election_id):
    """View election results"""
    if 'user_info' not in session:
        return redirect(url_for('index'))
    
    try:
        response = requests.get(f"{BACKEND_API_URL}/api/elections/{election_id}/results")
        results = response.json()
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Election Results</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .results {{ background: #f0f0f0; padding: 20px; border-radius: 8px; }}
                .chart {{ margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>Election Results: {results['title']}</h1>
            <div class="results">
                <p>Total Votes: {results['total_votes']}</p>
                <h3>Vote Counts:</h3>
                <pre>{json.dumps(results['vote_counts'], indent=2)}</pre>
                <h3>Demographics:</h3>
                <pre>{json.dumps(results['turnout_by_faculty'], indent=2)}</pre>
            </div>
            <a href="/dashboard">Back to Dashboard</a>
        </body>
        </html>
        """
    except:
        return "Error loading results", 500

# Admin routes (simplified examples)
@app.route('/admin/create-election')
def create_election_page():
    if 'user_info' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Create Election</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }
            .form-group { margin: 15px 0; }
            .form-group input, .form-group textarea { width: 100%; padding: 8px; }
            .btn { padding: 10px 20px; background: #4285f4; color: white; border: none; border-radius: 4px; }
        </style>
    </head>
    <body>
        <h1>Create New Election</h1>
        <form id="election-form">
            <div class="form-group">
                <label>Title:</label>
                <input type="text" id="title" required>
            </div>
            <div class="form-group">
                <label>Description:</label>
                <textarea id="description" rows="3"></textarea>
            </div>
            <div class="form-group">
                <label>Start Time:</label>
                <input type="datetime-local" id="start_time" required>
            </div>
            <div class="form-group">
                <label>End Time:</label>
                <input type="datetime-local" id="end_time" required>
            </div>
            <button type="submit" class="btn">Create Election</button>
        </form>
        <a href="/dashboard">Back to Dashboard</a>
        
        <script>
            document.getElementById('election-form').onsubmit = async (e) => {
                e.preventDefault();
                
                const data = {
                    title: document.getElementById('title').value,
                    description: document.getElementById('description').value,
                    start_time: new Date(document.getElementById('start_time').value).toISOString(),
                    end_time: new Date(document.getElementById('end_time').value).toISOString()
                };
                
                try {
                    const response = await fetch('${BACKEND_API_URL}/api/elections', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(data)
                    });
                    
                    if (response.ok) {
                        alert('Election created successfully!');
                        window.location.href = '/dashboard';
                    } else {
                        alert('Failed to create election');
                    }
                } catch (error) {
                    alert('Error: ' + error.message);
                }
            };
        </script>
    </body>
    </html>
    """.replace('${BACKEND_API_URL}', BACKEND_API_URL)

@app.route('/admin/audit-logs')
def view_audit_logs():
    if 'user_info' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))
    
    try:
        response = requests.get(f"{BACKEND_API_URL}/api/audit-logs?limit=50")
        logs = response.json()
        
        logs_html = ''.join([f"""
            <tr>
                <td>{log['timestamp']}</td>
                <td>{log['action_type']}</td>
                <td>{log.get('actor_email', 'N/A')}</td>
                <td>{log.get('election_id', 'N/A')}</td>
                <td><pre>{json.dumps(log.get('details', {}), indent=2)}</pre></td>
            </tr>
        """ for log in logs])
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Audit Logs</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background: #4285f4; color: white; }}
                pre {{ margin: 0; font-size: 12px; }}
            </style>
        </head>
        <body>
            <h1>Audit Logs</h1>
            <table>
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Action</th>
                        <th>Actor</th>
                        <th>Election ID</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
                    {logs_html}
                </tbody>
            </table>
            <a href="/dashboard">Back to Dashboard</a>
        </body>
        </html>
        """
    except:
        return "Error loading audit logs", 500

@app.route('/admin/templates')
def manage_templates():
    if 'user_info' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Manage Templates</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .template { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px; }
            .btn { padding: 10px 20px; background: #4285f4; color: white; border: none; border-radius: 4px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>Election Templates</h1>
        <div id="templates-container">Loading templates...</div>
        <a href="/dashboard">Back to Dashboard</a>
        
        <script>
            async function loadTemplates() {
                try {
                    const response = await fetch('""" + BACKEND_API_URL + """/api/templates');
                    const templates = await response.json();
                    
                    document.getElementById('templates-container').innerHTML = 
                        templates.map(t => `
                            <div class="template">
                                <h3>${t.name}</h3>
                                <p>${t.description}</p>
                                <pre>${JSON.stringify(t.config, null, 2)}</pre>
                            </div>
                        `).join('');
                } catch (error) {
                    document.getElementById('templates-container').innerHTML = 'Error loading templates';
                }
            }
            loadTemplates();
        </script>
    </body>
    </html>
    """

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# API proxy endpoints (optional - for additional security)
@app.route('/api/proxy/vote', methods=['POST'])
def proxy_vote():
    """Proxy vote requests to backend with authentication"""
    if 'user_info' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    # Add Google user info from session
    data['google_user_info'] = {
        'id': session['user_info']['id'],
        'email': session['user_info']['email'],
        'name': session['user_info'].get('name'),
        'picture': session['user_info'].get('picture')
    }
    
    try:
        response = requests.post(
            f"{BACKEND_API_URL}/api/vote",
            json=data,
            headers={'Authorization': f"Bearer {session.get('api_token')}"}
        )
        return jsonify(response.json()), response.status_code
    except:
        return jsonify({'error': 'Backend error'}), 500

if __name__ == '__main__':
    print("="*60)
    print("MONASH VOTING SYSTEM - INTEGRATED LOGIN")
    print("="*60)
    print(f"\nMake sure backend is running at: {BACKEND_API_URL}")
    print(f"Login interface will be at: {GOOGLE_REDIRECT_URI}")
    print("\nRequired .env variables:")
    print("  - GOOGLE_CLIENT_ID")
    print("  - GOOGLE_CLIENT_SECRET")
    print("  - GOOGLE_REDIRECT_URI")
    print("  - BACKEND_API_URL (optional, defaults to http://localhost:8000)")
    print("  - ADMIN_EMAILS (optional, comma-separated list)")
    print("\nPress Ctrl+C to stop the server")
    
    app.run(host='localhost', port=int(GOOGLE_REDIRECT_URI.split(':')[-1]), debug=True)