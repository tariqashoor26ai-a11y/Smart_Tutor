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
        body { font-family: Arial; text-align: center; margin-top: 50px; background: #f4f4f9;}
        input, select, button { padding: 10px; font-size: 16px; margin: 5px; }
        #chatBox { width: 80%; max-width: 600px; margin: 20px auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); min-height: 100px; white-space: pre-wrap; text-align: right; line-height: 1.6;}
        #audioPlayer { margin-top: 20px; display: none; outline: none; }
    </style>
</head>
<body>
    <h2>🇬🇧 مدرس اللغة الإنجليزية الذكي (يدعم الصوت)</h2>
    <select id="mode">
        <option value="adult">وضع الكبار (احترافي وعملي)</option>
        <option value="child">وضع الأطفال (مرح وبسيط)</option>
    </select>
    <br><br>
    <input type="text" id="userMsg" placeholder="اكتب رسالتك ثم اضغط Enter..." style="width: 60%;">
    <button onclick="sendMsg()">إرسال</button>
    
    <div id="chatBox">الرد سيظهر هنا...</div>
    <audio id="audioPlayer" controls></audio>

    <script>
        // تفعيل الإرسال عند الضغط على زر Enter
        document.getElementById("userMsg").addEventListener("keypress", function(event) {
            if (event.key === "Enter") {
                event.preventDefault(); // منع تحديث الصفحة
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
            
            chatBox.innerText = "جاري التفكير وتجهيز الصوت...";
            audioPlayer.style.display = "none";
            audioPlayer.pause();
            
            // تفريغ مربع النص بعد الإرسال لراحة المستخدم
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

        # توجيهات صارمة بخصوص اللغة والتفاعل
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
