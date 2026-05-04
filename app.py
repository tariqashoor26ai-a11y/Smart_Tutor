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
        h2 { color: #2c3e50; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); }
        select { 
            padding: 10px; 
            font-size: 16px; 
            border-radius: 8px; 
            border: 2px solid #3498db; 
            background-color: white; 
            color: #2c3e50;
            cursor: pointer;
            margin: 5px;
        }
        .controls { display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-bottom: 15px;}
        .input-container {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin-top: 20px;
        }
        input { 
            padding: 12px; 
            font-size: 16px; 
            border-radius: 25px; 
            border: 2px solid #bdc3c7; 
            width: 50%; 
            max-width: 500px;
            outline: none;
            transition: border-color 0.3s;
        }
        input:focus { border-color: #3498db; }
        button { 
            padding: 12px 20px; 
            font-size: 16px; 
            border-radius: 25px; 
            border: none; 
            background-color: #3498db; 
            color: white; 
            cursor: pointer; 
            transition: background-color 0.3s;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        button:hover { background-color: #2980b9; }
        #micBtn {
            background-color: #e74c3c;
            border-radius: 50%;
            width: 45px;
            height: 45px;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 20px;
            transition: transform 0.2s;
        }
        #micBtn:hover { background-color: #c0392b; transform: scale(1.05); }
        #micBtn.recording { animation: pulse 1.5s infinite; background-color: #ff4757; }
        
        @keyframes pulse {
            0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 71, 87, 0.7); }
            70% { transform: scale(1.1); box-shadow: 0 0 0 10px rgba(255, 71, 87, 0); }
            100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 71, 87, 0); }
        }

        #chatBox { 
            width: 80%; 
            max-width: 600px; 
            margin: 30px auto; 
            background: white; 
            padding: 25px; 
            border-radius: 15px; 
            box-shadow: 0 10px 20px rgba(0,0,0,0.05); 
            min-height: 150px; 
            text-align: right; 
            border-top: 5px solid #2ecc71;
        }
        
        #arabicTranslation {
            color: #7f8c8d;
            font-size: 16px;
            margin-bottom: 15px;
            border-bottom: 1px dashed #ecf0f1;
            padding-bottom: 10px;
        }
        
        #englishText {
            font-size: 24px;
            font-weight: bold;
            color: #ecf0f1;
            line-height: 1.6;
            direction: ltr;
            text-align: left;
        }
        
        .word {
            display: inline-block;
            margin-right: 5px;
            color: transparent;
            transition: color 0.1s ease-in;
        }
        
        .word.active { color: #e74c3c; transform: scale(1.05); }
        .word.spoken { color: #2c3e50; }

        #audioPlayer { display: none; }
    </style>
</head>
<body>
    <h2>مدرس اللغة الإنجليزية الذكي 🎙️</h2>
    
    <div class="controls">
        <select id="mode" onchange="changeStyle()">
            <option value="adult">وضع الكبار (احترافي)</option>
            <option value="child">وضع الأطفال (مرح)</option>
        </select>
        <select id="micLang">
            <option value="en-US">تحدث بالإنجليزية</option>
            <option value="ar-SA">تحدث بالعربية</option>
        </select>
    </div>
    
    <div class="input-container">
        <button id="micBtn" onclick="toggleMic()" title="تحدث الآن / مقاطعة المعلم">🎤</button>
        <input type="text" id="userMsg" placeholder="اكتب رسالتك أو اضغط الميكروفون...">
        <button onclick="sendMsg()">إرسال</button>
    </div>
    
    <div id="chatBox">
        <div id="arabicTranslation">الترجمة العربية ستظهر هنا...</div>
        <div id="englishText">النص الإنجليزي سيظهر هنا بشكل متزامن...</div>
    </div>
    
    <audio id="audioPlayer"></audio>

    <script>
        let wordInterval;
        let isRecording = false;
        let recognition;

        function changeStyle() {
            let mode = document.getElementById("mode").value;
            let chatBox = document.getElementById("chatBox");
            if(mode === "child") {
                document.body.style.background = "linear-gradient(135deg, #ff9a9e 0%, #fecfef 99%, #fecfef 100%)";
                chatBox.style.borderTopColor = "#ff6b81";
                chatBox.style.fontFamily = "'Comic Sans MS', cursive, sans-serif";
            } else {
                document.body.style.background = "linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%)";
                chatBox.style.borderTopColor = "#2ecc71";
                chatBox.style.fontFamily = "'Segoe UI', sans-serif";
            }
        }

        if ('webkitSpeechRecognition' in window) {
            recognition = new webkitSpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            
            recognition.onresult = function(event) {
                let transcript = event.results[0][0].transcript;
                document.getElementById("userMsg").value = transcript;
                stopMic();
            };
            
            recognition.onerror = function(event) { stopMic(); };
            recognition.onend = function() { stopMic(); };
        }

        function toggleMic() {
            let audioPlayer = document.getElementById("audioPlayer");
            
            if (!audioPlayer.paused) {
                audioPlayer.pause();
                clearInterval(wordInterval);
                let wordsElements = document.querySelectorAll(".word");
                wordsElements.forEach(el => el.classList.add("spoken"));
            }

            if (!recognition) return alert("متصفحك لا يدعم الإدخال الصوتي.");
            
            if (isRecording) {
                recognition.stop();
                stopMic();
            } else {
                recognition.lang = document.getElementById("micLang").value; 
                recognition.start();
                isRecording = true;
                document.getElementById("micBtn").classList.add("recording");
                document.getElementById("userMsg").placeholder = "جاري الاستماع... يمكنك التحدث الآن 🔴";
            }
        }

        function stopMic() {
            isRecording = false;
            document.getElementById("micBtn").classList.remove("recording");
            document.getElementById("userMsg").placeholder = "اكتب رسالتك أو اضغط الميكروفون...";
        }

        document.getElementById("userMsg").addEventListener("keypress", function(event) {
            if (event.key === "Enter") {
                event.preventDefault();
                sendMsg();
            }
        });

        async function sendMsg() {
            let inputField = document.getElementById("userMsg");
            let msg = inputField.value;
            let mode = document.getElementById("mode").value;
            let arabicBox = document.getElementById("arabicTranslation");
            let engBox = document.getElementById("englishText");
            let audioPlayer = document.getElementById("audioPlayer");
            
            if(!msg) return;
            if(isRecording) recognition.stop();
            
            audioPlayer.pause();
            clearInterval(wordInterval);
            
            arabicBox.innerText = "جاري التفكير...";
            engBox.innerHTML = "";
            inputField.value = ""; 
            
            try {
                let res = await fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({message: msg, mode: mode})
                });
                
                let data = await res.json();
                
                if(data.error) {
                    arabicBox.innerText = "⚠️ خطأ: " + data.error;
                    return;
                }
                
                arabicBox.innerText = data.arabic;
                
                let words = data.english.split(" ");
                engBox.innerHTML = "";
                words.forEach(word => {
                    let span = document.createElement("span");
                    span.className = "word";
                    span.innerText = word;
                    engBox.appendChild(span);
                });
                
                if(data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    
                    audioPlayer.oncanplay = function() {
                        audioPlayer.play();
                        let duration = audioPlayer.duration * 1000; 
                        let wordTime = duration / words.length;
                        
                        let spans = document.querySelectorAll(".word");
                        let i = 0;
                        
                        wordInterval = setInterval(() => {
                            if (i < spans.length) {
                                spans[i].style.color = "#e74c3c";
                                spans[i].style.transform = "scale(1.1)";
                                
                                if (i > 0) {
                                    spans[i-1].style.color = "#2c3e50";
                                    spans[i-1].style.transform = "scale(1)";
                                }
                                i++;
                            } else {
                                clearInterval(wordInterval);
                                if (spans.length > 0) {
                                    spans[spans.length-1].style.color = "#2c3e50";
                                    spans[spans.length-1].style.transform = "scale(1)";
                                }
                            }
                        }, wordTime);
                    };
                }
            } catch (e) {
                arabicBox.innerText = "⚠️ حدث خطأ في الاتصال بالسيرفر.";
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
        if not api_key: return jsonify({"error": "مفتاح GROQ_API_KEY مفقود."})

        client = Groq(api_key=api_key)
        data = request.json
        mode = data.get("mode", "adult")
        user_msg = data.get("message", "")

        if mode == "child":
            sys_msg = '''You are a very fun and patient English teacher for kids. 
            You MUST respond ONLY in valid JSON format exactly like this:
            {
                "english": "Write a very simple, short English response here. Max 10 words. End with a simple question.",
                "arabic": "اكتب الترجمة العربية المرحة والمبسطة هنا"
            }
            Do not add any other text outside the JSON block.'''
            voice_model = "en-US-AnaNeural"
        else:
            sys_msg = '''You are a professional English coach for adults. 
            You MUST respond ONLY in valid JSON format exactly like this:
            {
                "english": "Write your professional English response, correction, or advice here. Keep it concise.",
                "arabic": "اكتب الترجمة العربية الدقيقة هنا"
            }
            Do not add any other text outside the JSON block.'''
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
            eng_text = "Sorry, I had a small error. Let's try again!"
            ar_text = "عذراً، حدث خطأ بسيط. لنجرب مرة أخرى!"
        
        audio_base64 = asyncio.run(generate_audio(eng_text, voice_model))

        return jsonify({"english": eng_text, "arabic": ar_text, "audio": audio_base64})
    
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
