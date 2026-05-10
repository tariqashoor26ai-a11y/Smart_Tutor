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

# الهيكلية الأكاديمية (CEFR Framework)
FULL_SYLLABUS = {
    "A1": {
        "name": "Beginner (A1)",
        "lessons": {
            1: {"title": "Greetings", "focus": "Verb to be"},
            2: {"title": "Routine", "focus": "Present simple"},
            10: {"title": "A1 Final Review", "focus": "All A1 grammar review"}
        }
    },
    "A2": {
        "name": "Elementary (A2)",
        "lessons": {
            11: {"title": "Comparisons", "focus": "Comparative adjectives"},
            20: {"title": "A2 Final Review", "focus": "All A2 grammar"}
        }
    },
    "B1": {
        "name": "Intermediate (B1)",
        "lessons": {
            21: {"title": "Opinions", "focus": "Conditionals (If...)"},
            30: {"title": "B1 Final Review", "focus": "All B1 grammar"}
        }
    }
}

def get_lesson_info(lesson_id):
    if lesson_id <= 10: return "A1", FULL_SYLLABUS["A1"]["lessons"].get(lesson_id, {"title": f"Lesson {lesson_id}", "focus": "Vocabulary"})
    elif lesson_id <= 20: return "A2", FULL_SYLLABUS["A2"]["lessons"].get(lesson_id, {"title": f"Lesson {lesson_id}", "focus": "Vocabulary"})
    else: return "B1", FULL_SYLLABUS["B1"]["lessons"].get(lesson_id, {"title": f"Lesson {lesson_id}", "focus": "Vocabulary"})

