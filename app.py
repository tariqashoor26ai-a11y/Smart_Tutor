import os
import asyncio
import base64
import json
import re
import sqlite3
from flask import Flask, request, jsonify, render_template_string
from groq import Groq
import edge_tts

app = Flask(__name__)

# --- إعداد قاعدة البيانات ---
def init_db():
    with sqlite3.connect('academy.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS chat_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            role TEXT,
                            content TEXT,
                            arabic TEXT
                        )''')
init_db()

HTML_PAGE = """
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
        body { font-family: var(--chat-font); text-align: center; margin: 0; padding: 20px; background: linear-gradient(135deg, var(--bg) 0%, #c3cfe2 100%); min-height: 100vh; overflow-x: hidden;}
        h2 { color: var(--secondary); text-shadow: 1px 1px 2px rgba(0,0,0,0.1); margin-bottom: 5px;}
        
        @keyframes fadeSlideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes popIn { 0% { opacity: 0; transform: scale(0.9); } 100% { opacity: 1; transform: scale(1); } }
        @keyframes pulseMic { 0% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7); } 70% { box-shadow: 0 0 0 15px rgba(231, 76, 60, 0); } 100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0); } }

        .hamburger-btn { position: fixed; top: 20px; right: 20px; z-index: 1002; background: white; color: var(--secondary); padding: 10px 18px; border-radius: 12px; border: 1px solid #bdc3c7; font-size: 16px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.1); transition: all 0.3s ease; display: flex; align-items: center; gap: 8px;}
        .hamburger-btn:hover { background: #f8f9fa; transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0,0,0,0.15); color: var(--primary);}

        .drawer { position: fixed; top: 0; right: -320px; width: 280px; height: 100%; background: rgba(255,255,255,0.95); backdrop-filter: blur(15px); box-shadow: -5px 0 25px rgba(0,0,0,0.1); transition: right 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); z-index: 1001; padding-top: 80px; display: flex; flex-direction: column; gap: 12px; padding-left: 20px; padding-right: 20px; overflow-y: auto;}
        .drawer.open { right: 0; }
        
        .drawer-btn { border-radius: 15px; padding: 14px 18px; font-size: 14px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.05); transition: all 0.2s ease; display: flex; align-items: center; justify-content: flex-start; gap: 12px; border: 1px solid rgba(255,255,255,0.5); text-align: right; color: #2c3e50;}
        .drawer-btn:hover { transform: translateX(-5px); box-shadow: 0 6px 15px rgba(0,0,0,0.1);}
        .drawer-btn .icon { font-size: 18px; background: rgba(255,255,255,0.4); border-radius: 50%; padding: 6px;}

        .drawer-btn.plan { background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); }
        .drawer-btn.test { background: linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%); }
        .drawer-btn.topics { background: linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%); }
        .drawer-btn.upload { background: linear-gradient(135deg, #d4fc79 0%, #96e6a1 100%); }
        .drawer-btn.settings { background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); }
        .drawer-btn.about { background: white; border: 1px solid #e0e0e0; }

        .curriculum-info { background: rgba(255, 255, 255, 0.9); border-radius: 15px; padding: 10px; width: 80%; max-width: 700px; margin: 10px auto; font-size: 13px; color: var(--secondary); box-shadow: var(--soft-shadow); border: 1px solid rgba(255,255,255,0.5);}
        .curriculum-info a { color: var(--primary); text-decoration: none; font-weight: bold; margin: 0 10px;}

        .top-bar { display: flex; justify-content: center; align-items: center; width: 90%; max-width: 800px; margin: 0 auto 15px auto; gap: 15px; flex-wrap: wrap; }
        select { padding: 10px 15px; font-size: 14px; border-radius: 12px; border: 2px solid rgba(255,255,255,0.4); outline: none; cursor: pointer; background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); color: #2c3e50; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.05); text-align: center;}
        
        .start-btn { background: linear-gradient(135deg, var(--accent) 0%, #9b59b6 100%); font-weight: bold; padding: 10px 25px; font-size: 15px; border-radius: 12px; border: none; color: white; cursor: pointer; box-shadow: 0 5px 15px rgba(142, 68, 173, 0.3);}
        
        #liveIndicator { display: none; color: var(--danger); font-weight: bold; font-size: 14px; margin-top: 10px; animation: blink 1.5s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

        .input-container { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 20px;}
        input[type="text"] { padding: 16px 25px; font-size: 16px; border-radius: 30px; border: none; width: 65%; max-width: 600px; outline: none; background: rgba(255,255,255,0.95); box-shadow: var(--soft-shadow); }
        input[type="text"]:focus { background: white; box-shadow: 0 0 15px rgba(52, 152, 219, 0.2);}
        
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
        .modal-content { background: rgba(255,255,255,0.98); margin: 8vh auto; padding: 35px; border-radius: 25px; width: 85%; max-width: 750px; max-height: 80vh; overflow-y: auto; text-align: right; box-shadow: 0 25px 50px rgba(0,0,0,0.3); animation: popIn 0.4s ease-out;}
        .close-btn { color: #aaa; float: left; font-size: 32px; font-weight: bold; cursor: pointer; transition: color 0.2s; background: #f0f0f0; border-radius: 50%; width: 40px; height: 40px; display: flex; justify-content: center; align-items: center;}
        .close-btn:hover { color: white; background: var(--danger); }
        
        .topics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; margin-top: 15px; }
        .topic-item { background: #f8f9fa; padding: 12px; border-radius: 12px; font-size: 13px; text-align: center; cursor: pointer; transition: all 0.2s; border: 1px solid #dcdde1; font-weight: bold; color: #34495e;}
        .topic-item:hover { background: var(--primary); color: white; transform: translateY(-4px);}
        .topic-category { grid-column: 1 / -1; font-size: 16px; font-weight: bold; color: var(--accent); margin-top: 15px; border-bottom: 2px dashed #bdc3c7; padding-bottom: 5px; }

        .settings-group { margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between; background: #f9f9f9; padding: 12px 15px; border-radius: 12px; border: 1px solid #eee; box-shadow: 0 2px 5px rgba(0,0,0,0.02);}
        .settings-group label { font-weight: bold; color: var(--secondary); font-size: 15px;}
        .settings-group input[type="color"] { border: none; width: 45px; height: 45px; border-radius: 8px; cursor: pointer; background: transparent;}
        .settings-group select, .settings-group input[type="range"] { width: 50%; padding: 10px; border-radius: 8px; border: 1px solid #ccc; outline: none;}

        #audioPlayer { display: none; }
        #curriculumStatus { color: var(--success); font-size: 13px; font-weight: bold; margin-top: 5px; text-align: center;}
        #overlay { display: none; position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.3); z-index: 1000; backdrop-filter: blur(2px);}
        #overlay.active { display: block; }
    </style>
</head>
<body>

    <button class="hamburger-btn" onclick="toggleDrawer()">
        <span style="font-size: 20px;">☰</span> الخيارات
    </button>
    <div id="overlay" onclick="toggleDrawer()"></div>

    <div id="sideDrawer" class="drawer">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px; margin-top: 0;">الخدمات الأكاديمية</h3>
        <button class="drawer-btn plan" onclick="requestFeature('study_plan')"><span class="icon">📅</span><span>الخطة الدراسية</span></button>
        <button class="drawer-btn test" onclick="requestFeature('test')"><span class="icon">📝</span><span>التقييم والتدريب</span></button>
        <button class="drawer-btn topics" onclick="openModal('topicsModal')"><span class="icon">🗂️</span><span>المواضيع والقصص</span></button>
        <button class="drawer-btn upload" onclick="triggerUpload()"><span class="icon">📂</span><span>رفع منهج PDF</span></button>
        <button class="drawer-btn settings" onclick="openModal('settingsModal')"><span class="icon">🎨</span><span>تخصيص المظهر</span></button>
        <button class="drawer-btn about" onclick="openModal('aboutModal')"><span class="icon">🏫</span><span>نبذة عنا</span></button>
    </div>
    
    <input type="file" id="fileUpload" accept=".txt,.pdf,.doc,.docx" style="display: none;" onchange="handleFileUpload(event)">

    <div id="topicsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('topicsModal')">&times;</span>
            <h2 style="text-align:center; color: var(--accent);">اختر موضوعاً للمناقشة 🎯</h2>
            <div class="topics-grid" id="topicsList"></div>
        </div>
    </div>

    <div id="settingsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('settingsModal')">&times;</span>
            <h2 style="text-align:center; color: var(--primary);">🎨 تخصيص مظهر الأكاديمية</h2>
            <div class="settings-group"><label>صندوق المتدرب:</label><input type="color" id="userBgColor" value="#d5f5e3" onchange="applySettings()"></div>
            <div class="settings-group"><label>صندوق المدرب:</label><input type="color" id="aiBgColor" value="#e1f5fe" onchange="applySettings()"></div>
            <div class="settings-group"><label>لون النصوص:</label><input type="color" id="fontColor" value="#2c3e50" onchange="applySettings()"></div>
            <div class="settings-group"><label>حجم الخط:</label><input type="range" id="fontSize" min="12" max="24" value="16" oninput="applySettings()"><span id="fontSizeVal">16px</span></div>
            <div class="settings-group">
                <label>نوع الخط:</label>
                <select id="fontFamily" onchange="applySettings()">
                    <option value="'Segoe UI', Tahoma, Geneva, Verdana, sans-serif">Segoe UI (عصري)</option>
                    <option value="Arial, Helvetica, sans-serif">Arial (رسمي)</option>
                    <option value="'Comic Sans MS', cursive, sans-serif">Comic Sans (مرح)</option>
                </select>
            </div>
            <button class="send-btn" style="width: 100%; margin-top: 15px;" onclick="resetSettings()">🔄 استعادة الافتراضي</button>
        </div>
    </div>

    <div id="aboutModal" class="modal">
        <div class="modal-content" style="line-height: 1.8;">
            <span class="close-btn" onclick="closeModal('aboutModal')">&times;</span>
            <h2 style="text-align:center; color: #8e44ad;">🏫 Smart Academy V 5.0</h2>
            <p><strong>المعلم التفاعلي:</strong> يقترح خطة الدرس، يصحح الأخطاء، ويحفظ المحادثات في قاعدة بيانات آمنة.</p>
        </div>
    </div>

    <h2>Smart Academy 🎓</h2>
    <div id="curriculumStatus"></div>
    
    <div class="curriculum-info">
        📚 <strong>المنهج المعتمد:</strong> الإطار الأوروبي المرجعي المشترك (CEFR).
        <a href="https://www.coe.int/en/web/common-european-framework-reference-languages" target="_blank">🔗 الموقع الرسمي</a>
    </div>

    <div class="top-bar">
        <select id="mode" onchange="changeStyle()">
            <option value="adult">وضع الكبار (احترافي)</option>
            <option value="child">وضع الأطفال (مرح)</option>
        </select>
        <select id="micLang">
            <option value="en-US">الميكروفون: إنجليزي</option>
            <option value="ar-SA">الميكروفون: عربي</option>
        </select>
        <button class="start-btn" onclick="startLiveLesson()">🎓 ابدأ المكالمة الحية</button>
    </div>
    
    <div id="liveIndicator">🔴 المكالمة نشطة: تحدث للمقاطعة أو الرد...</div>
    
    <div class="input-container">
        <button id="micBtn" class="circle-btn" onclick="toggleMic()" title="تحدث للرد / قاطع المدرس">🎤</button>
        <input type="text" id="userMsg" placeholder="اكتب رسالتك أو اضغط الميكروفون للحديث...">
        <button class="send-btn" onclick="sendMsg()">إرسال</button>
    </div>

    <div id="audioControls">
        <button class="circle-btn control-btn" onclick="skipAudio(-5)">⏪</button>
        <button id="pauseBtn" class="circle-btn control-btn" onclick="togglePauseAudio()">⏸️</button>
        <button class="circle-btn control-btn" onclick="skipAudio(5)">⏩</button>
        <button class="circle-btn download-btn" onclick="downloadAudio()" title="حفظ الدرس">💾</button>
    </div>
    
    <div id="chatBox"></div>
    
    <audio id="audioPlayer"></audio>

    <script>
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';

        let isRecording = false, recognition, customCurriculumContent = "", wordsElements = [];
        let isLiveMode = false, silenceTimer, final_transcript = '', chatHistory = [], isTeacherSpeaking = false;

        function toggleDrawer() {
            document.getElementById('sideDrawer').classList.toggle('open');
            document.getElementById('overlay').classList.toggle('active');
        }

        const topicsLibrary = {
            "📱 تكنولوجيا": ["الذكاء الاصطناعي", "الأمن السيبراني", "تطور الهواتف", "إنترنت الأشياء"],
            "⚽ رياضة": ["كرة القدم", "الألعاب الأولمبية", "كرة السلة", "الفورمولا 1"],
            "🌍 علوم": ["الفضاء الخارجي", "التغير المناخي", "جسم الإنسان", "الحياة البحرية"],
            "✈️ سفر وثقافة": ["مصر القديمة", "الثقافة اليابانية", "السفر الاقتصادي", "تعلم اللغات"],
            "💼 حياة وعمل": ["مقابلات العمل", "إدارة الوقت", "التحدث للجمهور", "العمل عن بعد"]
        };

        function populateTopics() {
            let container = document.getElementById("topicsList");
            for (const [category, topics] of Object.entries(topicsLibrary)) {
                let catDiv = document.createElement("div"); catDiv.className = "topic-category"; catDiv.innerText = category; container.appendChild(catDiv);
                topics.forEach(topic => {
                    let btn = document.createElement("div"); btn.className = "topic-item"; btn.innerText = topic;
                    btn.onclick = () => { closeModal('topicsModal'); toggleDrawer(); sendMsg(`Let's discuss: ${topic}. Explain it and ask me a question.`); };
                    container.appendChild(btn);
                });
            }
        }
        populateTopics();

        function openModal(id) { document.getElementById(id).style.display = "block"; toggleDrawer(); }
        function closeModal(id) { document.getElementById(id).style.display = "none"; }
        window.onclick = function(e) { if(e.target.classList.contains('modal')) e.target.style.display = "none"; }

        function applySettings() {
            let root = document.documentElement;
            root.style.setProperty('--user-bg', document.getElementById('userBgColor').value);
            root.style.setProperty('--ai-bg', document.getElementById('aiBgColor').value);
            root.style.setProperty('--chat-color', document.getElementById('fontColor').value);
            root.style.setProperty('--chat-size', document.getElementById('fontSize').value + 'px');
            root.style.setProperty('--chat-font', document.getElementById('fontFamily').value);
            document.getElementById('fontSizeVal').innerText = document.getElementById('fontSize').value + 'px';
        }

        function resetSettings() {
            document.getElementById('userBgColor').value = "#d5f5e3"; document.getElementById('aiBgColor').value = "#e1f5fe";
            document.getElementById('fontColor').value = "#2c3e50"; document.getElementById('fontSize').value = "16";
            document.getElementById('fontFamily').value = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"; applySettings();
        }

        function changeStyle() {
            let mode = document.getElementById("mode").value;
            if (mode === "child") {
                document.getElementById('fontFamily').value = "'Comic Sans MS', cursive, sans-serif";
                document.getElementById('aiBgColor').value = "#ffebef";
            } else {
                document.getElementById('fontFamily').value = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
                document.getElementById('aiBgColor').value = "#e1f5fe";
            }
            applySettings();
        }

        async function startLiveLesson() {
            try { window.localStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); } catch (e) {}
            isLiveMode = true; document.getElementById("liveIndicator").style.display = "block"; final_transcript = '';
            if (!isRecording && recognition) { recognition.lang = document.getElementById("micLang").value; try { recognition.start(); } catch(e) {} }
            sendMsg("Hello! I am ready to start speaking. Please ask me a question.");
        }

        function requestFeature(type) {
            toggleDrawer();
            let p = {"study_plan": "Suggest a detailed CEFR study plan.", "test": "Give me a short English test."}[type];
            sendMsg(p);
        }

        function triggerUpload() {
            toggleDrawer();
            if(confirm("⚠️ تحذير قانوني: أنت مسؤول بالكامل عن محتوى الملف المرفوع. يمنع منعاً باتاً رفع أي مواد تخالف الشريعة، القوانين، أو حقوق الملكية. موافق؟")) { document.getElementById("fileUpload").click(); }
        }

        function handleFileUpload(event) {
            let file = event.target.files[0];
            if (!file) return;
            let status = document.getElementById("curriculumStatus"); status.innerText = "⏳ جاري قراءة الملف...";
            let ext = file.name.split('.').pop().toLowerCase();

            if (ext === 'txt') {
                let reader = new FileReader(); reader.onload = e => { customCurriculumContent = e.target.result; status.innerText = "✅ تم دمج المنهج."; }; reader.readAsText(file);
            } else if (ext === 'docx' || ext === 'doc') {
                let reader = new FileReader(); reader.onload = e => { mammoth.extractRawText({arrayBuffer: e.target.result}).then(res => { customCurriculumContent = res.value; status.innerText = "✅ تم استخراج نص Word."; }).catch(err => { status.innerText = "❌ خطأ في القراءة."; }); }; reader.readAsArrayBuffer(file);
            } else if (ext === 'pdf') {
                let reader = new FileReader(); reader.onload = async function(e) {
                    try {
                        let typedarray = new Uint8Array(e.target.result); let pdf = await pdfjsLib.getDocument(typedarray).promise; let fullText = "";
                        let maxPages = Math.min(pdf.numPages, 5); 
                        for(let i = 1; i <= maxPages; i++) { let page = await pdf.getPage(i); let textContent = await page.getTextContent(); fullText += textContent.items.map(item => item.str).join(" ") + " "; }
                        customCurriculumContent = fullText; status.innerText = `✅ تم استخراج نص PDF.`;
                    } catch(err) { status.innerText = "❌ خطأ في PDF."; }
                }; reader.readAsArrayBuffer(file);
            } else { status.innerText = "❌ صيغة غير مدعومة."; }
            event.target.value = '';
        }

        function skipAudio(s) { let a = document.getElementById("audioPlayer"); if (a.src) a.currentTime += s; }
        function downloadAudio() {
            let a = document.getElementById("audioPlayer"); if (!a.src) return;
            let link = document.createElement("a"); link.href = a.src; link.download = "SmartAcademy_Lesson.mp3"; 
            document.body.appendChild(link); link.click(); document.body.removeChild(link);
        }
        function togglePauseAudio() {
            let a = document.getElementById("audioPlayer"), btn = document.getElementById("pauseBtn");
            if(a.src === "") return;
            if (a.paused) { a.play(); btn.innerText = "⏸️"; } else { a.pause(); btn.innerText = "▶️"; }
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
                        if (event.results[i].isFinal) final_transcript += event.results[i][0].transcript + " "; else interim += event.results[i][0].transcript;
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
            } return false;
        }

        let isSpeechSupported = initSpeechRecognition();

        async function toggleMic() {
            if (!isSpeechSupported) return alert("المتصفح لا يدعم الميكروفون.");
            if (isTeacherSpeaking && !audioPlayer.paused) {
                audioPlayer.pause(); isTeacherSpeaking = false; document.getElementById("pauseBtn").innerText = "▶️";
                wordsElements.forEach(span => span.classList.add("spoken"));
                isLiveMode = true; final_transcript = ''; document.getElementById("liveIndicator").style.display = "block";
                recognition.lang = document.getElementById("micLang").value; try { recognition.start(); } catch(e) {} return;
            }
            if (isLiveMode || isRecording) {
                isLiveMode = false; if(isRecording) recognition.stop();
                document.getElementById("liveIndicator").style.display = "none";
                if(window.localStream) window.localStream.getTracks().forEach(t => t.stop());
            } else {
                try { window.localStream = await navigator.mediaDevices.getUserMedia({audio: { echoCancellation: true, noiseSuppression: true }}); } catch (e) {}
                isLiveMode = true; final_transcript = ''; document.getElementById("liveIndicator").style.display = "block";
                recognition.lang = document.getElementById("micLang").value; try { recognition.start(); } catch(e) {}
            }
        }

        document.getElementById("userMsg").addEventListener("keypress", function(e) { if (e.key === "Enter") { e.preventDefault(); sendMsg(); } });

        function appendBubble(text, isUser, data=null) {
            let box = document.getElementById("chatBox"), container = document.createElement("div");
            container.className = isUser ? "chat-bubble user-bubble" : "chat-bubble ai-bubble";
            
            if(isUser) { container.innerText = text; } 
            else {
                let engDiv = document.createElement("div"); engDiv.className = "english-text";
                wordsElements = [];
                // استخراج الكلمات الانجليزية للنطق دون التاثير بالكود البرمجي (في حال وجوده)
                data.english.split(" ").forEach(word => {
                    let span = document.createElement("span"); span.className = "word"; span.innerText = word;
                    engDiv.appendChild(span); wordsElements.push(span);
                });
                container.appendChild(engDiv);
                
                let arDiv = document.createElement("div"); arDiv.className = "arabic-translation"; arDiv.innerText = data.arabic; container.appendChild(arDiv);
                
                let details = "";
                if(data.keywords) details += `<div class="structured-data"><span class="section-title">🔑 Keywords:</span><br>${data.keywords}</div>`;
                if(data.summary) details += `<div class="structured-data"><span class="section-title">📝 Notes/Plan:</span><br>${data.summary}</div>`;
                if (details !== "") { let dDiv = document.createElement("div"); dDiv.innerHTML = details; container.appendChild(dDiv); }
            }
            box.appendChild(container); setTimeout(() => box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' }), 100);
        }

        // --- جلب المحادثات السابقة من قاعدة البيانات عند فتح الصفحة ---
        window.onload = async function() {
            document.getElementById('chatBox').innerHTML = '';
            try {
                let res = await fetch("/get_history");
                let history = await res.json();
                
                if (history.length > 0) {
                    history.forEach(item => {
                        if(item.role === 'user') {
                            appendBubble(item.content, true);
                            chatHistory.push({"role": "user", "content": item.content});
                        } else if(item.role === 'assistant') {
                            appendBubble("", false, {english: item.content, arabic: item.arabic});
                            chatHistory.push({"role": "assistant", "content": item.content});
                        }
                    });
                    document.getElementById("chatBox").scrollTop = document.getElementById("chatBox").scrollHeight;
                } else {
                    // إذا لم يكن هناك تاريخ (مستخدم جديد)، اطلب الترحيب
                    let prompt = "Generate a unique, warm welcome message for a new student. Include a brief overview of what we can learn today. Ask them how they want to start.";
                    sendMsg(prompt, true);
                }
            } catch(e) {
                let prompt = "Generate a unique, warm welcome message for a new student...";
                sendMsg(prompt, true);
            }
        };

        async function sendMsg(overrideMsg = null, isHidden = false) {
            let inputField = document.getElementById("userMsg"), msg = overrideMsg || inputField.value;
            if(!msg.trim()) return;
            
            if(!isHidden){
                appendBubble(msg, true); 
                chatHistory.push({"role": "user", "content": msg});
            } else {
                chatHistory.push({"role": "system", "content": msg});
            }
            
            final_transcript = ''; clearTimeout(silenceTimer); audioPlayer.pause(); document.getElementById("audioControls").style.display = "none"; inputField.value = ""; 
            
            let loadDiv = document.createElement("div"); loadDiv.className = "chat-bubble ai-bubble"; loadDiv.id = "loadingBubble";
            loadDiv.innerHTML = "<div class='arabic-translation' style='border:none;'>جاري التفكير وتجهيز الرد... ⏳</div>";
            document.getElementById("chatBox").appendChild(loadDiv);
            box = document.getElementById("chatBox"); box.scrollTop = box.scrollHeight;
            
            try {
                let res = await fetch("/chat", {
                    method: "POST", headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ message: msg, mode: document.getElementById("mode").value, custom_curriculum: customCurriculumContent })
                });
                let data = await res.json();
                document.getElementById("loadingBubble")?.remove();
                if(data.error) return alert("⚠️ خطأ: " + data.error);
                
                chatHistory.push({"role": "assistant", "content": data.english});
                appendBubble("", false, data);
                
                if(data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    document.getElementById("audioControls").style.display = "flex"; document.getElementById("pauseBtn").innerText = "⏸️";
                    isTeacherSpeaking = true; if(isRecording) recognition.stop();
                    let playPromise = audioPlayer.play();
                    if (playPromise !== undefined) playPromise.catch(error => { console.log("Auto-play blocked by browser."); });
                }
            } catch (e) { document.getElementById("loadingBubble")?.remove(); alert("⚠️ خطأ في الاتصال."); }
        }
    </script>
</body>
</html>
"""

async def generate_audio(text, voice):
    clean_text = re.sub(r'[^\w\s.,!?\']', '', text) 
    communicate = edge_tts.Communicate(clean_text, voice)
    await communicate.save("response.mp3")
    with open("response.mp3", "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

# --- استرجاع السجل من قاعدة البيانات ---
@app.route("/get_history", methods=["GET"])
def get_history():
    try:
        with sqlite3.connect('academy.db') as conn:
            cursor = conn.execute("SELECT role, content, arabic FROM chat_history ORDER BY id ASC")
            rows = cursor.fetchall()
            history = [{"role": r[0], "content": r[1], "arabic": r[2]} for r in rows]
        return jsonify(history)
    except Exception as e:
        return jsonify([])

@app.route("/chat", methods=["POST"])
def chat():
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key: return jsonify({"error": "Missing GROQ_API_KEY"})

        client = Groq(api_key=api_key)
        data = request.json
        mode = data.get("mode", "adult")
        user_msg = data.get("message", "")
        custom_curriculum = data.get("custom_curriculum", "")

        # استرجاع آخر 8 رسائل من قاعدة البيانات للسياق (لتجنب استهلاك الـ Tokens)
        with sqlite3.connect('academy.db') as conn:
            cursor = conn.execute("SELECT role, content FROM chat_history ORDER BY id DESC LIMIT 8")
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

        json_structure = '''
        Respond ONLY in JSON format:
        {
            "english": "Natural, human-like spoken English response.",
            "arabic": "Arabic translation",
            "keywords": "Keywords",
            "summary": "Notes / Lesson Plan / Corrections (if any)"
        }
        '''
        
        if mode == "child":
            sys_msg = core_rules + "\\nYou are a fun, highly energetic English teacher for kids. Speak cheerfully." + json_structure
            voice_model = "en-US-AriaNeural" 
        else:
            sys_msg = core_rules + "\\nYou are a professional, friendly English coach. Act as an interactive mentor." + json_structure
            voice_model = "en-US-ChristopherNeural" 

        # إضافة رسالة المستخدم الحالية
        messages = [{"role": "system", "content": sys_msg}] + history + [{"role": "user", "content": user_msg}]
        
        completion = client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages, response_format={"type": "json_object"})
        
        parsed = json.loads(completion.choices[0].message.content)
        eng_text = parsed.get("english", "Hello there!")
        ar_text = parsed.get("arabic", "")
        
        # --- حفظ الرسائل في قاعدة البيانات للأبد ---
        with sqlite3.connect('academy.db') as conn:
            # إذا لم تكن رسالة مخفية (System) نحفظها
            if "Generate a unique, warm welcome message" not in user_msg:
                conn.execute("INSERT INTO chat_history (role, content, arabic) VALUES (?, ?, ?)", ("user", user_msg, ""))
            conn.execute("INSERT INTO chat_history (role, content, arabic) VALUES (?, ?, ?)", ("assistant", eng_text, ar_text))
            
        audio_base64 = asyncio.run(generate_audio(eng_text, voice_model))

        return jsonify({ "english": eng_text, "arabic": ar_text, "keywords": parsed.get("keywords", ""), "summary": parsed.get("summary", ""), "audio": audio_base64 })
    except Exception as e: return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
