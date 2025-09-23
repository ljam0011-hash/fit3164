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
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>NilouVoter Login - Monash Voting System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            min-height: 100vh;
            background: #0f172a;
            color: white;
            overflow-x: hidden;
            position: relative;
        }
        
        /* Animated background */
        .background {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            overflow: hidden;
        }
        
        .aura-bg {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: conic-gradient(from 0deg at 20% 10%, #0ea5e9 0deg, #4338ca 120deg, #a21caf 240deg, #0ea5e9 360deg);
            opacity: 0.4;
            animation: spin-slow 40s linear infinite;
        }
        
        @keyframes spin-slow {
            to { transform: rotate(360deg); }
        }
        
        .vignette {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: radial-gradient(ellipse at center, rgba(0,0,0,0) 40%, rgba(0,0,0,0.6));
        }
        
        .floating-orb {
            position: absolute;
            border-radius: 50%;
            filter: blur(40px);
            opacity: 0.7;
            mix-blend-mode: screen;
            animation: float 6s ease-in-out infinite;
        }
        
        .orb-1 {
            width: 360px;
            height: 360px;
            background: linear-gradient(135deg, #38bdf8, #6366f1);
            top: -120px;
            left: -220px;
            animation-delay: 0.2s;
        }
        
        .orb-2 {
            width: 420px;
            height: 420px;
            background: linear-gradient(135deg, #d946ef, #f43f5e);
            top: 60px;
            right: -220px;
            animation-delay: 0.4s;
        }
        
        .orb-3 {
            width: 260px;
            height: 260px;
            background: linear-gradient(135deg, #2dd4bf, #10b981);
            bottom: -120px;
            left: -80px;
            animation-delay: 0.6s;
        }
        
        @keyframes float {
            0%, 100% { transform: translateY(0px) scale(1); }
            50% { transform: translateY(-20px) scale(1.05); }
        }
        
        .grid-pattern {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: 
                linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px);
            background-size: 40px 40px;
            opacity: 0.3;
        }
        
        .spotlight {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: radial-gradient(300px 300px at var(--mx, 50%) var(--my, 50%), rgba(255,255,255,0.08), transparent 60%);
            pointer-events: none;
        }
        
        /* Main content */
        .container {
            position: relative;
            z-index: 10;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        
        .header-text {
            text-align: center;
            margin-bottom: 3rem;
            animation: slideUp 0.8s ease-out;
        }
        
        .secure-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 2rem;
            padding: 0.5rem 1rem;
            font-size: 0.75rem;
            color: rgba(255,255,255,0.7);
            margin-bottom: 1rem;
            backdrop-filter: blur(10px);
        }
        
        .secure-indicator {
            width: 6px;
            height: 6px;
            background: #38bdf8;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .main-title {
            font-size: 3rem;
            font-weight: 600;
            line-height: 1.1;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #38bdf8, #d946ef);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .subtitle {
            font-size: 1.125rem;
            color: rgba(255,255,255,0.7);
            max-width: 32rem;
            line-height: 1.6;
        }
        
        .glass-card {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 1.5rem;
            padding: 2rem;
            backdrop-filter: blur(20px);
            box-shadow: 0 8px 80px rgba(0,0,0,0.4);
            width: 100%;
            max-width: 28rem;
            animation: slideUp 0.8s ease-out 0.2s both;
        }
        
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .brand-lockup {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .brand-icon {
            width: 3rem;
            height: 3rem;
            background: rgba(255,255,255,0.15);
            border-radius: 0.75rem;
            display: flex;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(10px);
        }
        
        .brand-text h1 {
            font-size: 1.5rem;
            font-weight: 600;
            line-height: 1.2;
        }
        
        .brand-text p {
            color: rgba(255,255,255,0.7);
            font-size: 0.875rem;
        }
        
        .google-btn {
            width: 100%;
            background: white;
            color: #1f2937;
            border: none;
            border-radius: 0.75rem;
            padding: 1.5rem;
            font-size: 1rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.75rem;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            position: relative;
            overflow: hidden;
        }
        
        .google-btn:hover {
            background: rgba(255,255,255,0.9);
            transform: translateY(-1px);
            box-shadow: 0 8px 30px rgba(0,0,0,0.3);
        }
        
        .google-btn:active {
            transform: translateY(0);
        }
        
        .google-btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.6), rgba(255,255,255,0.1));
            opacity: 0;
            transition: opacity 0.2s ease;
            border-radius: 0.75rem;
        }
        
        .google-btn:hover::before {
            opacity: 1;
        }
        
        .google-icon {
            width: 1.5rem;
            height: 1.5rem;
            z-index: 1;
            position: relative;
        }
        
        .restriction-notice {
            background: rgba(255, 243, 205, 0.1);
            color: #fbbf24;
            border: 1px solid rgba(251, 191, 36, 0.3);
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin: 2rem 0;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        
        .restriction-notice strong {
            display: block;
            margin-bottom: 0.5rem;
            font-size: 1.125rem;
        }
        
        .nilou-gif {
            max-width: 100%;
            height: auto;
            border-radius: 0.75rem;
            margin: 1rem auto;
            display: block;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        
        .error {
            color: #fca5a5;
            background: rgba(252, 165, 165, 0.1);
            border: 1px solid rgba(252, 165, 165, 0.3);
            border-radius: 0.75rem;
            padding: 1rem;
            margin: 1rem 0;
            backdrop-filter: blur(10px);
        }
        
        .footer-info {
            margin-top: 2rem;
            font-size: 0.75rem;
            color: rgba(255,255,255,0.5);
            text-align: center;
            line-height: 1.6;
        }
        
        .footer-links {
            margin-top: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 1rem;
            font-size: 0.875rem;
            color: rgba(255,255,255,0.7);
        }
        
        .footer-links a {
            color: inherit;
            text-decoration: none;
            transition: color 0.2s ease;
        }
        
        .footer-links a:hover {
            color: rgba(255,255,255,0.95);
        }
        
        .footer-links .separator {
            opacity: 0.3;
        }
        
        /* Responsive design */
        @media (max-width: 768px) {
            .container {
                padding: 1rem;
            }
            
            .main-title {
                font-size: 2rem;
            }
            
            .glass-card {
                padding: 1.5rem;
            }
            
            .brand-lockup {
                flex-direction: column;
                text-align: center;
                gap: 0.5rem;
            }
        }
        
        /* Accessibility */
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
        }
    </style>
</head>
<body>
    <div class="background">
        <div class="aura-bg"></div>
        <div class="vignette"></div>
        <div class="floating-orb orb-1"></div>
        <div class="floating-orb orb-2"></div>
        <div class="floating-orb orb-3"></div>
        <div class="grid-pattern"></div>
        <div class="spotlight" id="spotlight"></div>
    </div>
    
    <main class="container">
        <div class="header-text">
            <div class="secure-badge">
                <div class="secure-indicator"></div>
                Secure Access Portal
            </div>
            <h2 class="main-title">Welcome to NilouVoter</h2>
            <p class="subtitle">
                Sign in with your Monash student account to access the electronic voting system
            </p>
        </div>
        
        <div class="glass-card">
            <div class="brand-lockup">
                <div class="brand-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 12l2 2 4-4"/>
                        <path d="M21 12c-1 0-3-1-3-3s2-3 3-3 3 1 3 3-2 3-3 3"/>
                        <path d="M3 12c1 0 3-1 3-3s-2-3-3-3-3 1-3 3 2 3 3 3"/>
                        <path d="M12 3c0 1-1 3-3 3s-3-2-3-3 1-3 3-3 3 2 3 3"/>
                        <path d="M12 21c0-1-1-3-3-3s-3 2-3 3 1 3 3 3 3-2 3-3"/>
                    </svg>
                </div>
                <div class="brand-text">
                    <h1>Monash University</h1>
                    <p>Student Voting Portal</p>
                </div>
            </div>
            
            <div class="restriction-notice">
                <strong>Welcome to NilouVoter</strong>
                Only works with <strong>@student.monash.edu</strong> emails.
                <img src="https://media.tenor.com/v96jmNd3sr8AAAAd/nilou-genshin-impact.gif" 
                     alt="Nilou Dance" class="nilou-gif">
            </div>
            
            {% if error %}
            <div class="error">
                <strong>Error:</strong> {{ error }}
            </div>
            {% endif %}
            
            <a href="{{ auth_url }}" class="google-btn">
                <svg class="google-icon" viewBox="0 0 48 48" aria-hidden="true">
                    <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.9 32.6 29.3 36 24 36 16.8 36 11 30.2 11 23S16.8 10 24 10c3.6 0 6.8 1.5 9 3.9l5.7-5.7C35.5 4.1 30.1 2 24 2 12 2 2 12 2 24s10 22 22 22c11.2 0 21-8.1 21-22 0-1.2-.1-2.2-.4-3.5z"/>
                    <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 16.5 18.9 14 24 14c3.6 0 6.8 1.5 9 3.9l5.7-5.7C35.5 4.1 30.1 2 24 2 15.4 2 8 6.8 4.2 14.1l2.1.6z"/>
                    <path fill="#4CAF50" d="M24 46c5.2 0 10-2 13.6-5.3l-6.3-5.2C29.1 37.7 26.7 38.6 24 38.6 18.8 38.6 14.3 35 12.7 30l-6.5 5C10 41.5 16.6 46 24 46z"/>
                    <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-1.1 3.4-4.1 6.2-7.7 7.1l6.3 5.2C37.1 37.6 40 31.7 40 24c0-1.2-.1-2.2-.4-3.5z"/>
                </svg>
                Sign in with Monash Student Account
            </a>
            
            <div class="footer-info">
                This application will access your basic profile information<br>
                (name, email, profile picture)
            </div>
            
            <div class="footer-links">
                <a href="#">Privacy</a>
                <span class="separator">•</span>
                <a href="#">Terms</a>
                <span class="separator">•</span>
                <a href="#">Help</a>
            </div>
        </div>
    </main>
    
    <script>
        // Mouse tracking for spotlight effect
        document.addEventListener('mousemove', (e) => {
            const spotlight = document.getElementById('spotlight');
            const rect = document.body.getBoundingClientRect();
            const x = ((e.clientX - rect.left) / rect.width) * 100;
            const y = ((e.clientY - rect.top) / rect.height) * 100;
            spotlight.style.setProperty('--mx', x + '%');
            spotlight.style.setProperty('--my', y + '%');
        });
        
        // Subtle parallax effect on scroll
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            const orbs = document.querySelectorAll('.floating-orb');
            orbs.forEach((orb, index) => {
                const speed = 0.5 + (index * 0.1);
                orb.style.transform = `translateY(${scrolled * speed}px)`;
            });
        });
    </script>
