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
    <title>المدرس الذكي</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            text-align: center; 
            margin: 0; 
            padding: 20px; 
            background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
            min-height: 100vh;
        }
        h2 { color: #2c3e50; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); margin-bottom: 5px; }
        
        .curriculum-info {
            background-color: #e8f4f8;
            border: 1px solid #bde0ec;
            border-radius: 8px;
            padding: 12px;
            width: 80%;
            max-width: 600px;
            margin: 10px auto 20px auto;
            font-size: 14px;
            color: #2c3e50;
            text-align: right;
            line-height: 1.6;
        }
        .curriculum-info a { color: #2980b9; text-decoration: none; font-weight: bold; margin-left: 10px; }
        .curriculum-info a:hover { text-decoration: underline; }

        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 80%;
            max-width: 600px;
            margin: 0 auto 15px auto;
        }
        
        .controls { display: flex; gap: 10px; }
        select { padding: 8px; font-size: 14px; border-radius: 8px; border: 2px solid #3498db; cursor: pointer; }
        
        .upload-section { display: flex; align-items: center; gap: 10px; }
        #uploadBtn { background-color: #27ae60; border-radius: 8px; padding: 8px 12px; font-size: 14px; border: none; color: white; cursor: pointer; display: flex; align-items: center; gap: 5px;}
        #uploadBtn:hover { background-color: #219653; }

        .input-container { display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 20px; }
        input[type="text"] { padding: 12px; font-size: 16px; border-radius: 25px; border: 2px solid #bdc3c7; width: 60%; max-width: 500px; outline: none; }
        button.send-btn { padding: 12px 20px; font-size: 16px; border-radius: 25px; border: none; background-color: #3498db; color: white; cursor: pointer; }
        button.send-btn:hover { background-color: #2980b9; }
        
        .circle-btn {
            border-radius: 50%; width: 45px; height: 45px; padding: 0; 
            display: flex; justify-content: center; align-items: center; font-size: 20px; border: none; cursor: pointer;
        }
        #micBtn { background-color: #e74c3c; color: white;}
        #pauseBtn { background-color: #f39c12; color: white; display: none; }
        
        #chatBox { width: 80%; max-width: 600px; margin: 30px auto; background: white; padding: 25px; border-radius: 15px; box-shadow: 0 10px 20px rgba(0,0,0,0.05); min-height: 150px; text-align: right; border-top: 5px solid #2ecc71; }
        #arabicTranslation { color: #7f8c8d; font-size: 16px; margin-bottom: 15px; border-bottom: 1px dashed #ecf0f1; padding-bottom: 10px; }
        #englishText { font-size: 24px; font-weight: bold; color: #ecf0f1; line-height: 1.6; direction: ltr; text-align: left; }
        
        .word { display: inline-block; margin-right: 5px; color: #bdc3c7; transition: color 0.1s ease-in; }
        .word.active { color: #e74c3c; transform: scale(1.05); font-weight: 900;}
        .word.spoken { color: #2c3e50; }

        #audioPlayer { display: none; }
        #curriculumStatus { color: #27ae60; font-size: 12px; font-weight: bold; }
    </style>
</head>
<body>
    <h2>مدرس اللغة الإنجليزية الذكي 🎓</h2>
    
    <div class="curriculum-info">
        📚 <strong>المنهج المعتمد:</strong> الإطار الأوروبي المرجعي المشترك للغات (CEFR).<br>
        <a href="https://www.coe.int/en/web/common-european-framework-reference-languages" target="_blank">🔗 الموقع الرسمي</a>
        <a href="https://www.cambridgeenglish.org/exams-and-tests/cefr/" target="_blank">🔗 دليل المستويات</a>
    </div>

    <!-- شريط التحكم العلوي -->
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
        
        <div class="upload-section">
            <button id="uploadBtn" onclick="triggerUpload()" title="رفع منهج مخصص (TXT)">
                📂 رفع منهج
            </button>
            <input type="file" id="fileUpload" accept=".txt" style="display: none;" onchange="handleFileUpload(event)">
            <span id="curriculumStatus"></span>
        </div>
    </div>
    
    <div class="input-container">
        <button id="pauseBtn" class="circle-btn" onclick="togglePauseAudio()" title="إيقاف / استئناف النطق">⏸️</button>
        <button id="micBtn" class="circle-btn" onclick="toggleMic()" title="تحدث الآن / مقاطعة">🎤</button>
        <input type="text" id="userMsg" placeholder="اكتب رسالتك أو اضغط الميكروفون...">
        <button class="send-btn" onclick="sendMsg()">إرسال</button>
    </div>
    
    <div id="chatBox">
        <div id="arabicTranslation">الترجمة العربية ستظهر هنا...</div>
        <div id="englishText">النص الإنجليزي سيظهر هنا...</div>
    </div>
    
    <audio id="audioPlayer"></audio>

    <script>
        let isRecording = false;
        let recognition;
        let customCurriculumContent = "";
        let wordsElements = [];

        function changeStyle() {
            let mode = document.getElementById("mode").value;
            let chatBox = document.getElementById("chatBox");
            if(mode === "child") {
                document.body.style.background = "linear-gradient(135deg, #ff9a9e 0%, #fecfef 99%, #fecfef 100%)";
                chatBox.style.borderTopColor = "#ff6b81";
            } else {
                document.body.style.background = "linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%)";
                chatBox.style.borderTopColor = "#2ecc71";
            }
        }

        // يظهر التحذير في كل مرة يتم فيها النقر
        function triggerUpload() {
            let warning = "⚠️ تحذير قانوني وشرعي ⚠️\\n\\nأنت مسؤول بالكامل عن محتوى الملف المرفوع.\\nيمنع منعاً باتاً رفع أي مواد تخالف الشريعة الإسلامية، القوانين المحلية، أو تنتهك حقوق الملكية الفكرية والنشر.\\n\\nهل تتعهد بالالتزام وتوافق على الاستمرار؟";
            if(confirm(warning)) {
                document.getElementById("fileUpload").click();
            }
        }

        function handleFileUpload(event) {
            let file = event.target.files[0];
            if (!file) return;
            
            let reader = new FileReader();
            reader.onload = function(e) {
                customCurriculumContent = e.target.result;
                document.getElementById("curriculumStatus").innerText = "✅ تم الرفع";
            };
            reader.readAsText(file);
            // تصفير قيمة المدخل ليسمح برفع نفس الملف مرة أخرى إذا لزم الأمر
            event.target.value = '';
        }

        function togglePauseAudio() {
            let audioPlayer = document.getElementById("audioPlayer");
            let pauseBtn = document.getElementById("pauseBtn");
            if(audioPlayer.src === "") return;

            if (audioPlayer.paused) {
                audioPlayer.play();
                pauseBtn.innerText = "⏸️";
            } else {
                audioPlayer.pause();
                pauseBtn.innerText = "▶️";
            }
        }

        let audioPlayer = document.getElementById("audioPlayer");
        audioPlayer.ontimeupdate = function() {
            if (wordsElements.length === 0 || isNaN(audioPlayer.duration)) return;
            
            let progress = audioPlayer.currentTime / audioPlayer.duration;
            let activeIndex = Math.floor(progress * wordsElements.length);
            
            wordsElements.forEach((span, i) => {
                if (i === activeIndex) {
                    span.classList.add("active");
                    span.classList.remove("spoken");
                } else if (i < activeIndex) {
                    span.classList.remove("active");
                    span.classList.add("spoken");
                } else {
                    span.classList.remove("active", "spoken");
                }
            });
        };

        audioPlayer.onended = function() {
            document.getElementById("pauseBtn").style.display = "none";
            wordsElements.forEach(span => {
                span.classList.remove("active");
                span.classList.add("spoken");
            });
        };

        if ('webkitSpeechRecognition' in window) {
            recognition = new webkitSpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.onresult = function(event) {
                document.getElementById("userMsg").value = event.results[0][0].transcript;
                stopMic();
            };
            recognition.onerror = function() { stopMic(); };
            recognition.onend = function() { stopMic(); };
        }

        function toggleMic() {
            if (!audioPlayer.paused) {
                audioPlayer.pause();
                document.getElementById("pauseBtn").style.display = "none";
                wordsElements.forEach(span => span.classList.add("spoken"));
            }

            if (!recognition) return alert("المتصفح لا يدعم الصوت.");
            
            if (isRecording) {
                recognition.stop();
                stopMic();
            } else {
                recognition.lang = document.getElementById("micLang").value; 
                recognition.start();
                isRecording = true;
                document.getElementById("micBtn").style.backgroundColor = "#ff4757";
            }
        }

        function stopMic() {
            isRecording = false;
            document.getElementById("micBtn").style.backgroundColor = "#e74c3c";
        }

        document.getElementById("userMsg").addEventListener("keypress", function(event) {
            if (event.key === "Enter") { event.preventDefault(); sendMsg(); }
        });

        async function sendMsg() {
            let inputField = document.getElementById("userMsg");
            let msg = inputField.value;
            let mode = document.getElementById("mode").value;
            let arabicBox = document.getElementById("arabicTranslation");
            let engBox = document.getElementById("englishText");
            
            if(!msg) return;
            if(isRecording) recognition.stop();
            
            audioPlayer.pause();
            document.getElementById("pauseBtn").style.display = "none";
            
            arabicBox.innerText = "جاري التفكير...";
            engBox.innerHTML = "";
            inputField.value = ""; 
            
            try {
                let res = await fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        message: msg, 
                        mode: mode,
                        custom_curriculum: customCurriculumContent
                    })
                });
                
                let data = await res.json();
                if(data.error) { arabicBox.innerText = "⚠️ خطأ: " + data.error; return; }
                
                arabicBox.innerText = data.arabic;
                
                let words = data.english.split(" ");
                wordsElements = [];
                words.forEach(word => {
                    let span = document.createElement("span");
                    span.className = "word";
                    span.innerText = word;
                    engBox.appendChild(span);
                    wordsElements.push(span);
                });
                
                if(data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    document.getElementById("pauseBtn").style.display = "flex";
                    document.getElementById("pauseBtn").innerText = "⏸️";
                    audioPlayer.play();
                }
            } catch (e) {
                arabicBox.innerText = "⚠️ حدث خطأ.";
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
        user_msg = data.get("message", "")
        custom_curriculum = data.get("custom_curriculum", "")

        core_rules = """
        CRITICAL RULES: 
        1. MUST STRICTLY adhere to Islamic Sharia and local laws. Absolutely NO mentions of alcohol, dating, gambling, explicit content, pork, or illegal activities. If the user asks for something violating these rules, politely decline.
        2. Base language progression on the CEFR (Common European Framework of Reference for Languages).
        """
        
        if custom_curriculum:
            core_rules += f"\\n3. The user has provided a custom curriculum text. Incorporate this context into your teaching while respecting CEFR levels and Sharia rules: {custom_curriculum[:1500]}"

        if mode == "child":
            sys_msg = core_rules + '''
            You are a fun English teacher for kids. 
            Respond ONLY in valid JSON format:
            {
                "english": "Simple English response (Max 15 words).",
                "arabic": "الترجمة العربية المرحة هنا"
            }
            '''
            voice_model = "en-US-AnaNeural"
        else:
            sys_msg = core_rules + '''
            You are a professional English coach. 
            Respond ONLY in valid JSON format:
            {
                "english": "Professional English response.",
                "arabic": "الترجمة العربية الدقيقة هنا"
            }
            '''
            voice_model = "en-US-GuyNeural"

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg}
            ],
            response_format={"type": "json_object"}
        )
        
        reply_content = completion.choices[0].message.content
        
        try:
            parsed_reply = json.loads(reply_content)
            eng_text = parsed_reply.get("english", "Hello! Let's continue.")
            ar_text = parsed_reply.get("arabic", "مرحباً! دعنا نكمل.")
        except Exception:
            eng_text = "Sorry, error parsing response."
            ar_text = "عذراً، حدث خطأ."
        
        audio_base64 = asyncio.run(generate_audio(eng_text, voice_model))

        return jsonify({"english": eng_text, "arabic": ar_text, "audio": audio_base64})
    
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