def init_db():
    with sqlite3.connect('academy.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            password_hash TEXT NOT NULL,
                            auth_provider TEXT DEFAULT 'local',
                            current_state TEXT DEFAULT 'FREE_CHAT',
                            state_data TEXT DEFAULT '{}',
                            parent_pin TEXT DEFAULT '0000',
                            current_lesson_id INTEGER DEFAULT 1,
                            xp_points INTEGER DEFAULT 0,
                            last_quiz_score TEXT DEFAULT 'N/A',
                            is_certified INTEGER DEFAULT 0,
                            gdpr_consent INTEGER DEFAULT 0,
                            fluency_score INTEGER DEFAULT 0,
                            grammar_score INTEGER DEFAULT 0,
                            vocab_score INTEGER DEFAULT 0,
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
        conn.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            action TEXT NOT NULL,
                            detail TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )''')
        
        # التحديثات التراكمية لقاعدة البيانات
        cols = ["created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "current_state TEXT DEFAULT 'FREE_CHAT'", 
                "state_data TEXT DEFAULT '{}'", "parent_pin TEXT DEFAULT '0000'", "current_lesson_id INTEGER DEFAULT 1",
                "xp_points INTEGER DEFAULT 0", "last_quiz_score TEXT DEFAULT 'N/A'", "is_certified INTEGER DEFAULT 0",
                "gdpr_consent INTEGER DEFAULT 0", "fluency_score INTEGER DEFAULT 0", "grammar_score INTEGER DEFAULT 0", "vocab_score INTEGER DEFAULT 0"]
        for col in cols:
            try: conn.execute(f"ALTER TABLE users ADD COLUMN {col}")
            except: pass
        try: conn.execute("ALTER TABLE academy_chats ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except: pass
init_db()

def log_activity(user_id, action, detail=""):
    with sqlite3.connect('academy.db') as conn:
        conn.execute("INSERT INTO activity_logs (user_id, action, detail) VALUES (?, ?, ?)", (user_id, action, detail))
        conn.commit()

# ==========================================
# محرك المنطق المهيكل (Structured Workflow Manager)
# ==========================================
class WorkflowManager:
    @staticmethod
    def process_state(user_id, user_msg, mode, custom_curriculum):
        with sqlite3.connect('academy.db') as conn:
            cursor = conn.execute("SELECT current_state, state_data, current_lesson_id, xp_points FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            current_state = row[0] or 'FREE_CHAT'
            state_data = json.loads(row[1]) if row[1] else {}
            current_lesson_id = row[2] or 1
            xp_points = row[3] or 0

        user_msg_lower = user_msg.lower()
        
        # اعتراض النوايا
        if "comprehensive english placement test" in user_msg_lower:
            current_state = 'PLACEMENT_TEST'
            state_data = {"step": 1, "total_steps": 5}
        elif "deeply discuss this topic:" in user_msg_lower:
            current_state = 'TOPIC_DISCUSSION'
            try: topic = user_msg.split("topic: ")[1].split(".")[0]
            except: topic = "General English"
            state_data = {"topic": topic}
        elif "start the next syllabus lesson" in user_msg_lower:
            if current_lesson_id > 30: current_state = 'GRADUATED'
            else:
                current_state = 'LESSON_MODE'
                state_data = {"lesson_id": current_lesson_id}
                log_activity(user_id, "STARTED_LESSON", f"Lesson {current_lesson_id}")
        elif current_state != 'FREE_CHAT' and any(word in user_msg_lower for word in ["exit test", "stop", "خروج", "إنهاء الاختبار", "exit lesson"]):
            current_state = 'FREE_CHAT'
            state_data = {}
            log_activity(user_id, "EXITED_MODE", "Returned to free chat")
            return "CRITICAL: The user has chosen to exit the current mode. Acknowledge this warmly and return to free chat.", current_state, current_lesson_id, xp_points

        base_rule = "1. STRICT Law compliance. 2. Human-like voice.\n"
        json_structure = '\nRespond ONLY in valid JSON format: { "english": "...", "arabic": "...", "keywords": "...", "summary": "...", "scores": {"fluency": 0, "grammar": 0, "vocab": 0} }'
        
        if current_state == 'PLACEMENT_TEST':
            step = state_data.get("step", 1)
            total = state_data.get("total_steps", 5)
            if step <= total:
                sys_msg = base_rule + f"MODE: PLACEMENT TEST (Q{step}/{total}). Ask exactly ONE progressive English test question. Evaluate previous answer in 'summary'."
                state_data["step"] = step + 1
            else:
                sys_msg = base_rule + "MODE: TEST COMPLETE. Give estimated CEFR level, brief feedback, and welcome to free chat."
                current_state = 'FREE_CHAT'
                state_data = {}

        elif current_state == 'TOPIC_DISCUSSION':
            topic = state_data.get("topic", "English")
            sys_msg = base_rule + f"MODE: FOCUSED TOPIC ('{topic}'). Keep conversation strictly on this topic. Steer back gently if they stray."

        elif current_state == 'LESSON_MODE':
            level_name, lesson = get_lesson_info(current_lesson_id)
            if current_lesson_id in [10, 20, 30]:
                sys_msg = base_rule + f"CRITICAL MODE: LEVEL EXAM ({level_name}). Ask 3 tough questions to verify they master {level_name}."
                current_state = 'LEVEL_EXAM'
                state_data = {"step": 1, "score": 0}
                log_activity(user_id, "STARTED_EXAM", level_name)
            elif "ready for quiz" in user_msg_lower or "ready for test" in user_msg_lower:
                current_state = 'LESSON_QUIZ'
                state_data = {"step": 1, "score": 0}
                sys_msg = base_rule + f"QUIZ MODE for '{lesson['title']}'. Ask Q1."
            else:
                sys_msg = base_rule + f"TEACHING Level {level_name}, Lesson {current_lesson_id}: {lesson['title']}. Explain {lesson['focus']} briefly. Remind them to say 'I am ready for the quiz'."

        elif current_state == 'LESSON_QUIZ':
            level_name, lesson = get_lesson_info(current_lesson_id)
            step = state_data.get("step", 1)
            if step <= 3:
                sys_msg = base_rule + f"QUIZ (Q{step}/3) for {level_name}. Correct previous. Ask next question."
                state_data["step"] = step + 1
            else:
                current_lesson_id += 1
                xp_points += 50
                current_state = 'FREE_CHAT'
                sys_msg = base_rule + "QUIZ PASSED! Give 50XP and return to free chat."
                state_data = {}
                log_activity(user_id, "PASSED_QUIZ", f"Lesson {current_lesson_id - 1}")

        elif current_state == 'LEVEL_EXAM':
            level_name, lesson = get_lesson_info(current_lesson_id)
            step = state_data.get("step", 1)
            if step <= 3:
                sys_msg = base_rule + f"LEVEL EXAM {level_name} (Q{step}/3). Very formal examiner tone. Ask deep questions. Evaluate their last answer and fill the 'scores' JSON object out of 10 for fluency, grammar, and vocab."
                state_data["step"] = step + 1
            else:
                current_lesson_id += 1
                xp_points += 200
                current_state = 'FREE_CHAT'
                sys_msg = base_rule + f"EXAM PASSED! They are now certified for {level_name}. Give 200XP."
                state_data = {}
                log_activity(user_id, "PASSED_LEVEL_EXAM", level_name)
        
        elif current_state == 'GRADUATED':
            sys_msg = base_rule + "The student has finished all 30 lessons! Celebrate their graduation."

        else: # FREE_CHAT
            role = "a fun English teacher for kids" if mode == "child" else "an expert English coach"
            sys_msg = base_rule + f"MODE: FREE CHAT. You are {role}. Have a natural conversation. Use conversational fillers. Use proper punctuation for TTS pauses."
        
        with sqlite3.connect('academy.db') as conn:
            conn.execute("UPDATE users SET current_state = ?, state_data = ?, current_lesson_id = ?, xp_points = ? WHERE id = ?", (current_state, json.dumps(state_data), current_lesson_id, xp_points, user_id))
            conn.commit()

        return sys_msg + json_structure, current_state, current_lesson_id, xp_points

# ==========================================
# 1. واجهة تسجيل الدخول والتسويق (LOGIN_PAGE)
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
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); color: #2c3e50;}
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        .hero-section { display: flex; flex-wrap: wrap; gap: 30px; margin-bottom: 50px;}
        .box { background: rgba(255, 255, 255, 0.9); padding: 35px; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); flex: 1; min-width: 320px; }
        .auth-box h2 { margin-top: 0; }
        .input-group { margin-bottom: 15px; text-align: right; }
        .input-group input { width: 100%; padding: 12px; border-radius: 10px; border: 1px solid #bdc3c7; box-sizing: border-box; }
        .main-btn { width: 100%; padding: 12px; border-radius: 10px; border: none; font-weight: bold; color: white; background: #3498db; cursor: pointer;}
        #errorMsg { color: #e74c3c; font-size: 13px; font-weight: bold; margin-bottom: 10px; min-height: 18px;}
        .social-btn { width: 100%; padding: 10px; border-radius: 10px; border: none; cursor: pointer; margin-bottom: 10px;}
        .guest { background: #95a5a6; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <div class="hero-section">
            <div class="box intro-box">
                <h1>Smart Academy 🌟</h1>
                <p>مستقبلك في إتقان الإنجليزية يبدأ من هنا. تدرّب مع معلم ذكاء اصطناعي تفاعلي.</p>
            </div>
            <div class="box auth-box" id="loginBox">
                <h2 id="authTitle">تسجيل الدخول</h2>
                <div id="errorMsg"></div>
                <div class="input-group"><input type="text" id="username" placeholder="اسم المستخدم"></div>
                <div class="input-group"><input type="password" id="password" placeholder="كلمة المرور"></div>
                <button class="main-btn" id="submitBtn" onclick="submitAuth()">دخول إلى الأكاديمية</button>
                <div style="margin-top: 15px; cursor:pointer; color:#8e44ad;" onclick="toggleMode()" id="toggleDiv">إنشاء حساب جديد</div>
                <hr>
                <button class="social-btn guest" onclick="guestLogin()">👤 الدخول كضيف (تجربة مجانية)</button>
            </div>
        </div>
    </div>
    
    <script>
        let isLogin = true;
        function toggleMode() {
            isLogin = !isLogin;
            document.getElementById('authTitle').innerText = isLogin ? 'تسجيل الدخول' : 'إنشاء حساب جديد';
            document.getElementById('submitBtn').innerText = isLogin ? 'دخول' : 'تسجيل';
            document.getElementById('toggleDiv').innerText = isLogin ? 'إنشاء حساب جديد' : 'لدي حساب بالفعل';
        }
        async function executeAuth(action, username, password) {
            let err = document.getElementById('errorMsg'); err.innerText = "جاري التحقق...";
            try {
                let res = await fetch("/auth", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ action: action, username: username, password: password }) });
                let data = await res.json();
                if(data.success) window.location.href = "/?login=success"; 
                else err.innerText = data.error;
            } catch(e) { err.innerText = "خطأ في الاتصال."; }
        }
        async function submitAuth() {
            let user = document.getElementById('username').value, pass = document.getElementById('password').value;
            if(!user || !pass) return document.getElementById('errorMsg').innerText = "املأ الحقول";
            executeAuth(isLogin ? 'login' : 'register', user, pass);
        }
        async function guestLogin() { executeAuth('guest', '', ''); }
    </script>
</body>
</html>
"""

# ==========================================
# 2. الواجهة التفاعلية (MAIN_PAGE) المكتملة والنظيفة
# ==========================================
MAIN_PAGE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Academy - المدرس الذكي</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --primary: #3498db; --secondary: #2c3e50; --accent: #8e44ad; --danger: #e74c3c; --success: #2ecc71; --bg: #f5f7fa; --user-bg: #d5f5e3; --ai-bg: #e1f5fe; --chat-color: #2c3e50; --chat-size: 16px; }
        body { font-family: 'Segoe UI', Tahoma, sans-serif; text-align: center; margin: 0; padding: 20px 20px 80px 20px; background: linear-gradient(135deg, var(--bg) 0%, #c3cfe2 100%); min-height: 100vh; overflow-x: hidden;}
        
        .toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%) translateY(-100px); background: var(--success); color: white; padding: 12px 25px; border-radius: 30px; box-shadow: 0 10px 20px rgba(0,0,0,0.2); font-weight: bold; z-index: 4000; transition: 0.5s; }
        .toast.show { transform: translateX(-50%) translateY(0); }
        
        .hamburger-btn { position: fixed; top: 20px; right: 20px; z-index: 1002; background: white; padding: 10px 18px; border-radius: 12px; border: 1px solid #ccc; font-weight: bold; cursor: pointer;}
        .drawer { position: fixed; top: 0; right: -320px; width: 280px; height: 100%; background: rgba(255,255,255,0.95); backdrop-filter: blur(15px); box-shadow: -5px 0 25px rgba(0,0,0,0.1); transition: 0.4s; z-index: 1001; padding-top: 80px; display: flex; flex-direction: column; gap: 12px; padding-left: 20px; padding-right: 20px; overflow-y: auto;}
        .drawer.open { right: 0; }
        .drawer-btn { border-radius: 15px; padding: 14px; font-weight: bold; cursor: pointer; display: flex; align-items: center; gap: 12px; border: 1px solid #eee; background: #fdfdfd;}
        
        .top-bar { display: flex; justify-content: center; align-items: center; width: 90%; max-width: 800px; margin: 0 auto 15px auto; gap: 15px; flex-wrap: wrap; }
        select { padding: 10px 15px; border-radius: 12px; border: 2px solid #ccc; outline: none; }
        
        #liveIndicator { display: none; color: var(--danger); font-weight: bold; margin-top: 10px; animation: blink 1.5s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        
        .input-container { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 20px;}
        input[type="text"] { padding: 16px; border-radius: 30px; border: none; width: 65%; max-width: 600px; outline: none; box-shadow: 0 5px 15px rgba(0,0,0,0.05); }
        .circle-btn { border-radius: 50%; width: 55px; height: 55px; font-size: 24px; border: none; cursor: pointer; color: white; background: #ff4b2b;}
        .send-btn { padding: 14px 30px; border-radius: 30px; border: none; color: white; cursor: pointer; font-weight: bold; background: #3498db;}
        
        #audioControls { display: none; justify-content: center; gap: 15px; margin-top: 15px; background: white; padding: 12px; border-radius: 30px; width: fit-content; margin: 15px auto;}
        
        #chatBox { width: 95%; max-width: 900px; margin: 20px auto; background: white; padding: 25px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); height: 55vh; max-height: 600px; overflow-y: auto; display: flex; flex-direction: column; gap: 18px; border-top: 6px solid var(--primary); scroll-behavior: smooth; }
        .chat-bubble { max-width: 85%; padding: 18px 22px; border-radius: 20px; font-size: var(--chat-size); color: var(--chat-color); line-height: 1.6; word-wrap: break-word;}
        .user-bubble { background: var(--user-bg); align-self: flex-start; text-align: left; direction: ltr;}
        .ai-bubble { background: var(--ai-bg); align-self: flex-end; text-align: right;}
        .english-text { font-size: calc(var(--chat-size) + 4px); font-weight: bold; direction: ltr; text-align: left; margin-bottom: 10px; line-height: 1.5; word-wrap: break-word;}
        
        /* التزامن التتابعي */
        .word { opacity: 0; transition: 0.15s; border-radius: 4px; padding: 2px 0;}
        .word.active { opacity: 1; background-color: rgba(52, 152, 219, 0.2); }
        .word.spoken { opacity: 1; background-color: transparent; }
        
        .arabic-translation { border-top: 1px dashed rgba(0,0,0,0.15); padding-top: 10px; opacity: 0.9;}
        .structured-data { font-size: calc(var(--chat-size) - 2px); background-color: rgba(255,255,255,0.6); padding: 12px; border-radius: 12px; margin-top: 12px; text-align: left; direction: ltr; border-left: 5px solid rgba(0,0,0,0.2);}
        
        .modal { display: none; position: fixed; z-index: 2000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); backdrop-filter: blur(5px); }
        .modal-content { background: white; margin: 5vh auto; padding: 35px; border-radius: 25px; width: 85%; max-width: 750px; max-height: 85vh; overflow-y: auto; text-align: right;}
        .close-btn { color: #aaa; float: left; font-size: 32px; font-weight: bold; cursor: pointer;}
        
        #overlay { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.3); z-index: 1000;}
        #overlay.active { display: block; }
        #classroomBanner { display: none; background: #e74c3c; color: white; padding: 10px; font-weight: bold; border-radius: 10px; margin-bottom: 15px;}
        #stateBanner { display: none; background: #f39c12; color: white; padding: 10px; font-weight: bold; border-radius: 10px; margin-bottom: 15px; cursor: pointer;}
        
        .progress-container { width: 100%; max-width: 900px; margin: 0 auto 10px; background: #ddd; border-radius: 10px; height: 10px; overflow: hidden; }
        .progress-bar { height: 100%; background: var(--success); width: 0%; transition: 0.5s; }
    </style>
</head>
<body>
    <div id="loginToast" class="toast">✅ تم الدخول بنجاح! يتم الآن تحضير الأكاديمية...</div>
    
    <button class="hamburger-btn" onclick="toggleDrawer()"><span>☰</span> الخيارات</button>
    <div id="overlay" onclick="toggleDrawer()"></div>
    
    <div id="sideDrawer" class="drawer">
        <h3>الخدمات الأكاديمية</h3>
        <button class="drawer-btn" onclick="sendMsg('Start the next syllabus lesson', true); toggleDrawer();" style="background:#8e44ad; color:white;">📖 متابعة المسار التعليمي</button>
        <button class="drawer-btn" onclick="toggleClassroomMode()">🏫 الفصل الجماعي</button>
        <button class="drawer-btn" onclick="openModal('parentModal')">👨‍👩‍👧 لوحة الآباء</button>
        <button class="drawer-btn" onclick="openModal('academicModal')">🎓 المناهج والشهادات</button>
        <button class="drawer-btn" onclick="openModal('topicsModal')">🗂️ المواضيع الحرة</button>
        <button class="drawer-btn" onclick="openModal('statsModal')">📊 الإحصاءات</button>
        <button class="drawer-btn" onclick="openModal('settingsModal')">🎨 المظهر</button>
        <button class="drawer-btn" onclick="window.location.href='/logout'" style="color:red;">🚪 خروج</button>
    </div>
    
    <div id="gdprModal" class="modal">
        <div class="modal-content" style="border-right: 5px solid #2ecc71;">
            <h2 style="color: #2c3e50;">🔒 سياسة الخصوصية الأكاديمية</h2>
            <p>بموجب المعايير الأكاديمية، نقوم بمعالجة بياناتك الصوتية والنصية لتقديم التقييمات اللغوية فقط، ولا يتم تخزين الملفات الصوتية بشكل دائم.</p>
            <button onclick="acceptGDPR()" style="background:#2ecc71; color:white; width:100%; padding:15px; border:none; border-radius:10px; font-weight:bold; cursor:pointer;">أوافق، ابدأ التعلم</button>
        </div>
    </div>

    <div id="parentModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('parentModal')">&times;</span>
            <h2 style="color: #1e8449;">👨‍👩‍👧 لوحة الآباء</h2>
            <div id="parentAuthArea">
                <input type="password" id="parentPinInput" placeholder="PIN (الافتراضي 0000)" style="padding:10px; width:90%;">
                <button onclick="verifyParent()" style="padding:10px; margin-top:10px; width:100%;">استخراج التقرير الذكي</button>
                <div id="parentAuthError" style="color:red; margin-top:10px;"></div>
            </div>
            <div id="parentReportArea" style="display:none;">
                <div style="background:#fdfefe; padding:20px; border:1px solid #e5e8e8; border-radius:10px;">
                    <h3>📝 التقييم الشامل (CEFR)</h3>
                    <div id="aiParentSummary">⏳ جاري التحليل...</div>
                </div>
            </div>
        </div>
    </div>

    <div id="academicModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('academicModal')">&times;</span>
            <h2>🎓 الخطة الأكاديمية</h2>
            <ul>
                <li><button onclick="sendMsg('Give me a comprehensive English placement test.', true); closeModal('academicModal');">بدء اختبار تحديد المستوى</button></li>
                <li>المستوى A1: 10 دروس</li>
                <li>المستوى A2: 10 دروس</li>
                <li>المستوى B1: 10 دروس</li>
            </ul>
        </div>
    </div>
    
    <div id="statsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('statsModal')">&times;</span>
            <h2>📊 إحصاءاتك</h2>
            <p>إجمالي الرسائل: <span id="statTotal">0</span></p>
            <canvas id="usageChart" style="max-height: 300px;"></canvas>
        </div>
    </div>

    <div id="topicsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('topicsModal')">&times;</span>
            <h2>اختر موضوعاً للدردشة الحرة 🎯</h2>
            <div id="topicsList" style="display: flex; gap: 10px; flex-wrap: wrap;"></div>
        </div>
    </div>

    <div id="settingsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('settingsModal')">&times;</span>
            <h2>🎨 إعدادات المظهر</h2>
            <button onclick="closeModal('settingsModal')">إغلاق</button>
        </div>
    </div>

    <div style="max-width: 900px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center;">
        <h2>Smart Academy 🎓 <span style="font-size:12px; color:grey;">V1.3.1</span></h2>
        <div style="font-weight: bold; color: #8e44ad;">مرحباً {{ username }} | XP: <span id="xpDisplay">0</span></div>
    </div>
    
    <div class="progress-container"><div id="mainProgress" class="progress-bar"></div></div>
    
    <div id="classroomBanner">🏫 أنت الآن داخل الفصل الافتراضي الجماعي.</div>
    <div id="stateBanner" onclick="sendMsg('Exit test', true)">⚙️ وضع خاص (اضغط للخروج)</div>
    
    <div class="top-bar">
        <select id="mode"><option value="adult">الكبار</option><option value="child">الأطفال</option></select>
        <select id="micLang"><option value="en-US">الميكروفون: إنجليزي</option><option value="ar-SA">عربي</option></select>
    </div>
    
    <div id="liveIndicator">🔴 يتم الاستماع...</div>
    
    <div class="input-container">
        <button id="micBtn" class="circle-btn" onclick="toggleMic()">🎤</button>
        <input type="text" id="userMsg" placeholder="اكتب رسالتك...">
        <button class="send-btn" onclick="sendMsg()">إرسال</button>
    </div>
    
    <div id="audioControls">
        <button class="circle-btn control-btn" onclick="skipAudio(-5)">⏪</button>
        <button id="pauseBtn" class="circle-btn control-btn" onclick="togglePauseAudio()">⏸️</button>
        <button class="circle-btn control-btn" onclick="skipAudio(5)">⏩</button>
    </div>
    
    <div id="chatBox"></div>
    <audio id="audioPlayer"></audio>
    
    <script>
        let isRecording = false, recognition, isLiveMode = false, silenceTimer, final_transcript = '';
        let chatHistory = [], wordsElements = [], isTeacherSpeaking = false, userName = "{{ username }}";
        let isClassroomMode = false, lastMessageCount = null, chartInstance = null;

        // GDPR Logic
        async function checkGDPR() {
            let res = await fetch("/check_gdpr");
            let data = await res.json();
            if(!data.consented) {
                document.getElementById('gdprModal').style.display = "block";
                document.getElementById('micBtn').disabled = true;
            } else {
                loadPersonalChats();
            }
        }
        async function acceptGDPR() {
            await fetch("/accept_gdpr", {method: "POST"});
            document.getElementById('gdprModal').style.display = "none";
            document.getElementById('micBtn').disabled = false;
            loadPersonalChats();
        }

        window.onload = function() {
            if (window.location.search.includes("login=success")) { let t = document.getElementById("loginToast"); t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 4000); }
            checkGDPR();
            
            // Populate Topics
            let topics = ["Food", "Travel", "Sports", "Technology", "Jobs"];
            let tList = document.getElementById("topicsList");
            topics.forEach(topic => {
                let b = document.createElement("button"); b.innerText = topic; b.style.padding="10px"; b.style.cursor="pointer";
                b.onclick = () => { sendMsg("Let's deeply discuss this topic: " + topic, true); closeModal('topicsModal'); };
                tList.appendChild(b);
            });
        };

        // Parent Logic
        async function verifyParent() {
            let pin = document.getElementById('parentPinInput').value;
            let err = document.getElementById('parentAuthError'); err.innerText = "جاري التحقق...";
            try {
                let res = await fetch("/parent_dashboard", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ pin: pin, action: 'verify' }) });
                let data = await res.json();
                if(data.success) {
                    document.getElementById('parentAuthArea').style.display = "none";
                    document.getElementById('parentReportArea').style.display = "block";
                    document.getElementById('aiParentSummary').innerText = "جاري الاستخراج...";
                    let rRes = await fetch("/parent_dashboard", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ pin: pin, action: 'get_report' }) });
                    let rData = await rRes.json();
                    document.getElementById('aiParentSummary').innerHTML = rData.report.replace(/\\n/g, '<br>');
                } else err.innerText = "رمز خاطئ.";
            } catch(e) { err.innerText = "خطأ اتصال."; }
        }

        // Chat Logic & Karaoke
        function appendBubble(text, isUser, data=null, senderName=null) { 
            let box = document.getElementById("chatBox"), container = document.createElement("div"); 
            container.className = isUser ? "chat-bubble user-bubble" : "chat-bubble ai-bubble"; 
            if (isClassroomMode && senderName) { let nLabel = document.createElement("span"); nLabel.className = "sender-name"; nLabel.innerText = senderName; container.appendChild(nLabel); }
            
            if(isUser) { 
                let t = document.createElement("span"); t.innerText = text; container.appendChild(t); 
            } else { 
                let engDiv = document.createElement("div"); engDiv.className = "english-text"; 
                let engText = data.english || "";
                engText.split(" ").forEach(word => { 
                    let span = document.createElement("span"); span.className = "word"; span.innerText = word; 
                    engDiv.appendChild(span); engDiv.appendChild(document.createTextNode(" ")); 
                }); 
                container.appendChild(engDiv); 
                let arDiv = document.createElement("div"); arDiv.className = "arabic-translation"; arDiv.innerText = data.arabic; container.appendChild(arDiv); 
                if(data.summary) { let dDiv = document.createElement("div"); dDiv.className="structured-data"; dDiv.innerHTML = "📝 " + data.summary; container.appendChild(dDiv); }
            } 
            box.appendChild(container); setTimeout(() => box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' }), 100); 
        }

        async function loadPersonalChats() {
            let res = await fetch("/get_history"); let history = await res.json(); 
            if (history.length > 0) { 
                history.forEach(item => { 
                    if(item.role === 'user') { appendBubble(item.content, true); chatHistory.push({"role": "user", "content": item.content}); } 
                    else if(item.role === 'assistant') { appendBubble("", false, {english: item.content, arabic: item.arabic}); 
                    document.querySelectorAll(".word").forEach(w=>w.classList.add("spoken"));
                    chatHistory.push({"role": "assistant", "content": item.content}); } 
                }); 
            } else sendMsg("Welcome the student warmly.", true); 
        }

        async function sendMsg(overrideMsg = null, isHidden = false) { 
            let inputField = document.getElementById("userMsg"), msg = overrideMsg || inputField.value; 
            if(!msg.trim()) return; 
            
            if(!isHidden){ 
                appendBubble(msg, true); chatHistory.push({"role": "user", "content": msg}); 
            } else chatHistory.push({"role": "system", "content": msg}); 
            
            inputField.value = ""; 
            let loadDiv = document.createElement("div"); loadDiv.className = "chat-bubble ai-bubble"; loadDiv.id = "loadingBubble"; loadDiv.innerText = "⏳..."; document.getElementById("chatBox").appendChild(loadDiv);
            
            try { 
                let res = await fetch("/chat", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ message: msg, mode: document.getElementById("mode").value }) }); 
                let data = await res.json(); document.getElementById("loadingBubble").remove(); 
                
                let sBanner = document.getElementById("stateBanner");
                if(data.workflow_state !== 'FREE_CHAT') { 
                    sBanner.style.display = "block";
                    sBanner.innerText = data.workflow_state === 'LEVEL_EXAM' ? "🏛️ امتحان مستوى CEFR (للتخطي اكتب Exit)" : (data.workflow_state === 'LESSON_QUIZ' ? "📝 اختبار قصير" : "🎓 درس منهجي");
                    sBanner.style.background = data.workflow_state === 'LEVEL_EXAM' ? "#e74c3c" : "#8e44ad";
                } else sBanner.style.display = "none";

                document.getElementById("mainProgress").style.width = ((data.current_lesson / 30) * 100) + "%";
                document.getElementById("xpDisplay").innerText = data.xp_points || 0;

                chatHistory.push({"role": "assistant", "content": data.english}); 
                appendBubble("", false, data); 
                
                if(data.audio) { 
                    let ap = document.getElementById("audioPlayer"); ap.src = "data:audio/mp3;base64," + data.audio; 
                    document.getElementById("audioControls").style.display = "flex"; 
                    isTeacherSpeaking = true; if(isRecording) recognition.stop(); 
                    ap.play().catch(e => document.querySelectorAll(".word").forEach(w => w.classList.add("spoken"))); 
                } 
                wordsElements = document.querySelectorAll("#chatBox > div:last-child .english-text .word");
            } catch (e) { document.getElementById("loadingBubble")?.remove(); } 
        }

        let audioPlayer = document.getElementById("audioPlayer"); 
        audioPlayer.ontimeupdate = function() { 
            if (!wordsElements.length || isNaN(audioPlayer.duration)) return; 
            let activeIndex = Math.floor((audioPlayer.currentTime / audioPlayer.duration) * wordsElements.length); 
            wordsElements.forEach((span, i) => { 
                if (i === activeIndex) { span.classList.add("active"); span.classList.remove("spoken"); } 
                else if (i < activeIndex) { span.classList.remove("active"); span.classList.add("spoken"); } 
                else { span.classList.remove("active", "spoken"); } 
            }); 
        }; 
        audioPlayer.onended = function() { isTeacherSpeaking = false; wordsElements.forEach(s => { s.classList.remove("active"); s.classList.add("spoken");}); };
        function skipAudio(s) { let a = document.getElementById("audioPlayer"); if (a.src && !a.paused) a.currentTime += s; }
        function togglePauseAudio() { let a = document.getElementById("audioPlayer"); if (a.paused) a.play(); else a.pause(); }

        // Speech Recognition (المقاطعة الفورية)
        if (window.SpeechRecognition || window.webkitSpeechRecognition) {
            recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
            recognition.continuous = true; recognition.interimResults = true;
            recognition.onstart = () => { isRecording = true; document.getElementById("micBtn").classList.add("recording"); };
            recognition.onresult = (event) => { 
                if(isTeacherSpeaking) return;
                let interim = ''; 
                for (let i = event.resultIndex; i < event.results.length; ++i) { 
                    if (event.results[i].isFinal) final_transcript += event.results[i][0].transcript + " "; else interim += event.results[i][0].transcript; 
                } 
                let currentSpeech = (final_transcript + interim).trim(); 
                if (currentSpeech.length > 0) { 
                    document.getElementById("userMsg").value = currentSpeech; 
                    clearTimeout(silenceTimer); 
                    silenceTimer = setTimeout(() => { if (isLiveMode && currentSpeech.length > 0) sendMsg(); }, 2500); 
                } 
            };
            recognition.onend = () => { isRecording = false; document.getElementById("micBtn").classList.remove("recording"); if(isLiveMode && !isTeacherSpeaking) {try{recognition.start();}catch(e){}}};
        }
        
        async function toggleMic() { 
            if (!recognition) return alert("المتصفح لا يدعم الميكروفون."); 
            let ap = document.getElementById("audioPlayer"); 
            if (isTeacherSpeaking && !ap.paused) { 
                ap.pause(); isTeacherSpeaking = false; wordsElements.forEach(s => s.classList.add("spoken")); 
                isLiveMode = true; final_transcript = ''; document.getElementById("liveIndicator").style.display = "block"; recognition.lang = document.getElementById("micLang").value; try { recognition.start(); } catch(e) {} return; 
            } 
            if (isLiveMode || isRecording) { 
                isLiveMode = false; if(isRecording) recognition.stop(); document.getElementById("liveIndicator").style.display = "none"; 
            } else { 
                try { window.localStream = await navigator.mediaDevices.getUserMedia({audio: true}); } catch (e) {} 
                isLiveMode = true; final_transcript = ''; document.getElementById("liveIndicator").style.display = "block"; recognition.lang = document.getElementById("micLang").value; try { recognition.start(); } catch(e) {} 
            } 
        }
        document.getElementById("userMsg").addEventListener("keypress", function(e) { if (e.key === "Enter") { e.preventDefault(); sendMsg(); } });
    </script>
</body>
</html>
"""

# ==========================================
# 3. مسارات واجهة برمجة التطبيقات (API Routes)
# ==========================================

@app.route("/")
def home():
    if 'user_id' in session: return render_template_string(MAIN_PAGE, username=session['username'])
    else: return render_template_string(LOGIN_PAGE, google_id=GOOGLE_CLIENT_ID, fb_id=FACEBOOK_APP_ID)

@app.route("/check_gdpr", methods=["GET"])
def check_gdpr():
    if 'user_id' not in session: return jsonify({"consented": False})
    with sqlite3.connect('academy.db') as conn:
        row = conn.execute("SELECT gdpr_consent FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        return jsonify({"consented": bool(row and row[0] == 1)})

@app.route("/accept_gdpr", methods=["POST"])
def accept_gdpr():
    if 'user_id' in session:
        with sqlite3.connect('academy.db') as conn:
            conn.execute("UPDATE users SET gdpr_consent = 1 WHERE id = ?", (session['user_id'],))
            conn.commit()
            log_activity(session['user_id'], "CONSENT_GIVEN", "GDPR accepted")
        return jsonify({"success": True})
    return jsonify({"success": False})

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
            if cursor.fetchone(): return jsonify({"success": False, "error": "الاسم مستخدم."})
            hashed_pw = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, password_hash, auth_provider) VALUES (?, ?, ?)", (username, hashed_pw, 'local')); conn.commit()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,)); session['user_id'] = cursor.fetchone()[0]; session['username'] = username
            return jsonify({"success": True})
        elif action == 'login':
            cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)); user = cursor.fetchone()
            if user and check_password_hash(user[1], password): session['user_id'] = user[0]; session['username'] = username; return jsonify({"success": True})
            else: return jsonify({"success": False, "error": "بيانات خاطئة."})

@app.route("/logout")
def logout(): session.clear(); return redirect("/")

@app.route("/get_history", methods=["GET"])
def get_history():
    if 'user_id' not in session: return jsonify([])
    with sqlite3.connect('academy.db') as conn:
        return jsonify([{"role": r[0], "content": r[1], "arabic": r[2]} for r in conn.execute("SELECT role, content, arabic FROM academy_chats WHERE user_id = ? ORDER BY id ASC", (session['user_id'],)).fetchall()])

@app.route("/parent_dashboard", methods=["POST"])
def parent_dashboard():
    if 'user_id' not in session: return jsonify({"success": False})
    user_id = session['user_id']
    data = request.json
    action = data.get("action")
    pin = data.get("pin", "")

    try:
        with sqlite3.connect('academy.db') as conn:
            row = conn.execute("SELECT parent_pin, fluency_score, grammar_score, vocab_score FROM users WHERE id = ?", (user_id,)).fetchone()
            real_pin = row[0] if row and row[0] else "0000"

            if pin != real_pin: return jsonify({"success": False})

            if action == 'verify': return jsonify({"success": True})
            elif action == 'get_report':
                api_key = os.environ.get("GROQ_API_KEY")
                if not api_key: return jsonify({"success": True, "report": "API Key Missing."})
                client = Groq(api_key=api_key)
                user_msgs = [r[0] for r in conn.execute("SELECT content FROM academy_chats WHERE user_id = ? AND role = 'user' ORDER BY id DESC LIMIT 10", (user_id,)).fetchall()]
                prompt = f"You are an educational assessor. Recent messages: {user_msgs}. CEFR Scores (Fluency: {row[1]}, Grammar: {row[2]}, Vocab: {row[3]}). Provide a short summary for their parent IN ARABIC."
                completion = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "user", "content": prompt}])
                return jsonify({"success": True, "report": completion.choices[0].message.content})
    except Exception as e: return jsonify({"success": False})

async def generate_audio(text, voice):
    clean_text = re.sub(r'[*#_~`]', '', text) 
    communicate = edge_tts.Communicate(clean_text, voice)
    await communicate.save("response.mp3")
    with open("response.mp3", "rb") as f: return base64.b64encode(f.read()).decode('utf-8')

@app.route("/chat", methods=["POST"])
def chat():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"})
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        client = Groq(api_key=api_key)
        user_msg = request.json.get("message", "")
        user_id = session['user_id']

        with sqlite3.connect('academy.db') as conn:
            history = [{"role": r[0], "content": r[1]} for r in conn.execute("SELECT role, content FROM academy_chats WHERE user_id = ? ORDER BY id DESC LIMIT 8", (user_id,)).fetchall()[::-1]]

        sys_msg, current_state, current_lesson_id, xp = WorkflowManager.process_state(user_id, user_msg, 'adult', "")

        messages = [{"role": "system", "content": sys_msg}] + history + [{"role": "user", "content": user_msg}]
        completion = client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages, response_format={"type": "json_object"})
        
        parsed = json.loads(completion.choices[0].message.content)
        eng = parsed.get("english", ""); ar = parsed.get("arabic", "")
        scores = parsed.get("scores", {})

        with sqlite3.connect('academy.db') as conn:
            if current_state == 'LEVEL_EXAM' and isinstance(scores, dict):
                conn.execute("UPDATE users SET fluency_score = fluency_score + ?, grammar_score = grammar_score + ?, vocab_score = vocab_score + ? WHERE id = ?", (scores.get("fluency", 0), scores.get("grammar", 0), scores.get("vocab", 0), user_id))
            
            if not user_msg.startswith("Welcome") and not user_msg.startswith("Start"):
                conn.execute("INSERT INTO academy_chats (user_id, role, content, arabic) VALUES (?, ?, ?, ?)", (user_id, "user", user_msg, ""))
            conn.execute("INSERT INTO academy_chats (user_id, role, content, arabic) VALUES (?, ?, ?, ?)", (user_id, "assistant", eng, ar))
            conn.commit()
            
        voice_model = "en-GB-RyanNeural" if current_state in ['LEVEL_EXAM', 'LESSON_MODE', 'LESSON_QUIZ'] else "en-US-ChristopherNeural" 
        audio = asyncio.run(generate_audio(eng, voice_model))
        
        return jsonify({ "english": eng, "arabic": ar, "summary": parsed.get("summary", ""), "audio": audio, "workflow_state": current_state, "current_lesson": current_lesson_id, "xp_points": xp })
    except Exception as e: return jsonify({"error": "Error: " + str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