</body>
</html>
"""

VOTING_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>NilouVoter — Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            brand: {50:'#eef9ff',100:'#d9f1ff',200:'#b6e5ff',300:'#84d5ff',400:'#46bdff',500:'#1597f2',600:'#0c78c5',700:'#0b61a2',800:'#0e517f',900:'#0f4368'}
          }
        }
      }
    }
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>html,body{font-family:Inter,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#0b1020;color:#e6e7ec}</style>

  <!-- Libs -->
  <script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
  <script src="https://unpkg.com/dayjs@1/dayjs.min.js"></script>
  <script src="https://unpkg.com/dayjs@1/plugin/relativeTime.js"></script>
  <script src="https://unpkg.com/dayjs@1/plugin/utc.js"></script>
  <script src="https://unpkg.com/dayjs@1/plugin/timezone.js"></script>
  <script src="https://unpkg.com/htm@3.1.1/dist/htm.umd.js"></script>
</head>
<body class="min-h-screen">
  <div id="root"></div>

  <script>
    // Server-provided data
    window.__APP__ = {
      user: {{ user_info | tojson }},
      isAdmin: {{ 'true' if is_admin else 'false' }},
      apiUrl: {{ api_url | tojson }},
      apiToken: {{ (api_token or '') | tojson }}
    };
  </script>

  <!-- IMPORTANT: plain JS, not Babel -->
  <script type="text/javascript">
    const { useEffect, useMemo, useRef, useState } = React;
    dayjs.extend(dayjs_plugin_relativeTime);
    dayjs.extend(dayjs_plugin_utc);
    dayjs.extend(dayjs_plugin_timezone);
    const html = htm.bind(React.createElement);

    const Badge = ({ tone="info", children }) => {
      const tones = {
        info: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-400/20",
        success: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/20",
        danger: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-400/20",
        warning: "bg-amber-500/15 text-amber-200 ring-1 ring-amber-400/20",
        admin: "bg-fuchsia-500/15 text-fuchsia-300 ring-1 ring-fuchsia-400/20",
      };
      return html`<span className={"px-2.5 py-1 rounded-full text-xs font-medium ${tones[tone]} select-none"}>${children}</span>`;
    };

    const Card = ({className="", children}) =>
      html`<div className={"rounded-2xl bg-white/5 ring-1 ring-white/10 shadow-xl shadow-black/30 ${className}"}>${children}</div>`;

    const Header = ({user, isAdmin}) => html`
      <div className="sticky top-0 z-20 backdrop-blur-xl bg-[#0b1020]/60 border-b border-white/10">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-400 to-fuchsia-400 grid place-items-center ring-1 ring-white/20">
            <svg width="22" height="22" viewBox="0 0 24 24" className="text-white/90"><path fill="currentColor" d="M12 1.5 7.5 9 0 10.2l5.5 5.2L4.2 23 12 19.2 19.8 23l-1.3-7.6L24 10.2 16.5 9 12 1.5z"/></svg>
          </div>
          <div className="flex-1">
            <div className="text-white/90 font-semibold text-lg leading-tight">NilouVoter</div>
            <div className="text-white/50 text-xs -mt-0.5">Monash Student Council Electronic Voting</div>
          </div>
          <div className="flex items-center gap-3">
            ${isAdmin ? html`<${Badge} tone="admin">ADMIN</${Badge}>` : null}
            ${user?.picture ? html`<img src=${user.picture} className="w-9 h-9 rounded-full ring-2 ring-white/20" alt="pfp" />` : null}
            <div className="text-right hidden sm:block">
              <div className="text-white/90 text-sm font-medium">${user?.name || ''}</div>
              <div className="text-white/50 text-xs">${user?.email || ''}</div>
            </div>
            <a href="/logout" className="ml-2 inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 ring-1 ring-rose-400/30 transition">
              <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M10 17v-4H3v-2h7V7l5 5l-5 5Zm-6 4V3h8v2H6v14h6v2Z"/></svg>
              <span className="text-sm">Logout</span>
            </a>
          </div>
        </div>
      </div>
    `;

    const SkeletonCard = () => html`
      <${Card} className="p-5 animate-pulse space-y-3">
        <div className="h-4 w-2/3 bg-white/10 rounded"></div>
        <div className="h-3 w-1/2 bg-white/10 rounded"></div>
        <div className="h-3 w-1/3 bg-white/10 rounded"></div>
        <div className="flex gap-2 pt-2">
          <div className="h-8 w-24 bg-white/10 rounded-lg"></div>
          <div className="h-8 w-24 bg-white/10 rounded-lg"></div>
        </div>
      </${Card}>
    `;

    const StatusBadge = ({status, frozen}) => {
      const tone = status === 'active' ? 'success' : status === 'closed' ? 'danger' : 'warning';
      return html`<div className="flex items-center gap-2">
        <${Badge} tone=${tone}>${status?.toUpperCase()}</${Badge}>
        ${frozen ? html`<${Badge} tone="warning">FROZEN</${Badge}>` : null}
      </div>`;
    };

    const ElectionCard = ({e, apiUrl}) => {
      const start = dayjs(e.start_time);
      const end = dayjs(e.end_time);
      return html`
        <${Card} className="p-5 flex flex-col gap-3">
          <div className="flex items-start justify-between gap-3">
            <h3 className="text-white font-semibold text-lg">${e.title}</h3>
            <${StatusBadge} status=${e.status} frozen=${e.is_frozen} />
          </div>
          <p className="text-white/70 text-sm leading-relaxed">${e.description || 'No description provided.'}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-white/70">
            <div className="rounded-xl bg-white/5 ring-1 ring-white/10 p-3">
              <div className="text-white/50 text-xs">Starts</div>
              <div className="font-medium">${start.local().format('DD MMM YYYY, HH:mm')}</div>
            </div>
            <div className="rounded-xl bg-white/5 ring-1 ring-white/10 p-3">
              <div className="text-white/50 text-xs">Ends</div>
              <div className="font-medium">${end.local().format('DD MMM YYYY, HH:mm')}</div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 pt-2">
            ${e.status === 'active' && !e.is_frozen
              ? html`<a href=${"/vote/" + e.id} className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-brand-500/20 hover:bg-brand-500/30 text-sky-200 ring-1 ring-sky-400/30 transition">
                       <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M13 3v8h8v2h-8v8h-2v-8H3V11h8V3z"/></svg>
                       Vote Now
                     </a>`
              : e.status === 'closed'
              ? html`<a href=${"/results/" + e.id} className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-white ring-1 ring-white/20 transition">
                       <svg width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M5 9h3v12H5zm6-6h3v18h-3zM17 13h3v8h-3z"/></svg>
                       View Results
                     </a>`
              : html`<span className="text-white/50 text-sm">Voting not available</span>`
            }
          </div>
        </${Card}>
      `;
    };

    const AdminPanel = () => html`
      <${Card} className="p-4 border border-fuchsia-400/20 bg-fuchsia-500/5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <svg width="18" height="18" viewBox="0 0 24 24" className="text-fuchsia-300"><path fill="currentColor" d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12c5.16-1.26 9-6.45 9-12V5l-9-4Zm-1 6h2v6h-2Zm0 8h2v2h-2Z"/></svg>
            <div className="text-fuchsia-200 font-semibold">Admin Panel</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <a href="/admin/create-election" className="px-3 py-2 rounded-xl bg-brand-500/20 hover:bg-brand-500/30 text-sky-200 ring-1 ring-sky-400/30 transition">Create Election</a>
            <a href="/admin/audit-logs" className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-white ring-1 ring-white/20 transition">Audit Logs</a>
            <a href="/admin/templates" className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-white ring-1 ring-white/20 transition">Templates</a>
          </div>
        </div>
      </${Card}>
    `;

    const Filters = ({query, setQuery, status, setStatus}) => html`
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          value=${query}
          onChange=${e => setQuery(e.target.value)}
          placeholder="Search elections…"
          className="flex-1 px-4 py-2.5 rounded-xl bg-white/5 ring-1 ring-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
        />
        <select
          value=${status}
          onChange=${e => setStatus(e.target.value)}
          className="px-4 py-2.5 rounded-xl bg-white/5 ring-1 ring-white/10 text-white focus:outline-none focus:ring-2 focus:ring-brand-500/50"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="scheduled">Scheduled</option>
          <option value="closed">Closed</option>
        </select>
      </div>
    `;

    const Dashboard = () => {
      const { user, isAdmin, apiUrl } = window.__APP__;
      const [loading, setLoading] = useState(true);
      const [elections, setElections] = useState([]);
      const [query, setQuery] = useState("");
      const [status, setStatus] = useState("");
      const [error, setError] = useState("");

      const load = async () => {
        try {
          setError("");
          const res = await fetch(`${apiUrl}/api/elections`, { cache: "no-store" });
          const data = await res.json();
          setElections(Array.isArray(data) ? data : []);
        } catch (e) {
          setError("Failed to load elections. Please try again later.");
        } finally {
          setLoading(false);
        }
      };

      React.useEffect(() => {
        load();
        const id = setInterval(load, 30000);
        return () => clearInterval(id);
      }, []);

      const filtered = React.useMemo(() => {
        return elections.filter(e => {
          const okQ = !query || (e.title?.toLowerCase().includes(query.toLowerCase()) || e.description?.toLowerCase().includes(query.toLowerCase()));
          const okS = !status || e.status === status;
          return okQ && okS;
        });
      }, [elections, query, status]);

      return html`
        <${Header} user=${user} isAdmin=${isAdmin} />
        <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
          ${isAdmin ? html`<${AdminPanel} />` : null}
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Available Elections</h2>
            <span className="text-white/60 text-sm">${elections.length} total</span>
          </div>
          <${Filters} query=${query} setQuery=${setQuery} status=${status} setStatus=${setStatus} />
          ${error ? html`<div className="p-4 rounded-xl bg-rose-500/10 ring-1 ring-rose-400/20 text-rose-200">${error}</div>` : null}
          ${loading
            ? html`<div className="grid md:grid-cols-2 gap-4"><${SkeletonCard}/><${SkeletonCard}/><${SkeletonCard}/></div>`
            : filtered.length === 0
              ? html`<${Card} className="p-6 text-white/70">No elections match your filters.</${Card}>`
              : html`
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  ${filtered.map(e => html`<${ElectionCard} key=${e.id} e=${e} apiUrl=${apiUrl} />`)}
                </div>
              `
          }
        </main>
      `;
    };

    ReactDOM.createRoot(document.getElementById('root')).render(html`<${Dashboard} />`);
  </script>
</body>
</html>

"""

