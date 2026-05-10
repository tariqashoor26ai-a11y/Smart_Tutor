import os
import asyncio
import base64
import json
import re
import sqlite3
import random
import string
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, Response
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq
import edge_tts

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "smart-academy-super-secret-key-2026")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com")
FACEBOOK_APP_ID = os.environ.get("FACEBOOK_APP_ID", "YOUR_FACEBOOK_APP_ID")

def init_db():
    with sqlite3.connect('academy.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            auth_provider TEXT DEFAULT 'local',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS academy_chats (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            role TEXT,
                            content TEXT,
                            arabic TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY(user_id) REFERENCES users(id)
                        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS classroom_chats (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            username TEXT NOT NULL,
                            role TEXT,
                            content TEXT,
                            arabic TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )''')
        try: 
            conn.execute("ALTER TABLE academy_chats ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except: 
            pass
init_db()

# ==========================================
# 1. واجهة تسجيل الدخول والتسويق (Landing Page)
# ==========================================
LOGIN_PAGE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Academy - تعلم الإنجليزية باحتراف</title>
    <script src="https://accounts.google.com/gsi/client" async defer></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); overflow-x: hidden; color: #2c3e50;}
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        @keyframes popIn { 0% { opacity: 0; transform: translateY(20px); } 100% { opacity: 1; transform: translateY(0); } }
        .hero-section { display: flex; flex-wrap: wrap; gap: 30px; align-items: stretch; margin-bottom: 50px; animation: popIn 0.6s ease-out;}
        .box { background: rgba(255, 255, 255, 0.9); padding: 35px; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.5); flex: 1; min-width: 320px; }
        .intro-box h1 { color: #8e44ad; margin-top: 0; font-size: 32px; margin-bottom: 15px;}
        .intro-box p { line-height: 1.8; font-size: 16px; margin-bottom: 20px;}
        .features-list { list-style: none; padding: 0; margin-bottom: 25px;}
        .features-list li { margin-bottom: 12px; font-weight: bold; display: flex; align-items: center; gap: 10px;}
        .features-list li::before { content: '✅'; color: #2ecc71; }
        .audio-btn { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); border: none; padding: 12px 25px; border-radius: 12px; color: white; font-weight: bold; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; font-size: 15px; box-shadow: 0 4px 15px rgba(17, 153, 142, 0.3); transition: all 0.3s; align-self: flex-start;}
        .audio-btn:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(17, 153, 142, 0.4); }
        .auth-box { text-align: center; }
        .auth-box h2 { color: #2c3e50; margin-top: 0; font-size: 24px; margin-bottom: 20px;}
        .input-group { margin-bottom: 15px; text-align: right; }
        .input-group label { display: block; margin-bottom: 5px; font-weight: bold; font-size: 13px;}
        .input-group input { width: 100%; padding: 12px 15px; border-radius: 10px; border: 1px solid #bdc3c7; font-size: 14px; outline: none; box-sizing: border-box; background: #f9f9f9;}
        .input-group input:focus { border-color: #3498db; background: white; box-shadow: 0 0 10px rgba(52, 152, 219, 0.2); }
        .main-btn { width: 100%; padding: 12px; border-radius: 10px; border: none; font-size: 15px; font-weight: bold; color: white; cursor: pointer; transition: all 0.3s; background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3);}
        .main-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(52, 152, 219, 0.4); }
        .toggle-text { margin-top: 15px; font-size: 13px; color: #7f8c8d; }
        .toggle-text span { color: #8e44ad; font-weight: bold; cursor: pointer; }
        .social-btn { width: 100%; padding: 10px; border-radius: 10px; border: none; font-size: 14px; font-weight: bold; cursor: pointer; transition: all 0.3s; margin-bottom: 10px; display: flex; justify-content: center; align-items: center; gap: 10px;}
        .social-btn.facebook { background: #1877F2; color: white;}
        .social-btn.guest { background: #95a5a6; color: white; margin-bottom: 0;}
        #googleBtnContainer { margin-bottom: 10px; display: flex; justify-content: center; width: 100%;}
        #errorMsg { color: #e74c3c; font-size: 13px; font-weight: bold; margin-bottom: 10px; min-height: 18px;}
        .academic-section { display: flex; flex-wrap: wrap; gap: 30px; margin-top: 40px; animation: popIn 0.8s ease-out;}
        .acad-box { background: white; padding: 25px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); flex: 1; min-width: 300px; text-align: right;}
        .acad-box h3 { color: #3498db; font-size: 20px; margin-top: 0; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px;}
        .acad-box ul { list-style: none; padding: 0;}
        .acad-box ul li { margin-bottom: 15px; line-height: 1.6;}
        .pricing-section { text-align: center; margin-top: 50px;}
        .pricing-cards { display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; }
        .card { background: white; border-radius: 20px; padding: 30px 20px; flex: 1; min-width: 280px; max-width: 350px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); border: 1px solid #eee; transition: transform 0.3s; position: relative;}
        .card.popular { border: 2px solid #3498db; transform: scale(1.05); }
        .popular-badge { position: absolute; top: 15px; right: -35px; background: #e74c3c; color: white; padding: 5px 40px; transform: rotate(45deg); font-size: 12px; font-weight: bold;}
        .card h3 { margin-top: 0; font-size: 22px; color: #2c3e50;}
        .price { font-size: 36px; font-weight: bold; color: #3498db; margin: 15px 0;}
        .price span { font-size: 16px; color: #95a5a6; font-weight: normal;}
        .card ul { list-style: none; padding: 0; margin: 20px 0 30px 0; text-align: right;}
        .card ul li { margin-bottom: 12px; font-size: 14px; border-bottom: 1px dashed #ecf0f1; padding-bottom: 8px;}
        .card-btn { width: 100%; padding: 12px; border-radius: 10px; border: 2px solid #3498db; background: transparent; color: #3498db; font-weight: bold; cursor: pointer; transition: 0.3s; font-size: 15px;}
        .card.popular .card-btn { background: #3498db; color: white; }
    </style>
</head>
<body>
    <script>
      window.fbAsyncInit = function() { FB.init({ appId: '{{ fb_id }}', cookie: true, xfbml: true, version: 'v19.0' }); };
      (function(d, s, id){ var js, fjs = d.getElementsByTagName(s)[0]; if (d.getElementById(id)) {return;} js = d.createElement(s); js.id = id; js.src = "https://connect.facebook.net/en_US/sdk.js"; fjs.parentNode.insertBefore(js, fjs); }(document, 'script', 'facebook-jssdk'));
    </script>
    <div class="container">
        <div class="hero-section">
            <div class="box intro-box">
                <h1>Smart Academy 🌟</h1>
                <p>مستقبلك في إتقان الإنجليزية يبدأ من هنا. تدرّب مع معلم ذكاء اصطناعي تفاعلي يحاكي البشر ويصحح أخطاءك فوراً.</p>
                <ul class="features-list">
                    <li>محادثات صوتية حية وإحصاءات دقيقة.</li>
                    <li>فصل افتراضي جماعي (Classroom).</li>
                    <li>مناهج عالمية معتمدة وشهادات إتمام.</li>
                    <li>مكتبة موارد شاملة وحقيقية للتحميل.</li>
                </ul>
                <button class="audio-btn" id="introAudioBtn" onclick="playIntroAudio()"><span id="audioIcon">🔊</span> استمع لنبذة الأكاديمية</button>
                <audio id="introPlayer"></audio>
            </div>
            
            <div class="box auth-box" id="loginBox">
                <h2 id="authTitle">تسجيل الدخول</h2>
                <div id="errorMsg"></div>
                <div class="input-group"><label>الإيميل أو اسم المستخدم</label><input type="text" id="username" placeholder="أدخل بياناتك..."></div>
                <div class="input-group"><label>كلمة المرور</label><input type="password" id="password" placeholder="أدخل كلمة المرور..."></div>
                <button class="main-btn" id="submitBtn" onclick="submitAuth()">دخول إلى الأكاديمية</button>
                <div class="toggle-text" id="toggleDiv">ليس لديك حساب؟ <span onclick="toggleMode()">إنشاء حساب جديد</span></div>
                <div style="margin:15px 0; color:#bdc3c7; font-size:12px;">أو عبر المنصات</div>
                <div id="googleBtnContainer"></div>
                <button class="social-btn facebook" onclick="loginWithFacebook()">📘 الدخول بحساب Facebook</button>
                <button class="social-btn guest" onclick="guestLogin()">👤 الدخول كضيف (تجربة مجانية)</button>
            </div>
        </div>
    </div>
    
    <script>
        let isLogin = true;
        function toggleMode() {
            if(!isLogin) return; 
            isLogin = false;
            document.getElementById('authTitle').innerText = 'إنشاء حساب جديد ✨';
            document.getElementById('submitBtn').innerText = 'تسجيل الحساب وبدء التعلم';
            document.getElementById('toggleDiv').innerHTML = 'لديك حساب بالفعل؟ <span onclick="isLogin=true; toggleModeReal();">تسجيل الدخول</span>';
            document.getElementById('errorMsg').innerText = '';
        }
        function toggleModeReal() {
            document.getElementById('authTitle').innerText = 'تسجيل الدخول';
            document.getElementById('submitBtn').innerText = 'دخول إلى الأكاديمية';
            document.getElementById('toggleDiv').innerHTML = 'ليس لديك حساب؟ <span onclick="toggleMode()">إنشاء حساب جديد</span>';
            document.getElementById('errorMsg').innerText = '';
        }
        async function executeAuth(action, username, password, provider='local') {
            let err = document.getElementById('errorMsg'); err.innerText = "جاري التحقق..."; err.style.color = "#3498db";
            try {
                let res = await fetch("/auth", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ action: action, username: username, password: password, provider: provider }) });
                let data = await res.json();
                if(data.success) window.location.href = "/?login=success"; 
                else { err.style.color = "#e74c3c"; err.innerText = data.error; }
            } catch(e) { err.style.color = "#e74c3c"; err.innerText = "خطأ في الاتصال بالسيرفر."; }
        }
        async function submitAuth() {
            let user = document.getElementById('username').value, pass = document.getElementById('password').value;
            if(!user || !pass) { document.getElementById('errorMsg').innerText = "يرجى تعبئة الحقول."; return; }
            executeAuth(isLogin ? 'login' : 'register', user, pass);
        }
        async function guestLogin() { executeAuth('guest', '', ''); }
        window.onload = function () { google.accounts.id.initialize({ client_id: "{{ google_id }}", callback: handleGoogleResponse }); google.accounts.id.renderButton(document.getElementById("googleBtnContainer"), { theme: "outline", size: "large", width: "100%" }); };
        function handleGoogleResponse(response) { const payload = JSON.parse(atob(response.credential.split('.')[1])); executeAuth('social', payload.email, payload.name, 'google'); }
        function loginWithFacebook() { FB.login(function(response) { if (response.authResponse) { FB.api('/me', {fields: 'name,email'}, function(res) { executeAuth('social', res.email || res.id, res.name, 'facebook'); }); } else { document.getElementById('errorMsg').innerText = "تم إلغاء الدخول."; } }, {scope: 'public_profile,email'}); }
        async function playIntroAudio() { let btn = document.getElementById('introAudioBtn'), icon = document.getElementById('audioIcon'), player = document.getElementById('introPlayer'); if(!player.src) { icon.innerText = "⏳"; btn.disabled = true; try { let res = await fetch("/intro_audio"); let data = await res.json(); player.src = "data:audio/mp3;base64," + data.audio; player.play(); } catch(e) { alert("خطأ في التحميل."); } btn.disabled = false; } else { if(player.paused) player.play(); else player.pause(); } }
        document.getElementById('introPlayer').onplay = () => document.getElementById('audioIcon').innerText = "⏸️"; document.getElementById('introPlayer').onpause = () => document.getElementById('audioIcon').innerText = "🔊"; document.getElementById('introPlayer').onended = () => document.getElementById('audioIcon').innerText = "🔊";
    </script>
</body>
</html>
"""

# ==========================================
# 2. الواجهة التفاعلية للأكاديمية (Main App)
# ==========================================
MAIN_PAGE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Academy - المدرس الذكي</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.4.21/mammoth.browser.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --primary: #3498db; --secondary: #2c3e50; --accent: #8e44ad; --danger: #e74c3c; --success: #2ecc71; --bg: #f5f7fa; --user-bg: #d5f5e3; --ai-bg: #e1f5fe; --chat-color: #2c3e50; --chat-size: 16px; --chat-font: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; --soft-shadow: 0 10px 30px rgba(0,0,0,0.08); }
        body { font-family: var(--chat-font); text-align: center; margin: 0; padding: 20px 20px 80px 20px; background: linear-gradient(135deg, var(--bg) 0%, #c3cfe2 100%); min-height: 100vh; overflow-x: hidden;}
        h2 { color: var(--secondary); text-shadow: 1px 1px 2px rgba(0,0,0,0.1); margin-bottom: 5px;}
        .toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%) translateY(-100px); background: var(--success); color: white; padding: 12px 25px; border-radius: 30px; box-shadow: 0 10px 20px rgba(46, 204, 113, 0.3); font-weight: bold; font-size: 15px; z-index: 4000; transition: transform 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
        .toast.show { transform: translateX(-50%) translateY(0); }
        @keyframes fadeSlideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulseMic { 0% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7); } 70% { box-shadow: 0 0 0 15px rgba(231, 76, 60, 0); } 100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0); } }
        .hamburger-btn { position: fixed; top: 20px; right: 20px; z-index: 1002; background: white; color: var(--secondary); padding: 10px 18px; border-radius: 12px; border: 1px solid #bdc3c7; font-size: 16px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.1); transition: all 0.3s ease; display: flex; align-items: center; gap: 8px;}
        .drawer { position: fixed; top: 0; right: -320px; width: 280px; height: 100%; background: rgba(255,255,255,0.95); backdrop-filter: blur(15px); box-shadow: -5px 0 25px rgba(0,0,0,0.1); transition: right 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); z-index: 1001; padding-top: 80px; display: flex; flex-direction: column; gap: 12px; padding-left: 20px; padding-right: 20px; overflow-y: auto;}
        .drawer.open { right: 0; }
        .drawer-btn { border-radius: 15px; padding: 14px 18px; font-size: 14px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.05); transition: all 0.2s ease; display: flex; align-items: center; justify-content: flex-start; gap: 12px; border: 1px solid rgba(255,255,255,0.5); text-align: right; color: #2c3e50;}
        .drawer-btn .icon { font-size: 18px; background: rgba(255,255,255,0.4); border-radius: 50%; padding: 6px;}
        .drawer-btn.classroom { background: linear-gradient(135deg, #FF9A9E 0%, #FECFEF 100%); color: #c0392b;} 
        .drawer-btn.stats { background: linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%); }
        .drawer-btn.downloads { background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); }
        .drawer-btn.plan { background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); }
        .drawer-btn.topics { background: linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%); }
        .drawer-btn.upload { background: linear-gradient(135deg, #d4fc79 0%, #96e6a1 100%); }
        .drawer-btn.settings { background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); }
        .drawer-btn.logout { background: transparent; border: 1px solid #e74c3c; color: #e74c3c;}
        .top-bar { display: flex; justify-content: center; align-items: center; width: 90%; max-width: 800px; margin: 0 auto 15px auto; gap: 15px; flex-wrap: wrap; }
        select { padding: 10px 15px; font-size: 14px; border-radius: 12px; border: 2px solid rgba(255,255,255,0.4); outline: none; background: white;}
        #liveIndicator { display: none; color: var(--danger); font-weight: bold; font-size: 14px; margin-top: 10px; animation: blink 1.5s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .input-container { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 20px;}
        input[type="text"] { padding: 16px 25px; font-size: 16px; border-radius: 30px; border: none; width: 65%; max-width: 600px; outline: none; background: white; box-shadow: var(--soft-shadow); }
        .circle-btn { border-radius: 50%; width: 55px; height: 55px; display:
