import os
import asyncio
import base64
import json
import re
from flask import Flask, request, jsonify, render_template_string
from groq import Groq
import edge_tts

app = Flask(__name__)

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
        /* المتغيرات الأساسية للمظهر (تتغير ديناميكياً من الإعدادات) */
        :root { 
            --primary: #3498db; --secondary: #2c3e50; --accent: #8e44ad; --danger: #e74c3c; --success: #2ecc71; --bg: #f5f7fa;
            --user-bg: #d5f5e3; /* أخضر بازيلي خفيف */
            --ai-bg: #e1f5fe;   /* سماوي خفيف */
            --chat-color: #2c3e50;
            --chat-size: 16px;
            --chat-font: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        body { font-family: var(--chat-font); text-align: center; margin: 0; padding: 20px 20px 80px 20px; background: linear-gradient(135deg, var(--bg) 0%, #c3cfe2 100%); min-height: 100vh; overflow-x: hidden;}
        h2 { color: var(--secondary); text-shadow: 1px 1px 2px rgba(0,0,0,0.1); margin-bottom: 5px; animation: fadeSlideDown 0.8s ease forwards;}
        
        @keyframes fadeSlideDown { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeSlideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes popIn { 0% { opacity: 0; transform: scale(0.9); } 100% { opacity: 1; transform: scale(1); } }
        @keyframes slideInRight { from { opacity: 0; transform: translateX(50px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes pulseMic { 0% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7); } 70% { box-shadow: 0 0 0 15px rgba(231, 76, 60, 0); } 100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0); } }
        /* حركة كسر الملل العشوائية */
        @keyframes subtleBounce { 0%, 100% { transform: translateY(0) scale(1); } 50% { transform: translateY(-8px) scale(1.05); } }
        .anim-boredom { animation: subtleBounce 0.6s ease-in-out 2; }

        .curriculum-info { background: rgba(255, 255, 255, 0.85); border-radius: 12px; padding: 10px; width: 90%; max-width: 800px; margin: 10px auto; font-size: 13px; color: var(--secondary); box-shadow: 0 4px 10px rgba(0,0,0,0.05); backdrop-filter: blur(5px); animation: fadeSlideDown 0.8s ease forwards; animation-delay: 0.1s; opacity: 0;}
        .curriculum-info a { color: var(--primary); text-decoration: none; font-weight: bold; margin: 0 10px; transition: color 0.2s;}

        .top-bar { display: flex; justify-content: center; align-items: center; width: 90%; max-width: 800px; margin: 0 auto 15px auto; gap: 10px; flex-wrap: wrap; animation: fadeSlideDown 0.8s ease forwards; animation-delay: 0.2s; opacity: 0;}
        select { padding: 10px; font-size: 14px; border-radius: 8px; border: 1px solid #bdc3c7; outline: none; cursor: pointer; background: white;}
        
        .start-btn { background: linear-gradient(135deg, var(--accent) 0%, #9b59b6 100%); font-weight: bold; padding: 10px 25px; font-size: 15px; border-radius: 8px; border: none; color: white; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 10px rgba(142, 68, 173, 0.3);}
        .start-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(142, 68, 173, 0.4); }
        
        #liveIndicator { display: none; color: var(--danger); font-weight: bold; font-size: 14px; margin-top: 10px; animation: blink 1.5s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

        .circle-btn { border-radius: 50%; width: 55px; height: 55px; display: flex; justify-content: center; align-items: center; font-size: 24px; border: none; cursor: pointer; transition: all 0.2s ease; box-shadow: 0 4px 10px rgba(0,0,0,0.15); z-index: 10; color: white;}
        .circle-btn:active { transform: scale(0.9); }
        .circle-btn:hover { transform: translateY(-3px); box-shadow: 0 6px 15px rgba(0,0,0,0.2); }
        #micBtn { background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);}
        #micBtn.recording { animation: pulseMic 1.5s infinite; }

        .input-container { display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 15px; animation: fadeSlideUp 0.8s ease forwards; animation-delay: 0.3s; opacity: 0;}
        input[type="text"] { padding: 15px 20px; font-size: 16px; border-radius: 30px; border: 1px solid #bdc3c7; width: 65%; max-width: 600px; outline: none; transition: all 0.3s; background: rgba(255,255,255,0.95); box-shadow: 0 2px 5px rgba(0,0,0,0.02);}
        input[type="text"]:focus { border-color: var(--primary); background: white; box-shadow: 0 0 10px rgba(52, 152, 219, 0.2);}
        .send-btn { padding: 14px 25px; font-size: 16px; border-radius: 30px; border: none; color: white; cursor: pointer; font-weight: bold; background: linear-gradient(135deg, #36D1DC 0%, #5B86E5 100%); box-shadow: 0 4px 10px rgba(91, 134, 229, 0.3); transition: all 0.3s ease;}

        #audioControls { display: none; justify-content: center; gap: 15px; margin-top: 15px; background: rgba(255,255,255,0.9); padding: 10px 20px; border-radius: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); width: fit-content; margin: 15px auto;}
        .control-btn { background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); width: 45px; height: 45px; font-size: 18px;}
        .download-btn { background: linear-gradient(135deg, var(--success) 0%, #27ae60 100%); width: 45px; height: 45px; font-size: 18px;}

        /* صندوق المحادثة والألوان المتغيرة */
        #chatBox { width: 95%; max-width: 900px; margin: 20px auto; background: rgba(255, 255, 255, 0.95); padding: 25px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); height: 55vh; max-height: 600px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; border-top: 5px solid var(--primary); scroll-behavior: smooth; animation: popIn 0.8s ease forwards; animation-delay: 0.4s; opacity: 0;}
        .chat-bubble { max-width: 85%; padding: 15px 20px; border-radius: 20px; position: relative; font-size: var(--chat-size); color: var(--chat-color); line-height: 1.6; animation: fadeSlideUp 0.3s ease-out;}
        .user-bubble { background: var(--user-bg); align-self: flex-start; border-bottom-left-radius: 5px; text-align: left; direction: ltr;}
        .ai-bubble { background: var(--ai-bg); align-self: flex-end; border-bottom-right-radius: 5px; text-align: right; box-shadow: 0 2px 5px rgba(0,0,0,0.03);}
        
        .english-text { font-size: calc(var(--chat-size) + 4px); font-weight: bold; direction: ltr; text-align: left; margin-bottom: 10px;}
        .arabic-translation { border-top: 1px dashed rgba(0,0,0,0.2); padding-top: 8px; opacity: 0.9;}
        .structured-data { font-size: calc(var(--chat-size) - 2px); background-color: rgba(255,255,255,0.6); padding: 10px 12px; border-radius: 8px; margin-top: 10px; text-align: left; direction: ltr; border-left: 4px solid rgba(0,0,0,0.3);}
        .section-title { font-weight: bold; text-transform: uppercase; margin-bottom: 5px; display: block; opacity: 0.8;}
        
        .word { display: inline-block; margin-right: 5px; transition: color 0.1s ease-in; opacity: 0.6;}
        .word.active { color: var(--danger); transform: scale(1.1); font-weight: 900; opacity: 1;}
        .word.spoken { color: inherit; opacity: 1;}

        /* القائمة العائمة الجديدة بألوان زاهية */
        .side-menu { position: fixed; right: 20px; top: 50%; transform: translateY(-50%); display: flex; flex-direction: column; gap: 12px; z-index: 1000; }
        .menu-btn { 
            border-radius: 50px; padding: 10px 18px; font-size: 13px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.2); transition: all 0.3s ease; display: flex; align-items: center; justify-content: flex-start; gap: 10px; opacity: 0; animation: slideInRight 0.5s ease-out forwards; width: 190px; color: white; border: none;
        }
        .menu-btn:hover { transform: translateX(-5px) scale(1.03); box-shadow: 0 6px 15px rgba(0,0,0,0.3);}
        .menu-btn .icon { font-size: 18px; background: rgba(255,255,255,0.2); border-radius: 50%; padding: 4px;}
        
        .menu-btn.plan { background: linear-gradient(135deg, #FF416C, #FF4B2B); animation-delay: 0.3s; }
        .menu-btn.test { background: linear-gradient(135deg, #FDC830, #F37335); animation-delay: 0.4s; }
        .menu-btn.topics { background: linear-gradient(135deg, #4776E6, #8E54E9); animation-delay: 0.5s; }
        .menu-btn.upload { background: linear-gradient(135deg, #11998e, #38ef7d); animation-delay: 0.6s; }
        .menu-btn.settings { background: linear-gradient(135deg, #00B4DB, #0083B0); animation-delay: 0.7s; }
        .menu-btn.about { background: linear-gradient(135deg, #b20a2c, #fffbd5); color: #333; animation-delay: 0.8s; }

        /* النوافذ المنبثقة */
        .modal { display: none; position: fixed; z-index: 2000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); backdrop-filter: blur(4px); }
        .modal-content { background: white; margin: 10vh auto; padding: 30px; border-radius: 20px; width: 85%; max-width: 700px; max-height: 80vh; overflow-y: auto; text-align: right; box-shadow: 0 15px 40px rgba(0,0,0,0.2); animation: popIn 0.4s ease-out;}
        .close-btn { color: #aaa; float: left; font-size: 32px; font-weight: bold; cursor: pointer; transition: color 0.2s;}
        .close-btn:hover { color: var(--danger); }
        
        .topics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-top: 15px; }
        .topic-item { background: #f8f9fa; padding: 10px; border-radius: 8px; font-size: 13px; text-align: center; cursor: pointer; transition: all 0.2s; border: 1px solid #dcdde1; font-weight: 600; color: #333;}
        .topic-item:hover { background: var(--primary); color: white; transform: translateY(-2px);}
        .topic-category { grid-column: 1 / -1; font-size: 16px; font-weight: bold; color: var(--accent); margin-top: 15px; border-bottom: 2px solid #ecf0f1; padding-bottom: 5px; }

        /* تنسيقات إعدادات المظهر */
        .settings-group { margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between; background: #f9f9f9; padding: 10px; border-radius: 10px; border: 1px solid #eee;}
        .settings-group label { font-weight: bold; color: var(--secondary); font-size: 15px;}
        .settings-group input[type="color"] { border: none; width: 40px; height: 40px; border-radius: 5px; cursor: pointer;}
        .settings-group select, .settings-group input[type="range"] { width: 50%; padding: 8px; border-radius: 5px;}

        #audioPlayer { display: none; }
        #curriculumStatus { color: var(--success); font-size: 12px; font-weight: bold; margin-top: 5px; text-align: center;}
        
        /* إشعار الاستراحة */
        .break-notification { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: linear-gradient(135deg, #FFD200, #F7971E); color: white; padding: 15px 30px; border-radius: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); font-weight: bold; font-size: 16px; z-index: 3000; animation: fadeSlideDown 0.5s ease-out forwards; display: none;}

        @media (max-width: 768px) {
            body { padding-bottom: 130px; } 
            .side-menu { 
                position: fixed; bottom: 0; left: 0; top: auto; right: auto; transform: none; 
                flex-direction: row; width: 100%; justify-content: space-around; background: white; 
                padding: 10px 5px; box-shadow: 0 -2px 15px rgba(0,0,0,0.1); z-index: 1000;
                border-top-left-radius: 20px; border-top-right-radius: 20px; gap: 5px; flex-wrap: wrap;
            }
            .menu-btn { width: calc(33% - 10px); padding: 8px; border-radius: 12px; flex-direction: column; gap: 5px;}
            .menu-btn span:last-child { font-size: 10px; display: block; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%;}
            .menu-btn .icon { font-size: 20px; background: transparent; padding: 0;}
            .top-bar, .input-container { flex-direction: column; }
            input[type="text"] { width: 90%; }
        }
    </style>
</head>
<body>
    
    <!-- إشعار الاستراحة (Pomodoro) -->
    <div id="breakNotice" class="break-notification">⏰ مر 25 دقيقة! المدرب ينصحك بأخذ استراحة قصيرة لتجديد نشاطك ☕</div>

    <!-- القائمة الجانبية (الألوان الزاهية) -->
    <div class="side-menu">
        <button class="menu-btn plan" onclick="requestFeature('study_plan')">
            <span class="icon">📅</span><span>الخطة الدراسية</span>
        </button>
        <button class="menu-btn test" onclick="requestFeature('test')">
            <span class="icon">📝</span><span>التقييم والتدريب</span>
        </button>
        <button class="menu-btn topics" onclick="openModal('topicsModal')">
            <span class="icon">🗂️</span><span>المواضيع والقصص</span>
        </button>
        <button class="menu-btn upload" onclick="triggerUpload()">
            <span class="icon">📂</span><span>رفع منهج PDF</span>
        </button>
        <button class="menu-btn settings" onclick="openModal('settingsModal')">
            <span class="icon">🎨</span><span>تخصيص المظهر</span>
        </button>
        <button class="menu-btn about" onclick="openModal('aboutModal')">
            <span class="icon">🏫</span><span>نبذة عنا</span>
        </button>
    </div>
    
    <input type="file" id="fileUpload" accept=".txt,.pdf,.doc,.docx" style="display: none;" onchange="handleFileUpload(event)">

    <!-- نافذة المواضيع -->
    <div id="topicsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('topicsModal')">&times;</span>
            <h2 style="text-align:center; color: var(--accent);">اختر موضوعاً للمناقشة 🎯</h2>
            <div class="topics-grid" id="topicsList"></div>
        </div>
    </div>

    <!-- نافذة تخصيص المظهر -->
    <div id="settingsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeModal('settingsModal')">&times;</span>
            <h2 style="text-align:center; color: var(--primary);">🎨 تخصيص مظهر الأكاديمية</h2>
            
            <div class="settings-group">
                <label>لون صندوق المتدرب (أخضر افتراضي):</label>
                <input type="color" id="userBgColor" value="#d5f5e3" onchange="applySettings()">
            </div>
            <div class="settings-group">
                <label>لون صندوق المدرب (سماوي افتراضي):</label>
                <input type="color" id="aiBgColor" value="#e1f5fe" onchange="applySettings()">
            </div>
            <div class="settings-group">
                <label>لون نصوص المحادثة:</label>
                <input type="color" id="fontColor" value="#2c3e50" onchange="applySettings()">
            </div>
            <div class="settings-group">
                <label>حجم الخط:</label>
                <input type="range" id="fontSize" min="12" max="24" value="16" oninput="applySettings()">
                <span id="fontSizeVal">16px</span>
            </div>
            <div class="settings-group">
                <label>نوع الخط (الخطوط الجميلة):</label>
                <select id="fontFamily" onchange="applySettings()">
                    <option value="'Segoe UI', Tahoma, Geneva, Verdana, sans-serif">Segoe UI (عصري ومريح)</option>
                    <option value="Arial, Helvetica, sans-serif">Arial (رسمي)</option>
                    <option value="'Comic Sans MS', cursive, sans-serif">Comic Sans (مرح للأطفال)</option>
                    <option value="'Courier New', Courier, monospace">Courier New (كلاسيكي)</option>
                    <option value="'Times New Roman', Times, serif">Times New Roman (أكاديمي)</option>
                </select>
            </div>
            <button class="send-btn" style="width: 100%; margin-top: 15px;" onclick="resetSettings()">🔄 استعادة الافتراضي</button>
        </div>
    </div>

    <!-- نافذة نبذة عنا والإصدار -->
    <div id="aboutModal" class="modal">
        <div class="modal-content" style="line-height: 1.8;">
            <span class="close-btn" onclick="closeModal('aboutModal')">&times;</span>
            <h2 style="text-align:center; color: #8e44ad;">🏫 Smart Academy V 2.1</h2>
            <p><strong>من نحن:</strong> أكاديمية ذكية ومبتكرة تهدف إلى إحداث ثورة في تعلم الإنجليزية باستخدام الذكاء الاصطناعي التوليدي.</p>
            <p><strong>الإصدار الأحدث:</strong> يتيح تخصيصاً كاملاً للمظهر، استخراج محتوى PDF/Word، نظام استراحة (Pomodoro)، حركات لتنشيط الواجهة، وألوان مريحة للعين.</p>
            <p><strong>منهجيتنا:</strong> نعتمد على الإطار الأوروبي المرجعي المشترك للغات (CEFR).</p>
        </div>
    </div>

    <h2 class="anim-drop" id="mainTitle">Smart Academy 🎓</h2>
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
        <button class="start-btn" onclick="startLiveLesson()">🎓 ابدأ المكالمة والدرس</button>
    </div>
    
    <div id="liveIndicator">🔴 جلسة التدريب نشطة: تحدث بحرية...</div>
    
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
    
    <div id="chatBox">
        <div class="chat-bubble ai-bubble">
            <div class="arabic-translation" style="border: none; padding: 0; font-weight:bold;">
                مرحباً بك! صندوق المدرب يظهر بهذا اللون المريح، وصندوقك سيظهر باللون البازيلي الخفيف. يمكنك تغيير الألوان من "تخصيص المظهر".
            </div>
        </div>
    </div>
    
    <audio id="audioPlayer"></audio>

    <script>
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';

        let isRecording = false, recognition, customCurriculumContent = "", wordsElements = [];
        let isLiveMode = false, silenceTimer, final_transcript = '', chatHistory = [], isTeacherSpeaking = false;

        // مكتبة المواضيع الشاملة
        const topicsLibrary = {
            "📱 تكنولوجيا": ["الذكاء الاصطناعي", "الأمن السيبراني", "تطور الهواتف", "إنترنت الأشياء", "البرمجة للمبتدئين"],
            "⚽ رياضة": ["كرة القدم التكتيكية", "الألعاب الأولمبية", "كرة السلة", "الفورمولا 1", "الرياضات الإلكترونية"],
            "🌍 علوم وطبيعة": ["الفضاء الخارجي", "التغير المناخي", "جسم الإنسان", "الحياة البحرية", "علم الوراثة"],
            "✈️ سفر وثقافة": ["الحضارة المصرية", "الثقافة اليابانية", "السفر الاقتصادي", "المطابخ العالمية", "تعلم اللغات"],
            "💼 حياة وعمل": ["مقابلات العمل", "إدارة الوقت", "التحدث أمام الجمهور", "العمل عن بعد", "الذكاء العاطفي"]
        };

        function populateTopics() {
            let container = document.getElementById("topicsList");
            for (const [category, topics] of Object.entries(topicsLibrary)) {
                let catDiv = document.createElement("div"); catDiv.className = "topic-category"; catDiv.innerText = category; container.appendChild(catDiv);
                topics.forEach(topic => {
                    let btn = document.createElement("div"); btn.className = "topic-item"; btn.innerText = topic;
                    btn.onclick = () => { closeModal('topicsModal'); sendMsg(`Let's discuss: ${topic}. Explain it and ask me a question.`); };
                    container.appendChild(btn);
                });
            }
        }
        populateTopics();

        function openModal(id) { document.getElementById(id).style.display = "block"; }
        function closeModal(id) { document.getElementById(id).style.display = "none"; }
        window.onclick = function(e) { if(e.target.classList.contains('modal')) e.target.style.display = "none"; }

        // --- نظام تخصيص المظهر الديناميكي ---
        function applySettings() {
            let root = document.documentElement;
            let uBg = document.getElementById('userBgColor').value;
            let aBg = document.getElementById('aiBgColor').value;
            let fontColor = document.getElementById('fontColor').value;
            let fontSize = document.getElementById('fontSize').value;
            let fontFam = document.getElementById('fontFamily').value;

            root.style.setProperty('--user-bg', uBg);
            root.style.setProperty('--ai-bg', aBg);
            root.style.setProperty('--chat-color', fontColor);
            root.style.setProperty('--chat-size', fontSize + 'px');
            root.style.setProperty('--chat-font', fontFam);
            
            document.getElementById('fontSizeVal').innerText = fontSize + 'px';
        }

        function resetSettings() {
            document.getElementById('userBgColor').value = "#d5f5e3";
            document.getElementById('aiBgColor').value = "#e1f5fe";
            document.getElementById('fontColor').value = "#2c3e50";
            document.getElementById('fontSize').value = "16";
            document.getElementById('fontFamily').value = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
            applySettings();
        }

        // --- نظام استراحة بومودورو (25 دقيقة) ---
        let studyMinutes = 0;
        setInterval(() => {
            studyMinutes++;
            if (studyMinutes === 25) {
                let notice = document.getElementById("breakNotice");
                notice.style.display = "block";
                setTimeout(() => { notice.style.display = "none"; studyMinutes = 0; }, 10000); // يخفي بعد 10 ثواني ويصفر العداد
            }
        }, 60000); // تحديث كل دقيقة

        // --- حركات عشوائية لكسر الملل ---
        setInterval(() => {
            let elements = [document.getElementById('micBtn'), document.querySelector('.start-btn'), document.getElementById('mainTitle')];
            let randomEl = elements[Math.floor(Math.random() * elements.length)];
            if(randomEl) {
                randomEl.classList.add('anim-boredom');
                setTimeout(() => randomEl.classList.remove('anim-boredom'), 1200);
            }
        }, 30000); // كل 30 ثانية

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
            sendMsg("Hello! I am ready. Please introduce yourself and ask me the first question.");
        }

        function requestFeature(type) {
            let p = {"study_plan": "Suggest a detailed CEFR study plan.", "test": "Give me a short English test."}[type];
            sendMsg(p);
        }

        function triggerUpload() { document.getElementById("fileUpload").click(); }

        // قراءة الملفات في المتصفح
        function handleFileUpload(event) {
            let file = event.target.files[0];
            if (!file) return;
            let status = document.getElementById("curriculumStatus");
            status.innerText = "⏳ جاري قراءة الملف...";
            let ext = file.name.split('.').pop().toLowerCase();

            if (ext === 'txt') {
                let reader = new FileReader();
                reader.onload = e => { customCurriculumContent = e.target.result; status.innerText = "✅ تم دمج المنهج في الذاكرة."; };
                reader.readAsText(file);
            } 
            else if (ext === 'docx' || ext === 'doc') {
                let reader = new FileReader();
                reader.onload = e => {
                    mammoth.extractRawText({arrayBuffer: e.target.result})
                        .then(res => { customCurriculumContent = res.value; status.innerText = "✅ تم استخراج نص الـ Word."; })
                        .catch(err => { status.innerText = "❌ خطأ في قراءة Word."; });
                };
                reader.readAsArrayBuffer(file);
            } 
            else if (ext === 'pdf') {
                let reader = new FileReader();
                reader.onload = async function(e) {
                    try {
                        let typedarray = new Uint8Array(e.target.result);
                        let pdf = await pdfjsLib.getDocument(typedarray).promise;
                        let fullText = "";
                        let maxPages = Math.min(pdf.numPages, 5); 
                        for(let i = 1; i <= maxPages; i++) {
                            let page = await pdf.getPage(i);
                            let textContent = await page.getTextContent();
                            fullText += textContent.items.map(item => item.str).join(" ") + " ";
                        }
                        customCurriculumContent = fullText;
                        status.innerText = `✅ تم استخراج نص PDF (${maxPages} صفحات).`;
                    } catch(err) { status.innerText = "❌ خطأ في PDF."; }
                };
                reader.readAsArrayBuffer(file);
            } else { status.innerText = "❌ صيغة غير مدعومة."; }
            event.target.value = '';
        }

        function skipAudio(s) { let a = document.getElementById("audioPlayer"); if (a.src) a.currentTime += s; }
        function downloadAudio() {
            let a = document.getElementById("audioPlayer"); if (!a.src) return;
            let link = document.createElement("a"); link.href = a.src; link.download = "SmartAcademy_Audio.mp3"; 
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
                data.english.split(" ").forEach(word => {
                    let span = document.createElement("span"); span.className = "word"; span.innerText = word;
                    engDiv.appendChild(span); wordsElements.push(span);
                });
                container.appendChild(engDiv);
                
                let arDiv = document.createElement("div"); arDiv.className = "arabic-translation"; arDiv.innerText = data.arabic; container.appendChild(arDiv);
                
                let details = "";
                if(data.keywords) details += `<div class="structured-data"><span class="section-title">🔑 Keywords:</span><br>${data.keywords}</div>`;
                if(data.summary) details += `<div class="structured-data"><span class="section-title">📝 Summary/Plan:</span><br>${data.summary}</div>`;
                if (details !== "") { let dDiv = document.createElement("div"); dDiv.innerHTML = details; container.appendChild(dDiv); }
            }
            box.appendChild(container); setTimeout(() => box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' }), 100);
        }

        async function sendMsg(overrideMsg = null) {
            let inputField = document.getElementById("userMsg"), msg = overrideMsg || inputField.value;
            if(!msg.trim()) return;
            
            appendBubble(msg, true); chatHistory.push({"role": "user", "content": msg});
            final_transcript = ''; clearTimeout(silenceTimer); audioPlayer.pause(); document.getElementById("audioControls").style.display = "none"; inputField.value = ""; 
            
            let loadDiv = document.createElement("div"); loadDiv.className = "chat-bubble ai-bubble"; loadDiv.id = "loadingBubble";
            loadDiv.innerHTML = "<div class='arabic-translation' style='border:none;'>جاري التفكير وتجهيز الرد... ⏳</div>";
            document.getElementById("chatBox").appendChild(loadDiv);
            box = document.getElementById("chatBox"); box.scrollTop = box.scrollHeight;
            
            try {
                let res = await fetch("/chat", {
                    method: "POST", headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ history: chatHistory.slice(-10), mode: document.getElementById("mode").value, custom_curriculum: customCurriculumContent })
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
                    audioPlayer.play();
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

@app.route("/chat", methods=["POST"])
def chat():
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key: return jsonify({"error": "Missing GROQ_API_KEY"})

        client = Groq(api_key=api_key)
        data = request.json
        mode = data.get("mode", "adult")
        history = data.get("history", [])
        custom_curriculum = data.get("custom_curriculum", "")

        core_rules = """
        CRITICAL RULES: 
        1. MUST STRICTLY adhere to Islamic Sharia and local laws.
        2. Base language progression on the CEFR.
        3. YOU ARE A REAL HUMAN TUTOR. REMEMBER the conversation context.
        """
        if custom_curriculum: core_rules += f"\\n4. Context from uploaded files: {custom_curriculum[:2500]}"

        json_structure = '''
        Respond ONLY in JSON format:
        {
            "english": "Spoken English response.",
            "arabic": "Arabic translation",
            "keywords": "Keywords",
            "summary": "Summary/Notes"
        }
        '''
        sys_msg = core_rules + ("\\nYou are a fun English teacher for kids." if mode == "child" else "\\nYou are a professional English coach.") + json_structure
        voice_model = "en-US-AnaNeural" if mode == "child" else "en-US-GuyNeural"

        messages = [{"role": "system", "content": sys_msg}] + history
        completion = client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages, response_format={"type": "json_object"})
        
        parsed = json.loads(completion.choices[0].message.content)
        eng_text = parsed.get("english", "Hello!")
        audio_base64 = asyncio.run(generate_audio(eng_text, voice_model))

        return jsonify({ "english": eng_text, "arabic": parsed.get("arabic", ""), "keywords": parsed.get("keywords", ""), "summary": parsed.get("summary", ""), "audio": audio_base64 })
    except Exception as e: return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
