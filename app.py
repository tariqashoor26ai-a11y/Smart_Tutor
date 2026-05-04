import os
import asyncio
import base64
from flask import Flask, request, jsonify, render_template_string
from groq import Groq
import edge_tts

app = Flask(__name__)

# واجهة الموقع المطورة (تحتوي على مشغل صوت وإظهار للأخطاء)
HTML_PAGE = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>المدرس الذكي</title>
    <style>
        body { font-family: Arial; text-align: center; margin-top: 50px; background: #f4f4f9;}
        input, select, button { padding: 10px; font-size: 16px; margin: 5px; }
        #chatBox { width: 80%; max-width: 600px; margin: 20px auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); min-height: 100px; white-space: pre-wrap;}
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
    <input type="text" id="userMsg" placeholder="اكتب رسالتك بالإنجليزية أو العربية..." style="width: 60%;">
    <button onclick="sendMsg()">إرسال</button>
    
    <div id="chatBox">الرد سيظهر هنا...</div>
    <audio id="audioPlayer" controls></audio>

    <script>
        async function sendMsg() {
            let msg = document.getElementById("userMsg").value;
            let mode = document.getElementById("mode").value;
            let chatBox = document.getElementById("chatBox");
            let audioPlayer = document.getElementById("audioPlayer");
            
            if(!msg) return;
            
            chatBox.innerText = "جاري التفكير وتجهيز الصوت (قد يستغرق بضع ثوانٍ)...";
            audioPlayer.style.display = "none";
            audioPlayer.pause();
            
            try {
                let res = await fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({message: msg, mode: mode})
                });
                
                let data = await res.json();
                
                // إذا كان هناك خطأ، اعرضه فوراً
                if(data.error) {
                    chatBox.innerText = "⚠️ يوجد خطأ يمنع الاستجابة: " + data.error;
                    return;
                }
                
                chatBox.innerText = data.reply;
                
                // تشغيل الصوت
                if(data.audio) {
                    audioPlayer.src = "data:audio/mp3;base64," + data.audio;
                    audioPlayer.style.display = "inline";
                    audioPlayer.play();
                }
            } catch (e) {
                chatBox.innerText = "⚠️ حدث خطأ في الاتصال بالسيرفر. يرجى التأكد من أن السيرفر يعمل.";
            }
        }
    </script>
</body>
</html>
"""

# وظيفة تحويل النص إلى صوت
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
        # التأكد من وجود المفتاح
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return jsonify({"error": "مفتاح GROQ_API_KEY مفقود في إعدادات Render."})

        client = Groq(api_key=api_key)
        data = request.json
        mode = data.get("mode", "adult")
        user_msg = data.get("message", "")

        # تخصيص الشخصية والصوت
        if mode == "child":
            sys_msg = "You are a fun English teacher for kids. Speak ONLY in simple English so the kid can listen and learn. Be highly encouraging."
            voice_model = "en-US-AnaNeural" # صوت مرح للأطفال
        else:
            sys_msg = "You are a professional English coach for adults. Focus on practical conversation and corrections. Speak ONLY in clear English."
            voice_model = "en-US-GuyNeural" # صوت احترافي للكبار

        # استدعاء الذكاء الاصطناعي
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg}
            ]
        )
        
        reply_text = completion.choices[0].message.content
        
        # إنشاء المقطع الصوتي
        audio_base64 = asyncio.run(generate_audio(reply_text, voice_model))

        return jsonify({"reply": reply_text, "audio": audio_base64})
    
    except Exception as e:
        # التقاط أي خطأ وإرساله للواجهة لتسهيل الحل
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
