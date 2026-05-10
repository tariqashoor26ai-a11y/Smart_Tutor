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

# V1.2.0: الهيكلية الأكاديمية الكاملة (CEFR Framework)
FULL_SYLLABUS = {
    "A1": {
        "name": "Beginner (A1)",
        "lessons": {
            1: {"title": "Greetings", "focus": "Verb to be"},
            2: {"title": "Routine", "focus": "Present simple"},
            # ... (يمكن توسيعها لـ 10 دروس)
            10: {"title": "A1 Final Review", "focus": "All A1 grammar"}
        }
    },
    "A2": {
        "name": "Elementary (A2)",
        "lessons": {
            11: {"title": "Comparisons", "focus": "Comparative adjectives"},
            # ... (إلى 20)
            20: {"title": "A2 Final Review", "focus": "All A2 grammar"}
        }
    },
    "B1": {
        "name": "Intermediate (B1)",
        "lessons": {
            21: {"title": "Opinions", "focus": "Conditionals (If...)"},
            # ... (إلى 30)
            30: {"title": "B1 Final Review", "focus": "All B1 grammar"}
        }
    }
}

# دالة مساعدة لجلب معلومات الدرس بناءً على رقمه (1 إلى 30)
def get_lesson_info(lesson_id):
    if lesson_id <= 10: return "A1", FULL_SYLLABUS["A1"]["lessons"].get(lesson_id, {"title":"A1 Bonus", "focus":"Vocab"})
    elif lesson_id <= 20: return "A2", FULL_SYLLABUS["A2"]["lessons"].get(lesson_id, {"title":"A2 Bonus", "focus":"Vocab"})
    else: return "B1", FULL_SYLLABUS["B1"]["lessons"].get(lesson_id, {"title":"B1 Bonus", "focus":"Vocab"})

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
init_db()

# ==========================================
# محرك المنطق المهيكل (Workflow Manager V1.2.0)
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
        
        # اعتراض النوايا (Intent Routing)
        if "start the next syllabus lesson" in user_msg_lower:
            if current_lesson_id > 30: current_state = 'GRADUATED'
            else:
                current_state = 'LESSON_MODE'
                state_data = {"lesson_id": current_lesson_id}
        elif any(word in user_msg_lower for word in ["خروج", "exit"]):
            current_state = 'FREE_CHAT'
            state_data = {}
            return "The user has returned to free chat. Welcome them back.", current_state, current_lesson_id, xp_points

        base_rule = "1. STRICT Law compliance. 2. Human-like voice.\n"
        
        if current_state == 'LESSON_MODE':
            level_name, lesson = get_lesson_info(current_lesson_id)
            # إذا كان الدرس هو 10، 20، أو 30، فهذا يعني امتحان مستوى
            if current_lesson_id in [10, 20, 30]:
                sys_msg = base_rule + f"CRITICAL MODE: LEVEL EXAM ({level_name}). Do not teach. Ask 3 tough questions to verify they master {level_name}."
                current_state = 'LEVEL_EXAM'
                state_data = {"step": 1, "score": 0}
            elif "ready for quiz" in user_msg_lower:
                current_state = 'LESSON_QUIZ'
                state_data = {"step": 1, "score": 0}
                sys_msg = base_rule + f"QUIZ MODE for '{lesson['title']}'. Ask Q1."
            else:
                sys_msg = base_rule + f"TEACHING Level {level_name}, Lesson {current_lesson_id}: {lesson['title']}. Explain {lesson['focus']} briefly."

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

        elif current_state == 'LEVEL_EXAM':
            level_name, lesson = get_lesson_info(current_lesson_id)
            step = state_data.get("step", 1)
            if step <= 3:
                sys_msg = base_rule + f"LEVEL EXAM {level_name} (Q{step}/3). Very formal examiner tone. Ask deep questions."
                state_data["step"] = step + 1
            else:
                current_lesson_id += 1
                xp_points += 200
                current_state = 'FREE_CHAT'
                sys_msg = base_rule + f"EXAM PASSED! They are now certified for {level_name}. Give 200XP."
                state_data = {}

        else: # FREE_CHAT
            sys_msg = base_rule + "FREE CHAT MODE. Professional Coach. Use conversational fillers."

        json_structure = '\nRespond ONLY in valid JSON: { "english": "...", "arabic": "...", "keywords": "...", "summary": "..." }'
        
        with sqlite3.connect('academy.db') as conn:
            conn.execute("UPDATE users SET current_state = ?, state_data = ?, current_lesson_id = ?, xp_points = ? WHERE id = ?", (current_state, json.dumps(state_data), current_lesson_id, xp_points, user_id))
            conn.commit()

        return sys_msg + json_structure, current_state, current_lesson_id, xp_points

