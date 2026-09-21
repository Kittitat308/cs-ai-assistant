# CS AI Assistant

เว็บแอปผู้ช่วย AI สำหรับสาขาวิทยาการคอมพิวเตอร์ รองรับการสนทนาด้วยเสียง การจดจำใบหน้า การระบุตัวตนผู้ใช้ และการนำข้อมูลจาก PostgreSQL เช่น ข้อมูลผู้ใช้และตารางเรียน มาใช้ตอบคำถาม

## ความสามารถหลัก

- สนทนาด้วยเสียงผ่านหน้าเว็บ โดยแสดงข้อความที่ผู้ใช้พูดและคำตอบของ AI
- แปลงเสียงเป็นข้อความด้วย Groq Whisper และสร้างคำตอบด้วย Gemini
- อ่านคำตอบภาษาไทยผ่านลำโพงด้วย Edge TTS
- ตรวจจับและจดจำใบหน้าด้วย InsightFace
- รู้จักผู้ใช้ว่าเป็นอาจารย์ นักศึกษา หรือผู้ใช้ทั่วไป
- จำชื่อและประวัติการสนทนาภายใน session ปัจจุบัน
- ลงทะเบียนผู้ใช้พร้อมใบหน้าแบบ transaction เดียว หากทำไม่ครบจะไม่บันทึกข้อมูล
- ตรวจสอบรหัสนักศึกษา 10 หลักไม่ให้ซ้ำ
- เพิ่มตารางเรียนแบบหนึ่งรายวิชามีหลายวันหรือหลายช่วงเวลาได้
- เลือกห้องเรียนจากข้อมูลห้อง ชั้น ประเภทห้อง และอาคารในฐานข้อมูล

## เทคโนโลยี

| ส่วนระบบ | เทคโนโลยี |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript |
| Backend | FastAPI, Python 3.11 |
| Database | PostgreSQL, SQLAlchemy |
| Speech-to-Text | Groq API (`whisper-large-v3-turbo`) |
| AI | Google Gemini API |
| Text-to-Speech | Edge TTS |
| Face Recognition | InsightFace + ONNX Runtime |

## โครงสร้างโปรเจกต์

```text
cs-ai-assistant/
├── backend/
│   ├── app/
│   │   ├── core/       # การตั้งค่าและฐานข้อมูล
│   │   ├── models/     # SQLAlchemy models
│   │   ├── routers/    # FastAPI endpoints
│   │   ├── services/   # AI, STT, TTS และ Face Recognition
│   │   └── main.py
│   ├── .env.example
│   └── requirements.txt
└── frontend/
    ├── src/app/        # หน้า Home, ลงทะเบียน และ Chat
    ├── .env.local.example
    └── package.json
```

## สิ่งที่ต้องติดตั้ง

