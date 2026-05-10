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
        .circle-btn { border-radius: 50%; width: 55px; height: 55px; display: flex; justify-content: center; align-items: center; font-size: 24px; border: none; cursor: pointer; color: white; transition: all 0.2s ease;}
        .circle-btn:active { transform: scale(0.9); }
        .circle-btn:hover { transform: translateY(-3px); box-shadow: 0 6px 15px rgba(0,0,0,0.2); }
        #micBtn { background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);}
        #micBtn.recording { animation: pulseMic 1.5s infinite; }
        .send-btn { padding: 14px 30px; font-size: 16px; border-radius: 30px; border: none; color: white; cursor: pointer; font-weight: bold; background: linear-gradient(135deg, #36D1DC 0%, #5B86E5 100%);}
        
        #audioControls { display: none; justify-content: center; gap: 15px; margin-top: 15px; background: rgba(255,255,255,0.95); padding: 12px 25px; border-radius: 30px; box-shadow: var(--soft-shadow); width: fit-content; margin: 15px auto;}
        .control-btn { background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); width: 45px; height: 45px; font-size: 18px;}
        .download-btn { background: linear-gradient(135deg, var(--success) 0%, #27ae60 100%); width: 45px; height: 45px; font-size: 18px;}
        
        #chatBox { width: 95%; max-width: 900px; margin: 20px auto; background: rgba(255, 255, 255, 0.95); padding: 25px; border-radius: 20px; box-shadow: var(--soft-shadow); height: 55vh; max-height: 600px; overflow-y: auto; display: flex; flex-direction: column; gap: 18px; border-top: 6px solid var(--primary); scroll-behavior: smooth; }
        .chat-bubble { max-width: 85%; padding: 18px 22px; border-radius: 20px; position: relative; font-size: var(--chat-size); color: var(--chat-color); line-height: 1.6; animation: fadeSlideUp 0.3s ease-out; box-shadow: 0 4px 10px rgba(0,0,0,0.04); word-wrap: break-word; overflow-wrap: break-word;}
        .user-bubble { background: var(--user-bg); align-self: flex-start; border-bottom-left-radius: 5px; text-align: left; direction: ltr;}
        .ai-bubble { background: var(--ai-bg); align-self: flex-end; border-bottom-right-radius: 5px; text-align: right;}
        .sender-name { font-size: 12px; font-weight: bold; color: #7f8c8d; margin-bottom: 5px; display: block; border-bottom: 1px solid rgba(0,0,0,0.1); padding-bottom: 3px;}
        .english-text { font-size: calc(var(--chat-size) + 4px); font-weight: bold; direction: ltr; text-align: left; margin-bottom: 10px; line-height: 1.5; word-wrap: break-word;}
        
        /* V1.0.5 Fix: Hidden text that reveals sequentially with light highlight */
        .word { opacity: 0; transition: opacity 0.15s ease-in, background-color 0.15s ease-in; border-radius: 4px; padding: 2px 0;}
        .word.active { opacity: 1; background-color: rgba(52, 152, 219, 0.15); } /* Light blue highlight */
        .word.spoken { opacity: 1; background-color: transparent; }
        
        .arabic-translation { border-top: 1px dashed rgba(0,0,0,0.15); padding-top: 10px; opacity: 0.9;}
        .structured-data { font-size: calc(var(--chat-size) - 2px); background-color: rgba(255,255,255,0.6); padding: 12px 15px; border-radius: 12px; margin-top: 12px; text-align: left; direction: ltr; border-left: 5px solid rgba(0,0,0,0.2);}
        
        .modal { display: none; position: fixed; z-index: 2000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.4); backdrop-filter: blur(6px); }
        .modal-content { background: rgba(255,255,255,0.98); margin: 5vh auto; padding: 35px; border-radius: 25px; width: 85%; max-width: 750px; max-height: 85vh; overflow-y: auto; text-align: right; box-shadow: 0 25px 50px rgba(0,0,0,0.3);}
        .close-btn { color: #aaa; float: left; font-size: 32px; font-weight: bold; cursor: pointer; transition: color 0.2s;}
        
        .stats-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .stats-table th, .stats-table td { border: 1px solid #ecf0f1; padding: 12px; text-align: center; }
        .stats-table th { background: #3498db; color: white; }
        .stats-table tr:nth-child(even) { background-color: #f9f9f9; }
        .topics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; margin-top: 15px; }
        .topic-item { background: #f8f9fa; padding: 12px; border-radius: 12px; font-size: 13px; text-align: center; cursor: pointer; transition: all 0.2s; border: 1px solid #dcdde1; font-weight: bold; color: #34495e;}
        .topic-item.locked { opacity: 0.6; background: #ecf0f1; border-color: #bdc3c7; }
        .topic-item:hover:not(.locked) { background: var(--primary); color: white; transform: translateY(-4px);}
        .topic-category { grid-column: 1 / -1; font-size: 16px; font-weight: bold; color: var(--accent); margin-top: 15px; border-bottom: 2px dashed #bdc3c7; padding-bottom: 5px; }
        .settings-group { margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between; background: #f9f9f9; padding: 12px 15px; border-radius: 12px; border: 1px solid #eee;}
        .settings-group input[type="color"] { border: none; width: 45px; height: 45px; border-radius: 8px; cursor: pointer; background: transparent;}
        .settings-group select, .settings-group input[type="range"] { width: 50%; padding: 10px; border-radius: 8px; border: 1px solid #ccc; outline: none;}
        
        #overlay { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.3); z-index: 1000;}
        #overlay.active { display: block; }
        #classroomBanner { display: none; background: #e74c3c; color: white; padding: 10px; font-weight: bold; border-radius: 10px; margin-bottom: 15px;}
        .break-notification { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: linear-gradient(135deg, #FFD200, #F7971E); color: white; padding: 15px 30px; border-radius: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); font-weight: bold; font-size: 16px; z-index: 3000; display: none;}
    </style>
</head>
<body>
    <div id="loginToast" class="toast">✅ تم الدخول بنجاح! يتم الآن تحضير الأكاديمية...</div>
    <div id="breakNotice" class="break-notification">⏰ مر 25 دقيقة! المعلم ينصحك بأخذ استراحة قصيرة ☕</div>
    
    <button class="hamburger-btn" onclick="toggleDrawer()"><span>☰</span> الخيارات</button>
    <div id="overlay" onclick="toggleDrawer()"></div>
    
    <div id="sideDrawer" class="drawer">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px; margin-top: 0;">الخدمات الأكاديمية</h3>
        <button class="drawer-btn classroom" onclick="toggleClassroomMode()"><span class="icon">🏫</span><span id="classroomBtnText">الدخول للفصل الجماعي</span></button>
        <button class="drawer-btn plan" onclick="openModal('academicModal')"><span class="icon">🎓</span><span>المناهج والشهادات</span></button>
        <button class="drawer-btn topics" onclick="openModal('topicsModal')"><span class="icon">🗂️</span><span>المواضيع والمحادثات</span></button>
        <button class="drawer-btn downloads" onclick="openModal('downloadsModal')"><span class="icon">📚</span><span>مكتبة الموارد (PDF/MP3)</span></button>
        <button class="drawer-btn stats" onclick="openStatsModal()"><span class="icon">📊</span><span>إحصاءات الاستخدام</span></button>
        <button class="drawer-btn upload" onclick="triggerUpload()"><span class="icon">📂</span><span>رفع منهج خاص</span></button>
        <button class="drawer-btn settings" onclick="openModal('settingsModal')"><span class="icon">🎨</span><span>إعدادات المظهر</span></button>
        <button class="drawer-btn logout" onclick="window.location.href='/logout'"><span class="icon">🚪</span><span>تسجيل الخروج</span></button>
    </div>
    
    <input type="file" id="fileUpload" accept=".txt,.pdf,.doc,.docx" style="display: none;" onchange="handleFileUpload(event)">
    
    <div id="downloadsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('downloadsModal')">&times;</span>
            <h2 style="text-align:center; color: var(--primary);">📚 مكتبة الموارد والملفات</h2>
            <h3 style="color: var(--success); border-bottom: 2px dashed #ecf0f1; padding-bottom: 5px;">🆓 موارد مجانية (متاحة الآن)</h3>
            <div class="topics-grid">
                <div class="topic-item" onclick="downloadFile('study_plan')">📄 خطة دراسية شاملة CEFR (TXT)</div>
                <div class="topic-item" onclick="downloadFile('vocab')">📕 أهم 500 كلمة للمبتدئين A1 (TXT)</div>
            </div>
            <h3 style="color: #e74c3c; border-bottom: 2px dashed #ecf0f1; padding-bottom: 5px; margin-top: 20px;">💎 موارد مدفوعة (Pro / VIP)</h3>
            <div class="topics-grid">
                <div class="topic-item locked" onclick="upgradeAlert()">🔒 خطة اجتياز IELTS الشاملة (PDF)</div>
                <div class="topic-item locked" onclick="upgradeAlert()">🔒 عروض تفاعلية للدروس (PPT)</div>
                <div class="topic-item locked" onclick="upgradeAlert()">🔒 مكتبة الصوتيات الكاملة (MP3)</div>
            </div>
        </div>
    </div>

    <div id="academicModal" class="modal">
        <div class="modal-content" style="line-height: 1.8;">
            <span class="close-btn" onclick="closeModal('academicModal')">&times;</span>
            <h2 style="text-align:center; color: var(--accent);">🎓 الخطة الأكاديمية والشهادات</h2>
            <h3 style="color: #3498db; border-bottom: 1px solid #ecf0f1;">مصادرنا المعتمدة:</h3>
            <p>نعتمد في تدريبنا على: <b>Oxford OER, Cambridge English, BBC Learning English.</b></p>
            <h3 style="color: #3498db; border-bottom: 1px solid #ecf0f1;">مسار الاختبارات:</h3>
            <ul style="padding-right: 20px;">
                <li><b>اختبار تحديد المستوى (Placement Test):</b> <button onclick="requestFeature('placement_test'); closeModal('academicModal');" style="background:#2ecc71; color:white; border:none; border-radius:5px; cursor:pointer; padding:3px 8px; font-size:12px;">ابدأ الاختبار الآن</button></li>
                <li><b>التقييم المرحلي (Quizzes):</b> بعد إتمام موضوع معين لقياس الفهم.</li>
                <li><b>الاختبار النهائي (Final Exam):</b> اختبار شامل نهاية المستوى لطلب الشهادة.</li>
            </ul>
        </div>
    </div>

    <div id="statsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('statsModal')">&times;</span>
            <h2 style="text-align:center; color: var(--primary);">📊 إحصاءات الاستخدام الخاصة بك</h2>
            <table class="stats-table" id="summaryTable">
                <tr><th>إجمالي التفاعلات</th><th>الساعات التقديرية للتعلم</th><th>المستوى المقدر</th></tr>
                <tr><td id="statTotal">0</td><td id="statHours">0</td><td style="color:#2ecc71; font-weight:bold;">قيد التقييم...</td></tr>
            </table>
            <h3 style="margin-top: 30px; text-align: center; color: #8e44ad;">نشاطك في آخر 7 أيام</h3>
            <div style="position: relative; height:40vh; width:100%"><canvas id="usageChart"></canvas></div>
        </div>
    </div>

    <div id="topicsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('topicsModal')">&times;</span>
            <h2 style="text-align:center; color: var(--accent);">اختر موضوعاً 🎯</h2>
            <div class="topics-grid" id="topicsList"></div>
        </div>
    </div>
    
    <div id="settingsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('settingsModal')">&times;</span>
            <h2 style="text-align:center; color: var(--primary);">🎨 المظهر</h2>
            <div class="settings-group"><label>صندوق المتدرب:</label><input type="color" id="userBgColor" value="#d5f5e3" onchange="applySettings()"></div>
            <div class="settings-group"><label>صندوق المدرب:</label><input type="color" id="aiBgColor" value="#e1f5fe" onchange="applySettings()"></div>
            <div class="settings-group"><label>لون النصوص:</label><input type="color" id="fontColor" value="#2c3e50" onchange="applySettings()"></div>
            <div class="settings-group"><label>حجم الخط:</label><input type="range" id="fontSize" min="12" max="24" value="16" oninput="applySettings()"><span id="fontSizeVal">16px</span></div>
            <button class="send-btn" style="width: 100%; margin-top: 15px;" onclick="resetSettings()">🔄 استعادة</button>
        </div>
    </div>

    <h2>Smart Academy 🎓 <span style="font-size:12px; color:#bdc3c7;">v1.0.5</span></h2>
    <div style="font-size: 14px; color: #7f8c8d; margin-bottom: 10px; font-weight: bold;">مرحباً بك يا {{ username }}!</div>
    
    <div id="classroomBanner">🏫 أنت الآن داخل الفصل الافتراضي الجماعي. يرجى التحدث باحترام مع زملائك والمدرس.</div>
    
    <div class="top-bar">
        <select id="mode" onchange="applySettings()">
            <option value="adult">وضع الكبار</option>
            <option value="child">وضع الأطفال</option>
        </select>
        <select id="micLang">
            <option value="en-US">الميكروفون: إنجليزي</option>
            <option value="ar-SA">الميكروفون: عربي</option>
        </select>
    </div>
    
    <div id="liveIndicator">🔴 يتم الاستماع الآن...</div>
    
    <div class="input-container">
        <button id="micBtn" class="circle-btn" onclick="toggleMic()" title="اضغط للتحدث أو مقاطعة المدرس">🎤</button>
        <input type="text" id="userMsg" placeholder="اكتب رسالتك هنا...">
        <button class="send-btn" onclick="sendMsg()">إرسال</button>
    </div>
    
    <div id="audioControls">
        <button class="circle-btn control-btn" onclick="skipAudio(-5)" title="تأخير 5 ثواني">⏪</button>
        <button id="pauseBtn" class="circle-btn control-btn" onclick="togglePauseAudio()" title="إيقاف / تشغيل">⏸️</button>
        <button class="circle-btn control-btn" onclick="skipAudio(5)" title="تقديم 5 ثواني">⏩</button>
        <button class="circle-btn download-btn" onclick="downloadAudio()" title="تحميل الصوت">💾</button>
    </div>
    
    <div id="chatBox"></div>
    <audio id="audioPlayer"></audio>
    
    <script>
        const topicsLibrary = {
            "🗣️ مواضيع للمبتدئين (A1-A2)": ["Introducing Yourself", "Daily Routines", "Family Members", "Weather and Seasons", "Ordering Food"],
            "🌍 الثقافات والمجتمع (A2-B2)": ["Global Cuisines", "Traveling on Budget", "Ancient History", "Japanese Culture", "Learning Languages"],
            "📱 التكنولوجيا والابتكار (B1-C1)": ["Artificial Intelligence", "Cybersecurity", "Future of Smartphones", "Internet of Things", "Space Exploration"],
            "💼 الأعمال والمهن (B2-C1)": ["Job Interviews", "Time Management", "Remote Work", "Public Speaking", "Financial Literacy"],
            "⚽ الرياضة والصحة (A1-B2)": ["Football Tactics", "Olympic Games", "Healthy Eating", "Mental Health", "Extreme Sports"]
        };

        let isRecording = false, recognition;
        let isLiveMode = false, silenceTimer, final_transcript = '', chatHistory = [], isTeacherSpeaking = false, userName = "{{ username }}";
        let isClassroomMode = false, classroomPollingInterval = null, lastMessageCount = null, chartInstance = null;
        let wordsElements = [];

        let studyMinutes = 0;
        setInterval(() => {
            studyMinutes++;
            if (studyMinutes === 25) {
                let notice = document.getElementById("breakNotice");
                notice.style.display = "block";
                setTimeout(() => { notice.style.display = "none"; studyMinutes = 0; }, 10000); 
            }
        }, 60000);

        function toggleDrawer() { document.getElementById('sideDrawer').classList.toggle('open'); document.getElementById('overlay').classList.toggle('active'); }
        function openModal(id) { document.getElementById(id).style.display = "block"; toggleDrawer(); } 
        function closeModal(id) { document.getElementById(id).style.display = "none"; }
        
        function populateTopics() {
            let container = document.getElementById("topicsList");
            for (const [category, topics] of Object.entries(topicsLibrary)) {
                let catDiv = document.createElement("div"); catDiv.className = "topic-category"; catDiv.innerText = category; container.appendChild(catDiv);
                topics.forEach(topic => {
                    let btn = document.createElement("div"); btn.className = "topic-item"; btn.innerText = topic;
                    btn.onclick = () => { closeModal('topicsModal'); toggleDrawer(); sendMsg(`Let's deeply discuss this topic: ${topic}. Guide me as a Cambridge examiner.`); };
                    container.appendChild(btn);
                });
            }
        }
        populateTopics();

        function downloadFile(fileType) {
            window.location.href = '/download/' + fileType;
            closeModal('downloadsModal');
        }
        function upgradeAlert() { alert("💎 هذا الملف مخصص لاشتراكات Pro و VIP فقط. يرجى ترقية حسابك للوصول إلى هذه الميزة."); closeModal('downloadsModal'); }

        function requestFeature(type) { 
            let p = {"placement_test": "Act as a Cambridge certified examiner. Give me a comprehensive English placement test right now to determine my CEFR level. Ask questions one by one.", "test": "Give me a short quick English test to check my grammar."}[type];
            if(p) sendMsg(p);
        }

        function skipAudio(seconds) { 
            let a = document.getElementById("audioPlayer"); 
            if (a.src && !a.paused) { a.currentTime += seconds; } 
        } 
        function downloadAudio() { 
            let a = document.getElementById("audioPlayer"); 
            if (!a.src) return; 
            let link = document.createElement("a"); link.href = a.src; link.download = "SmartAcademy_Lesson.mp3"; 
            document.body.appendChild(link); link.click(); document.body.removeChild(link); 
        } 
        function togglePauseAudio() { 
            let a = document.getElementById("audioPlayer"), btn = document.getElementById("pauseBtn"); 
            if(a.src === "") return; 
            if (a.paused) { a.play(); btn.innerText = "⏸️"; } else { a.pause(); btn.innerText = "▶️"; } 
        }
        
        function applySettings() { 
            let root = document.documentElement; 
            root.style.setProperty('--user-bg', document.getElementById('userBgColor').value); 
            root.style.setProperty('--ai-bg', document.getElementById('aiBgColor').value); 
            root.style.setProperty('--chat-color', document.getElementById('fontColor').value); 
            root.style.setProperty('--chat-size', document.getElementById('fontSize').value + 'px'); 
            document.getElementById('fontSizeVal').innerText = document.getElementById('fontSize').value + 'px'; 
            
            if (document.getElementById("mode").value === "child") {
                root.style.setProperty('--ai-bg', "#ffebef");
            }
        }
        function resetSettings() { 
            document.getElementById('userBgColor').value = "#d5f5e3"; document.getElementById('aiBgColor').value = "#e1f5fe"; document.getElementById('fontColor').value = "#2c3e50"; document.getElementById('fontSize').value = "16"; applySettings(); 
        }

        function toggleClassroomMode() {
            toggleDrawer(); isClassroomMode = !isClassroomMode;
            let banner = document.getElementById("classroomBanner"), btnText = document.getElementById("classroomBtnText");
            if (isClassroomMode) {
                banner.style.display = "block"; btnText.innerText = "الخروج من الفصل الجماعي";
                document.getElementById('chatBox').innerHTML = ''; chatHistory = []; lastMessageCount = 0;
                fetchClassroomChats(); classroomPollingInterval = setInterval(fetchClassroomChats, 4000);
            } else {
                banner.style.display = "none"; btnText.innerText = "الدخول للفصل الجماعي";
                if(classroomPollingInterval) clearInterval(classroomPollingInterval);
                document.getElementById('chatBox').innerHTML = ''; chatHistory = []; loadPersonalChats(); 
            }
        }

        async function fetchClassroomChats() {
            if(!isClassroomMode) return;
            try {
                let res = await fetch("/get_classroom_history"); let history = await res.json();
                if (history.length > lastMessageCount) {
                    document.getElementById('chatBox').innerHTML = ''; chatHistory = [];
                    history.forEach(item => {
                        let isMe = (item.username === userName && item.role === 'user'), isTeacher = (item.role === 'assistant');
                        if (isTeacher) { appendBubble("", false, {english: item.content, arabic: item.arabic}, "المعلم الذكي 🎓", true); chatHistory.push({"role": "assistant", "content": item.content}); } 
                        else { appendBubble(item.content, true, null, isMe ? "أنت" : "الزميل: " + item.username, true); chatHistory.push({"role": "user", "content": `[${item.username}]: ${item.content}`}); }
                    });
                    lastMessageCount = history.length; document.getElementById("chatBox").scrollTop = document.getElementById("chatBox").scrollHeight;
                }
            } catch(e) {}
        }

        async function openStatsModal() {
            toggleDrawer(); document.getElementById('statsModal').style.display = "block";
            try {
                let res = await fetch("/get_stats"); let data = await res.json();
                document.getElementById("statTotal").innerText = data.total_messages;
                document.getElementById("statHours").innerText = (data.total_messages * 2 / 60).toFixed(1) + " ساعة"; 
                let ctx = document.getElementById('usageChart').getContext('2d');
                if(chartInstance) chartInstance.destroy();
                chartInstance = new Chart(ctx, {
                    type: 'bar', data: { labels: data.labels, datasets: [{ label: 'رسائلك', data: data.values, backgroundColor: 'rgba(52, 152, 219, 0.6)', borderColor: 'rgba(52, 152, 219, 1)', borderWidth: 2, borderRadius: 5 }] },
                    options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
                });
            } catch (e) { alert("فشل تحميل الإحصاءات"); }
        }

        // V1.0.5 Fix: Added forceVisible parameter for history loading
        function appendBubble(text, isUser, data=null, senderName=null, forceVisible=false) { 
            let box = document.getElementById("chatBox"), container = document.createElement("div"); 
            container.className = isUser ? "chat-bubble user-bubble" : "chat-bubble ai-bubble"; 
            if (isClassroomMode && senderName) { let nameLabel = document.createElement("span"); nameLabel.className = "sender-name"; nameLabel.innerText = senderName; container.appendChild(nameLabel); }
            if(isUser) { 
                let t = document.createElement("span"); t.innerText = text; container.appendChild(t); 
            } else { 
                let engDiv = document.createElement("div"); engDiv.className = "english-text"; 
                let engText = data.english || "";
                engText.split(" ").forEach(word => { 
                    let span = document.createElement("span"); 
                    span.className = "word"; 
                    if(forceVisible) span.classList.add("spoken");
                    span.innerText = word; 
                    engDiv.appendChild(span); 
                    engDiv.appendChild(document.createTextNode(" ")); 
                }); 
                container.appendChild(engDiv); 
                let arDiv = document.createElement("div"); arDiv.className = "arabic-translation"; arDiv.innerText = data.arabic; container.appendChild(arDiv); 
                let details = ""; 
                if(data.keywords) details += `<div class="structured-data"><span class="section-title">🔑 Keywords:</span><br>${data.keywords}</div>`; 
                if(data.summary) details += `<div class="structured-data"><span class="section-title">📝 Corrections & Plan:</span><br>${data.summary}</div>`; 
                if (details !== "") { let dDiv = document.createElement("div"); dDiv.innerHTML = details; container.appendChild(dDiv); } 
            } 
            box.appendChild(container); setTimeout(() => box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' }), 100); 
        }
        
        async function loadPersonalChats() {
            try { 
                let res = await fetch("/get_history"); let history = await res.json(); 
                if (history.length > 0) { 
                    history.forEach(item => { 
                        if(item.role === 'user') { appendBubble(item.content, true, null, null, true); chatHistory.push({"role": "user", "content": item.content}); } 
                        else if(item.role === 'assistant') { appendBubble("", false, {english: item.content, arabic: item.arabic}, null, true); chatHistory.push({"role": "assistant", "content": item.content}); } 
                    }); 
                    document.getElementById("chatBox").scrollTop = document.getElementById("chatBox").scrollHeight; 
                } else { 
                    let prompt = `Act as a professional Cambridge examiner and tutor. Welcome the student (${userName}) warmly in BOTH English and Arabic. Tell them we follow CEFR standards.`; 
                    sendMsg(prompt, true); 
                } 
            } catch(e) {} 
        }

        window.onload = async function() { 
            if (window.location.search.includes("login=success")) { let toast = document.getElementById("loginToast"); toast.classList.add("show"); setTimeout(() => toast.classList.remove("show"), 4000); } 
            document.getElementById('chatBox').innerHTML = ''; loadPersonalChats();
        };
        
        async function sendMsg(overrideMsg = null, isHidden = false) { 
            let inputField = document.getElementById("userMsg"), msg = overrideMsg || inputField.value; 
            if(!msg.trim()) return; 
            
            if(!isHidden){ 
                appendBubble(msg, true, null, isClassroomMode ? "أنت" : null, true); 
                chatHistory.push({"role": "user", "content": isClassroomMode ? `[${userName}]: ${msg}` : msg}); 
                if(isClassroomMode) lastMessageCount++; 
            } else { 
                chatHistory.push({"role": "system", "content": msg}); 
            } 
            
            inputField.value = ""; 
            let loadDiv = document.createElement("div"); loadDiv.className = "chat-bubble ai-bubble"; loadDiv.id = "loadingBubble"; loadDiv.innerHTML = "<div class='arabic-translation' style='border:none;'>جاري التفكير وتجهيز الرد... ⏳</div>"; document.getElementById("chatBox").appendChild(loadDiv); document.getElementById("chatBox").scrollTop = document.getElementById("chatBox").scrollHeight; 
            
            let targetUrl = isClassroomMode ? "/classroom_chat" : "/chat";
            try { 
                let res = await fetch(targetUrl, { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ history: chatHistory.slice(-10), message: msg, mode: document.getElementById("mode").value }) }); 
                let data = await res.json(); document.getElementById("loadingBubble")?.remove(); 
                if(data.error) return alert("⚠️ تنبيه: " + data.error); 
                
                chatHistory.push({"role": "assistant", "content": data.english}); 
                appendBubble("", false, data, isClassroomMode ? "المعلم الذكي 🎓" : null, false); 
                
                if(data.audio) { 
                    let ap = document.getElementById("audioPlayer"); ap.src = "data:audio/mp3;base64," + data.audio; 
                    document.getElementById("audioControls").style.display = "flex"; 
                    document.getElementById("pauseBtn").innerText = "⏸️"; 
                    isTeacherSpeaking = true; if(isRecording) recognition.stop(); 
                    
                    // V1.0.5 Fix: Handle Autoplay blocks to prevent stuck invisible text
                    let playPromise = ap.play(); 
                    if (playPromise !== undefined) {
                        playPromise.catch(error => { 
                            console.log("Auto-play blocked."); 
                            document.querySelectorAll(".english-text .word").forEach(w => w.classList.add("spoken"));
                        }); 
                    }
                } 
                
                wordsElements = document.querySelectorAll("#chatBox > div:last-child .english-text .word");
            } catch (e) { document.getElementById("loadingBubble")?.remove(); alert("⚠️ خطأ في الاتصال."); } 
        }
        
        let audioPlayer = document.getElementById("audioPlayer"); 
        audioPlayer.ontimeupdate = function() { 
            if (wordsElements.length === 0 || isNaN(audioPlayer.duration)) return; 
            let activeIndex = Math.floor((audioPlayer.currentTime / audioPlayer.duration) * wordsElements.length); 
            wordsElements.forEach((span, i) => { 
                if (i === activeIndex) { span.classList.add("active"); span.classList.remove("spoken"); } 
                else if (i < activeIndex) { span.classList.remove("active"); span.classList.add("spoken"); } 
                else { span.classList.remove("active", "spoken"); } 
            }); 
        }; 
        audioPlayer.onended = function() { 
            isTeacherSpeaking = false; document.getElementById("pauseBtn").innerText = "▶️"; 
            wordsElements.forEach(span => { span.classList.remove("active"); span.classList.add("spoken"); }); 
            if (isLiveMode) setTimeout(() => { try { recognition.start(); } catch(e) {} }, 300); 
        };

        function initSpeechRecognition() { 
            window.SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition; 
            if (window.SpeechRecognition) { 
                recognition = new window.SpeechRecognition(); recognition.continuous = true; recognition.interimResults = true; 
                recognition.onstart = () => { isRecording = true; document.getElementById("micBtn").classList.add("recording"); }; 
                recognition.onresult = (event) => { 
                    if(isTeacherSpeaking) return; 
                    let interim = ''; 
                    for (let i = event.resultIndex; i < event.results.length; ++i) { 
                        if (event.results[i].isFinal) final_transcript += event.results[i][0].transcript + " "; 
                        else interim += event.results[i][0].transcript; 
                    } 
                    let currentSpeech = (final_transcript + interim).trim(); 
                    if (currentSpeech.length > 0) { 
                        document.getElementById("userMsg").value = currentSpeech; 
                        clearTimeout(silenceTimer); 
                        silenceTimer = setTimeout(() => { if (isLiveMode && currentSpeech.length > 0) sendMsg(); }, 2500); 
                    } 
                }; 
                recognition.onend = () => { 
                    isRecording = false; document.getElementById("micBtn").classList.remove("recording"); 
                    if (isLiveMode && !isTeacherSpeaking) { try { recognition.start(); } catch(e) {} } 
                }; 
                return true; 
            } 
            return false; 
        } 
        let isSpeechSupported = initSpeechRecognition();

        async function toggleMic() { 
            if (!isSpeechSupported) return alert("المتصفح لا يدعم الميكروفون."); 
            let ap = document.getElementById("audioPlayer"); 
            
            if (isTeacherSpeaking && !ap.paused) { 
                ap.pause(); isTeacherSpeaking = false; document.getElementById("pauseBtn").innerText = "▶️"; 
                wordsElements.forEach(span => span.classList.add("spoken")); 
                isLiveMode = true; final_transcript = ''; document.getElementById("liveIndicator").style.display = "block"; 
                recognition.lang = document.getElementById("micLang").value; 
                try { recognition.start(); } catch(e) {} 
                return; 
            } 
            
            if (isLiveMode || isRecording) { 
                isLiveMode = false; if(isRecording) recognition.stop(); 
                document.getElementById("liveIndicator").style.display = "none"; 
                if(window.localStream) window.localStream.getTracks().forEach(t => t.stop()); 
            } else { 
                try { window.localStream = await navigator.mediaDevices.getUserMedia({audio: { echoCancellation: true, noiseSuppression: true }}); } catch (e) {} 
                isLiveMode = true; final_transcript = ''; document.getElementById("liveIndicator").style.display = "block"; 
                recognition.lang = document.getElementById("micLang").value; 
                try { recognition.start(); } catch(e) {} 
            } 
        }
        
        document.getElementById("userMsg").addEventListener("keypress", function(e) { if (e.key === "Enter") { e.preventDefault(); sendMsg(); } });

        function triggerUpload() { toggleDrawer(); if(confirm("⚠️ يمنع رفع أي مواد تخالف القوانين أو حقوق النشر. موافق؟")) { document.getElementById("fileUpload").click(); } }
        function handleFileUpload(event) { 
            let file = event.target.files[0]; if (!file) return; 
            let status = document.getElementById("curriculumStatus"); if (status) status.innerText = "⏳ جاري القراءة..."; 
            let ext = file.name.split('.').pop().toLowerCase(); 
            if (ext === 'txt') { 
                let reader = new FileReader(); reader.onload = e => { customCurriculumContent = e.target.result; if(status) status.innerText = "✅ تم الدمج."; }; reader.readAsText(file); 
            } else if (ext === 'pdf') { 
                let reader = new FileReader(); reader.onload = async function(e) { 
                    try { 
                        let typedarray = new Uint8Array(e.target.result); let pdf = await pdfjsLib.getDocument(typedarray).promise; let fullText = ""; 
                        for(let i=1; i<=Math.min(pdf.numPages, 3); i++) { let page = await pdf.getPage(i); let textContent = await page.getTextContent(); fullText += textContent.items.map(item => item.str).join(" ") + " "; } 
                        customCurriculumContent = fullText; if(status) status.innerText = `✅ تم الاستخراج.`; 
                    } catch(err) { if(status) status.innerText = "❌ خطأ."; } 
                }; reader.readAsArrayBuffer(file); 
            } 
            event.target.value = ''; 
        }
    </script>
</body>
</html>
"""

# ==========================================
# 3. مسارات واجهة برمجة التطبيقات (API Routes)
# ==========================================

@app.route("/")
def home():
    if 'user_id' in session: 
        return render_template_string(MAIN_PAGE, username=session['username'])
    else: 
        return render_template_string(LOGIN_PAGE, google_id=GOOGLE_CLIENT_ID, fb_id=FACEBOOK_APP_ID)

@app.route("/download/<file_id>")
def download_file(file_id):
    if 'user_id' not in session: return redirect(url_for('home'))
    
    if file_id == 'study_plan':
        content = """=== Smart Academy CEFR Study Plan ===\n\n1. Level A1 (Beginner):\n- Focus: Basic phrases, introducing yourself.\n- Grammar: Present simple, basic pronouns.\n\n2. Level A2 (Elementary):\n- Focus: Routine tasks, simple shopping.\n- Grammar: Past simple, future plans.\n\n3. Level B1 (Intermediate):\n- Focus: Travel, expressing opinions.\n- Grammar: Perfect tenses, conditionals.\n\nKeep practicing daily with our AI Tutor!"""
        filename = "Study_Plan_CEFR.txt"
    elif file_id == 'vocab':
        content = """=== Essential 500 English Words (A1) ===\n\n1. Always\n2. Because\n3. Beautiful\n4. Company\n5. Different\n6. Enough\n7. Family\n... (Keep using the Academy to learn them all in context!)"""
        filename = "Basic_Vocab.txt"
    else:
        return "File not found", 404
        
    response = app.response_class(content, mimetype='text/plain')
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

@app.route("/intro_audio")
def intro_audio():
    text = "مَرْحَبًا بِكَ فِي أَكَادِيمِيَّتِكَ الذَّكِيَّةِ لِتَعَلُّمِ اللُّغَةِ الْإِنْجِلِيزِيَّةِ. هُنَا نُقَدِّمُ لَكَ مُعَلِّمًا بِشَخْصِيَّةٍ حَقِيقِيَّةٍ يُصَحِّحُ أَخْطَاءَكَ، وَيُوَجِّهُكَ فِي مُحَادَثَاتٍ حَيَّةٍ وَمُمْتِعَةٍ تُغَطِّي مِئَاتِ الْمَوَاضِيعِ وَفْقَ الْمَعَايِيرِ الْعَالَمِيَّةِ. سَجِّلْ دُخُولَكَ الْآنَ لِتَبْدَأَ رِحْلَتَكَ."
    try:
        audio = asyncio.run(generate_audio(text, "ar-SA-HamedNeural")) 
        return jsonify({"audio": audio})
    except: return jsonify({"error": "فشل توليد الصوت"})

@app.route("/auth", methods=["POST"])
def auth():
    data = request.json; action = data.get('action'); username = data.get('username', ''); password = data.get('password', ''); provider = data.get('provider', 'local')
    with sqlite3.connect('academy.db') as conn:
        cursor = conn.cursor()
        if action == 'guest':
            guest_name = f"ضيف_{random.randint(1000, 9999)}"
            cursor.execute("INSERT INTO users (username, password_hash, auth_provider) VALUES (?, ?, ?)", (guest_name, "GUEST", "guest")); conn.commit()
            cursor.execute("SELECT id FROM users WHERE username = ?", (guest_name,)); session['user_id'] = cursor.fetchone()[0]; session['username'] = guest_name
            return jsonify({"success": True})
        elif action == 'social':
            email = username; name = password 
            cursor.execute("SELECT id FROM users WHERE username = ?", (email,)); user = cursor.fetchone()
            if not user:
                random_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=16)); hashed_pw = generate_password_hash(random_pass)
                cursor.execute("INSERT INTO users (username, password_hash, auth_provider) VALUES (?, ?, ?)", (email, hashed_pw, provider)); conn.commit()
                cursor.execute("SELECT id FROM users WHERE username = ?", (email,)); user_id = cursor.fetchone()[0]
            else: user_id = user[0]
            session['user_id'] = user_id; session['username'] = name.split()[0] if name else email.split('@')[0]; return jsonify({"success": True})
        elif action == 'register':
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone(): return jsonify({"success": False, "error": "الاسم مستخدم مسبقاً."})
            hashed_pw = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, password_hash, auth_provider) VALUES (?, ?, ?)", (username, hashed_pw, 'local')); conn.commit()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,)); session['user_id'] = cursor.fetchone()[0]; session['username'] = username
            return jsonify({"success": True})
        elif action == 'login':
            cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)); user = cursor.fetchone()
            if user and check_password_hash(user[1], password): session['user_id'] = user[0]; session['username'] = username; return jsonify({"success": True})
            else: return jsonify({"success": False, "error": "بيانات الدخول غير صحيحة."})

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for('home'))

@app.route("/get_stats", methods=["GET"])
def get_stats():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"})
    try:
        user_id = session['user_id']
        with sqlite3.connect('academy.db') as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM academy_chats WHERE user_id = ? AND role = 'user'", (user_id,))
            total_messages = cursor.fetchone()[0]
            cursor = conn.execute('''SELECT SUBSTR(created_at, 1, 10) as date, COUNT(*) FROM academy_chats WHERE user_id = ? AND role = 'user' GROUP BY date ORDER BY date DESC LIMIT 7''', (user_id,))
            rows = cursor.fetchall()
            labels = []; values = []
            for row in reversed(rows): labels.append(row[0]); values.append(row[1])
            if not labels:
                labels = [datetime.now().strftime('%Y-%m-%d')]; values = [0]
        return jsonify({"total_messages": total_messages, "labels": labels, "values": values})
    except Exception as e: return jsonify({"error": str(e)})

@app.route("/get_history", methods=["GET"])
def get_history():
    if 'user_id' not in session: return jsonify([])
    try:
        user_id = session['user_id']
        with sqlite3.connect('academy.db') as conn:
            cursor = conn.execute("SELECT role, content, arabic FROM academy_chats WHERE user_id = ? ORDER BY id ASC", (user_id,))
            return jsonify([{"role": r[0], "content": r[1], "arabic": r[2]} for r in cursor.fetchall()])
    except: return jsonify([])

@app.route("/get_classroom_history", methods=["GET"])
def get_classroom_history():
    if 'user_id' not in session: return jsonify([])
    try:
        with sqlite3.connect('academy.db') as conn:
            cursor = conn.execute("SELECT username, role, content, arabic FROM classroom_chats ORDER BY id DESC LIMIT 50")
            rows = cursor.fetchall()[::-1]
            return jsonify([{"username": r[0], "role": r[1], "content": r[2], "arabic": r[3]} for r in rows])
    except: return jsonify([])

async def generate_audio(text, voice):
    clean_text = re.sub(r'[*#_~`]', '', text) 
    communicate = edge_tts.Communicate(clean_text, voice)
    await communicate.save("response.mp3")
    with open("response.mp3", "rb") as f: return base64.b64encode(f.read()).decode('utf-8')

@app.route("/chat", methods=["POST"])
def chat():
    if 'user_id' not in session: return jsonify({"error": "يرجى تسجيل الدخول أولاً."})
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key or not api_key.strip():
            return jsonify({"error": "تنبيه للمطور: مفتاح Groq API غير موجود أو فارغ. تأكد من إعادة تشغيل (Restart) السيرفر في Render بعد إضافته."})

        client = Groq(api_key=api_key)
        data = request.json
        mode = data.get("mode", "adult")
        user_msg = data.get("message", "")
        custom_curriculum = data.get("custom_curriculum", "")
        user_id = session['user_id']

        with sqlite3.connect('academy.db') as conn:
            cursor = conn.execute("SELECT role, content FROM academy_chats WHERE user_id = ? ORDER BY id DESC LIMIT 8", (user_id,))
            recent_rows = cursor.fetchall()[::-1]
            history = [{"role": r[0], "content": r[1]} for r in recent_rows]

        core_rules = """
        CRITICAL RULES: 
        1. MUST STRICTLY adhere to Islamic Sharia and local laws.
        2. Act as a certified Cambridge/Oxford examiner and professional coach.
        3. Make your 'english' response sound EXTREMELY natural, warm, and human. Use conversational fillers (e.g., 'Well,', 'You see,', 'Ah,', 'Great job!'). Use commas and exclamation marks properly so the TTS voice pauses naturally. Do NOT sound like a robot.
        """
        if custom_curriculum: core_rules += f"\\n4. Context from uploaded files: {custom_curriculum[:2500]}"

        json_structure = 'Respond ONLY in valid JSON format: { "english": "Natural spoken English.", "arabic": "Arabic translation", "keywords": "Keywords", "summary": "Notes / Test Feedback / Grammar Corrections" }'
        sys_msg = core_rules + ("\\nYou are a fun, cheerful English teacher for kids." if mode == "child" else "\\nYou are an expert, professional English coach.") + json_structure
        
        voice_model = "en-US-JennyNeural" if mode == "child" else "en-GB-RyanNeural" 

        messages = [{"role": "system", "content": sys_msg}] + history + [{"role": "user", "content": user_msg}]
        completion = client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages, response_format={"type": "json_object"})
        
        try: parsed = json.loads(completion.choices[0].message.content)
        except: parsed = {"english": "I'm sorry, I couldn't process that. Could you repeat?", "arabic": "عذراً، لم أستطع معالجة ذلك. هل يمكنك التكرار؟"}
        
        eng = parsed.get("english", ""); ar = parsed.get("arabic", "")
        
        with sqlite3.connect('academy.db') as conn:
            if "Act as a professional Cambridge examiner" not in user_msg and "Welcome the student" not in user_msg:
                conn.execute("INSERT INTO academy_chats (user_id, role, content, arabic) VALUES (?, ?, ?, ?)", (user_id, "user", user_msg, ""))
            conn.execute("INSERT INTO academy_chats (user_id, role, content, arabic) VALUES (?, ?, ?, ?)", (user_id, "assistant", eng, ar))
            conn.commit()
            
        audio = asyncio.run(generate_audio(eng, voice_model))
        return jsonify({ "english": eng, "arabic": ar, "keywords": parsed.get("keywords", ""), "summary": parsed.get("summary", ""), "audio": audio })
    except Exception as e:
        err_str = str(e)
        if "401" in err_str or "API Key" in err_str:
            return jsonify({"error": "مفتاح Groq API غير صالح. يرجى التأكد من نسخه بدون مسافات إضافية والتأكد من فعاليته."})
        return jsonify({"error": "حدث خطأ غير متوقع: " + err_str})

@app.route("/classroom_chat", methods=["POST"])
def classroom_chat():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"})
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key or not api_key.strip():
            return jsonify({"error": "تنبيه للمطور: مفتاح Groq API غير موجود أو فارغ. تأكد من إعادة تشغيل (Restart) السيرفر في Render بعد إضافته."})
        
        client = Groq(api_key=api_key)
        user_msg = request.json.get("message", "")
        user_id = session['user_id']
        username = session['username']

        with sqlite3.connect('academy.db') as conn:
            history = [{"role": r[0], "content": r[1]} for r in conn.execute("SELECT role, content FROM classroom_chats ORDER BY id DESC LIMIT 10").fetchall()[::-1]]

        sys_msg = """CRITICAL RULES: 
        1. You are teaching a VIRTUAL CLASSROOM. Be highly engaging and human-like. Use proper punctuation for TTS pauses.
        2. Address the specific student who spoke, keep it brief and conversational.
        Respond ONLY in valid JSON: { "english": "Natural spoken English.", "arabic": "Arabic translation", "keywords": "", "summary": "" }"""
        
        formatted_msg = f"[{username}]: {user_msg}"
        completion = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "system", "content": sys_msg}] + history + [{"role": "user", "content": formatted_msg}], response_format={"type": "json_object"})
        
        try: parsed = json.loads(completion.choices[0].message.content)
        except: parsed = {"english": "Let's continue our lesson.", "arabic": "دعونا نكمل درسنا."}
        
        eng = parsed.get("english", ""); ar = parsed.get("arabic", "")
        
        with sqlite3.connect('academy.db') as conn:
            conn.execute("INSERT INTO classroom_chats (user_id, username, role, content, arabic) VALUES (?, ?, ?, ?, ?)", (user_id, username, "user", user_msg, ""))
            conn.execute("INSERT INTO classroom_chats (user_id, username, role, content, arabic) VALUES (?, ?, ?, ?, ?)", (0, "Teacher", "assistant", eng, ar))
            conn.commit()
            
        audio = asyncio.run(generate_audio(eng, "en-GB-RyanNeural"))
        return jsonify({ "english": eng, "arabic": ar, "audio": audio })
    except Exception as e:
        err_str = str(e)
        if "401" in err_str or "API Key" in err_str:
            return jsonify({"error": "مفتاح Groq API غير صالح. يرجى التأكد من نسخه بدون مسافات إضافية والتأكد من فعاليته."})
        return jsonify({"error": "حدث خطأ غير متوقع: " + err_str})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