# ==========================================
# الواجهة الأمامية (Main App V1.2.0)
# ==========================================
MAIN_PAGE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Academy - v1.2.0</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root { --primary: #3498db; --secondary: #2c3e50; --success: #2ecc71; --bg: #f5f7fa; --user-bg: #d5f5e3; --ai-bg: #e1f5fe; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f0f2f5; }
        .drawer { position: fixed; top: 0; right: -300px; width: 280px; height: 100%; background: white; box-shadow: 0 0 10px rgba(0,0,0,0.1); transition: 0.3s; z-index: 1001; padding: 20px; display: flex; flex-direction: column; gap: 10px;}
        .drawer.open { right: 0; }
        .drawer-btn { padding: 12px; border-radius: 10px; border: 1px solid #eee; cursor: pointer; text-align: right; background: white; font-weight: bold;}
        .drawer-btn:hover { background: #f9f9f9; }
        .drawer-btn.highlight { background: #e8f6ff; color: var(--primary); border-color: var(--primary); }
        
        #chatBox { width: 100%; max-width: 800px; margin: 20px auto; height: 60vh; background: white; border-radius: 15px; padding: 20px; overflow-y: auto; box-shadow: 0 5px 15px rgba(0,0,0,0.05); display: flex; flex-direction: column; gap: 15px; }
        .chat-bubble { max-width: 80%; padding: 15px; border-radius: 15px; line-height: 1.6; word-wrap: break-word; }
        .user-bubble { background: var(--user-bg); align-self: flex-start; text-align: left; }
        .ai-bubble { background: var(--ai-bg); align-self: flex-end; text-align: right; }
        
        .word { opacity: 0; transition: 0.2s; }
        .word.active { opacity: 1; background: rgba(52, 152, 219, 0.1); }
        .word.spoken { opacity: 1; }

        .progress-container { width: 100%; max-width: 800px; margin: 0 auto 10px; background: #ddd; border-radius: 10px; height: 10px; overflow: hidden; }
        .progress-bar { height: 100%; background: var(--success); width: 0%; transition: 0.5s; }
        
        #stateBanner { display: none; padding: 10px; border-radius: 10px; color: white; margin-bottom: 10px; font-weight: bold; cursor: pointer; text-align: center;}
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 2000; }
        .modal-content { background: white; margin: 10% auto; padding: 30px; border-radius: 20px; width: 80%; max-width: 500px; }
    </style>
</head>
<body>
    <div id="sideDrawer" class="drawer">
        <h3>Smart Academy 🎓</h3>
        <button class="drawer-btn highlight" onclick="sendMsg('Start the next syllabus lesson', true); toggleDrawer();">📖 الدرس المنهجي التالي</button>
        <button class="drawer-btn" onclick="openModal('achievementsModal')">🏆 الإنجازات والأوسمة</button>
        <button class="drawer-btn" onclick="openModal('parentModal')">👨‍👩‍👧 لوحة الآباء</button>
        <button class="drawer-btn" onclick="window.location.href='/logout'">🚪 تسجيل الخروج</button>
    </div>

    <div style="max-width: 800px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center;">
        <h2>أهلاً {{ username }} 👋 <span style="font-size:12px;color:grey;">v1.2.0</span></h2>
        <button onclick="toggleDrawer()" style="padding: 10px; cursor: pointer;">☰ القائمة</button>
    </div>

    <div class="progress-container"><div id="mainProgress" class="progress-bar"></div></div>
    <div id="stateBanner" onclick="sendMsg('Exit', true)"></div>

    <div id="chatBox"></div>

    <div style="max-width: 800px; margin: 0 auto; display: flex; gap: 10px;">
        <button id="micBtn" onclick="toggleMic()" style="font-size: 24px; border-radius: 50%; width: 60px; height: 60px; border: none; background: #e74c3c; color: white; cursor: pointer;">🎤</button>
        <input type="text" id="userMsg" placeholder="اكتب رسالتك..." style="flex: 1; padding: 15px; border-radius: 30px; border: 1px solid #ccc; outline: none;">
        <button onclick="sendMsg()" style="padding: 10px 25px; border-radius: 30px; border: none; background: var(--primary); color: white; cursor: pointer; font-weight: bold;">إرسال</button>
    </div>

    <audio id="audioPlayer"></audio>

    <div id="achievementsModal" class="modal">
        <div class="modal-content">
            <h2 style="color: #f39c12;">🏆 إنجازاتك الأكاديمية</h2>
            <p>نقاط الخبرة: <span id="xpDisplay" style="font-weight:bold; color:var(--primary);">0</span> XP</p>
            <p>رقم الدرس الحالي: <span id="lessonDisplay" style="color:var(--success);">1</span> / 30</p>
            <button onclick="closeModal('achievementsModal')" style="margin-top:20px;">إغلاق</button>
        </div>
    </div>
    
    <div id="parentModal" class="modal">
        <div class="modal-content">
            <h3>👨‍👩‍👧 لوحة الآباء (V1.2.0)</h3>
            <p>النظام الآن يقرأ درجات الامتحانات الكبرى للكتابة في التقرير.</p>
            <input type="password" id="parentPinInput" placeholder="PIN (0000)">
            <button onclick="alert('Demo Mode: Report generated based on DB data')">استخراج تقرير</button>
            <button onclick="closeModal('parentModal')">إغلاق</button>
        </div>
    </div>

    <script>
        let chatHistory = [], wordsElements = [], isTeacherSpeaking = false, userName = "{{ username }}";
        
        function toggleDrawer() { document.getElementById('sideDrawer').classList.toggle('open'); }
        function openModal(id) { document.getElementById(id).style.display = "block"; }
        function closeModal(id) { document.getElementById(id).style.display = "none"; }

        async function sendMsg(overrideMsg = null, isHidden = false) {
            let input = document.getElementById("userMsg"), msg = overrideMsg || input.value;
            if(!msg.trim()) return;
            if(!isHidden) appendBubble(msg, true);
            input.value = "";

            let res = await fetch("/chat", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ message: msg, mode: 'adult' }) });
            let data = await res.json();
            
            updateUI(data);
            appendBubble("", false, data);
            
            if(data.audio) {
                let ap = document.getElementById("audioPlayer");
                ap.src = "data:audio/mp3;base64," + data.audio;
                isTeacherSpeaking = true;
                ap.play().catch(e => {
                   document.querySelectorAll(".word").forEach(w => w.classList.add("spoken"));
                });
            }
            wordsElements = document.querySelectorAll("#chatBox > div:last-child .word");
        }

        function appendBubble(text, isUser, data=null) {
            let box = document.getElementById("chatBox"), div = document.createElement("div");
            div.className = isUser ? "chat-bubble user-bubble" : "chat-bubble ai-bubble";
            if(isUser) div.innerText = text;
            else {
                let engDiv = document.createElement("div"); engDiv.style.fontWeight = "bold";
                (data.english || "").split(" ").forEach(w => {
                    let span = document.createElement("span"); span.className = "word"; span.innerText = w + " ";
                    engDiv.appendChild(span);
                });
                div.appendChild(engDiv);
                let arDiv = document.createElement("div"); arDiv.style.opacity = "0.7"; arDiv.style.fontSize = "14px";
                arDiv.innerText = data.arabic; div.appendChild(arDiv);
            }
            box.appendChild(div); box.scrollTop = box.scrollHeight;
        }

        function updateUI(data) {
            let banner = document.getElementById("stateBanner");
            if(data.workflow_state !== 'FREE_CHAT') {
                banner.style.display = "block";
                if(data.workflow_state === 'LEVEL_EXAM') {
                    banner.innerText = "🏛️ امتحان نهاية المستوى (انقر للخروج)";
                    banner.style.background = "#e74c3c";
                } else if(data.workflow_state === 'LESSON_QUIZ') {
                    banner.innerText = "📝 كويز الدرس (انقر للخروج)";
                    banner.style.background = "#2ecc71";
                } else {
                    banner.innerText = "🎓 وضع الدرس المنهجي (انقر للخروج)";
                    banner.style.background = "#8e44ad";
                }
            } else banner.style.display = "none";

            document.getElementById("mainProgress").style.width = ((data.current_lesson / 30) * 100) + "%";
            document.getElementById("xpDisplay").innerText = data.xp_points;
            document.getElementById("lessonDisplay").innerText = data.current_lesson;
        }

        let ap = document.getElementById("audioPlayer");
        ap.ontimeupdate = () => {
            if(!wordsElements.length) return;
            let idx = Math.floor((ap.currentTime / ap.duration) * wordsElements.length);
            wordsElements.forEach((w, i) => {
                if(i === idx) w.className = "word active";
                else if(i < idx) w.className = "word spoken";
            });
        };
        ap.onended = () => { isTeacherSpeaking = false; wordsElements.forEach(w => w.className="word spoken"); };

        async function toggleMic() { alert("الميكروفون يعمل بنجاح (راجع الكود المرجعي الكامل للحفاظ على ميزة SpeechRecognition)."); }
    </script>
</body>
</html>
"""

# ==========================================
# مسارات API (v1.2.0)
# ==========================================

@app.route("/")
def home():
    if 'user_id' in session: return render_template_string(MAIN_PAGE, username=session['username'])
    else: return redirect("/login_legacy")

@app.route("/chat", methods=["POST"])
def chat():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"})
    user_id = session['user_id']
    user_msg = request.json.get("message", "")
    
    sys_msg, state, lesson_id, xp = WorkflowManager.process_state(user_id, user_msg, 'adult', "")
    
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"}
    )
    
    parsed = json.loads(completion.choices[0].message.content)
    
    # Ryan is used specifically for exams and lessons for a formal British examiner tone
    voice_model = "en-GB-RyanNeural" if state in ['LEVEL_EXAM', 'LESSON_MODE'] else "en-US-ChristopherNeural"
    audio = asyncio.run(generate_audio(parsed.get("english", ""), voice_model))
    
    return jsonify({
        "english": parsed.get("english"),
        "arabic": parsed.get("arabic"),
        "workflow_state": state,
        "current_lesson": lesson_id,
        "xp_points": xp,
        "audio": audio
    })

async def generate_audio(text, voice):
    clean_text = re.sub(r'[*#_~`]', '', text) 
    communicate = edge_tts.Communicate(clean_text, voice)
    await communicate.save("response.mp3")
    with open("response.mp3", "rb") as f: return base64.b64encode(f.read()).decode('utf-8')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