ADMIN_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>NilouVoter Admin Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            brand: {50:'#eef9ff',100:'#d9f1ff',200:'#b6e5ff',300:'#84d5ff',400:'#46bdff',500:'#1597f2',600:'#0c78c5',700:'#0b61a2',800:'#0e517f',900:'#0f4368'}
          },
          animation: {
            'fade-in': 'fadeIn 0.2s ease-out',
            'slide-up': 'slideUp 0.3s ease-out',
            'pulse-slow': 'pulse 3s infinite',
          },
          keyframes: {
            fadeIn: {
              '0%': { opacity: '0' },
              '100%': { opacity: '1' },
            },
            slideUp: {
              '0%': { opacity: '0', transform: 'translateY(20px)' },
              '100%': { opacity: '1', transform: 'translateY(0)' },
            }
          },
          backdropBlur: {
            'xs': '2px',
          }
        }
      }
    }
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    html,body{font-family:Inter,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#0b1020;color:#e6e7ec}
    .modal-backdrop { backdrop-filter: blur(8px); }
    .glassmorphism { background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); }
    .candidate-drag { transition: all 0.2s ease; }
    .candidate-drag:hover { transform: translateY(-2px); }
  </style>
  <script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
  <script src="https://unpkg.com/dayjs@1/dayjs.min.js"></script>
  <script src="https://unpkg.com/dayjs@1/plugin/relativeTime.js"></script>
  <script src="https://unpkg.com/dayjs@1/plugin/utc.js"></script>
  <script src="https://unpkg.com/dayjs@1/plugin/timezone.js"></script>
  <script src="https://unpkg.com/htm@3.1.1/dist/htm.umd.js"></script>
