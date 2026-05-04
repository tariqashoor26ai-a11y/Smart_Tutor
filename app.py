import os
import asyncio
import base64
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
        }
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
        }
        #micBtn:hover { background-color: #c0392b; }
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
            min-height: 120px; 
            white-space: pre-wrap; 
            text-align: right; 
            line-height: 1.8;
            font-size: 18px;
            color: #34495e;
            border-top: 5px solid #2ecc71;
        }
        #audioPlayer { margin-top: 20px; display: none; outline: none; width: 80%; max-width: 600px; }
    </style>
</head>
<body>
    <h2>🇬🇧 مدرس اللغة الإنجليزية الذكي 🎙️</h2>
    
    <select id="mode" onchange="changeStyle()">
        <option value="adult">وضع الكبار (احترافي وعملي)</option>
        <option value="child">وضع الأطفال (مرح وبسيط)</option>
    </select>
    
    <div class="input-container">
        <button id="micBtn" onclick="toggleMic()" title="تحدث الآن">🎤</button>
        <input type="text" id="userMsg" placeholder="اكتب رسالتك أو اضغط الميكروفون للتحدث...">
        <button onclick="sendMsg()">إرسال</button>
    </div>
    
    <div id="chatBox">الرد سيظهر هنا...</div>
    <audio id="audioPlayer" controls></audio>

    <script>
        // تغيير الألوان بناءً على الوضع المختار
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

        // إعداد الإدخال الصوتي (Speech Recognition)
        let recognition;
        let isRecording = false;
        if ('webkitSpeechRecognition' in window) {
            recognition = new webkitSpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            // يمكن تعيين لغة التعرف هنا، حالياً نتركه يتعرف على الإنجليزية والعربية
            recognition.lang = 'en-US'; 
            
            recognition.onresult = function(event) {
                let transcript = event.results[0][0].transcript;
                document.getElementById("userMsg").value = transcript;
                stopMic();
                // يمكن تفعيل الإرسال التلقائي بعد التحدث بفك التعليق عن السطر التالي:
                // sendMsg(); 
            };
            
            recognition.onerror = function(event) {
                console.error("Speech recognition error", event.error);
                stopMic();
            };
            
            recognition.onend = function() {
                stopMic();
            };
        } else {
            document.getElementById("micBtn").style.display = "none";
            console.log("Speech Recognition Not Available in this browser.");
        }

        function toggleMic() {
            if (!recognition) return alert("متصفحك لا يدعم الإدخال الصوتي.");
            
            if (isRecording) {
                recognition.stop();
                stopMic();
            } else {
                // محاولة التعرف على لغة الإدخال بناءً على الوضع
                // إذا أردت التعرف على العربية بشكل أفضل، يمكنك استخدام 'ar-SA'
                recognition.lang = document.getElementById("mode").value === "adult" ? 'en-US' : 'en-US'; 
                recognition.start();
                isRecording = true;
                document.getElementById("micBtn").classList.add("recording");
                document.getElementById("userMsg").placeholder = "جاري الاستماع... 🔴";
            }
        }

        function stopMic() {
            isRecording = false;
            document.getElementById("micBtn").classList.remove("recording");
            document.getElementById("userMsg").placeholder = "اكتب رسالتك أو اضغط الميكروفون للتحدث...";
        }

        // تفعيل الإرسال عند الضغط على زر Enter
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
            let chatBox = document.getElementById("chatBox");
            let audioPlayer = document.getElementById("audioPlayer");
            
            if(!msg) return;
            
            if(isRecording) recognition.stop();
            
            chatBox.innerText = "جاري التفكير وتجهيز الصوت...";
            audioPlayer.style.display = "none";
            audioPlayer.pause();
            
            inputField.value = ""; 
            
            try {
                let res = await fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({message: msg, mode: mode})
                });
                
                let data = await res.json();
                
                if(data.error) {
                    chatBox.innerText = "⚠️ يوجد خطأ يمنع الاستجابة: " + data.error;
                    return;
                }
                
                chatBox.innerText = data.reply;
                
                if(data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    audioPlayer.style.display = "inline";
                    audioPlayer.play();
                }
            } catch (e) {
                chatBox.innerText = "⚠️ حدث خطأ في الاتصال بالسيرفر.";
            }
        }
        
        // تشغيل النمط المبدئي
        changeStyle();
    </script>
</body>
</html>
"""

async def generate_audio(text, voice):
    communicate = edge_tts.Communicate(text, voice)
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
        if not api_key:
            return jsonify({"error": "مفتاح GROQ_API_KEY مفقود."})

        client = Groq(api_key=api_key)
        data = request.json
        mode = data.get("mode", "adult")
        user_msg = data.get("message", "")

        if mode == "child":
            sys_msg = "أنت مدرس لغة إنجليزية مرح للأطفال. تواصل حصرياً باللغتين الإنجليزية والعربية فقط. يمنع استخدام أي لغة أخرى. أجب على الطفل بكلمات بسيطة، اقترح عليه كلمة جديدة ليتعلمها، وفي نهاية ردك اطرح عليه سؤالاً بسيطاً جداً بالإنجليزية لتشجيعه على الرد."
            voice_model = "en-US-AnaNeural"
        else:
            sys_msg = "أنت مدرب لغة إنجليزية محترف للبالغين. تواصل حصرياً باللغتين الإنجليزية والعربية فقط. يمنع استخدام أي لغة أخرى. أجب على المستخدم، قدم له تصحيحاً أو اقتراحاً عملياً لتحسين لغته، وفي نهاية ردك اسأله دائماً 'What is the next step?' أو اطرح سؤالاً متعلقاً بالموضوع لتوجيه المحادثة للخطوة التالية."
            voice_model = "en-US-GuyNeural"

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg}
            ]
        )
        
        reply_text = completion.choices[0].message.content
        
        audio_base64 = asyncio.run(generate_audio(reply_text, voice_model))

        return jsonify({"reply": reply_text, "audio": audio_base64})
    
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
