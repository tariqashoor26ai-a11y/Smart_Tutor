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
    <title>Smart Academy - المدرس الذكي</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            text-align: center; margin: 0; padding: 20px; 
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); 
            min-height: 100vh;
            overflow-x: hidden;
        }
        h2 { color: #2c3e50; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); margin-bottom: 5px; }
        
        /* حركات الظهور التفاعلية (Animations) */
        @keyframes fadeSlideDown { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeSlideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes popIn { 0% { opacity: 0; transform: scale(0.95); } 100% { opacity: 1; transform: scale(1); } }
        @keyframes slideInRight { from { opacity: 0; transform: translateX(50px); } to { opacity: 1; transform: translateX(0); } }
        
        .anim-drop { animation: fadeSlideDown 0.8s cubic-bezier(0.25, 0.8, 0.25, 1) forwards; }
        .anim-up { animation: fadeSlideUp 0.8s cubic-bezier(0.25, 0.8, 0.25, 1) forwards; opacity: 0; animation-delay: 0.3s;}
        .anim-pop { animation: popIn 0.8s cubic-bezier(0.25, 0.8, 0.25, 1) forwards; opacity: 0; animation-delay: 0.5s;}

        .curriculum-info {
            background-color: rgba(255, 255, 255, 0.85); border: 1px solid #bde0ec; border-radius: 12px; padding: 12px;
            width: 80%; max-width: 800px; margin: 10px auto 20px auto; font-size: 14px; color: #2c3e50; text-align: right; line-height: 1.6;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); backdrop-filter: blur(5px);
        }
        .curriculum-info a { color: #2980b9; text-decoration: none; font-weight: bold; margin-left: 15px; display: inline-block; transition: transform 0.2s;}
        .curriculum-info a:hover { text-decoration: underline; transform: translateY(-1px); color: #8e44ad;}

        .top-bar { display: flex; justify-content: center; align-items: center; width: 80%; max-width: 800px; margin: 0 auto 15px auto; gap: 15px;}
        .controls { display: flex; gap: 10px; }
        select { padding: 10px 15px; font-size: 14px; border-radius: 8px; border: 1px solid #bdc3c7; outline: none; cursor: pointer; background: white; transition: all 0.3s;}
        select:hover { border-color: #3498db; }
        
        .start-btn { 
            background: linear-gradient(135deg, #8e44ad 0%, #9b59b6 100%); font-weight: bold; padding: 10px 25px; font-size: 15px;
            border-radius: 8px; border: none; color: white; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 10px rgba(142, 68, 173, 0.3);
        }
        .start-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(142, 68, 173, 0.4); }
        
        #liveIndicator { display: none; color: #e74c3c; font-weight: bold; font-size: 15px; margin-top: 10px; animation: blink 1.5s infinite; }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }

        .circle-btn {
            border-radius: 50%; width: 55px; height: 55px; padding: 0; 
            display: flex; justify-content: center; align-items: center; font-size: 24px; border: none; cursor: pointer; 
            transition: all 0.2s ease; box-shadow: 0 4px 10px rgba(0,0,0,0.15); z-index: 10;
        }
        .circle-btn:active { transform: scale(0.9); }
        .circle-btn:hover { transform: translateY(-3px); box-shadow: 0 6px 15px rgba(0,0,0,0.2); }
        
        #micBtn { background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%); color: white;}
        #micBtn.recording { animation: pulse 1.5s infinite; }
        @keyframes pulse {
            0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 65, 108, 0.7); }
            70% { transform: scale(1.1); box-shadow: 0 0 0 15px rgba(255, 65, 108, 0); }
            100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 65, 108, 0); }
        }

        .input-container { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 20px; position: relative;}
        input[type="text"] { 
            padding: 16px 25px; font-size: 16px; border-radius: 30px; border: 1px solid #bdc3c7; width: 65%; max-width: 600px; 
            outline: none; transition: all 0.3s; box-shadow: inset 0 2px 5px rgba(0,0,0,0.03); background: rgba(255,255,255,0.9);
        }
        input[type="text"]:focus { border-color: #3498db; background: white; box-shadow: 0 0 10px rgba(52, 152, 219, 0.2);}
        button.send-btn { 
            padding: 14px 30px; font-size: 16px; border-radius: 30px; border: none; color: white; cursor: pointer; font-weight: bold;
            background: linear-gradient(135deg, #36D1DC 0%, #5B86E5 100%); box-shadow: 0 4px 10px rgba(91, 134, 229, 0.3);
            transition: all 0.3s ease;
        }
        button.send-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(91, 134, 229, 0.4); }

        #audioControls { display: none; justify-content: center; align-items: center; gap: 15px; margin-top: 20px; background: rgba(255,255,255,0.9); padding: 10px 20px; border-radius: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); width: fit-content; margin-left: auto; margin-right: auto; }
        .control-btn { background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); color: white; width: 45px; height: 45px; font-size: 18px;}
        .download-btn { background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%); color: white; width: 45px; height: 45px; font-size: 18px;}

        /* صندوق المحادثة - تم تكبيره واستيعابه للنصوص الطويلة */
        #chatBox { 
            width: 95%; max-width: 950px; margin: 30px auto; background: rgba(255, 255, 255, 0.95); padding: 30px; 
            border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); height: 60vh; max-height: 700px; overflow-y: auto; 
            display: flex; flex-direction: column; gap: 15px; border-top: 5px solid #3498db; scroll-behavior: smooth;
        }
        
        .chat-bubble { max-width: 85%; padding: 18px 22px; border-radius: 20px; position: relative; font-size: 17px; line-height: 1.6; animation: fadeSlideUp 0.4s ease-out;}
        .user-bubble { background: linear-gradient(135deg, #E2E2E2 0%, #C9D6FF 100%); color: #2c3e50; align-self: flex-start; border-bottom-left-radius: 5px; text-align: left; direction: ltr;}
        .ai-bubble { background: linear-gradient(135deg, #ffffff 0%, #f1f2f6 100%); border: 1px solid #e0e0e0; color: #2c3e50; align-self: flex-end; border-bottom-right-radius: 5px; text-align: right; box-shadow: 0 4px 8px rgba(0,0,0,0.04);}
        
        .english-text { font-size: 22px; font-weight: bold; color: #2c3e50; direction: ltr; text-align: left; margin-bottom: 12px;}
        .arabic-translation { color: #7f8c8d; font-size: 16px; border-top: 1px dashed #bdc3c7; padding-top: 10px;}
        .structured-data { color: #34495e; font-size: 14px; background-color: #f8f9fa; padding: 12px 15px; border-radius: 10px; margin-top: 12px; text-align: left; direction: ltr; border-left: 4px solid #3498db;}
        .section-title { font-size: 12px; font-weight: bold; color: #7f8c8d; text-transform: uppercase; margin-bottom: 5px; display: block;}
        
        .word { display: inline-block; margin-right: 6px; color: #95a5a6; transition: color 0.1s ease-in; }
        .word.active { color: #e74c3c; transform: scale(1.15); font-weight: 900;}
        .word.spoken { color: #2c3e50; }

        /* القائمة العائمة (Floating Menu) */
        .floating-menu {
            position: fixed; right: 20px; top: 50%; transform: translateY(-50%);
            display: flex; flex-direction: column; gap: 12px; z-index: 1000;
        }
        .float-btn {
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); color: white; border: none; border-radius: 50px;
            padding: 12px 20px; font-size: 14px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            transition: all 0.3s ease; display: flex; align-items: center; justify-content: center; gap: 8px;
            opacity: 0; animation: slideInRight 0.5s ease-out forwards;
        }
        .float-btn:hover { transform: scale(1.05) translateX(-5px); box-shadow: 0 6px 20px rgba(0,0,0,0.3); background: linear-gradient(135deg, #2980b9 0%, #2471a3 100%);}
        
        /* تلوين أزرار القائمة بشكل مختلف لتسهيل التعرف عليها */
        .float-btn:nth-child(1) { animation-delay: 0.2s; background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);} /* الخطة */
        .float-btn:nth-child(2) { animation-delay: 0.3s; background: linear-gradient(135deg, #f12711 0%, #f5af19 100%);} /* الاختبارات */
        .float-btn:nth-child(3) { animation-delay: 0.4s; background: linear-gradient(135deg, #8E2DE2 0%, #4A00E0 100%);} /* قصة طويلة */
        .float-btn:nth-child(4) { animation-delay: 0.5s; background: linear-gradient(135deg, #FF416C 0%, #FF4B2B 100%);} /* محادثة طويلة */
        .float-btn:nth-child(5) { animation-delay: 0.6s; background: linear-gradient(135deg, #3a7bd5 0%, #3a6073 100%);} /* تصنيف المواضيع */

        /* تصميم نافذة المواضيع المنبثقة (Modal) */
        .modal { display: none; position: fixed; z-index: 2000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.6); backdrop-filter: blur(5px); }
        .modal-content { background: white; margin: 5vh auto; padding: 25px; border-radius: 15px; width: 85%; max-width: 900px; max-height: 85vh; overflow-y: auto; text-align: right; box-shadow: 0 10px 40px rgba(0,0,0,0.3); animation: popIn 0.4s ease-out;}
        .close-btn { color: #aaa; float: left; font-size: 32px; font-weight: bold; cursor: pointer; transition: color 0.2s;}
        .close-btn:hover { color: #e74c3c; }
        .topics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-top: 15px; }
        .topic-item { background: #f8f9fa; padding: 12px; border-radius: 10px; font-size: 14px; text-align: center; cursor: pointer; transition: all 0.2s; color: #2c3e50; border: 1px solid #dcdde1; font-weight: 600;}
        .topic-item:hover { background: #3498db; color: white; transform: translateY(-3px); box-shadow: 0 4px 10px rgba(52, 152, 219, 0.3);}
        .topic-category { grid-column: 1 / -1; font-size: 18px; font-weight: bold; color: #8e44ad; margin-top: 20px; border-bottom: 2px solid #ecf0f1; padding-bottom: 5px; }

        #audioPlayer { display: none; }
        .bottom-controls { display: flex; flex-direction: column; align-items: center; margin-top: 20px; gap: 10px; padding-top: 20px; width: 80%; max-width: 600px; margin-left: auto; margin-right: auto;}
        .upload-btn { background: transparent; border: 1px dashed #7f8c8d; color: #7f8c8d; padding: 8px 15px; border-radius: 8px; cursor: pointer; font-size: 13px; transition: all 0.2s;}
        .upload-btn:hover { background: #ecf0f1; border-color: #2c3e50; color: #2c3e50; }
        #curriculumStatus { color: #27ae60; font-size: 12px; font-weight: bold; }
        
        /* إخفاء القائمة العائمة في الشاشات الصغيرة وتغيير مكانها */
        @media (max-width: 768px) {
            .floating-menu { position: static; transform: none; flex-direction: row; flex-wrap: wrap; justify-content: center; margin-top: 20px;}
            .float-btn { padding: 10px 15px; font-size: 12px; }
        }
    </style>
</head>
<body>
    <!-- القائمة العائمة للخيارات الأكاديمية والمواضيع -->
    <div class="floating-menu">
        <button class="float-btn" onclick="requestFeature('study_plan')">📅 الخطة الدراسية</button>
        <button class="float-btn" onclick="requestFeature('test')">📝 التدريب والتقييم</button>
        <button class="float-btn" onclick="requestFeature('story')">📖 قراءة قصة طويلة</button>
        <button class="float-btn" onclick="requestFeature('conversation')">🗣️ محادثة طويلة</button>
        <button class="float-btn" onclick="openTopicsModal()">🗂️ تصنيف المواضيع (50+)</button>
    </div>

    <!-- نافذة المواضيع (Modal) -->
    <div id="topicsModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeTopicsModal()">&times;</span>
            <h2 style="color:#2c3e50; text-align:center; margin-bottom: 5px;">اختر موضوعاً للمناقشة 🎯</h2>
            <p style="text-align:center; color:#7f8c8d; font-size:14px;">اضغط على أي موضوع ليبدأ المدرس بشرحه ومناقشته معك فوراً.</p>
            <div class="topics-grid" id="topicsList">
                <!-- سيتم توليد المواضيع هنا عبر الجافاسكريبت -->
            </div>
        </div>
    </div>

    <h2 class="anim-drop">Smart Academy 🎓</h2>
    
    <!-- تم إعادة قسم الروابط كما طلبت -->
    <div class="curriculum-info anim-drop">
        📚 <strong>المنهج المعتمد:</strong> الإطار الأوروبي المرجعي المشترك للغات (CEFR).<br>
        <a href="https://www.coe.int/en/web/common-european-framework-reference-languages" target="_blank">🔗 الموقع الرسمي (مجلس أوروبا)</a>
        <a href="https://www.cambridgeenglish.org/exams-and-tests/cefr/" target="_blank">🔗 دليل المستويات (Cambridge)</a>
    </div>

    <div class="top-bar anim-drop">
        <div class="controls">
            <select id="mode" onchange="changeStyle()">
                <option value="adult">وضع الكبار (احترافي)</option>
                <option value="child">وضع الأطفال (مرح)</option>
            </select>
            <select id="micLang">
                <option value="en-US">إدخال: إنجليزي</option>
                <option value="ar-SA">إدخال: عربي</option>
            </select>
        </div>
        <button class="start-btn" onclick="startLiveLesson()">🎓 ابدأ الدرس والمحادثة</button>
    </div>
    
    <div id="liveIndicator">🔴 جلسة التدريب نشطة: المدرس يستمع إليك...</div>
    
    <div class="input-container anim-up">
        <button id="micBtn" class="circle-btn" onclick="toggleMic()" title="تحدث للرد / قاطع المدرس">🎤</button>
        <input type="text" id="userMsg" placeholder="اضغط ابدأ الدرس، أو اختر من القائمة، أو اكتب هنا...">
        <button class="send-btn" onclick="sendMsg()">إرسال</button>
    </div>

    <div id="audioControls">
        <button class="circle-btn control-btn" onclick="skipAudio(-5)">⏪</button>
        <button id="pauseBtn" class="circle-btn control-btn" onclick="togglePauseAudio()">⏸️</button>
        <button class="circle-btn control-btn" onclick="skipAudio(5)">⏩</button>
        <div style="border-left: 2px solid #ecf0f1; height: 30px; margin: 0 5px;"></div>
        <button class="circle-btn download-btn" onclick="downloadAudio()" title="حفظ الدرس">💾</button>
    </div>
    
    <div id="chatBox" class="anim-pop">
        <div class="chat-bubble ai-bubble">
            <div class="arabic-translation" style="border: none; padding: 0;">مرحباً بك في أكاديميتك الذكية! الواجهة الآن أوسع ومستعدة لعرض المناهج والقصص الطويلة. يمكنك البدء من القائمة الجانبية أو الضغط على زر البدء.</div>
        </div>
    </div>
    
    <audio id="audioPlayer"></audio>

    <div class="bottom-controls anim-up">
        <button class="upload-btn" onclick="triggerUpload()">📂 إدراج منهج مخصص (ملف TXT)</button>
        <input type="file" id="fileUpload" accept=".txt" style="display: none;" onchange="handleFileUpload(event)">
        <div id="curriculumStatus"></div>
    </div>

    <script>
        let isRecording = false;
        let recognition;
        let customCurriculumContent = "";
        let wordsElements = [];
        let isLiveMode = false; 
        let silenceTimer;
        let final_transcript = '';
        let chatHistory = [];
        let isTeacherSpeaking = false;

        // مكتبة الـ 50 موضوع مقسمة لتصنيفات
        const topicsLibrary = {
            "📱 تكنولوجيا واتصالات": ["شبكات 5G", "الذكاء الاصطناعي في حياتنا", "الأمن السيبراني", "تطور الهواتف الذكية", "إنترنت الأشياء", "الحوسبة السحابية", "الواقع الافتراضي", "الألياف الضوئية", "تأثير السوشيال ميديا", "الروبوتات والمستقبل"],
            "⚽ رياضة ولياقة": ["تكتيكات كرة القدم", "تاريخ الألعاب الأولمبية", "أساسيات كرة السلة", "بطولات التنس الكبرى", "الرياضات الإلكترونية (E-Sports)", "سباقات فورمولا 1", "فوائد السباحة", "الفنون القتالية", "رياضة الجري والماراثون", "الرياضات العنيفة والمغامرات"],
            "🌍 علوم وطبيعة": ["استكشاف الفضاء", "التغير المناخي", "الحياة البحرية", "الطاقة المتجددة", "جسم الإنسان والطب", "علم الوراثة والجينات", "علم الفلك والنجوم", "غابات الأمازون", "الزلازل والبراكين", "الفيزياء الكمية (مبسطة)"],
            "✈️ سفر وثقافات": ["الحضارة المصرية القديمة", "الثقافة اليابانية", "السفر بميزانية محدودة", "أشهر المطابخ العالمية", "عجائب الدنيا السبع", "أهمية تعلم لغات جديدة", "مهرجانات غريبة حول العالم", "حياة البدو والصحراء", "مغامرات تسلق الجبال", "العيش في مدن أجنبية"],
            "💼 حياة وعمل": ["مقابلات العمل", "إدارة الوقت", "الأكل الصحي والنظام الغذائي", "الثقافة المالية والادخار", "العمل عن بعد", "التحدث أمام الجمهور", "الصحة النفسية", "بدء مشروع تجاري", "الهوايات والمهارات اليدوية", "المدينة مقابل الريف"]
        };

        // توليد واجهة المواضيع في الـ Modal
        function populateTopics() {
            let container = document.getElementById("topicsList");
            for (const [category, topics] of Object.entries(topicsLibrary)) {
                let catDiv = document.createElement("div");
                catDiv.className = "topic-category";
                catDiv.innerText = category;
                container.appendChild(catDiv);
                
                topics.forEach(topic => {
                    let btn = document.createElement("div");
                    btn.className = "topic-item";
                    btn.innerText = topic;
                    btn.onclick = () => {
                        closeTopicsModal();
                        sendMsg(`Let's discuss this topic comprehensively: ${topic}. Give me interesting facts, vocabulary, and ask me a question about it.`);
                    };
                    container.appendChild(btn);
                });
            }
        }
        // استدعاء الدالة عند تحميل الصفحة
        populateTopics();

        function openTopicsModal() { document.getElementById("topicsModal").style.display = "block"; }
        function closeTopicsModal() { document.getElementById("topicsModal").style.display = "none"; }
        
        // إغلاق النافذة عند الضغط خارجها
        window.onclick = function(event) {
            let modal = document.getElementById("topicsModal");
            if (event.target == modal) { modal.style.display = "none"; }
        }

        function changeStyle() {
            let mode = document.getElementById("mode").value;
            let chatBox = document.getElementById("chatBox");
            if(mode === "child") {
                document.body.style.background = "linear-gradient(135deg, #ff9a9e 0%, #fecfef 99%, #fecfef 100%)";
                chatBox.style.borderTopColor = "#ff6b81";
            } else {
                document.body.style.background = "linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)";
                chatBox.style.borderTopColor = "#3498db";
            }
        }

        async function startLiveLesson() {
            try {
                window.localStream = await navigator.mediaDevices.getUserMedia({
                    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
                });
            } catch (e) {}

            isLiveMode = true;
            document.getElementById("liveIndicator").style.display = "block";
            final_transcript = '';
            
            if (!isRecording && recognition) {
                recognition.lang = document.getElementById("micLang").value; 
                try { recognition.start(); } catch(e) {}
            }
            sendMsg("Hello! I am ready. Please introduce yourself and ask me the first question.");
        }

        // معالجة الأزرار الجانبية
        function requestFeature(type) {
            let prompt = "";
            if(type === 'study_plan') prompt = "I need a comprehensive study plan tailored to my level based on CEFR. Please suggest one in detail.";
            if(type === 'test') prompt = "Please give me a short test, exercise, or evaluation to check my current English skills.";
            if(type === 'story') prompt = "Tell me a long, engaging story in English. Use advanced vocabulary and provide the moral of the story. Ensure the response is long enough to fill the screen.";
            if(type === 'conversation') prompt = "Let's start a long, deep roleplay conversation about a professional workplace scenario. You start with a long opening scenario.";
            sendMsg(prompt);
        }

        function triggerUpload() {
            if(confirm("تحذير: يمنع رفع مواد تخالف الشريعة أو حقوق الملكية. موافق؟")) { document.getElementById("fileUpload").click(); }
        }
        function handleFileUpload(event) {
            let file = event.target.files[0];
            if (!file) return;
            let reader = new FileReader();
            reader.onload = function(e) {
                customCurriculumContent = e.target.result;
                document.getElementById("curriculumStatus").innerText = "✅ تم دمج المنهج في ذاكرة المعلم.";
            };
            reader.readAsText(file);
            event.target.value = '';
        }

        function skipAudio(seconds) {
            let audioPlayer = document.getElementById("audioPlayer");
            if (audioPlayer.src) audioPlayer.currentTime += seconds;
        }

        function downloadAudio() {
            let audioPlayer = document.getElementById("audioPlayer");
            if (!audioPlayer.src) return;
            let a = document.createElement("a");
            a.href = audioPlayer.src;
            a.download = "SmartAcademy_Audio.mp3"; 
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }

        function togglePauseAudio() {
            let audioPlayer = document.getElementById("audioPlayer");
            let pauseBtn = document.getElementById("pauseBtn");
            if(audioPlayer.src === "") return;
            if (audioPlayer.paused) { audioPlayer.play(); pauseBtn.innerText = "⏸️"; } 
            else { audioPlayer.pause(); pauseBtn.innerText = "▶️"; }
        }

        let audioPlayer = document.getElementById("audioPlayer");
        audioPlayer.ontimeupdate = function() {
            if (wordsElements.length === 0 || isNaN(audioPlayer.duration)) return;
            let progress = audioPlayer.currentTime / audioPlayer.duration;
            let activeIndex = Math.floor(progress * wordsElements.length);
            
            wordsElements.forEach((span, i) => {
                if (i === activeIndex) {
                    span.classList.add("active"); span.classList.remove("spoken");
                } else if (i < activeIndex) {
                    span.classList.remove("active"); span.classList.add("spoken");
                } else {
                    span.classList.remove("active", "spoken");
                }
            });
        };

        audioPlayer.onended = function() {
            isTeacherSpeaking = false;
            document.getElementById("pauseBtn").innerText = "▶️";
            wordsElements.forEach(span => { span.classList.remove("active"); span.classList.add("spoken"); });
            
            if (isLiveMode) {
                setTimeout(() => {
                    document.getElementById("userMsg").placeholder = "المدرس يستمع إليك... تحدث الآن";
                    try { recognition.start(); } catch(e) {}
                }, 300);
            }
        };

        function initSpeechRecognition() {
            window.SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (window.SpeechRecognition) {
                recognition = new window.SpeechRecognition();
                recognition.continuous = true; 
                recognition.interimResults = true; 
                
                recognition.onstart = function() {
                    isRecording = true;
                    document.getElementById("micBtn").classList.add("recording");
                };

                recognition.onresult = function(event) {
                    if(isTeacherSpeaking) return;

                    let interim_transcript = '';
                    for (let i = event.resultIndex; i < event.results.length; ++i) {
                        if (event.results[i].isFinal) {
                            final_transcript += event.results[i][0].transcript + " ";
                        } else {
                            interim_transcript += event.results[i][0].transcript;
                        }
                    }
                    
                    let currentSpeech = (final_transcript + interim_transcript).trim();
                    
                    if (currentSpeech.length > 0) {
                        document.getElementById("userMsg").value = currentSpeech;
                        
                        clearTimeout(silenceTimer);
                        silenceTimer = setTimeout(() => {
                            if (isLiveMode && currentSpeech.length > 0) {
                                sendMsg(); 
                            }
                        }, 2500); 
                    }
                };
                
                recognition.onend = function() { 
                    isRecording = false;
                    document.getElementById("micBtn").classList.remove("recording");
                    
                    if (isLiveMode && !isTeacherSpeaking) {
                        try { recognition.start(); } catch(e) {}
                    } else if (isTeacherSpeaking) {
                        document.getElementById("userMsg").placeholder = "المدرس يتحدث الآن... (اضغط الميكروفون للمقاطعة)";
                    } else {
                        document.getElementById("userMsg").placeholder = "اكتب رسالتك هنا أو اختر موضوعاً...";
                    }
                };
                return true;
            }
            return false;
        }

        let isSpeechSupported = initSpeechRecognition();

        async function toggleMic() {
            if (!isSpeechSupported) return alert("المتصفح لا يدعم الميكروفون.");
            
            if (isTeacherSpeaking && !audioPlayer.paused) {
                audioPlayer.pause();
                isTeacherSpeaking = false;
                document.getElementById("pauseBtn").innerText = "▶️";
                wordsElements.forEach(span => span.classList.add("spoken"));
                
                isLiveMode = true;
                final_transcript = '';
                document.getElementById("liveIndicator").style.display = "block";
                document.getElementById("userMsg").placeholder = "تمت المقاطعة. المدرس يستمع إليك الآن...";
                recognition.lang = document.getElementById("micLang").value; 
                try { recognition.start(); } catch(e) {}
                return;
            }

            if (isLiveMode || isRecording) {
                isLiveMode = false;
                if(isRecording) recognition.stop();
                document.getElementById("liveIndicator").style.display = "none";
                document.getElementById("userMsg").placeholder = "اكتب رسالتك هنا...";
                if(window.localStream) {
                    window.localStream.getTracks().forEach(track => track.stop());
                }
            } else {
                try {
                    window.localStream = await navigator.mediaDevices.getUserMedia({
                        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
                    });
                } catch (e) {}

                isLiveMode = true;
                final_transcript = '';
                document.getElementById("liveIndicator").style.display = "block";
                document.getElementById("userMsg").placeholder = "الميكروفون نشط.. تحدث للرد أو المقاطعة.";
                recognition.lang = document.getElementById("micLang").value; 
                try { recognition.start(); } catch(e) {}
            }
        }

        document.getElementById("userMsg").addEventListener("keypress", function(event) {
            if (event.key === "Enter") { event.preventDefault(); sendMsg(); }
        });

        function appendUserBubble(text) {
            let box = document.getElementById("chatBox");
            let div = document.createElement("div");
            div.className = "chat-bubble user-bubble";
            div.innerText = text;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }

        function appendAIBubble(data) {
            let box = document.getElementById("chatBox");
            let container = document.createElement("div");
            container.className = "chat-bubble ai-bubble";
            
            let engDiv = document.createElement("div");
            engDiv.className = "english-text";
            let words = data.english.split(" ");
            wordsElements = [];
            words.forEach(word => {
                let span = document.createElement("span");
                span.className = "word";
                span.innerText = word;
                engDiv.appendChild(span);
                wordsElements.push(span);
            });
            container.appendChild(engDiv);

            let arDiv = document.createElement("div");
            arDiv.className = "arabic-translation";
            arDiv.innerText = data.arabic;
            container.appendChild(arDiv);

            let detailsHTML = "";
            if(data.keywords) detailsHTML += `<div class="structured-data"><span class="section-title">🔑 كلمات مفتاحية (Keywords):</span><br>${data.keywords}</div>`;
            if(data.summary) detailsHTML += `<div class="structured-data"><span class="section-title">📝 ملخص / ملاحظات:</span><br>${data.summary}</div>`;
            
            if (detailsHTML !== "") {
                let detailsDiv = document.createElement("div");
                detailsDiv.innerHTML = detailsHTML;
                container.appendChild(detailsDiv);
            }

            box.appendChild(container);
            
            // التمرير السلس للأسفل
            setTimeout(() => {
                box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' });
            }, 100);
        }

        async function sendMsg(overrideMsg = null) {
            let inputField = document.getElementById("userMsg");
            let msg = overrideMsg || inputField.value;
            let mode = document.getElementById("mode").value;
            let controlsDiv = document.getElementById("audioControls");
            
            if(!msg.trim()) return;
            
            appendUserBubble(msg);
            chatHistory.push({"role": "user", "content": msg});
            
            final_transcript = '';
            clearTimeout(silenceTimer);
            audioPlayer.pause();
            controlsDiv.style.display = "none";
            inputField.value = ""; 
            
            let box = document.getElementById("chatBox");
            let loadingDiv = document.createElement("div");
            loadingDiv.className = "chat-bubble ai-bubble";
            loadingDiv.id = "loadingBubble";
            loadingDiv.innerHTML = "<div class='arabic-translation' style='border:none;'>جاري تجهيز المحتوى والرد... ⏳</div>";
            box.appendChild(loadingDiv);
            box.scrollTop = box.scrollHeight;
            
            try {
                let res = await fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ 
                        history: chatHistory.slice(-10), // الاحتفاظ بآخر 10 رسائل في الذاكرة
                        mode: mode, 
                        custom_curriculum: customCurriculumContent 
                    })
                });
                
                let data = await res.json();
                
                let loadBub = document.getElementById("loadingBubble");
                if(loadBub) loadBub.remove();

                if(data.error) { alert("⚠️ خطأ: " + data.error); return; }
                
                chatHistory.push({"role": "assistant", "content": data.english});
                appendAIBubble(data);
                
                if(data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    controlsDiv.style.display = "flex";
                    document.getElementById("pauseBtn").innerText = "⏸️";
                    
                    isTeacherSpeaking = true;
                    if(isRecording) { recognition.stop(); }
                    document.getElementById("userMsg").placeholder = "المدرس يتحدث الآن... (اضغط الميكروفون للمقاطعة)";
                    
                    audioPlayer.play();
                }
            } catch (e) {
                let loadBub = document.getElementById("loadingBubble");
                if(loadBub) loadBub.remove();
                alert("⚠️ حدث خطأ في الاتصال بالسيرفر.");
            }
        }
        changeStyle();
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
        1. MUST STRICTLY adhere to Islamic Sharia and local laws. NO mentions of alcohol, dating, gambling, explicit content, pork, or illegal activities.
        2. Base language progression on the CEFR.
        3. YOU ARE A REAL HUMAN TUTOR. REMEMBER the conversation context.
        4. If the user asks for a 'Long Story', 'Long Conversation', or a 'Specific Topic', provide a detailed, comprehensive response in English that is sufficiently long, informative, and engaging. 
        """
        
        if custom_curriculum:
            core_rules += f"\\n5. Incorporate this provided curriculum text into your teaching: {custom_curriculum[:1500]}"

        json_structure = '''
        Respond ONLY in valid JSON format with exactly these keys:
        {
            "english": "Your spoken English response (Can be a long story, long discussion about a topic, or standard chat).",
            "arabic": "الترجمة العربية الوافية للرسالة الإنجليزية",
            "keywords": "5-8 key vocabulary words from this message in English and Arabic",
            "summary": "ملخص أو خطة دراسية أو ملاحظة للمتعلم باللغة العربية. اتركها فارغة إذا لم تكن ضرورية."
        }
        '''

        if mode == "child":
            sys_msg = core_rules + "\\nYou are a fun English teacher for kids. Make stories/topics exciting and relatively simple." + json_structure
            voice_model = "en-US-AnaNeural"
        else:
            sys_msg = core_rules + "\\nYou are a professional English coach for adults. Provide in-depth stories, advanced topics, and sophisticated conversations." + json_structure
            voice_model = "en-US-GuyNeural"

        messages = [{"role": "system", "content": sys_msg}]
        for h in history:
            messages.append({"role": h["role"], "content": h["content"]})

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        reply_content = completion.choices[0].message.content
        
        try:
            parsed_reply = json.loads(reply_content)
            eng_text = parsed_reply.get("english", "Hello! Let's continue.")
            ar_text = parsed_reply.get("arabic", "مرحباً! دعنا نكمل.")
            keywords = parsed_reply.get("keywords", "")
            summary = parsed_reply.get("summary", "")
        except Exception:
            eng_text = "Sorry, error parsing response. Shall we try again?"
            ar_text = "عذراً، حدث خطأ. هل نجرب مرة أخرى؟"
            keywords = summary = ""
        
        audio_base64 = asyncio.run(generate_audio(eng_text, voice_model))

        return jsonify({
            "english": eng_text, 
            "arabic": ar_text, 
            "keywords": keywords,
            "summary": summary,
            "audio": audio_base64
        })
    
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
