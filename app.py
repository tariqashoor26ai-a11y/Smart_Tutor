import os
import asyncio
import base64
import json
import re
import sqlite3
import random
import string
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq
import edge_tts

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "smart-academy-super-secret-key-2026")

# === ضع الأرقام التعريفية الخاصة بك هنا ===
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com")
FACEBOOK_APP_ID = os.environ.get("FACEBOOK_APP_ID", "YOUR_FACEBOOK_APP_ID")

def init_db():
    with sqlite3.connect('academy.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            auth_provider TEXT DEFAULT 'local'
                        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS academy_chats (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            role TEXT,
                            content TEXT,
                            arabic TEXT,
                            FOREIGN KEY(user_id) REFERENCES users(id)
                        )''')
init_db()

# ==========================================
# 1. واجهة بوابة الدخول (Landing & Login)
# ==========================================
LOGIN_PAGE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>بوابة الدخول - Smart Academy</title>
    
    <!-- مكتبة Google Identity الحقيقية -->
    <script src="https://accounts.google.com/gsi/client" async defer></script>
    
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; }
        .wrapper { display: flex; flex-wrap: wrap; gap: 20px; width: 100%; max-width: 900px; justify-content: center; align-items: stretch; animation: popIn 0.6s ease-out;}
        @keyframes popIn { 0% { opacity: 0; transform: translateY(20px); } 100% { opacity: 1; transform: translateY(0); } }
        
        .box { background: rgba(255, 255, 255, 0.9); padding: 30px; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.5); flex: 1; min-width: 300px; }
        
        .intro-box { text-align: right; display: flex; flex-direction: column; justify-content: center;}
        .intro-box h2 { color: #8e44ad; margin-top: 0; font-size: 26px;}
        .intro-box p { color: #2c3e50; line-height: 1.8; font-size: 15px;}
        .audio-btn { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); border: none; padding: 12px 20px; border-radius: 12px; color: white; font-weight: bold; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; font-size: 14px; box-shadow: 0 4px 15px rgba(17, 153, 142, 0.3); transition: all 0.3s; align-self: flex-start; margin-top: 10px;}
        .audio-btn:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(17, 153, 142, 0.4); }

        .auth-box { text-align: center; }
        .auth-box h2 { color: #2c3e50; margin-top: 0; font-size: 24px; margin-bottom: 20px;}
        .input-group { margin-bottom: 15px; text-align: right; }
        .input-group label { display: block; margin-bottom: 5px; color: #34495e; font-weight: bold; font-size: 13px;}
        .input-group input { width: 100%; padding: 12px 15px; border-radius: 10px; border: 1px solid #bdc3c7; font-size: 14px; outline: none; box-sizing: border-box; transition: all 0.3s; background: #f9f9f9;}
        .input-group input:focus { border-color: #3498db; background: white; box-shadow: 0 0 10px rgba(52, 152, 219, 0.2); }
        
        .main-btn { width: 100%; padding: 12px; border-radius: 10px; border: none; font-size: 15px; font-weight: bold; color: white; cursor: pointer; transition: all 0.3s; background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3);}
        .main-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(52, 152, 219, 0.4); }
        
        .toggle-text { margin-top: 15px; font-size: 13px; color: #7f8c8d; }
        .toggle-text span { color: #8e44ad; font-weight: bold; cursor: pointer; }
        .toggle-text span:hover { text-decoration: underline; }
        
        .divider { display: flex; align-items: center; text-align: center; margin: 20px 0; color: #bdc3c7; font-size: 12px; }
        .divider::before, .divider::after { content: ''; flex: 1; border-bottom: 1px solid #ecf0f1; }
        .divider:not(:empty)::before { margin-left: .25em; }
        .divider:not(:empty)::after { margin-right: .25em; }

        .social-btn { width: 100%; padding: 10px; border-radius: 10px; border: none; font-size: 14px; font-weight: bold; cursor: pointer; transition: all 0.3s; margin-bottom: 10px; display: flex; justify-content: center; align-items: center; gap: 10px;}
        .social-btn.facebook { background: #1877F2; color: white; box-shadow: 0 4px 10px rgba(24, 119, 242, 0.3);}
        .social-btn.facebook:hover { background: #166fe5; }
        .social-btn.guest { background: #95a5a6; color: white; margin-bottom: 0;}
        .social-btn.guest:hover { background: #7f8c8d; }

        #googleBtnContainer { margin-bottom: 10px; display: flex; justify-content: center; width: 100%;}
        #errorMsg { color: #e74c3c; font-size: 13px; font-weight: bold; margin-bottom: 10px; min-height: 18px;}
    </style>
</head>
<body>
    <script>
      window.fbAsyncInit = function() {
        FB.init({
          appId      : '{{ fb_id }}',
          cookie     : true,
          xfbml      : true,
          version    : 'v19.0'
        });
      };
      (function(d, s, id){
         var js, fjs = d.getElementsByTagName(s)[0];
         if (d.getElementById(id)) {return;}
         js = d.createElement(s); js.id = id;
         js.src = "https://connect.facebook.net/en_US/sdk.js";
         fjs.parentNode.insertBefore(js, fjs);
       }(document, 'script', 'facebook-jssdk'));
    </script>

    <div class="wrapper">
        <div class="box intro-box">
            <h2>مرحباً بك في Smart Academy 🌟</h2>
            <p>أكاديميتك الذكية لتعلم اللغة الإنجليزية بطريقة تفاعلية تحاكي الواقع. <br><br>نقدم لك <b>معلماً بشخصية حقيقية</b> يصحح أخطاءك ويقودك في محادثات حية وممتعة، وفق معايير <b>CEFR</b> العالمية.</p>
            <button class="audio-btn" id="introAudioBtn" onclick="playIntroAudio()">
                <span id="audioIcon">🔊</span> استمع لنبذة الأكاديمية
            </button>
            <audio id="introPlayer"></audio>
        </div>

        <div class="box auth-box" id="loginBox">
            <h2 id="authTitle">تسجيل الدخول</h2>
            <div id="errorMsg"></div>
            
            <div class="input-group">
                <label>اسم المستخدم أو الإيميل</label>
                <input type="text" id="username" placeholder="أدخل بياناتك هنا...">
            </div>
            <div class="input-group">
                <label>كلمة المرور</label>
                <input type="password" id="password" placeholder="أدخل كلمة المرور...">
            </div>
            <button class="main-btn" id="submitBtn" onclick="submitAuth()">دخول إلى الأكاديمية</button>
            
            <div class="toggle-text" id="toggleDiv">ليس لديك حساب؟ <span onclick="toggleMode()">إنشاء حساب جديد</span></div>
            
            <div class="divider">أو عبر المنصات</div>
            
            <div id="googleBtnContainer"></div>
            <button class="social-btn facebook" onclick="loginWithFacebook()">📘 الدخول بحساب Facebook</button>
            <button class="social-btn guest" onclick="guestLogin()">👤 الدخول كضيف (تجربة سريعة)</button>
        </div>
    </div>

    <script>
        let isLogin = true;
        
        function toggleMode() {
            isLogin = !isLogin;
            document.getElementById('authTitle').innerText = isLogin ? 'تسجيل الدخول' : 'إنشاء حساب جديد ✨';
            document.getElementById('submitBtn').innerText = isLogin ? 'دخول إلى الأكاديمية' : 'تسجيل الحساب';
            document.getElementById('toggleDiv').innerHTML = isLogin ? 'ليس لديك حساب؟ <span onclick="toggleMode()">إنشاء حساب جديد</span>' : 'لديك حساب بالفعل؟ <span onclick="toggleMode()">تسجيل الدخول</span>';
            document.getElementById('errorMsg').innerText = '';
        }

        async function executeAuth(action, username, password, provider='local') {
            let err = document.getElementById('errorMsg');
            err.innerText = "جاري التحقق والمصادقة..."; err.style.color = "#3498db";
            try {
                let res = await fetch("/auth", {
                    method: "POST", headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ action: action, username: username, password: password, provider: provider })
                });
                let data = await res.json();
                if(data.success) {
                    window.location.href = "/?login=success"; 
                } else {
                    err.style.color = "#e74c3c"; err.innerText = data.error;
                }
            } catch(e) { err.style.color = "#e74c3c"; err.innerText = "خطأ في الاتصال بالسيرفر."; }
        }

        async function submitAuth() {
            let user = document.getElementById('username').value;
            let pass = document.getElementById('password').value;
            if(!user || !pass) { document.getElementById('errorMsg').innerText = "يرجى تعبئة جميع الحقول."; return; }
            executeAuth(isLogin ? 'login' : 'register', user, pass);
        }

        async function guestLogin() { executeAuth('guest', '', ''); }

        window.onload = function () {
            google.accounts.id.initialize({
                client_id: "{{ google_id }}",
                callback: handleGoogleResponse
            });
            google.accounts.id.renderButton(
                document.getElementById("googleBtnContainer"),
                { theme: "outline", size: "large", width: "100%", text: "continue_with" }
            );
        };

        function handleGoogleResponse(response) {
            const responsePayload = JSON.parse(atob(response.credential.split('.')[1]));
            let email = responsePayload.email;
            let name = responsePayload.name;
            executeAuth('social', email, name, 'google');
        }

        function loginWithFacebook() {
            FB.login(function(response) {
                if (response.authResponse) {
                    FB.api('/me', {fields: 'name,email'}, function(res) {
                        let email = res.email || res.id; 
                        let name = res.name;
                        executeAuth('social', email, name, 'facebook');
                    });
                } else {
                    document.getElementById('errorMsg').innerText = "تم إلغاء الدخول بواسطة فيسبوك.";
                }
            }, {scope: 'public_profile,email'});
        }

        async function playIntroAudio() {
            let btn = document.getElementById('introAudioBtn'), icon = document.getElementById('audioIcon'), player = document.getElementById('introPlayer');
            if(!player.src) {
                icon.innerText = "⏳"; btn.disabled = true;
                try {
                    let res = await fetch("/intro_audio"); let data = await res.json();
                    player.src = "data:audio/mp3;base64," + data.audio; player.play();
                } catch(e) { alert("حدث خطأ في تحميل الصوت."); }
                btn.disabled = false;
            } else { if(player.paused) player.play(); else player.pause(); }
        }
        document.getElementById('introPlayer').onplay = () => document.getElementById('audioIcon').innerText = "⏸️";
        document.getElementById('introPlayer').onpause = () => document.getElementById('audioIcon').innerText = "🔊";
        document.getElementById('introPlayer').onended = () => document.getElementById('audioIcon').innerText = "🔊";
    </script>
</body>
</html>
"""

# ==========================================
# 2. واجهة الأكاديمية الرئيسية (Main App)
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
        .drawer-btn.plan { background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); }
        .drawer-btn.test { background: linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%); }
        .drawer-btn.topics { background: linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%); }
        .drawer-btn.upload { background: linear-gradient(135deg, #d4fc79 0%, #96e6a1 100%); }
        .drawer-btn.settings { background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); }
        .drawer-btn.logout { background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%); color: #c0392b;}
        .curriculum-info { background: rgba(255, 255, 255, 0.9); border-radius: 15px; padding: 10px; width: 80%; max-width: 700px; margin: 10px auto; font-size: 13px; color: var(--secondary); box-shadow: var(--soft-shadow); border: 1px solid rgba(255,255,255,0.5);}
        .top-bar { display: flex; justify-content: center; align-items: center; width: 90%; max-width: 800px; margin: 0 auto 15px auto; gap: 15px; flex-wrap: wrap; }
        select { padding: 10px 15px; font-size: 14px; border-radius: 12px; border: 2px solid rgba(255,255,255,0.4); outline: none; cursor: pointer; background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); color: #2c3e50; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.05); text-align: center;}
        .start-btn { background: linear-gradient(135deg, var(--accent) 0%, #9b59b6 100%); font-weight: bold; padding: 10px 25px; font-size: 15px; border-radius: 12px; border: none; color: white; cursor: pointer; box-shadow: 0 5px 15px rgba(142, 68, 173, 0.3);}
        #liveIndicator { display: none; color: var(--danger); font-weight: bold; font-size: 14px; margin-top: 10px; animation: blink 1.5s infinite; }
        .input-container { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 20px;}
        input[type="text"] { padding: 16px 25px; font-size: 16px; border-radius: 30px; border: none; width: 65%; max-width: 600px; outline: none; background: rgba(255,255,255,0.95); box-shadow: var(--soft-shadow); }
        .circle-btn { border-radius: 50%; width: 55px; height: 55px; display: flex; justify-content: center; align-items: center; font-size: 24px; border: none; cursor: pointer; transition: all 0.2s ease; box-shadow: 0 6px 15px rgba(0,0,0,0.15); color: white;}
        #micBtn { background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);}
        #micBtn.recording { animation: pulseMic 1.5s infinite; }
        .send-btn { padding: 14px 30px; font-size: 16px; border-radius: 30px; border: none; color: white; cursor: pointer; font-weight: bold; background: linear-gradient(135deg, #36D1DC 0%, #5B86E5 100%); box-shadow: 0 6px 15px rgba(91, 134, 229, 0.3);}
        #audioControls { display: none; justify-content: center; gap: 15px; margin-top: 15px; background: rgba(255,255,255,0.95); padding: 12px 25px; border-radius: 30px; box-shadow: var(--soft-shadow); width: fit-content; margin: 15px auto;}
        .control-btn { background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); width: 45px; height: 45px; font-size: 18px;}
        .download-btn { background: linear-gradient(135deg, var(--success) 0%, #27ae60 100%); width: 45px; height: 45px; font-size: 18px;}
        #chatBox { width: 95%; max-width: 900px; margin: 20px auto; background: rgba(255, 255, 255, 0.95); padding: 25px; border-radius: 20px; box-shadow: var(--soft-shadow); height: 55vh; max-height: 600px; overflow-y: auto; display: flex; flex-direction: column; gap: 18px; border-top: 6px solid var(--primary); scroll-behavior: smooth; }
        .chat-bubble { max-width: 85%; padding: 18px 22px; border-radius: 20px; position: relative; font-size: var(--chat-size); color: var(--chat-color); line-height: 1.6; animation: fadeSlideUp 0.3s ease-out; box-shadow: 0 4px 10px rgba(0,0,0,0.04);}
        .user-bubble { background: var(--user-bg); align-self: flex-start; border-bottom-left-radius: 5px; text-align: left; direction: ltr;}
        .ai-bubble { background: var(--ai-bg); align-self: flex-end; border-bottom-right-radius: 5px; text-align: right;}
        .english-text { font-size: calc(var(--chat-size) + 4px); font-weight: bold; direction: ltr; text-align: left; margin-bottom: 10px;}
        .arabic-translation { border-top: 1px dashed rgba(0,0,0,0.15); padding-top: 10px; opacity: 0.9;}
        .structured-data { font-size: calc(var(--chat-size) - 2px); background-color: rgba(255,255,255,0.6); padding: 12px 15px; border-radius: 12px; margin-top: 12px; text-align: left; direction: ltr; border-left: 5px solid rgba(0,0,0,0.2);}
        .section-title { font-weight: bold; text-transform: uppercase; margin-bottom: 5px; display: block; opacity: 0.8;}
        .word { display: inline-block; margin-right: 5px; transition: color 0.1s ease-in; opacity: 0.7;}
        .word.active { color: var(--danger); transform: scale(1.15); font-weight: 900; opacity: 1;}
        .modal { display: none; position: fixed; z-index: 2000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.4); backdrop-filter: blur(6px); }
        .modal-content { background: rgba(255,255,255,0.98); margin: 8vh auto; padding: 35px; border-radius: 25px; width: 85%; max-width: 750px; max-height: 80vh; overflow-y: auto; text-align: right; box-shadow: 0 25px 50px rgba(0,0,0,0.3);}
        .close-btn { color: #aaa; float: left; font-size: 32px; font-weight: bold; cursor: pointer; transition: color 0.2s; background: #f0f0f0; border-radius: 50%; width: 40px; height: 40px; display: flex; justify-content: center; align-items: center;}
        .topics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; margin-top: 15px; }
        .topic-item { background: #f8f9fa; padding: 12px; border-radius: 12px; font-size: 13px; text-align: center; cursor: pointer; transition: all 0.2s; border: 1px solid #dcdde1; font-weight: bold; color: #34495e;}
        .topic-category { grid-column: 1 / -1; font-size: 16px; font-weight: bold; color: var(--accent); margin-top: 15px; border-bottom: 2px dashed #bdc3c7; padding-bottom: 5px; }
        .settings-group { margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between; background: #f9f9f9; padding: 12px 15px; border-radius: 12px; border: 1px solid #eee;}
        .settings-group input[type="color"] { border: none; width: 45px; height: 45px; border-radius: 8px; cursor: pointer; background: transparent;}
        .settings-group select, .settings-group input[type="range"] { width: 50%; padding: 10px; border-radius: 8px; border: 1px solid #ccc; outline: none;}
        #overlay { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.3); z-index: 1000; backdrop-filter: blur(2px);}
        #overlay.active { display: block; }
    </style>
</head>
<body>
    <div id="loginToast" class="toast">✅ تم تسجيل الدخول بنجاح! يتم الآن تحضير خطة الدرس...</div>
    <button class="hamburger-btn" onclick="toggleDrawer()"><span>☰</span> الخيارات</button>
    <div id="overlay" onclick="toggleDrawer()"></div>
    <div id="sideDrawer" class="drawer">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px; margin-top: 0;">الخدمات الأكاديمية</h3>
        <button class="drawer-btn plan" onclick="requestFeature('study_plan')"><span class="icon">📅</span><span>الخطة الدراسية</span></button>
        <button class="drawer-btn test" onclick="requestFeature('test')"><span class="icon">📝</span><span>التقييم والتدريب</span></button>
        <button class="drawer-btn topics" onclick="openModal('topicsModal')"><span class="icon">🗂️</span><span>المواضيع والقصص</span></button>
        <button class="drawer-btn upload" onclick="triggerUpload()"><span class="icon">📂</span><span>رفع منهج PDF</span></button>
        <button class="drawer-btn settings" onclick="openModal('settingsModal')"><span class="icon">🎨</span><span>تخصيص المظهر</span></button>
        <button class="drawer-btn logout" onclick="window.location.href='/logout'"><span class="icon">🚪</span><span>تسجيل الخروج</span></button>
    </div>
    <input type="file" id="fileUpload" accept=".txt,.pdf,.doc,.docx" style="display: none;" onchange="handleFileUpload(event)">
    <div id="topicsModal" class="modal"><div class="modal-content"><span class="close-btn" onclick="closeModal('topicsModal')">&times;</span><h2 style="text-align:center; color: var(--accent);">اختر موضوعاً 🎯</h2><div class="topics-grid" id="topicsList"></div></div></div>
    <div id="settingsModal" class="modal"><div class="modal-content"><span class="close-btn" onclick="closeModal('settingsModal')">&times;</span><h2 style="text-align:center; color: var(--primary);">🎨 المظهر</h2><div class="settings-group"><label>صندوق المتدرب:</label><input type="color" id="userBgColor" value="#d5f5e3" onchange="applySettings()"></div><div class="settings-group"><label>صندوق المدرب:</label><input type="color" id="aiBgColor" value="#e1f5fe" onchange="applySettings()"></div><div class="settings-group"><label>لون النصوص:</label><input type="color" id="fontColor" value="#2c3e50" onchange="applySettings()"></div><div class="settings-group"><label>حجم الخط:</label><input type="range" id="fontSize" min="12" max="24" value="16" oninput="applySettings()"><span id="fontSizeVal">16px</span></div><button class="send-btn" style="width: 100%; margin-top: 15px;" onclick="resetSettings()">🔄 استعادة</button></div></div>
    <h2>Smart Academy 🎓</h2>
    <div style="font-size: 14px; color: #7f8c8d; margin-bottom: 20px; font-weight: bold;">مرحباً بك يا {{ username }}! سجل محادثاتك محفوظ.</div>
    <div class="curriculum-info">📚 <strong>المنهج:</strong> (CEFR). <span id="curriculumStatus" style="color:var(--success); font-weight:bold; margin-right:10px;"></span></div>
    <div class="top-bar"><select id="mode" onchange="changeStyle()"><option value="adult">وضع الكبار</option><option value="child">وضع الأطفال</option></select><select id="micLang"><option value="en-US">الميكروفون: إنجليزي</option><option value="ar-SA">الميكروفون: عربي</option></select><button class="start-btn" onclick="startLiveLesson()">🎓 ابدأ المكالمة الحية</button></div>
    <div id="liveIndicator">🔴 المكالمة نشطة...</div>
    <div class="input-container"><button id="micBtn" class="circle-btn" onclick="toggleMic()">🎤</button><input type="text" id="userMsg" placeholder="اكتب أو تحدث..."><button class="send-btn" onclick="sendMsg()">إرسال</button></div>
    <div id="audioControls"><button class="circle-btn control-btn" onclick="skipAudio(-5)">⏪</button><button id="pauseBtn" class="circle-btn control-btn" onclick="togglePauseAudio()">⏸️</button><button class="circle-btn control-btn" onclick="skipAudio(5)">⏩</button><button class="circle-btn download-btn" onclick="downloadAudio()">💾</button></div>
    <div id="chatBox"></div><audio id="audioPlayer"></audio>
    <script>
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';
        let isRecording = false, recognition, customCurriculumContent = "", wordsElements = [];
        let isLiveMode = false, silenceTimer, final_transcript = '', chatHistory = [], isTeacherSpeaking = false, userName = "{{ username }}";
        function toggleDrawer() { document.getElementById('sideDrawer').classList.toggle('open'); document.getElementById('overlay').classList.toggle('active'); }
        const topicsLibrary = { "📱 تكنولوجيا": ["الذكاء الاصطناعي", "الأمن السيبراني"], "⚽ رياضة": ["كرة القدم", "كرة السلة"], "💼 حياة": ["مقابلات العمل", "إدارة الوقت"] };
        function populateTopics() { let container = document.getElementById("topicsList"); for (const [category, topics] of Object.entries(topicsLibrary)) { let catDiv = document.createElement("div"); catDiv.className = "topic-category"; catDiv.innerText = category; container.appendChild(catDiv); topics.forEach(topic => { let btn = document.createElement("div"); btn.className = "topic-item"; btn.innerText = topic; btn.onclick = () => { closeModal('topicsModal'); toggleDrawer(); sendMsg(`Let's discuss: ${topic}.`); }; container.appendChild(btn); }); } } populateTopics();
        function openModal(id) { document.getElementById(id).style.display = "block"; toggleDrawer(); } function closeModal(id) { document.getElementById(id).style.display = "none"; }
        function applySettings() { let root = document.documentElement; root.style.setProperty('--user-bg', document.getElementById('userBgColor').value); root.style.setProperty('--ai-bg', document.getElementById('aiBgColor').value); root.style.setProperty('--chat-color', document.getElementById('fontColor').value); root.style.setProperty('--chat-size', document.getElementById('fontSize').value + 'px'); document.getElementById('fontSizeVal').innerText = document.getElementById('fontSize').value + 'px'; }
        function resetSettings() { document.getElementById('userBgColor').value = "#d5f5e3"; document.getElementById('aiBgColor').value = "#e1f5fe"; document.getElementById('fontColor').value = "#2c3e50"; document.getElementById('fontSize').value = "16"; applySettings(); }
        function changeStyle() { document.getElementById('aiBgColor').value = document.getElementById("mode").value === "child" ? "#ffebef" : "#e1f5fe"; applySettings(); }
        async function startLiveLesson() { try { window.localStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); } catch (e) {} isLiveMode = true; document.getElementById("liveIndicator").style.display = "block"; final_transcript = ''; if (!isRecording && recognition) { recognition.lang = document.getElementById("micLang").value; try { recognition.start(); } catch(e) {} } sendMsg(`Hello! I am ready. Please ask me a question to start.`); }
        function requestFeature(type) { toggleDrawer(); sendMsg({"study_plan": "Suggest a CEFR study plan.", "test": "Give me a short test."}[type]); }
        function triggerUpload() { toggleDrawer(); if(confirm("⚠️ يمنع رفع أي مواد تخالف القوانين أو حقوق النشر. موافق؟")) { document.getElementById("fileUpload").click(); } }
        function handleFileUpload(event) { let file = event.target.files[0]; if (!file) return; let status = document.getElementById("curriculumStatus"); status.innerText = "⏳ جاري قراءة الملف..."; let ext = file.name.split('.').pop().toLowerCase(); if (ext === 'txt') { let reader = new FileReader(); reader.onload = e => { customCurriculumContent = e.target.result; status.innerText = "✅ تم دمج المنهج."; }; reader.readAsText(file); } else if (ext === 'pdf') { let reader = new FileReader(); reader.onload = async function(e) { try { let typedarray = new Uint8Array(e.target.result); let pdf = await pdfjsLib.getDocument(typedarray).promise; let fullText = ""; for(let i=1; i<=Math.min(pdf.numPages, 3); i++) { let page = await pdf.getPage(i); let textContent = await page.getTextContent(); fullText += textContent.items.map(item => item.str).join(" ") + " "; } customCurriculumContent = fullText; status.innerText = `✅ تم الاستخراج.`; } catch(err) { status.innerText = "❌ خطأ."; } }; reader.readAsArrayBuffer(file); } event.target.value = ''; }
        function skipAudio(s) { let a = document.getElementById("audioPlayer"); if (a.src) a.currentTime += s; } function downloadAudio() { let a = document.getElementById("audioPlayer"); if (!a.src) return; let link = document.createElement("a"); link.href = a.src; link.download = "SmartAcademy_Lesson.mp3"; document.body.appendChild(link); link.click(); document.body.removeChild(link); } function togglePauseAudio() { let a = document.getElementById("audioPlayer"), btn = document.getElementById("pauseBtn"); if(a.src === "") return; if (a.paused) { a.play(); btn.innerText = "⏸️"; } else { a.pause(); btn.innerText = "▶️"; } }
        let audioPlayer = document.getElementById("audioPlayer"); audioPlayer.ontimeupdate = function() { if (wordsElements.length === 0 || isNaN(audioPlayer.duration)) return; let activeIndex = Math.floor((audioPlayer.currentTime / audioPlayer.duration) * wordsElements.length); wordsElements.forEach((span, i) => { if (i === activeIndex) { span.classList.add("active"); span.classList.remove("spoken"); } else if (i < activeIndex) { span.classList.remove("active"); span.classList.add("spoken"); } else { span.classList.remove("active", "spoken"); } }); }; audioPlayer.onended = function() { isTeacherSpeaking = false; document.getElementById("pauseBtn").innerText = "▶️"; wordsElements.forEach(span => { span.classList.remove("active"); span.classList.add("spoken"); }); if (isLiveMode) setTimeout(() => { try { recognition.start(); } catch(e) {} }, 300); };
        function initSpeechRecognition() { window.SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition; if (window.SpeechRecognition) { recognition = new window.SpeechRecognition(); recognition.continuous = true; recognition.interimResults = true; recognition.onstart = () => { isRecording = true; document.getElementById("micBtn").classList.add("recording"); }; recognition.onresult = (event) => { if(isTeacherSpeaking) return; let interim = ''; for (let i = event.resultIndex; i < event.results.length; ++i) { if (event.results[i].isFinal) final_transcript += event.results[i][0].transcript + " "; else interim += event.results[i][0].transcript; } let currentSpeech = (final_transcript + interim).trim(); if (currentSpeech.length > 0) { document.getElementById("userMsg").value = currentSpeech; clearTimeout(silenceTimer); silenceTimer = setTimeout(() => { if (isLiveMode && currentSpeech.length > 0) sendMsg(); }, 2500); } }; recognition.onend = () => { isRecording = false; document.getElementById("micBtn").classList.remove("recording"); if (isLiveMode && !isTeacherSpeaking) { try { recognition.start(); } catch(e) {} } }; return true; } return false; } let isSpeechSupported = initSpeechRecognition();
        async function toggleMic() { if (!isSpeechSupported) return alert("المتصفح لا يدعم الميكروفون."); if (isTeacherSpeaking && !audioPlayer.paused) { audioPlayer.pause(); isTeacherSpeaking = false; document.getElementById("pauseBtn").innerText = "▶️"; wordsElements.forEach(span => span.classList.add("spoken")); isLiveMode = true; final_transcript = ''; document.getElementById("liveIndicator").style.display = "block"; recognition.lang = document.getElementById("micLang").value; try { recognition.start(); } catch(e) {} return; } if (isLiveMode || isRecording) { isLiveMode = false; if(isRecording) recognition.stop(); document.getElementById("liveIndicator").style.display = "none"; if(window.localStream) window.localStream.getTracks().forEach(t => t.stop()); } else { try { window.localStream = await navigator.mediaDevices.getUserMedia({audio: { echoCancellation: true, noiseSuppression: true }}); } catch (e) {} isLiveMode = true; final_transcript = ''; document.getElementById("liveIndicator").style.display = "block"; recognition.lang = document.getElementById("micLang").value; try { recognition.start(); } catch(e) {} } }
        document.getElementById("userMsg").addEventListener("keypress", function(e) { if (e.key === "Enter") { e.preventDefault(); sendMsg(); } });
        function appendBubble(text, isUser, data=null) { let box = document.getElementById("chatBox"), container = document.createElement("div"); container.className = isUser ? "chat-bubble user-bubble" : "chat-bubble ai-bubble"; if(isUser) { container.innerText = text; } else { let engDiv = document.createElement("div"); engDiv.className = "english-text"; wordsElements = []; data.english.split(" ").forEach(word => { let span = document.createElement("span"); span.className = "word"; span.innerText = word; engDiv.appendChild(span); wordsElements.push(span); }); container.appendChild(engDiv); let arDiv = document.createElement("div"); arDiv.className = "arabic-translation"; arDiv.innerText = data.arabic; container.appendChild(arDiv); let details = ""; if(data.keywords) details += `<div class="structured-data"><span class="section-title">🔑 Keywords:</span><br>${data.keywords}</div>`; if(data.summary) details += `<div class="structured-data"><span class="section-title">📝 Notes:</span><br>${data.summary}</div>`; if (details !== "") { let dDiv = document.createElement("div"); dDiv.innerHTML = details; container.appendChild(dDiv); } } box.appendChild(container); setTimeout(() => box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' }), 100); }
        window.onload = async function() { if (window.location.search.includes("login=success")) { let toast = document.getElementById("loginToast"); toast.classList.add("show"); setTimeout(() => toast.classList.remove("show"), 4000); } document.getElementById('chatBox').innerHTML = ''; try { let res = await fetch("/get_history"); let history = await res.json(); if (history.length > 0) { history.forEach(item => { if(item.role === 'user') { appendBubble(item.content, true); chatHistory.push({"role": "user", "content": item.content}); } else if(item.role === 'assistant') { appendBubble("", false, {english: item.content, arabic: item.arabic}); chatHistory.push({"role": "assistant", "content": item.content}); } }); document.getElementById("chatBox").scrollTop = document.getElementById("chatBox").scrollHeight; } else { let prompt = `Welcome the student (${userName}) warmly. Outline a short lesson plan for today. Ask if they are ready.`; sendMsg(prompt, true); } } catch(e) {} };
        async function sendMsg(overrideMsg = null, isHidden = false) { let inputField = document.getElementById("userMsg"), msg = overrideMsg || inputField.value; if(!msg.trim()) return; if(!isHidden){ appendBubble(msg, true); chatHistory.push({"role": "user", "content": msg}); } else { chatHistory.push({"role": "system", "content": msg}); } final_transcript = ''; clearTimeout(silenceTimer); audioPlayer.pause(); document.getElementById("audioControls").style.display = "none"; inputField.value = ""; let loadDiv = document.createElement("div"); loadDiv.className = "chat-bubble ai-bubble"; loadDiv.id = "loadingBubble"; loadDiv.innerHTML = "<div class='arabic-translation' style='border:none;'>جاري تجهيز الرد... ⏳</div>"; document.getElementById("chatBox").appendChild(loadDiv); document.getElementById("chatBox").scrollTop = document.getElementById("chatBox").scrollHeight; try { let res = await fetch("/chat", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ history: chatHistory.slice(-10), mode: document.getElementById("mode").value, custom_curriculum: customCurriculumContent }) }); let data = await res.json(); document.getElementById("loadingBubble")?.remove(); if(data.error) return alert("⚠️ خطأ: " + data.error); chatHistory.push({"role": "assistant", "content": data.english}); appendBubble("", false, data); if(data.audio) { audioPlayer.src = "data:audio/mp3;base64," + data.audio; document.getElementById("audioControls").style.display = "flex"; document.getElementById("pauseBtn").innerText = "⏸️"; isTeacherSpeaking = true; if(isRecording) recognition.stop(); let playPromise = audioPlayer.play(); if (playPromise !== undefined) playPromise.catch(error => { console.log("Auto-play blocked."); }); } } catch (e) { document.getElementById("loadingBubble")?.remove(); alert("⚠️ خطأ في الاتصال."); } }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    if 'user_id' in session: return render_template_string(MAIN_PAGE, username=session['username'])
    else: return render_template_string(LOGIN_PAGE, google_id=GOOGLE_CLIENT_ID, fb_id=FACEBOOK_APP_ID)

@app.route("/intro_audio")
def intro_audio():
    text = "مرحباً بك في أكاديميتك الذكية لتعلم اللغة الإنجليزية. هنا نقدم لك معلماً بشخصية حقيقية يصحح أخطاءك، ويوجهك في محادثات حية وممتعة تغطي مئات المواضيع وفق المعايير العالمية. سجل دخولك الآن لتبدأ رحلتك."
    try:
        audio = asyncio.run(generate_audio(text, "ar-SA-HamedNeural")) 
        return jsonify({"audio": audio})
    except: return jsonify({"error": "فشل توليد الصوت"})

@app.route("/auth", methods=["POST"])
def auth():
    data = request.json
    action = data.get('action')
    username = data.get('username', '')
    password = data.get('password', '')
    provider = data.get('provider', 'local')
    
    with sqlite3.connect('academy.db') as conn:
        cursor = conn.cursor()
        
        if action == 'guest':
            guest_name = f"ضيف_{random.randint(1000, 9999)}"
            cursor.execute("INSERT INTO users (username, password_hash, auth_provider) VALUES (?, ?, ?)", (guest_name, "GUEST", "guest"))
            conn.commit()
            cursor.execute("SELECT id FROM users WHERE username = ?", (guest_name,))
            session['user_id'] = cursor.fetchone()[0]
            session['username'] = guest_name
            return jsonify({"success": True})

        elif action == 'social':
            email = username 
            name = password 
            cursor.execute("SELECT id FROM users WHERE username = ?", (email,))
            user = cursor.fetchone()
            
            if not user:
                random_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
                hashed_pw = generate_password_hash(random_pass)
                cursor.execute("INSERT INTO users (username, password_hash, auth_provider) VALUES (?, ?, ?)", (email, hashed_pw, provider))
                conn.commit()
                cursor.execute("SELECT id FROM users WHERE username = ?", (email,))
                user_id = cursor.fetchone()[0]
            else:
                user_id = user[0]
                
            session['user_id'] = user_id
            session['username'] = name.split()[0] if name else email.split('@')[0]
            return jsonify({"success": True})

        elif action == 'register':
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone(): return jsonify({"success": False, "error": "الاسم مستخدم مسبقاً."})
            hashed_pw = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, password_hash, auth_provider) VALUES (?, ?, ?)", (username, hashed_pw, 'local'))
            conn.commit()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            session['user_id'] = cursor.fetchone()[0]
            session['username'] = username
            return jsonify({"success": True})
            
        elif action == 'login':
            cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                return jsonify({"success": True})
            else: return jsonify({"success": False, "error": "بيانات الدخول غير صحيحة."})

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for('home'))

@app.route("/get_history", methods=["GET"])
def get_history():
    if 'user_id' not in session: return jsonify([])
    try:
        user_id = session['user_id']
        with sqlite3.connect('academy.db') as conn:
            cursor = conn.execute("SELECT role, content, arabic FROM academy_chats WHERE user_id = ? ORDER BY id ASC", (user_id,))
            rows = cursor.fetchall()
            history = [{"role": r[0], "content": r[1], "arabic": r[2]} for r in rows]
        return jsonify(history)
    except Exception as e: return jsonify([])

async def generate_audio(text, voice):
    clean_text = re.sub(r'[^\w\s.,!?\']', '', text) 
    communicate = edge_tts.Communicate(clean_text, voice)
    await communicate.save("response.mp3")
    with open("response.mp3", "rb") as f: return base64.b64encode(f.read()).decode('utf-8')

@app.route("/chat", methods=["POST"])
def chat():
    if 'user_id' not in session: return jsonify({"error": "يرجى تسجيل الدخول أولاً."})
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key: return jsonify({"error": "Missing GROQ_API_KEY"})

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
        2. Base language progression on the CEFR.
        3. ACT EXACTLY LIKE A REAL, EMPATHETIC HUMAN TUTOR. Provide proactive guidance.
        4. Make your 'english' response sound 100% natural, using conversational fillers.
        """
        if custom_curriculum: core_rules += f"\\n5. Context from uploaded files: {custom_curriculum[:2500]}"

        json_structure = 'Respond ONLY in JSON format: { "english": "Natural spoken English.", "arabic": "Arabic translation", "keywords": "Keywords", "summary": "Notes / Lesson Plan / Gentle Corrections" }'
        
        sys_msg = core_rules + ("\\nYou are a fun English teacher for kids." if mode == "child" else "\\nYou are a professional English coach.") + json_structure
        voice_model = "en-US-AriaNeural" if mode == "child" else "en-US-ChristopherNeural" 

        messages = [{"role": "system", "content": sys_msg}] + history + [{"role": "user", "content": user_msg}]
        completion = client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages, response_format={"type": "json_object"})
        
        parsed = json.loads(completion.choices[0].message.content)
        eng_text = parsed.get("english", "Hello there!")
        ar_text = parsed.get("arabic", "")
        
        with sqlite3.connect('academy.db') as conn:
            if "Generate a unique, warm welcome message" not in user_msg:
                conn.execute("INSERT INTO academy_chats (user_id, role, content, arabic) VALUES (?, ?, ?, ?)", (user_id, "user", user_msg, ""))
            conn.execute("INSERT INTO academy_chats (user_id, role, content, arabic) VALUES (?, ?, ?, ?)", (user_id, "assistant", eng_text, ar_text))
            
        audio_base64 = asyncio.run(generate_audio(eng_text, voice_model))

        return jsonify({ "english": eng_text, "arabic": ar_text, "keywords": parsed.get("keywords", ""), "summary": parsed.get("summary", ""), "audio": audio_base64 })
    except Exception as e: return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
