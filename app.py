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
            text-align: center; 
            margin: 0; 
            padding: 20px; 
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            min-height: 100vh;
        }
        h2 { color: #2c3e50; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); margin-bottom: 5px; }
        
        .curriculum-info {
            background-color: rgba(255, 255, 255, 0.8); border: 1px solid #bde0ec; border-radius: 12px; padding: 12px;
            width: 80%; max-width: 600px; margin: 10px auto 20px auto; font-size: 14px; color: #2c3e50; text-align: right; line-height: 1.6;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }
        .curriculum-info a { color: #2980b9; text-decoration: none; font-weight: bold; margin-left: 10px; }

        .top-bar { display: flex; justify-content: center; align-items: center; width: 80%; max-width: 600px; margin: 0 auto 15px auto; gap: 15px;}
        .controls { display: flex; gap: 10px; }
        select { padding: 8px 12px; font-size: 14px; border-radius: 8px; border: 1px solid #bdc3c7; outline: none; cursor: pointer; background: white;}
        
        .start-btn { 
            background: linear-gradient(135deg, #8e44ad 0%, #9b59b6 100%); font-weight: bold; padding: 10px 20px; font-size: 15px;
            border-radius: 8px; border: none; color: white; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 10px rgba(142, 68, 173, 0.3);
        }
        .start-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(142, 68, 173, 0.4); }
        
        #liveIndicator { display: none; color: #e74c3c; font-weight: bold; font-size: 15px; margin-top: 10px; animation: blink 1.5s infinite; }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }

        /* تجميل أزرار الصوت والميكروفون */
        .circle-btn {
            border-radius: 50%; width: 50px; height: 50px; padding: 0; 
            display: flex; justify-content: center; align-items: center; font-size: 22px; border: none; cursor: pointer; 
            transition: all 0.2s ease; box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }
        .circle-btn:active { transform: scale(0.9); }
        .circle-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0,0,0,0.2); }
        
        #micBtn { background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%); color: white;}
        #micBtn.recording { animation: pulse 1.5s infinite; }
        @keyframes pulse {
            0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 65, 108, 0.7); }
            70% { transform: scale(1.1); box-shadow: 0 0 0 15px rgba(255, 65, 108, 0); }
            100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 65, 108, 0); }
        }

        .input-container { display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 20px; }
        input[type="text"] { 
            padding: 14px 20px; font-size: 16px; border-radius: 25px; border: 1px solid #bdc3c7; width: 60%; max-width: 500px; 
            outline: none; transition: border-color 0.3s; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
        }
        input[type="text"]:focus { border-color: #3498db; }
        button.send-btn { 
            padding: 12px 25px; font-size: 16px; border-radius: 25px; border: none; color: white; cursor: pointer;
            background: linear-gradient(135deg, #36D1DC 0%, #5B86E5 100%); box-shadow: 0 4px 10px rgba(91, 134, 229, 0.3);
            transition: all 0.3s ease;
        }
        button.send-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 15px rgba(91, 134, 229, 0.4); }

        #audioControls { display: none; justify-content: center; align-items: center; gap: 15px; margin-top: 20px; background: rgba(255,255,255,0.9); padding: 10px 20px; border-radius: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); width: fit-content; margin-left: auto; margin-right: auto; }
        .control-btn { background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); color: white; width: 45px; height: 45px; font-size: 18px;}
        .download-btn { background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: #2c3e50; width: 45px; height: 45px; font-size: 18px;}

        /* تنسيق صندوق المحادثة الجديد (Chat History) */
        #chatBox { 
            width: 85%; max-width: 700px; margin: 30px auto; background: rgba(255, 255, 255, 0.95); padding: 25px; 
            border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); height: 400px; overflow-y: auto; 
            display: flex; flex-direction: column; gap: 15px; border-top: 5px solid #3498db; scroll-behavior: smooth;
        }
        
        .chat-bubble { max-width: 80%; padding: 15px 20px; border-radius: 20px; position: relative; font-size: 16px; line-height: 1.5; animation: fadeIn 0.3s ease-in;}
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        .user-bubble { background: linear-gradient(135deg, #E2E2E2 0%, #C9D6FF 100%); color: #2c3e50; align-self: flex-start; border-bottom-left-radius: 5px; text-align: left; direction: ltr;}
        .ai-bubble { background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); border: 1px solid #e0e0e0; color: #2c3e50; align-self: flex-end; border-bottom-right-radius: 5px; text-align: right; box-shadow: 0 4px 6px rgba(0,0,0,0.02);}
        
        .english-text { font-size: 22px; font-weight: bold; color: #2c3e50; direction: ltr; text-align: left; margin-bottom: 8px;}
        .arabic-translation { color: #7f8c8d; font-size: 15px; border-top: 1px dashed #bdc3c7; padding-top: 8px;}
        .structured-data { color: #34495e; font-size: 13px; background-color: #f0f4f8; padding: 8px 12px; border-radius: 8px; margin-top: 10px; text-align: left; direction: ltr;}
        .section-title { font-size: 11px; font-weight: bold; color: #7f8c8d; text-transform: uppercase;}
        
        .word { display: inline-block; margin-right: 5px; color: #95a5a6; transition: color 0.1s ease-in; }
        .word.active { color: #e74c3c; transform: scale(1.1); font-weight: 900;}
        .word.spoken { color: #2c3e50; }

        /* القائمة العائمة (Floating Menu) */
        .floating-menu {
            position: fixed; right: 20px; top: 50%; transform: translateY(-50%);
            display: flex; flex-direction: column; gap: 15px; z-index: 1000;
        }
        .float-btn {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; border: none; border-radius: 50px;
            padding: 15px 20px; font-size: 14px; font-weight: bold; cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            transition: all 0.3s ease; display: flex; align-items: center; gap: 8px;
        }
        .float-btn:hover { transform: scale(1.05) translateX(-5px); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }
        .float-btn.test-btn { background: linear-gradient(135deg, #f12711 0%, #f5af19 100%); }

        #audioPlayer { display: none; }
        .bottom-controls { display: flex; flex-direction: column; align-items: center; margin-top: 20px; gap: 10px; padding-top: 20px; width: 80%; max-width: 600px; margin-left: auto; margin-right: auto;}
        .upload-btn { background: transparent; border: 1px dashed #7f8c8d; color: #7f8c8d; padding: 8px 15px; border-radius: 8px; cursor: pointer; font-size: 13px; transition: all 0.2s;}
        .upload-btn:hover { background: #ecf0f1; border-color: #2c3e50; color: #2c3e50; }
        #curriculumStatus { color: #27ae60; font-size: 12px; font-weight: bold; }
    </style>
</head>
<body>
    <!-- القائمة العائمة الجديدة -->
    <div class="floating-menu">
        <button class="float-btn" onclick="requestStudyPlan()">📅 الخطة الدراسية</button>
        <button class="float-btn test-btn" onclick="requestEvaluation()">📝 التدريبات والتقييم</button>
    </div>

    <h2>المدرس الذكي 🎓</h2>
    
    <div class="curriculum-info">
        📚 <strong>المنهج المعتمد:</strong> الإطار الأوروبي المرجعي المشترك للغات (CEFR).<br>
    </div>

    <div class="top-bar">
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
    
    <div id="liveIndicator">🔴 جلسة التدريب نشطة: المدرس يستمع إليك دائماً.. (تحدث بحرية)</div>
    
    <div class="input-container">
        <button id="micBtn" class="circle-btn" onclick="toggleMic()" title="الميكروفون للمقاطعة">🎤</button>
        <input type="text" id="userMsg" placeholder="اضغط ابدأ الدرس أو اكتب رسالتك هنا...">
        <button class="send-btn" onclick="sendMsg()">إرسال</button>
    </div>

    <div id="audioControls">
        <button class="circle-btn control-btn" onclick="skipAudio(-5)">⏪</button>
        <button id="pauseBtn" class="circle-btn control-btn" onclick="togglePauseAudio()">⏸️</button>
        <button class="circle-btn control-btn" onclick="skipAudio(5)">⏩</button>
        <div style="border-left: 2px solid #ecf0f1; height: 30px; margin: 0 5px;"></div>
        <button class="circle-btn download-btn" onclick="downloadAudio()" title="حفظ الدرس">💾</button>
    </div>
    
    <!-- صندوق المحادثة التراكمي -->
    <div id="chatBox">
        <div class="chat-bubble ai-bubble">
            <div class="arabic-translation" style="border: none; padding: 0;">مرحباً! اضغط على "ابدأ الدرس" أو اختر من القائمة العائمة لتبدأ...</div>
        </div>
    </div>
    
    <audio id="audioPlayer"></audio>

    <div class="bottom-controls">
        <button class="upload-btn" onclick="triggerUpload()">📂 إدراج منهج مخصص (TXT)</button>
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
        
        // ذاكرة المحادثة الجديدة
        let chatHistory = [];

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

        // أوامر القائمة العائمة
        function requestStudyPlan() {
            sendMsg("I need a comprehensive study plan tailored to my level based on CEFR. Please suggest one.");
        }
        function requestEvaluation() {
            sendMsg("Please give me a short test, exercise, or evaluation to check my current English skills.");
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
            document.getElementById("pauseBtn").innerText = "▶️";
            wordsElements.forEach(span => { span.classList.remove("active"); span.classList.add("spoken"); });
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
                        if (!audioPlayer.paused) {
                            audioPlayer.pause();
                            document.getElementById("pauseBtn").innerText = "▶️";
                            wordsElements.forEach(span => span.classList.add("spoken"));
                        }
                        
                        document.getElementById("userMsg").value = currentSpeech;
                        
                        clearTimeout(silenceTimer);
                        silenceTimer = setTimeout(() => {
                            if (isLiveMode && currentSpeech.length > 0) {
                                sendMsg(); 
                            }
                        }, 2500); 
                    }
                };
                
                recognition.onerror = function(event) {};
                
                recognition.onend = function() { 
                    if (isLiveMode) {
                        try { recognition.start(); } catch(e) {}
                    } else {
                        isRecording = false;
                        document.getElementById("micBtn").classList.remove("recording");
                    }
                };
                return true;
            }
            return false;
        }

        let isSpeechSupported = initSpeechRecognition();

        async function toggleMic() {
            if (!isSpeechSupported) return alert("المتصفح لا يدعم الميكروفون.");
            
            if (isLiveMode || isRecording) {
                isLiveMode = false;
                isRecording = false;
                recognition.stop();
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
            
            // النص الإنجليزي (مع إعداد التزامن)
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

            // الترجمة العربية
            let arDiv = document.createElement("div");
            arDiv.className = "arabic-translation";
            arDiv.innerText = data.arabic;
            container.appendChild(arDiv);

            // البنية الإضافية (خطة، كلمات، الخ)
            let detailsHTML = "";
            if(data.keywords) detailsHTML += `<div class="structured-data"><span class="section-title">🔑 Keywords:</span><br>${data.keywords}</div>`;
            if(data.summary) detailsHTML += `<div class="structured-data"><span class="section-title">📝 Summary/Plan:</span><br>${data.summary}</div>`;
            
            if (detailsHTML !== "") {
                let detailsDiv = document.createElement("div");
                detailsDiv.innerHTML = detailsHTML;
                container.appendChild(detailsDiv);
            }

            box.appendChild(container);
            box.scrollTop = box.scrollHeight;
        }

        async function sendMsg(overrideMsg = null) {
            let inputField = document.getElementById("userMsg");
            let msg = overrideMsg || inputField.value;
            let mode = document.getElementById("mode").value;
            let controlsDiv = document.getElementById("audioControls");
            
            if(!msg.trim()) return;
            
            // إضافة رسالة المستخدم للواجهة والذاكرة
            appendUserBubble(msg);
            chatHistory.push({"role": "user", "content": msg});
            
            final_transcript = '';
            clearTimeout(silenceTimer);
            audioPlayer.pause();
            controlsDiv.style.display = "none";
            inputField.value = ""; 
            
            // فقاعة انتظار
            let box = document.getElementById("chatBox");
            let loadingDiv = document.createElement("div");
            loadingDiv.className = "chat-bubble ai-bubble";
            loadingDiv.id = "loadingBubble";
            loadingDiv.innerHTML = "<div class='arabic-translation' style='border:none;'>جاري التفكير وتجهيز الرد...</div>";
            box.appendChild(loadingDiv);
            box.scrollTop = box.scrollHeight;
            
            try {
                let res = await fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    // إرسال آخر 8 رسائل فقط للحفاظ على الذاكرة
                    body: JSON.stringify({ 
                        history: chatHistory.slice(-8), 
                        mode: mode, 
                        custom_curriculum: customCurriculumContent 
                    })
                });
                
                let data = await res.json();
                
                // إزالة فقاعة الانتظار
                let loadBub = document.getElementById("loadingBubble");
                if(loadBub) loadBub.remove();

                if(data.error) { 
                    alert("⚠️ خطأ: " + data.error); 
                    return; 
                }
                
                // حفظ رد المدرس في الذاكرة
                chatHistory.push({"role": "assistant", "content": data.english});
                
                // عرض فقاعة المدرس
                appendAIBubble(data);
                
                if(data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    controlsDiv.style.display = "flex";
                    document.getElementById("pauseBtn").innerText = "⏸️";
                    audioPlayer.play();
                }
            } catch (e) {
                let loadBub = document.getElementById("loadingBubble");
                if(loadBub) loadBub.remove();
                alert("⚠️ حدث خطأ في الاتصال.");
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
        3. YOU ARE A REAL HUMAN TUTOR. ENGAGE IN A CONTINUOUS BACK-AND-FORTH CONVERSATION. 
        4. REMEMBER the conversation context provided in the messages.
        5. If the user asks for a 'Study Plan' or 'Test/Exercise', provide it clearly within the JSON output.
        """
        
        if custom_curriculum:
            core_rules += f"\\n6. Incorporate this provided curriculum text into your teaching: {custom_curriculum[:1500]}"

        json_structure = '''
        Respond ONLY in valid JSON format with exactly these keys:
        {
            "english": "Your spoken English response. (Ask a question if it's a normal chat, or provide the test/plan in English).",
            "arabic": "الترجمة العربية للرسالة السابقة",
            "keywords": "3-5 key vocabulary words from this message",
            "summary": "إذا طلب الطالب خطة دراسية أو تقييم، اكتب الملخص أو التعليمات هنا بالعربية. وإلا اتركها فارغة."
        }
        '''

        if mode == "child":
            sys_msg = core_rules + "\\nYou are a fun English teacher for kids. Keep 'english' simple." + json_structure
            voice_model = "en-US-AnaNeural"
        else:
            sys_msg = core_rules + "\\nYou are a professional English coach for adults." + json_structure
            voice_model = "en-US-GuyNeural"

        # بناء الرسائل شاملة الذاكرة
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