- Python 3.11
- Node.js 20 ขึ้นไป
- PostgreSQL 14 ขึ้นไป
- เว็บเบราว์เซอร์ที่อนุญาตการใช้กล้องและไมโครโฟน
- API key ของ [Groq](https://console.groq.com/keys)
- API key ของ [Google AI Studio](https://aistudio.google.com/app/apikey)

> การใช้กล้องและไมโครโฟนบนเครื่องอื่นควรเปิดเว็บผ่าน HTTPS ส่วน `localhost` สามารถใช้ระหว่างพัฒนาได้

## วิธีติดตั้ง

### 1. ดาวน์โหลดโปรเจกต์

```powershell
git clone https://github.com/Kittitat308/cs-ai-assistant.git
cd cs-ai-assistant
```

### 2. สร้างฐานข้อมูล PostgreSQL

เข้าสู่ PostgreSQL แล้วสร้างฐานข้อมูล:

```sql
CREATE DATABASE cs_ai_assistant;
```

ระบบจะสร้างตารางที่จำเป็นให้อัตโนมัติเมื่อ Backend เริ่มทำงานครั้งแรก

### 3. ตั้งค่าและติดตั้ง Backend

คำสั่งสำหรับ Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

แก้ไขไฟล์ `backend/.env` อย่างน้อยตามตัวอย่างนี้:

```dotenv
APP_NAME=CS AI Assistant
DEBUG=true
FRONTEND_URL=http://localhost:3000

DATABASE_URL=postgresql+psycopg://postgres:รหัสผ่าน_PostgreSQL@localhost:5432/cs_ai_assistant

GROQ_API_KEY=ใส่_Groq_API_Key
GROQ_STT_MODEL=whisper-large-v3-turbo

GEMINI_API_KEY=ใส่_Gemini_API_Key
GEMINI_MODEL=gemini-3.5-flash-lite

TTS_VOICE=th-TH-NiwatNeural
FACE_MODEL=buffalo_l
FACE_DETECTION_SIZE=640
FACE_THRESHOLD=0.45

ADMIN_TOKEN=เปลี่ยนเป็นข้อความสุ่มที่ยาวและคาดเดายาก
```

เปิด Backend:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

เมื่อเปิดครั้งแรก InsightFace อาจดาวน์โหลดโมเดล `buffalo_l` จึงใช้เวลานานกว่าปกติ ตรวจสอบสถานะได้ที่ [http://localhost:8000/health](http://localhost:8000/health) และเอกสาร API ที่ [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. ตั้งค่าและติดตั้ง Frontend

เปิด PowerShell อีกหน้าต่างหนึ่งจากโฟลเดอร์โปรเจกต์:

```powershell
cd frontend
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

เปิด [http://localhost:3000](http://localhost:3000) แล้วอนุญาตการใช้กล้องและไมโครโฟน

## วิธีใช้งาน

1. กด **ลงทะเบียน** บนหน้า Home
2. กรอกชื่อ เลือกสถานะ และกรอกรหัสนักศึกษา 10 หลักเมื่อเลือกสถานะนักศึกษา
3. เพิ่มรายวิชาและช่วงเวลาเรียน หรือกดข้าม
4. สแกนใบหน้าและยืนยันการลงทะเบียน
5. กลับหน้า Home แล้วกด **เข้าใช้งาน**
6. มองกล้องเพื่อให้ระบบระบุตัวตน จากนั้นกดพูดเพื่อสนทนากับ AI

## นำเข้าข้อมูลอาจารย์จากรูปภาพ

สคริปต์ `backend/scripts/enroll_teachers.py` ใช้เพิ่มหรือปรับปรุงข้อมูลอาจารย์ โปรไฟล์สาธารณะ และ face embedding แบบ transaction เดียว โดยจะตรวจรูปทั้งหมดก่อนบันทึกและไม่สร้าง face embedding ซ้ำเมื่อรันอีกครั้ง

เตรียมไฟล์รูปให้มีชื่อตรงกับรายการที่กำหนดในสคริปต์ แล้วรัน:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python scripts\enroll_teachers.py "C:\path\to\teacher-images"
```

แต่ละภาพต้องมีใบหน้าที่มองเห็นชัดเจนเพียงหนึ่งคน หากรูปใดไม่ผ่าน ระบบจะยกเลิกก่อนเปลี่ยนแปลงฐานข้อมูล

## เพิ่มหรือปรับปรุงข้อมูลห้อง

ข้อมูลห้องเริ่มต้นของสาขาอยู่ใน `backend/scripts/seed_rooms.py` สามารถเพิ่มหรือปรับปรุงใน PostgreSQL โดยไม่สร้างข้อมูลซ้ำด้วยคำสั่ง:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python scripts\seed_rooms.py
```

## การตรวจสอบก่อนใช้งาน

```powershell
# ตรวจ Backend
cd backend
.\.venv\Scripts\python.exe -m compileall app

# ตรวจ Frontend
cd ..\frontend
npm run lint
npm run build
```

## ข้อควรระวังด้านข้อมูลส่วนบุคคล

ระบบจัดเก็บ face embedding และประวัติการสนทนาในฐานข้อมูล ผู้ดูแลระบบควรขอความยินยอมจากผู้ใช้ จำกัดสิทธิ์เข้าถึงฐานข้อมูล ใช้ HTTPS และกำหนดนโยบายลบข้อมูลให้เหมาะสมก่อนนำไปใช้จริง

ห้าม commit ไฟล์ `backend/.env` หรือ `frontend/.env.local` เพราะมีข้อมูลลับและ API key โดยไฟล์เหล่านี้ถูกระบุไว้ใน `.gitignore` แล้ว

## คำสั่งสำหรับ Production

Frontend:

```powershell
cd frontend
npm install
npm run build
npm run start
```

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

สำหรับ Production ควรใช้ reverse proxy, HTTPS, process manager และระบบ migration เช่น Alembic เพิ่มเติม

## License

โปรเจกต์นี้ยังไม่ได้กำหนดสัญญาอนุญาต หากต้องการให้บุคคลอื่นนำไปแก้ไขหรือเผยแพร่ต่อ ควรเพิ่มไฟล์ `LICENSE` ให้ชัดเจน