</head>
<body class="min-h-screen">
  <div id="root"></div>
  <script>
    window.__APP__ = {
      user: {{ user_info | tojson }},
      isAdmin: {{ 'true' if is_admin else 'false' }},
      apiUrl: {{ api_url | tojson }},
      apiToken: {{ (api_token or '') | tojson }}
    };
  </script>
  <script type="text/javascript">
    const { useEffect, useMemo, useRef, useState, useCallback } = React;
    dayjs.extend(dayjs_plugin_relativeTime);
    dayjs.extend(dayjs_plugin_utc);
    dayjs.extend(dayjs_plugin_timezone);
    const html = htm.bind(React.createElement);

    const Badge = ({ tone="info", children, className="" }) => {
      const tones = {
        info: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-400/20",
        success: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/20",
        danger: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-400/20",
        warning: "bg-amber-500/15 text-amber-200 ring-1 ring-amber-400/20",
        admin: "bg-fuchsia-500/15 text-fuchsia-300 ring-1 ring-fuchsia-400/20",
      };
      return html`<span className=${`px-2.5 py-1 rounded-full text-xs font-medium ${tones[tone]} select-none ${className}`}>${children}</span>`;
    };

    const Card = ({className="", children, onClick}) =>
      html`<div onClick=${onClick} className=${`rounded-2xl bg-white/5 ring-1 ring-white/10 shadow-xl shadow-black/30 ${className} ${onClick ? 'cursor-pointer hover:bg-white/10 transition-colors' : ''}`}>${children}</div>`;

    const Button = ({ variant="primary", size="md", disabled=false, loading=false, children, onClick, className="" }) => {
      const variants = {
        primary: "bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 text-white shadow-lg shadow-brand-500/25",
        secondary: "bg-white/10 hover:bg-white/15 text-white ring-1 ring-white/20",
        danger: "bg-gradient-to-r from-rose-500 to-rose-600 hover:from-rose-600 hover:to-rose-700 text-white shadow-lg shadow-rose-500/25",
        ghost: "hover:bg-white/10 text-white/70 hover:text-white"
      };
      const sizes = {
        sm: "px-3 py-1.5 text-sm",
        md: "px-4 py-2 text-sm",
        lg: "px-6 py-3 text-base"
      };
      
      return html`
        <button 
          onClick=${onClick}
          disabled=${disabled || loading}
          className=${`inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
        >
          ${loading ? html`<div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>` : null}
          ${children}
        </button>
      `;
    };

    const Header = ({user, onCreateElection, onViewAuditLogs, onManageTemplates}) => html`
      <div className="sticky top-0 z-30 backdrop-blur-xl bg-[#0b1020]/80 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-400 to-fuchsia-400 grid place-items-center ring-1 ring-white/20">
                <svg width="22" height="22" viewBox="0 0 24 24" className="text-white/90">
                  <path fill="currentColor" d="M12 1.5 7.5 9 0 10.2l5.5 5.2L4.2 23 12 19.2 19.8 23l-1.3-7.6L24 10.2 16.5 9 12 1.5z"/>
                </svg>
              </div>
              <div>
                <div className="text-white/90 font-semibold text-lg leading-tight">NilouVoter Admin</div>
                <div className="text-white/50 text-xs -mt-0.5">Election Management Dashboard</div>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <${Button} variant="primary" onClick=${onCreateElection} className="hidden sm:flex">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5v14M5 12h14"/>
                </svg>
                Create Election
              </${Button}>
              
              <div className="hidden md:flex items-center gap-2">
                <${Button} variant="ghost" size="sm" onClick=${onViewAuditLogs}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14,2 14,8 20,8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                    <polyline points="10,9 9,9 8,9"/>
                  </svg>
                  Audit Logs
                </${Button}>
                <${Button} variant="ghost" size="sm" onClick=${onManageTemplates}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <rect x="7" y="7" width="3" height="9"/>
                    <rect x="14" y="7" width="3" height="5"/>
                  </svg>
                  Templates
                </${Button}>
              </div>
              
              <div className="flex items-center gap-3">
                <${Badge} tone="admin">ADMIN</${Badge}>
                ${user?.picture ? html`<img src=${user.picture} className="w-9 h-9 rounded-full ring-2 ring-white/20" alt="pfp" />` : null}
                <div className="text-right hidden sm:block">
                  <div className="text-white/90 text-sm font-medium">${user?.name || ''}</div>
                  <div className="text-white/50 text-xs">${user?.email || ''}</div>
                </div>
                <a href="/logout" className="ml-2 inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 ring-1 ring-rose-400/30 transition">
                  <svg width="16" height="16" viewBox="0 0 24 24">
                    <path fill="currentColor" d="M10 17v-4H3v-2h7V7l5 5l-5 5Zm-6 4V3h8v2H6v14h6v2Z"/>
                  </svg>
                  <span className="text-sm">Logout</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    const Modal = ({ isOpen, onClose, title, children, size="lg" }) => {
      const sizeClasses = {
        sm: "max-w-md",
        md: "max-w-lg", 
        lg: "max-w-2xl",
        xl: "max-w-4xl",
        full: "max-w-6xl"
      };

      useEffect(() => {
        if (isOpen) {
          document.body.style.overflow = 'hidden';
        } else {
          document.body.style.overflow = 'unset';
        }
        return () => { document.body.style.overflow = 'unset'; };
      }, [isOpen]);

      if (!isOpen) return null;

      return html`
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/50 modal-backdrop animate-fade-in" onClick=${onClose}></div>
          <div className=${`relative w-full ${sizeClasses[size]} max-h-[90vh] overflow-hidden`}>
            <div className="glassmorphism rounded-2xl shadow-2xl animate-slide-up">
              <div className="flex items-center justify-between p-6 border-b border-white/10">
                <h2 className="text-xl font-semibold text-white">${title}</h2>
                <button onClick=${onClose} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
              <div className="p-6 max-h-[70vh] overflow-y-auto">
                ${children}
              </div>
            </div>
          </div>
        </div>
      `;
    };

    const CreateElectionModal = ({ isOpen, onClose, onSuccess, apiUrl }) => {
      const [step, setStep] = useState(1);
      const [loading, setLoading] = useState(false);
      const [formData, setFormData] = useState({
        title: '',
        description: '',
        start_time: '',
        end_time: '',
        template_id: null
      });
      const [candidates, setCandidates] = useState([]);
      const [templates, setTemplates] = useState([]);

      const resetForm = () => {
        setStep(1);
        setFormData({
          title: '',
          description: '',
          start_time: '',
          end_time: '',
          template_id: null
        });
        setCandidates([]);
      };

      useEffect(() => {
        if (isOpen) {
          loadTemplates();
          resetForm();
        }
      }, [isOpen]);

      const loadTemplates = async () => {
        try {
          const response = await fetch(`${apiUrl}/api/templates`);
          const data = await response.json();
          setTemplates(Array.isArray(data) ? data : []);
        } catch (error) {
          console.error('Failed to load templates:', error);
        }
      };

      const handleInputChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
      };

      const addCandidate = () => {
        setCandidates(prev => [...prev, { name: '', faculty: '', manifesto: '', external_id: '' }]);
      };

      const removeCandidate = (index) => {
        setCandidates(prev => prev.filter((_, i) => i !== index));
      };

      const updateCandidate = (index, field, value) => {
        setCandidates(prev => prev.map((candidate, i) => 
          i === index ? { ...candidate, [field]: value } : candidate
        ));
      };

      const handleBulkImport = (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            if (file.type === 'application/json') {
              const data = JSON.parse(e.target.result);
              if (data.candidates && Array.isArray(data.candidates)) {
                setCandidates(data.candidates);
              }
            } else if (file.name.endsWith('.csv')) {
              const lines = e.target.result.split('\\n');
              const headers = lines[0].split(',').map(h => h.trim());
              const candidates = lines.slice(1)
                .filter(line => line.trim())
                .map(line => {
                  const values = line.split(',').map(v => v.trim());
                  const candidate = {};
                  headers.forEach((header, i) => {
                    candidate[header] = values[i] || '';
                  });
                  return candidate;
                });
              setCandidates(candidates);
            }
          } catch (error) {
            alert('Failed to parse file. Please check the format.');
          }
        };
        reader.readAsText(file);
        event.target.value = '';
      };

      const validateStep1 = () => {
        return formData.title && formData.start_time && formData.end_time;
      };

      const validateStep2 = () => {
        return candidates.length > 0 && candidates.every(c => c.name.trim());
      };

      const createElection = async () => {
        setLoading(true);
        try {
          // Create election
          const electionData = {
            title: formData.title,
            description: formData.description,
            start_time: new Date(formData.start_time).toISOString(),
            end_time: new Date(formData.end_time).toISOString(),
            ...(formData.template_id && { template_id: formData.template_id })
          };

          const electionResponse = await fetch(`${apiUrl}/api/elections`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(electionData)
          });

          if (!electionResponse.ok) {
            throw new Error('Failed to create election');
          }

          const election = await electionResponse.json();
          const electionId = election.election_id;

          // Add candidates if any
          if (candidates.length > 0) {
            const candidatesData = {
              candidates: candidates.map(c => ({
                name: c.name,
                faculty: c.faculty || '',
                manifesto: c.manifesto || '',
                ...(c.external_id && { external_id: c.external_id })
              }))
            };

            const candidatesResponse = await fetch(`${apiUrl}/api/elections/${electionId}/candidates/bulk`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(candidatesData)
            });

            if (!candidatesResponse.ok) {
              console.warn('Failed to add candidates, but election was created');
            }
          }

          onSuccess();
          onClose();
        } catch (error) {
          alert(`Error: ${error.message}`);
        } finally {
          setLoading(false);
        }
      };

      const renderStep1 = () => html`
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-white/90 mb-2">Election Title *</label>
              <input
                type="text"
                value=${formData.title}
                onChange=${(e) => handleInputChange('title', e.target.value)}
                className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-xl text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50"
                placeholder="e.g., Student Council President Election 2025"
                required
              />
            </div>
            
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-white/90 mb-2">Description</label>
              <textarea
                value=${formData.description}
                onChange=${(e) => handleInputChange('description', e.target.value)}
                rows="3"
                className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-xl text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50"
                placeholder="Brief description of the election..."
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-white/90 mb-2">Start Date & Time *</label>
              <input
                type="datetime-local"
                value=${formData.start_time}
                onChange=${(e) => handleInputChange('start_time', e.target.value)}
                className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-white/90 mb-2">End Date & Time *</label>
              <input
                type="datetime-local"
                value=${formData.end_time}
                onChange=${(e) => handleInputChange('end_time', e.target.value)}
                className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50"
                required
              />
            </div>
            
            ${templates.length > 0 ? html`
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-white/90 mb-2">Use Template (Optional)</label>
                <select
                  value=${formData.template_id || ''}
                  onChange=${(e) => handleInputChange('template_id', e.target.value || null)}
                  className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50"
                >
                  <option value="">No template</option>
                  ${templates.map(template => html`
                    <option key=${template.id} value=${template.id}>${template.name}</option>
                  `)}
                </select>
              </div>
            ` : null}
          </div>
          
          <div className="flex justify-end gap-3">
            <${Button} variant="secondary" onClick=${onClose}>Cancel</${Button}>
            <${Button} variant="primary" onClick=${() => setStep(2)} disabled=${!validateStep1()}>
              Next: Add Candidates
            </${Button}>
          </div>
        </div>
      `;

      const renderStep2 = () => html`
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-white">Candidates</h3>
            <div className="flex gap-2">
              <input
                type="file"
                accept=".json,.csv"
                onChange=${handleBulkImport}
                className="hidden"
                id="bulk-import"
              />
              <${Button} variant="secondary" size="sm" onClick=${() => document.getElementById('bulk-import').click()}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="7,10 12,15 17,10"/>
                  <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                Import JSON/CSV
              </${Button}>
              <${Button} variant="ghost" size="sm" onClick=${addCandidate}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5v14M5 12h14"/>
                </svg>
                Add Candidate
              </${Button}>
            </div>
          </div>
          
          ${candidates.length === 0 ? html`
            <div className="text-center py-8 text-white/60">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mx-auto mb-3 text-white/40">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
              <p>No candidates added yet</p>
              <p className="text-sm">Click "Add Candidate" or import from JSON/CSV</p>
            </div>
          ` : html`
            <div className="space-y-3 max-h-96 overflow-y-auto">
              ${candidates.map((candidate, index) => html`
                <div key=${index} className="candidate-drag glassmorphism p-4 rounded-xl">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-white/70 mb-1">Name *</label>
                      <input
                        type="text"
                        value=${candidate.name}
                        onChange=${(e) => updateCandidate(index, 'name', e.target.value)}
                        className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white text-sm placeholder-white/50 focus:outline-none focus:ring-1 focus:ring-brand-500/50"
                        placeholder="Candidate name"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-white/70 mb-1">Faculty</label>
                      <input
                        type="text"
                        value=${candidate.faculty}
                        onChange=${(e) => updateCandidate(index, 'faculty', e.target.value)}
                        className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white text-sm placeholder-white/50 focus:outline-none focus:ring-1 focus:ring-brand-500/50"
                        placeholder="e.g., Engineering"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <div className="flex items-center justify-between mb-1">
                        <label className="block text-xs font-medium text-white/70">Manifesto</label>
                        <button
                          onClick=${() => removeCandidate(index)}
                          className="text-rose-400 hover:text-rose-300 p-1"
                          title="Remove candidate"
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <polyline points="3,6 5,6 21,6"/>
                            <path d="m19,6v14a2,2 0,0 1,-2,2H7a2,2 0,0 1,-2,-2V6m3,0V4a2,2 0,0 1,2,-2h4a2,2 0,0 1,2,2v2"/>
                          </svg>
                        </button>
                      </div>
                      <textarea
                        value=${candidate.manifesto}
                        onChange=${(e) => updateCandidate(index, 'manifesto', e.target.value)}
                        rows="2"
                        className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white text-sm placeholder-white/50 focus:outline-none focus:ring-1 focus:ring-brand-500/50"
                        placeholder="Campaign manifesto or key points..."
                      />
                    </div>
                  </div>
                </div>
              `)}
            </div>
          `}
          
          <div className="flex justify-between">
            <${Button} variant="secondary" onClick=${() => setStep(1)}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="m15 18-6-6 6-6"/>
              </svg>
              Back
            </${Button}>
            <${Button} variant="primary" onClick=${() => setStep(3)} disabled=${!validateStep2()}>
              Next: Review
            </${Button}>
          </div>
        </div>
      `;

      const renderStep3 = () => html`
        <div className="space-y-6">
          <h3 className="text-lg font-medium text-white">Review Election</h3>
          
          <div className="glassmorphism p-6 rounded-xl space-y-4">
            <div>
              <h4 className="font-medium text-white mb-2">${formData.title}</h4>
              <p className="text-white/70 text-sm">${formData.description || 'No description'}</p>
            </div>
            
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-white/60">Start:</span>
                <div className="text-white">${dayjs(formData.start_time).format('MMM DD, YYYY HH:mm')}</div>
              </div>
              <div>
                <span className="text-white/60">End:</span>
                <div className="text-white">${dayjs(formData.end_time).format('MMM DD, YYYY HH:mm')}</div>
              </div>
            </div>
            
            <div>
              <span className="text-white/60">Candidates (${candidates.length}):</span>
              <div className="mt-2 space-y-2">
                ${candidates.map((candidate, index) => html`
                  <div key=${index} className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                    <div className="w-8 h-8 rounded-full bg-brand-500/20 text-brand-200 flex items-center justify-center text-sm font-medium">
                      ${index + 1}
                    </div>
                    <div className="flex-1">
                      <div className="text-white text-sm font-medium">${candidate.name}</div>
                      <div className="text-white/60 text-xs">${candidate.faculty || 'No faculty specified'}</div>
                    </div>
                  </div>
                `)}
              </div>
            </div>
          </div>
          
          <div className="flex justify-between">
            <${Button} variant="secondary" onClick=${() => setStep(2)}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="m15 18-6-6 6-6"/>
              </svg>
              Back
            </${Button}>
            <${Button} variant="primary" onClick=${createElection} loading=${loading}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 6 9 17l-5-5"/>
              </svg>
              Create Election
            </${Button}>
          </div>
        </div>
      `;

      const steps = [
        { number: 1, title: "Details", component: renderStep1 },
        { number: 2, title: "Candidates", component: renderStep2 },
        { number: 3, title: "Review", component: renderStep3 }
      ];

      return html`
        <${Modal} isOpen=${isOpen} onClose=${onClose} title="Create New Election" size="xl">
          <div className="mb-6">
            <div className="flex items-center justify-center gap-4">
              ${steps.map(({ number, title }) => html`
                <div key=${number} className=${`flex items-center gap-2 ${step >= number ? 'text-brand-400' : 'text-white/40'}`}>
                  <div className=${`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                    step > number ? 'bg-brand-500 text-white' : 
                    step === number ? 'bg-brand-500/20 text-brand-400 ring-2 ring-brand-500/30' : 
                    'bg-white/10 text-white/40'
                  }`}>
                    ${step > number ? html`
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="20,6 9,17 4,12"/>
                      </svg>
                    ` : number}
                  </div>
                  <span className="text-sm font-medium">${title}</span>
                  ${number < steps.length ? html`
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-white/20">
                      <polyline points="9,18 15,12 9,6"/>
                    </svg>
                  ` : null}
                </div>
              `)}
            </div>
          </div>
          
          ${steps[step - 1].component()}
        </${Modal}>
      `;
    };

    const StatsCard = ({ title, value, change, icon, trend = "up" }) => html`
      <${Card} className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-white/60 text-sm">${title}</p>
            <p className="text-2xl font-bold text-white mt-1">${value}</p>
            ${change ? html`
              <div className=${`flex items-center gap-1 mt-2 text-xs ${trend === 'up' ? 'text-emerald-400' : 'text-rose-400'}`}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points=${trend === 'up' ? "23,6 13.5,15.5 8.5,10.5 1,18" : "23,18 13.5,8.5 8.5,13.5 1,6"}/>
                  <polyline points=${trend === 'up' ? "17,6 23,6 23,12" : "17,18 23,18 23,12"}/>
                </svg>
                ${change}
              </div>
            ` : null}
          </div>
          <div className="w-12 h-12 rounded-xl bg-brand-500/20 text-brand-400 flex items-center justify-center">
            ${icon}
          </div>
        </div>
      </${Card}>
    `;

    const ElectionCard = ({ election, onEdit, onDelete, onFreeze, onUnfreeze, onViewResults }) => {
      const start = dayjs(election.start_time);
      const end = dayjs(election.end_time);
      const now = dayjs();
      
      const getStatusInfo = () => {
        if (election.is_frozen) return { color: 'warning', text: 'FROZEN' };
        if (now.isBefore(start)) return { color: 'info', text: 'SCHEDULED' };
        if (now.isAfter(end)) return { color: 'danger', text: 'CLOSED' };
        return { color: 'success', text: 'ACTIVE' };
      };

      const statusInfo = getStatusInfo();

      return html`
        <${Card} className="p-6 hover:ring-2 hover:ring-brand-500/30 transition-all">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-white mb-2">${election.title}</h3>
              <p className="text-white/70 text-sm mb-3 line-clamp-2">${election.description || 'No description provided'}</p>
            </div>
            <${Badge} tone=${statusInfo.color} className="ml-3">${statusInfo.text}</${Badge}>
          </div>
          
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-white/50 text-xs">Starts</div>
              <div className="text-white text-sm font-medium">${start.format('MMM DD, HH:mm')}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-white/50 text-xs">Ends</div>
              <div className="text-white text-sm font-medium">${end.format('MMM DD, HH:mm')}</div>
            </div>
          </div>
          
          <div className="flex items-center justify-between">
            <div className="text-white/60 text-sm">
              ID: ${election.id} • Created ${dayjs(election.created_at).fromNow()}
            </div>
            <div className="flex gap-2">
              ${statusInfo.text === 'CLOSED' ? html`
                <${Button} variant="ghost" size="sm" onClick=${() => onViewResults(election.id)}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 3v5h5M21 21v-5h-5M21 3l-9 9-4-4-5 5M3 21l9-9 4 4 5-5"/>
                  </svg>
                </${Button}>
              ` : null}
              
              ${!election.is_frozen && (statusInfo.text === 'ACTIVE' || statusInfo.text === 'SCHEDULED') ? html`
                <${Button} variant="ghost" size="sm" onClick=${() => onFreeze(election.id)} title="Freeze Election">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                    <circle cx="12" cy="16" r="1"/>
                    <path d="m7 11V7a5 5 0 0 1 10 0v4"/>
                  </svg>
                </${Button}>
              ` : null}
              
              ${election.is_frozen ? html`
                <${Button} variant="ghost" size="sm" onClick=${() => onUnfreeze(election.id)} title="Unfreeze Election">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                    <circle cx="12" cy="16" r="1"/>
                    <path d="m7 11V7a5 5 0 0 1 5-5 5 5 0 0 1 5 5"/>
                    <line x1="12" y1="1" x2="12" y2="3"/>
                    <line x1="21" y1="4.5" x2="19" y2="6.5"/>
                    <line x1="3" y1="4.5" x2="5" y2="6.5"/>
                  </svg>
                </${Button}>
              ` : null}
              
              <${Button} variant="ghost" size="sm" onClick=${() => onEdit(election)} title="Edit Election">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </${Button}>
              
              <${Button} variant="ghost" size="sm" onClick=${() => onDelete(election.id)} title="Delete Election" className="text-rose-400 hover:text-rose-300">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="3,6 5,6 21,6"/>
                  <path d="m19,6v14a2,2 0,0 1,-2,2H7a2,2 0,0 1,-2,-2V6m3,0V4a2,2 0,0 1,2,-2h4a2,2 0,0 1,2,2v2"/>
                  <line x1="10" y1="11" x2="10" y2="17"/>
                  <line x1="14" y1="11" x2="14" y2="17"/>
                </svg>
              </${Button}>
            </div>
          </div>
        </${Card}>
      `;
    };

    const Dashboard = () => {
      const { user, apiUrl } = window.__APP__;
      const [loading, setLoading] = useState(true);
      const [elections, setElections] = useState([]);
      const [stats, setStats] = useState({
        total: 0,
        active: 0,
        scheduled: 0,
        closed: 0
      });
      const [showCreateModal, setShowCreateModal] = useState(false);
      const [refreshTrigger, setRefreshTrigger] = useState(0);

      const loadElections = useCallback(async () => {
        try {
          setLoading(true);
          const response = await fetch(`${apiUrl}/api/elections`);
          const data = await response.json();
          const electionsArray = Array.isArray(data) ? data : [];
          setElections(electionsArray);
          
          // Calculate stats
          const now = dayjs();
          const stats = electionsArray.reduce((acc, election) => {
            acc.total++;
            if (election.is_frozen) return acc;
            
            const start = dayjs(election.start_time);
            const end = dayjs(election.end_time);
            
            if (now.isBefore(start)) acc.scheduled++;
            else if (now.isAfter(end)) acc.closed++;
            else acc.active++;
            
            return acc;
          }, { total: 0, active: 0, scheduled: 0, closed: 0 });
          
          setStats(stats);
        } catch (error) {
          console.error('Failed to load elections:', error);
        } finally {
          setLoading(false);
        }
      }, [apiUrl, refreshTrigger]);

      useEffect(() => {
        loadElections();
        const interval = setInterval(loadElections, 30000);
        return () => clearInterval(interval);
      }, [loadElections]);

      const handleCreateSuccess = () => {
        setRefreshTrigger(prev => prev + 1);
        setShowCreateModal(false);
      };

      const handleFreeze = async (electionId) => {
        if (!confirm('Are you sure you want to freeze this election? This will prevent new votes.')) return;
        
        try {
          const response = await fetch(`${apiUrl}/api/elections/${electionId}/freeze`, {
            method: 'POST'
          });
          if (response.ok) {
            setRefreshTrigger(prev => prev + 1);
          } else {
            alert('Failed to freeze election');
          }
        } catch (error) {
          alert('Error freezing election: ' + error.message);
        }
      };

      const handleUnfreeze = async (electionId) => {
        if (!confirm('Are you sure you want to unfreeze this election?')) return;
        
        try {
          const response = await fetch(`${apiUrl}/api/elections/${electionId}/unfreeze`, {
            method: 'POST'
          });
          if (response.ok) {
            setRefreshTrigger(prev => prev + 1);
          } else {
            alert('Failed to unfreeze election');
          }
        } catch (error) {
          alert('Error unfreezing election: ' + error.message);
        }
      };

      const handleDelete = async (electionId) => {
        if (!confirm('Are you sure you want to delete this election? This action cannot be undone.')) return;
        
        try {
          const response = await fetch(`${apiUrl}/api/elections/${electionId}`, {
            method: 'DELETE'
          });
          if (response.ok) {
            setRefreshTrigger(prev => prev + 1);
          } else {
            alert('Failed to delete election');
          }
        } catch (error) {
          alert('Error deleting election: ' + error.message);
        }
      };

      const handleViewResults = (electionId) => {
        window.open(`/results/${electionId}`, '_blank');
      };

      const handleViewAuditLogs = () => {
        window.open('/admin/audit-logs', '_blank');
      };

      const handleManageTemplates = () => {
        window.open('/admin/templates', '_blank');
      };

      return html`
        <div className="min-h-screen bg-[#0b1020]">
          <${Header} 
            user=${user} 
            onCreateElection=${() => setShowCreateModal(true)}
            onViewAuditLogs=${handleViewAuditLogs}
            onManageTemplates=${handleManageTemplates}
          />
          
          <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
            <!-- Quick Stats -->
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <${StatsCard} 
                title="Total Elections" 
                value=${stats.total}
                icon=${html`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27,6.96 12,12.01 20.73,6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`}
              />
              <${StatsCard} 
                title="Active Elections" 
                value=${stats.active}
                change="+2 this week"
                trend="up"
                icon=${html`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12,6 12,12 16,14"/></svg>`}
              />
              <${StatsCard} 
                title="Scheduled" 
                value=${stats.scheduled}
                icon=${html`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`}
              />
              <${StatsCard} 
                title="Completed" 
                value=${stats.closed}
                icon=${html`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22,4 12,14.01 9,11.01"/></svg>`}
              />
            </div>

            <!-- Quick Actions -->
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-semibold text-white">Election Management</h2>
              <div className="flex gap-3">
                <${Button} variant="secondary" onClick=${() => setRefreshTrigger(prev => prev + 1)}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="23,4 23,10 17,10"/>
                    <polyline points="1,20 1,14 7,14"/>
                    <path d="m3.51,9a9,9 0,0 1,14.85-3.36L23,10M1,14l4.64,4.36A9,9 0,0 0,20.49,15"/>
                  </svg>
                  Refresh
                </${Button}>
                <${Button} variant="primary" onClick=${() => setShowCreateModal(true)} className="sm:hidden">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 5v14M5 12h14"/>
                  </svg>
                  Create
                </${Button}>
              </div>
            </div>

            <!-- Elections Grid -->
            ${loading ? html`
              <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-6">
                ${Array(6).fill().map((_, i) => html`
                  <${Card} key=${i} className="p-6 animate-pulse">
                    <div className="space-y-3">
                      <div className="h-4 w-3/4 bg-white/10 rounded"></div>
                      <div className="h-3 w-1/2 bg-white/10 rounded"></div>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="h-12 bg-white/10 rounded"></div>
                        <div className="h-12 bg-white/10 rounded"></div>
                      </div>
                      <div className="flex gap-2 pt-2">
                        <div className="h-8 w-8 bg-white/10 rounded"></div>
                        <div className="h-8 w-8 bg-white/10 rounded"></div>
                        <div className="h-8 w-8 bg-white/10 rounded"></div>
                      </div>
                    </div>
                  </${Card}>
                `)}
              </div>
            ` : elections.length === 0 ? html`
              <${Card} className="p-12 text-center">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mx-auto mb-4 text-white/40">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <h3 className="text-lg font-medium text-white mb-2">No Elections Found</h3>
                <p className="text-white/60 mb-6">Get started by creating your first election.</p>
                <${Button} variant="primary" onClick=${() => setShowCreateModal(true)}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 5v14M5 12h14"/>
                  </svg>
                  Create Your First Election
                </${Button}>
              </${Card}>
            ` : html`
              <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-6">
                ${elections.map(election => html`
                  <${ElectionCard}
                    key=${election.id}
                    election=${election}
                    onEdit=${() => console.log('Edit:', election.id)}
                    onDelete=${handleDelete}
                    onFreeze=${handleFreeze}
                    onUnfreeze=${handleUnfreeze}
                    onViewResults=${handleViewResults}
                  />
                `)}
              </div>
            `}
          </main>

          <${CreateElectionModal}
            isOpen=${showCreateModal}
            onClose=${() => setShowCreateModal(false)}
            onSuccess=${handleCreateSuccess}
            apiUrl=${apiUrl}
          />
        </div>
      `;
    };

    ReactDOM.createRoot(document.getElementById('root')).render(html`<${Dashboard} />`);
  </script>
</body>
</html>
"""


VOTING_PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>Vote - NilouVoter</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
            background: #f8fafc;
            color: #1e293b;
            position: relative;
            overflow-x: hidden;
        }
        
        /* Animated background */
        .background {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            overflow: hidden;
            opacity: 0.6;
        }
        
        .gradient-wash {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(120deg, #93c5fd, #e9d5ff, #a5f3fc);
            background-size: 400% 400%;
            animation: gradientShift 18s ease-in-out infinite;
            opacity: 0.3;
        }
        
        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        .dots-pattern {
            position: absolute;
            width: 100%;
            height: 100%;
            background-image: radial-gradient(circle at 2px 2px, #3b82f6 2px, transparent 0);
            background-size: 20px 20px;
            opacity: 0.1;
        }
        
        .floating-blob {
            position: absolute;
            border-radius: 50%;
            filter: blur(48px);
            opacity: 0.3;
            animation: float 6s ease-in-out infinite;
        }
        
        .blob-1 {
            width: 288px;
            height: 288px;
            background: #38bdf8;
            top: 40px;
            left: 80px;
            animation-delay: 0s;
        }
        
        .blob-2 {
            width: 320px;
            height: 320px;
            background: #a855f7;
            bottom: 80px;
            right: 128px;
            animation-delay: 2s;
        }
        
        @keyframes float {
            0%, 100% { transform: translateY(0px) scale(1); }
            50% { transform: translateY(-20px) scale(1.05); }
        }
        
        .sparkles {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        
        .sparkle {
            position: absolute;
            width: 4px;
            height: 4px;
            background: #0ea5e9;
            border-radius: 50%;
            box-shadow: 0 0 8px rgba(14, 165, 233, 0.6);
            animation: twinkle 4s ease-in-out infinite;
        }
        
        @keyframes twinkle {
            0%, 100% { opacity: 0.2; transform: scale(0.8); }
            50% { opacity: 1; transform: scale(1.3); }
        }
        
        /* Main content */
        .container {
            position: relative;
            z-index: 10;
            min-height: 100vh;
            max-width: 32rem;
            margin: 0 auto;
            padding: 2.5rem 1.5rem;
        }
        
        .header {
            text-align: center;
            margin-bottom: 1.5rem;
            animation: slideUp 0.8s ease-out;
        }
        
        .university-logo {
            height: 2rem;
            object-fit: contain;
            margin-bottom: 1.5rem;
            filter: brightness(0.8);
        }
        
        .back-button {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(148, 163, 184, 0.3);
            border-radius: 0.75rem;
            padding: 0.75rem 1rem;
            color: #64748b;
            text-decoration: none;
            font-size: 0.875rem;
            font-weight: 500;
            transition: all 0.2s ease;
            backdrop-filter: blur(10px);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 1.5rem;
        }
        
        .back-button:hover {
            background: rgba(255, 255, 255, 0.95);
            border-color: rgba(148, 163, 184, 0.5);
            transform: translateY(-1px);
            color: #475569;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(203, 213, 225, 0.5);
            border-radius: 1.5rem;
            padding: 2rem;
            backdrop-filter: blur(20px);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            animation: slideUp 0.8s ease-out 0.2s both;
        }
        
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .election-title {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #0ea5e9, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .election-dates {
            color: #64748b;
            font-size: 0.875rem;
            margin-bottom: 1.5rem;
        }
        
        .info-box {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            background: rgba(14, 165, 233, 0.05);
            border: 1px solid rgba(14, 165, 233, 0.2);
            border-radius: 0.75rem;
            padding: 1rem;
            margin-bottom: 1.5rem;
            font-size: 0.875rem;
            line-height: 1.5;
        }
        
        .info-icon {
            width: 1.25rem;
            height: 1.25rem;
            background: #0ea5e9;
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            font-weight: 600;
            flex-shrink: 0;
            margin-top: 0.125rem;
        }
        
        .progress-container {
            margin: 1.5rem 0;
        }
        
        .progress-bar {
            width: 100%;
            height: 0.5rem;
            background: #f1f5f9;
            border-radius: 0.25rem;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #0ea5e9, #3b82f6);
            border-radius: 0.25rem;
            transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }
        
        .progress-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
            animation: shimmer 2s infinite;
        }
        
        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        .candidates-section {
            margin: 1.5rem 0;
        }
        
        .section-title {
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #334155;
        }
        
        .candidates-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        
        .candidate-card {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 0.75rem;
            padding: 1rem;
            cursor: pointer;
            transition: all 0.2s ease;
            position: relative;
            overflow: hidden;
        }
        
        .candidate-card:hover {
            border-color: #0ea5e9;
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(14, 165, 233, 0.15);
        }
        
        .candidate-card.selected {
            border-color: #0ea5e9;
            background: rgba(14, 165, 233, 0.05);
        }
        
        .candidate-card.inactive {
            background: #f8fafc;
            border-color: #e2e8f0;
            color: #94a3b8;
        }
        
        .candidate-card.inactive:hover {
            border-color: #cbd5e1;
            transform: none;
            box-shadow: none;
        }
        
        .rank-badge {
            width: 2rem;
            height: 2rem;
            background: #0ea5e9;
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.875rem;
            font-weight: 600;
            flex-shrink: 0;
            transition: all 0.2s ease;
        }
        
        .candidate-card.inactive .rank-badge {
            background: #cbd5e1;
            color: #64748b;
        }
        
        .candidate-info {
            flex: 1;
        }
        
        .candidate-name {
            font-weight: 500;
            margin-bottom: 0.25rem;
        }
        
        .candidate-subtitle {
            font-size: 0.75rem;
            color: #64748b;
        }
        
        .voter-info-section {
            background: rgba(251, 191, 36, 0.05);
            border: 1px solid rgba(251, 191, 36, 0.2);
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin: 1.5rem 0;
        }
        
        .voter-info-title {
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #92400e;
        }
        
        .voter-info-description {
            font-size: 0.875rem;
            color: #92400e;
            margin-bottom: 1rem;
            line-height: 1.5;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .form-group.full-width {
            grid-column: 1 / -1;
        }
        
        .form-label {
            font-size: 0.875rem;
            font-weight: 500;
            color: #374151;
        }
        
        .form-select {
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 0.5rem;
            padding: 0.75rem;
            font-size: 0.875rem;
            transition: all 0.2s ease;
            outline: none;
        }
        
        .form-select:focus {
            border-color: #0ea5e9;
            box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1);
        }
        
        .button-group {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 1.5rem;
            gap: 1rem;
        }
        
        .btn {
            border: none;
            border-radius: 0.75rem;
            padding: 0.875rem 1.5rem;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            position: relative;
            overflow: hidden;
        }
        
        .btn-secondary {
            background: #f8fafc;
            color: #64748b;
            border: 1px solid #e2e8f0;
        }
        
        .btn-secondary:hover {
            background: #f1f5f9;
            color: #475569;
            transform: translateY(-1px);
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #0ea5e9, #3b82f6);
            color: white;
            border: none;
            box-shadow: 0 4px 15px rgba(14, 165, 233, 0.4);
            font-size: 1rem;
            padding: 1rem 2rem;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(14, 165, 233, 0.5);
        }
        
        .btn-primary:disabled {
            background: #cbd5e1;
            color: #94a3b8;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .btn-primary::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        
        .btn-primary:hover::before {
            left: 100%;
        }
        
        .security-notice {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.875rem;
            color: #059669;
            margin-top: 1rem;
        }
        
        .security-icon {
            width: 1.25rem;
            height: 1.25rem;
            background: #10b981;
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            flex-shrink: 0;
        }
        
        .help-link {
            text-align: right;
            margin-top: 0.5rem;
        }
        
        .help-link a {
            color: #0ea5e9;
            text-decoration: underline;
            font-size: 0.75rem;
        }
        
        .message {
            margin-top: 1.5rem;
            padding: 1.5rem;
            border-radius: 0.75rem;
            animation: slideUp 0.5s ease-out;
        }
        
        .message.success {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #047857;
        }
        
        .message.error {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: #dc2626;
        }
        
        .success-content h2 {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        
        .confirmation-details {
            background: rgba(255, 255, 255, 0.5);
            border-radius: 0.5rem;
            padding: 1rem;
            margin: 1rem 0;
            font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
            font-size: 0.875rem;
        }
        
        .success-actions {
            display: flex;
            gap: 1rem;
            margin-top: 1.5rem;
            flex-wrap: wrap;
        }
        
        /* Step indicator */
        .step-indicator {
            display: flex;
            justify-content: center;
            margin-bottom: 2rem;
            gap: 1rem;
        }
        
        .step {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: #94a3b8;
            font-size: 0.875rem;
        }
        
        .step.active {
            color: #0ea5e9;
        }
        
        .step.completed {
            color: #10b981;
        }
        
        .step-number {
            width: 1.5rem;
            height: 1.5rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            font-weight: 600;
            background: #f1f5f9;
            color: #94a3b8;
        }
        
        .step.active .step-number {
            background: #0ea5e9;
            color: white;
        }
        
        .step.completed .step-number {
            background: #10b981;
            color: white;
        }
        
        /* Responsive design */
        @media (max-width: 768px) {
            .container {
                padding: 1.5rem 1rem;
            }
            
            .card {
                padding: 1.5rem;
            }
            
            .form-grid {
                grid-template-columns: 1fr;
            }
            
            .button-group {
                flex-direction: column;
                align-items: stretch;
            }
            
            .success-actions {
                flex-direction: column;
            }
        }
        
        /* Loading states */
        .loading {
            opacity: 0.6;
            pointer-events: none;
        }
        
        .spinner {
            width: 1rem;
            height: 1rem;
            border: 2px solid transparent;
            border-top: 2px solid currentColor;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="background">
        <div class="gradient-wash"></div>
        <div class="dots-pattern"></div>
        <div class="floating-blob blob-1"></div>
        <div class="floating-blob blob-2"></div>
        <div class="sparkles" id="sparkles"></div>
    </div>
    
    <main class="container">
        <div class="header">
            <img src="https://bump2babyandme.org/wp-content/uploads/2020/02/2016-Monash_2-Black_NEW_TO-SEND_RGB.jpg" 
                 alt="Monash University" class="university-logo">
        </div>
        
        <a href="/dashboard" class="back-button">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="m15 18-6-6 6-6"/>
            </svg>
            Back to Dashboard
        </a>
        
        <div class="step-indicator">
            <div class="step active" id="step-rank">
                <div class="step-number">1</div>
                <span>Rank</span>
            </div>
            <div class="step" id="step-review">
                <div class="step-number">2</div>
                <span>Review</span>
            </div>
            <div class="step" id="step-done">
                <div class="step-number">3</div>
                <span>Submit</span>
            </div>
        </div>
        
        <div class="card">
            <div id="voting-content">
                <h1 class="election-title" id="election-title">Loading...</h1>
                <p class="election-dates" id="election-dates">Loading election details...</p>
                
                <div class="info-box">
                    <div class="info-icon">i</div>
                    <p>Click candidates in order of preference. Your first click is your <strong>highest</strong> preference.</p>
                </div>
                
                <div class="voter-info-section">
                    <h3 class="voter-info-title">Voter Information</h3>
                    <p class="voter-info-description">Please provide your details for demographic analysis (your vote remains secret):</p>
                    
                    <div class="form-grid">
                        <div class="form-group">
                            <label class="form-label" for="faculty">Faculty:</label>
                            <select class="form-select" id="faculty" required>
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
                            <label class="form-label" for="gender">Gender:</label>
                            <select class="form-select" id="gender" required>
                                <option value="">Select Gender</option>
                                <option value="Male">Male</option>
                                <option value="Female">Female</option>
                                <option value="Non-binary">Non-binary</option>
                                <option value="Prefer not to say">Prefer not to say</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label" for="study_level">Study Level:</label>
                            <select class="form-select" id="study_level" required>
                                <option value="">Select Study Level</option>
                                <option value="Undergraduate">Undergraduate</option>
                                <option value="Postgraduate">Postgraduate</option>
                                <option value="PhD">PhD</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label" for="year_level">Year Level:</label>
                            <select class="form-select" id="year_level" required>
                                <option value="">Select Year</option>
                                <option value="1">1st Year</option>
                                <option value="2">2nd Year</option>
                                <option value="3">3rd Year</option>
                                <option value="4">4th Year</option>
                                <option value="5">5+ Year</option>
                            </select>
                        </div>
                    </div>
                </div>
                
                <div class="candidates-section">
                    <h2 class="section-title">Rank Candidates</h2>
                    <div class="candidates-list" id="candidates-container">
                        Loading candidates...
                    </div>
                </div>
                
                <div class="progress-container">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
                    </div>
                </div>
                
                <div class="button-group">
                    <button class="btn btn-secondary" onclick="resetBallot()">Reset ballot</button>
                    <button class="btn btn-primary" id="submit-btn" onclick="submitVote()" disabled>
                        Submit Vote
                    </button>
                </div>
                
                <div class="security-notice">
                    <div class="security-icon">✓</div>
                    <span>Your vote is anonymous and cannot be traced back to your identity.</span>
                </div>
                
                <div class="help-link">
                    <a href="#" onclick="showHelp()">Help</a>
                </div>
            </div>
            
            <div id="message"></div>
        </div>
    </main>
    
    <script>
        const electionId = {{ election_id }};
        const userInfo = {{ user_info | tojson }};
        const apiUrl = '{{ api_url }}';
        
        let candidates = [];
        let rankedOrder = [];
        let currentStep = 'rank';
        
        // Initialize sparkles
        function createSparkles() {
            const sparklesContainer = document.getElementById('sparkles');
            for (let i = 0; i < 20; i++) {
                const sparkle = document.createElement('div');
                sparkle.className = 'sparkle';
                sparkle.style.top = Math.random() * 100 + '%';
                sparkle.style.left = Math.random() * 100 + '%';
                sparkle.style.animationDelay = Math.random() * 4 + 's';
                sparkle.style.animationDuration = (4 + Math.random() * 4) + 's';
                sparklesContainer.appendChild(sparkle);
            }
        }
        
        // Load election and candidates
        async function loadElection() {
            try {
                // Load election details
                const electionResponse = await fetch(`${apiUrl}/api/elections`);
                const elections = await electionResponse.json();
                const election = elections.find(e => e.id === electionId);
                
                if (election) {
                    document.getElementById('election-title').textContent = election.title;
                    const startDate = new Date(election.start_time).toLocaleDateString();
                    const endDate = new Date(election.end_time).toLocaleDateString();
                    document.getElementById('election-dates').textContent = `Voting period: ${startDate} - ${endDate}`;
                }
                
                // Load candidates
                const candidatesResponse = await fetch(`${apiUrl}/api/elections/${electionId}/candidates`);
                candidates = await candidatesResponse.json();
                
                renderCandidates();
                updateProgress();
                
            } catch (error) {
                document.getElementById('candidates-container').innerHTML = 
                    '<div style="color: #ef4444; text-align: center; padding: 2rem;">Failed to load candidates. Please try again.</div>';
            }
        }
        
        function renderCandidates() {
            const container = document.getElementById('candidates-container');
            container.innerHTML = '';
            
            // Render ranked candidates first
            rankedOrder.forEach((candidateId, index) => {
                const candidate = candidates.find(c => c.id === candidateId);
                if (candidate) {
                    const card = createCandidateCard(candidate, index + 1, true);
                    container.appendChild(card);
                }
            });
            
            // Render unranked candidates
            candidates.forEach(candidate => {
                if (!rankedOrder.includes(candidate.id)) {
                    const card = createCandidateCard(candidate, null, false);
                    container.appendChild(card);
                }
            });
        }
        
        function createCandidateCard(candidate, rank, isRanked) {
            const card = document.createElement('div');
            card.className = `candidate-card ${isRanked ? 'selected' : 'inactive'}`;
            card.onclick = () => toggleCandidate(candidate.id);
            
            card.innerHTML = `
                <div class="rank-badge">${rank || ''}</div>
                <div class="candidate-info">
                    <div class="candidate-name">${candidate.name}</div>
                    <div class="candidate-subtitle">${candidate.faculty || 'Not specified'} • ${candidate.manifesto || 'No manifesto provided'}</div>
                </div>
            `;
            
            return card;
        }
        
        function toggleCandidate(candidateId) {
            if (rankedOrder.includes(candidateId)) {
                // Remove from ranking
                rankedOrder = rankedOrder.filter(id => id !== candidateId);
            } else {
                // Add to ranking
                rankedOrder.push(candidateId);
            }
            
            renderCandidates();
            updateProgress();
            updateSubmitButton();
        }
        
        function updateProgress() {
            const progress = (rankedOrder.length / candidates.length) * 100;
            document.getElementById('progress-fill').style.width = progress + '%';
        }
        
        function updateSubmitButton() {
            const submitBtn = document.getElementById('submit-btn');
            const allRanked = rankedOrder.length === candidates.length;
            const formValid = validateForm();
            
            submitBtn.disabled = !allRanked || !formValid;
            submitBtn.textContent = allRanked && formValid ? 'Submit Vote' : 
                !allRanked ? `Rank ${candidates.length - rankedOrder.length} more candidates` : 'Complete voter information';
        }
        
        function validateForm() {
            const faculty = document.getElementById('faculty').value;
            const gender = document.getElementById('gender').value;
            const studyLevel = document.getElementById('study_level').value;
            const yearLevel = document.getElementById('year_level').value;
            
            return faculty && gender && studyLevel && yearLevel;
        }
        
        function resetBallot() {
            rankedOrder = [];
            renderCandidates();
            updateProgress();
            updateSubmitButton();
        }
        
        function updateStepIndicator(step) {
            const steps = ['rank', 'review', 'done'];
            steps.forEach((stepName, index) => {
                const stepElement = document.getElementById(`step-${stepName}`);
                stepElement.classList.remove('active', 'completed');
                
                if (stepName === step) {
                    stepElement.classList.add('active');
                } else if (steps.indexOf(stepName) < steps.indexOf(step)) {
                    stepElement.classList.add('completed');
                }
            });
        }
        
        function showReviewStep() {
            currentStep = 'review';
            updateStepIndicator('review');
            
            const content = document.getElementById('voting-content');
            content.innerHTML = `
                <h1 class="election-title">Review Your Vote</h1>
                <p class="election-dates">Please review your ranked choices before submitting your vote.</p>
                
                <div class="candidates-section">
                    <h2 class="section-title">Your Ranked Choices</h2>
                    <div class="candidates-list">
                        ${rankedOrder.map((candidateId, index) => {
                            const candidate = candidates.find(c => c.id === candidateId);
                            return `
                                <div class="candidate-card selected">
                                    <div class="rank-badge">${index + 1}</div>
                                    <div class="candidate-info">
                                        <div class="candidate-name">${candidate.name}</div>
                                        <div class="candidate-subtitle">${candidate.faculty || 'Not specified'} • ${candidate.manifesto || 'No manifesto provided'}</div>
                                    </div>
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
                
                <div class="security-notice">
                    <div class="security-icon">✓</div>
                    <span>Your vote is anonymous and cannot be traced back to your identity.</span>
                </div>
                
                <div class="button-group">
                    <button class="btn btn-secondary" onclick="backToRanking()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="m15 18-6-6 6-6"/>
                        </svg>
                        Back
                    </button>
                    <button class="btn btn-primary" onclick="confirmSubmit()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M20 6 9 17l-5-5"/>
                        </svg>
                        Confirm and Submit
                    </button>
                </div>
                
                <div class="help-link">
                    <a href="#" onclick="showHelp()">Help</a>
                </div>
            `;
        }
        
        function backToRanking() {
            currentStep = 'rank';
            updateStepIndicator('rank');
            location.reload(); // Simple way to restore original state
        }
        
        async function submitVote() {
            if (currentStep === 'rank') {
                // First, validate everything
                if (rankedOrder.length !== candidates.length) {
                    alert('Please rank all candidates before proceeding.');
                    return;
                }
                
                if (!validateForm()) {
                    alert('Please fill in all voter information fields.');
                    return;
                }
                
                // Move to review step
                showReviewStep();
                return;
            }
        }
        
        async function confirmSubmit() {
            const submitBtn = event.target;
            const originalText = submitBtn.textContent;
            
            try {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<div class="spinner"></div> Submitting...';
                
                // Get voter traits
                const faculty = document.getElementById('faculty')?.value;
                const gender = document.getElementById('gender')?.value;
                const studyLevel = document.getElementById('study_level')?.value;
                const yearLevel = document.getElementById('year_level')?.value;
                
                // Build preferences object
                const preferences = {};
                rankedOrder.forEach((candidateId, index) => {
                    preferences[candidateId] = index + 1;
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
                
                const response = await fetch(`${apiUrl}/api/vote`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(voteData)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showSuccessStep(result);
                } else {
                    throw new Error(result.detail || 'Failed to submit vote');
                }
                
            } catch (error) {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
                
                document.getElementById('message').innerHTML = `
                    <div class="message error">
                        <strong>Error:</strong> ${error.message}
                    </div>
                `;
            }
        }
        
        function showSuccessStep(result) {
            currentStep = 'done';
            updateStepIndicator('done');
            
            const content = document.getElementById('voting-content');
            content.innerHTML = `
                <div style="text-align: center; margin-bottom: 2rem;">
                    <img src="https://bump2babyandme.org/wp-content/uploads/2020/02/2016-Monash_2-Black_NEW_TO-SEND_RGB.jpg" 
                         alt="Monash University" style="height: 2rem; object-fit: contain; margin-bottom: 1rem;">
                    <h2 style="font-size: 1.5rem; font-weight: 600; margin-bottom: 0.5rem; color: #059669;">Electronic Voting System</h2>
                    <p style="font-size: 1.125rem; margin-bottom: 1rem;">Your vote has been recorded successfully!</p>
                </div>
                
                <div class="confirmation-details">
                    <div style="margin-bottom: 0.5rem;"><strong>Confirmation Code:</strong> ${result.confirmation_code}</div>
                    <div style="margin-bottom: 0.5rem;"><strong>Receipt Number:</strong> ${result.receipt_number}</div>
                    <div style="color: #64748b; font-size: 0.875rem;">Keep these codes for your records. You can verify your vote was counted using the confirmation code.</div>
                </div>
                
                <p style="text-align: center; color: #64748b; margin: 1rem 0;">
                    Election results will be announced after voting closes.
                </p>
                
                <div class="success-actions">
                    <a href="/dashboard" class="btn btn-primary">
                        Return to Dashboard
                    </a>
                    <a href="/receipt/${result.receipt_number}" class="btn btn-secondary" target="_blank">
                        View Receipt
                    </a>
                    <a href="/verify-vote" class="btn btn-secondary">
                        Verify Vote
                    </a>
                </div>
            `;
        }
        
        function showHelp() {
            alert('Help: This is a ranked-choice voting system. Click candidates in order of your preference, with your first choice being your most preferred candidate. All fields must be completed before you can submit your vote.');
        }
        
        // Add form change listeners
        function setupFormListeners() {
            const formFields = ['faculty', 'gender', 'study_level', 'year_level'];
            formFields.forEach(fieldId => {
                const field = document.getElementById(fieldId);
                if (field) {
                    field.addEventListener('change', updateSubmitButton);
                }
            });
        }
        
        // Initialize the page
        document.addEventListener('DOMContentLoaded', function() {
            createSparkles();
            loadElection();
            setupFormListeners();
        });
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
    
    # Redirect admins to admin dashboard
    if session.get('is_admin', False):
        return redirect(url_for('admin_dashboard'))
    
    return render_template_string(
        VOTING_DASHBOARD,  # Keep the original student dashboard
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

@app.route('/admin')
def admin_dashboard():
    """Modern admin dashboard"""
    if 'user_info' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))
    
    return render_template_string(
        ADMIN_DASHBOARD,
        user_info=session['user_info'],
        is_admin=True,
        api_token=session.get('api_token'),
        api_url=BACKEND_API_URL
    )




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