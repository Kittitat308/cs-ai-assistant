"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import Link from "next/link";


/* =========================================
   Types
========================================= */

type ChatMessage = {
  role: "user" | "ai";
  text: string;
};


type RecognizedUser = {
  name: string;
  role: string;
};


/* =========================================
   Config
========================================= */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL
  ?? "http://localhost:8000";


/*
 * Voice Activity Detection แบบง่าย
 *
 * ค่า RMS มากกว่านี้ถือว่าผู้ใช้กำลังพูด
 *
 * ภายหลังสามารถปรับ threshold
 * ให้เหมาะกับไมโครโฟนจริง
 */
const VOICE_THRESHOLD = 0.035;


/*
 * เมื่อเสียงเงียบต่อเนื่องเกินเวลานี้
 * จะถือว่าผู้ใช้พูดจบ
 */
const SILENCE_TIME_MS = 900;


/* =========================================
   Main Component
========================================= */

export default function Home() {

  /* ---------------------------------------
     HTML references
  --------------------------------------- */

  const videoRef =
    useRef<HTMLVideoElement | null>(null);

  const canvasRef =
    useRef<HTMLCanvasElement | null>(null);

  const messagesEndRef =
    useRef<HTMLDivElement | null>(null);


  /* ---------------------------------------
     Media references
  --------------------------------------- */

  const cameraStreamRef =
    useRef<MediaStream | null>(null);

  const microphoneStreamRef =
    useRef<MediaStream | null>(null);

  const mediaRecorderRef =
    useRef<MediaRecorder | null>(null);


  /* ---------------------------------------
     Audio/VAD
  --------------------------------------- */

  const audioContextRef =
    useRef<AudioContext | null>(null);

  const analyserRef =
    useRef<AnalyserNode | null>(null);

  const vadTimerRef =
    useRef<number | null>(null);

  const audioChunksRef =
    useRef<Blob[]>([]);

  const silenceStartedRef =
    useRef<number | null>(null);

  const isRecordingRef =
    useRef(false);

  const processingRef =
    useRef(false);


  /* ---------------------------------------
     Face Recognition
  --------------------------------------- */

  const recognizingRef =
    useRef(false);

  const sessionTokenRef =
    useRef<string | null>(null);


  /* ---------------------------------------
     React state
  --------------------------------------- */

  const [cameraReady, setCameraReady] =
    useState(false);

  const [recognizedUser, setRecognizedUser] =
    useState<RecognizedUser | null>(null);

  const [claimedName, setClaimedName] =
    useState<string | null>(null);

  const [faceStatus, setFaceStatus] =
    useState("กำลังเปิดกล้อง...");

  const [listening, setListening] =
    useState(false);

  const [processing, setProcessing] =
    useState(false);

  const [messages, setMessages] =
    useState<ChatMessage[]>([]);


  /* =========================================
     Camera
  ========================================= */

  async function startCamera() {

    try {

      const stream =
        await navigator.mediaDevices.getUserMedia({
          video: {
            width: {
              ideal: 640,
            },

            height: {
              ideal: 480,
            },

            facingMode: "user",
          },

          audio: false,
        });


      cameraStreamRef.current =
        stream;


      if (videoRef.current) {

        videoRef.current.srcObject =
          stream;

        await videoRef.current.play();

        setCameraReady(true);

        setFaceStatus(
          "กล้องพร้อม กำลังตรวจสอบใบหน้า..."
        );
      }

    } catch (error) {

      console.error(
        "Camera error:",
        error
      );

      setFaceStatus(
        "ไม่สามารถเปิดกล้องได้"
      );
    }
  }


  /* =========================================
     Capture camera frame
  ========================================= */

  async function captureFrame():
    Promise<Blob | null> {

    const video =
      videoRef.current;

    const canvas =
      canvasRef.current;


    if (
      !video
      || !canvas
      || video.videoWidth === 0
    ) {
      return null;
    }


    canvas.width =
      video.videoWidth;

    canvas.height =
      video.videoHeight;


    const context =
      canvas.getContext("2d");


    if (!context) {
      return null;
    }


    /*
     * ส่งภาพจริงให้ backend
     *
     * ไม่ mirror เหมือนภาพที่แสดงบน UI
     */
    context.drawImage(
      video,
      0,
      0,
      canvas.width,
      canvas.height,
    );


    return new Promise((resolve) => {

      canvas.toBlob(
        resolve,
        "image/jpeg",
        0.8,
      );

    });
  }


  /* =========================================
     Face Recognition
  ========================================= */

  async function recognizeFace() {

    /*
     * ป้องกัน request ซ้อน
     */
    if (recognizingRef.current) {
      return;
    }


    recognizingRef.current = true;


    try {

      const image =
        await captureFrame();


      if (!image) {
        return;
      }


      const formData =
        new FormData();


      formData.append(
        "image",
        image,
        "face.jpg",
      );


      if (sessionTokenRef.current) {

        formData.append(
          "session_token",
          sessionTokenRef.current,
        );
      }


      const response =
        await fetch(
          `${API_URL}/api/face/recognize`,
          {
            method: "POST",
            body: formData,
          }
        );


      if (!response.ok) {
        return;
      }


      const data =
        await response.json();


      /*
       * เก็บ backend session token
       */
      if (data.session_token) {

        sessionTokenRef.current =
          data.session_token;
      }


      /* ---------------------------------------
         Recognized
      --------------------------------------- */

      if (data.status === "recognized") {

        setClaimedName(null);

        setRecognizedUser({
          name: data.name,
          role: data.role,
        });


        setFaceStatus(
          `ยืนยันตัวตนแล้ว (${Math.round(
            data.similarity * 100
          )}%)`
        );


        /*
         * หลังรู้ว่าใครแล้ว
         * เริ่มเปิดระบบไมโครโฟน
         */
        if (!microphoneStreamRef.current) {

          await startVoiceDetection();
        }


        return;
      }


      /* ---------------------------------------
         Unknown
      --------------------------------------- */

      if (data.status === "unknown") {

        setRecognizedUser(null);

        setClaimedName(
          data.claimed_name ?? null
        );

        setFaceStatus(
          data.claimed_name
            ? "จำชื่อจากบทสนทนาแล้ว แต่ยังไม่ยืนยันใบหน้า"
            : "ไม่รู้จักผู้ใช้นี้"
        );


        /*
         * Guest ก็สามารถคุยกับ AI ได้
         */
        if (!microphoneStreamRef.current) {

          await startVoiceDetection();
        }


        return;
      }


      /* ---------------------------------------
         No face
      --------------------------------------- */

      if (data.status === "no_face") {

        setFaceStatus(
          "ไม่พบใบหน้า"
        );

        return;
      }


      /* ---------------------------------------
         Multiple faces
      --------------------------------------- */

      if (
        data.status
        === "multiple_faces"
      ) {

        setFaceStatus(
          "กรุณาให้มีผู้ใช้เพียงหนึ่งคนหน้ากล้อง"
        );
      }

    } catch (error) {

      console.error(
        "Face recognition error:",
        error
      );

    } finally {

      recognizingRef.current =
        false;
    }
  }


  /* =========================================
     Microphone + Voice Activity Detection
  ========================================= */

  async function startVoiceDetection() {

    try {

      const stream =
        await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: false,
        });


      microphoneStreamRef.current =
        stream;


      const AudioContextClass =
        window.AudioContext;


      const audioContext =
        new AudioContextClass();


      audioContextRef.current =
        audioContext;


      const source =
        audioContext.createMediaStreamSource(
          stream
        );


      const analyser =
        audioContext.createAnalyser();


      analyser.fftSize = 2048;


      source.connect(
        analyser
      );


      analyserRef.current =
        analyser;


      /*
       * MediaRecorder จะสร้าง WEBM/Opus
       *
       * Groq รองรับ WEBM โดยตรง
       */
      const recorder =
        new MediaRecorder(
          stream,
          {
            mimeType:
              "audio/webm;codecs=opus",
          }
        );


      mediaRecorderRef.current =
        recorder;


      recorder.ondataavailable =
        (event) => {

          if (event.data.size > 0) {

            audioChunksRef.current.push(
              event.data
            );
          }
        };


      recorder.onstop = async () => {

        isRecordingRef.current =
          false;

        setListening(false);


        const audioBlob =
          new Blob(
            audioChunksRef.current,
            {
              type: "audio/webm",
            }
          );


        audioChunksRef.current =
          [];


        /*
         * ป้องกันไฟล์เสียงสั้น/ว่างเกินไป
         */
        if (audioBlob.size > 1500) {

          await sendVoice(
            audioBlob
          );
        }
      };


      /*
       * เริ่ม loop ตรวจระดับเสียง
       */
      vadTimerRef.current =
        window.requestAnimationFrame(
          detectVoice
        );

    } catch (error) {

      console.error(
        "Microphone error:",
        error
      );
    }
  }


  /* =========================================
     Voice detector loop
  ========================================= */

  function detectVoice(
    frameTime: number
  ) {

    const analyser =
      analyserRef.current;


    if (!analyser) {
      return;
    }


    const data =
      new Uint8Array(
        analyser.fftSize
      );


    analyser.getByteTimeDomainData(
      data
    );


    /*
     * คำนวณ RMS volume
     */
    let sumSquares = 0;


    for (
      let i = 0;
      i < data.length;
      i++
    ) {

      const normalized =
        (data[i] - 128) / 128;


      sumSquares +=
        normalized * normalized;
    }


    const rms =
      Math.sqrt(
        sumSquares / data.length
      );


    const hasVoice =
      rms > VOICE_THRESHOLD;


    /* ---------------------------------------
       เริ่มพูด
    --------------------------------------- */

    if (
      hasVoice
      && !isRecordingRef.current
      && !processingRef.current
      && sessionTokenRef.current
    ) {

      startRecording();
    }


    /* ---------------------------------------
       กำลังอัด
    --------------------------------------- */

    if (isRecordingRef.current) {

      if (hasVoice) {

        silenceStartedRef.current =
          null;

      } else {

        /*
         * เริ่มจับเวลาความเงียบ
         */
        if (
          silenceStartedRef.current
          === null
        ) {

          silenceStartedRef.current =
            frameTime;
        }


        const silenceDuration =
          frameTime
          - silenceStartedRef.current;


        /*
         * เงียบประมาณ 900 ms
         * ถือว่าพูดจบ
         */
        if (
          silenceDuration
          >= SILENCE_TIME_MS
        ) {

          stopRecording();
        }
      }
    }


    vadTimerRef.current =
      window.requestAnimationFrame(
        detectVoice
      );
  }


  /* =========================================
     Start recording
  ========================================= */

  function startRecording() {

    const recorder =
      mediaRecorderRef.current;


    if (!recorder) {
      return;
    }


    if (
      recorder.state
      !== "inactive"
    ) {
      return;
    }


    audioChunksRef.current =
      [];


    silenceStartedRef.current =
      null;


    isRecordingRef.current =
      true;


    setListening(true);


    recorder.start();
  }


  /* =========================================
     Stop recording
  ========================================= */

  function stopRecording() {

    const recorder =
      mediaRecorderRef.current;


    if (
      !recorder
      || recorder.state
      !== "recording"
    ) {
      return;
    }


    recorder.stop();
  }


  /* =========================================
     Voice pipeline
  ========================================= */

  async function sendVoice(
    audioBlob: Blob
  ) {

    if (!sessionTokenRef.current) {
      return;
    }


    processingRef.current =
      true;

    setProcessing(true);


    try {

      const formData =
        new FormData();


      formData.append(
        "session_token",
        sessionTokenRef.current,
      );


      formData.append(
        "audio",
        audioBlob,
        "speech.webm",
      );


      const response =
        await fetch(
          `${API_URL}/api/voice/converse`,
          {
            method: "POST",
            body: formData,
          }
        );


      if (!response.ok) {

        const error =
          await response.text();

        console.error(
          "Voice API:",
          error
        );

        return;
      }


      const data =
        await response.json();

      if (data.claimed_name) {
        setClaimedName(
          data.claimed_name
        );
      }


      /* ---------------------------------------
         Show user message
      --------------------------------------- */

      setMessages(
        (current) => [
          ...current,

          {
            role: "user",
            text: data.user_text,
          },

          {
            role: "ai",
            text: data.assistant_text,
          },
        ]
      );


      /* ---------------------------------------
         Play TTS
      --------------------------------------- */

      await playBase64Audio(
        data.audio,
        data.audio_mime_type,
      );

    } catch (error) {

      console.error(
        "Conversation error:",
        error
      );

    } finally {

      processingRef.current =
        false;

      setProcessing(false);
    }
  }


  /* =========================================
     Play MP3
  ========================================= */

  async function playBase64Audio(
    base64Audio: string,
    mimeType: string,
  ) {

    /*
     * decode Base64 → binary
     */
    const binary =
      window.atob(
        base64Audio
      );


    const bytes =
      new Uint8Array(
        binary.length
      );


    for (
      let i = 0;
      i < binary.length;
      i++
    ) {

      bytes[i] =
        binary.charCodeAt(i);
    }


    const blob =
      new Blob(
        [bytes],
        {
          type: mimeType,
        }
      );


    const url =
      URL.createObjectURL(
        blob
      );


    const audio =
      new Audio(url);


    /*
     * ระหว่าง AI พูด
     * processingRef ยังเป็น true
     *
     * ทำให้ VAD ไม่อัดเสียง AI
     * กลับเข้า microphone pipeline
     */
    await audio.play();


    await new Promise<void>(
      (resolve) => {

        audio.onended = () => {

          URL.revokeObjectURL(
            url
          );

          resolve();
        };
      }
    );
  }


  /* =========================================
     Cleanup
  ========================================= */

  function stopAllMedia() {

    if (vadTimerRef.current) {

      window.cancelAnimationFrame(
        vadTimerRef.current
      );
    }


    cameraStreamRef.current
      ?.getTracks()
      .forEach(
        (track) =>
          track.stop()
      );


    microphoneStreamRef.current
      ?.getTracks()
      .forEach(
        (track) =>
          track.stop()
      );


    audioContextRef.current
      ?.close();
  }


  /* =========================================
     Role text
  ========================================= */

  function roleLabel(
    role?: string
  ) {

    if (role === "student") {
      return "นักศึกษา";
    }

    if (role === "lecturer") {
      return "อาจารย์";
    }

    if (role === "admin") {
      return "ผู้ดูแลระบบ";
    }

    return "ผู้ใช้ทั่วไป";
  }


  /* =========================================
     Start application
  ========================================= */

  useEffect(() => {

    const startTimer =
      window.setTimeout(
        () => {
          void startCamera();
        },
        0,
      );

    return () => {
      window.clearTimeout(startTimer);
      stopAllMedia();
    };

  }, []);


  /*
   * เมื่อกล้องพร้อม
   * เริ่ม Face Recognition
   */
  useEffect(() => {

    if (!cameraReady) {
      return;
    }

    const firstRecognitionTimer =
      window.setTimeout(
        () => {
          void recognizeFace();
        },
        0,
      );

    const interval =
      window.setInterval(
        recognizeFace,
        2000,
      );

    return () => {
      window.clearTimeout(
        firstRecognitionTimer
      );
      window.clearInterval(interval);
    };

    // recognizeFace ใช้เฉพาะ refs ซึ่งคงที่ตลอดอายุ component
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraReady]);


  /*
   * เลื่อน chat ลงล่างอัตโนมัติ
   */
  useEffect(() => {

    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });

  }, [messages]);


  /* =========================================
     UI
  ========================================= */

  return (

    <main className="app">

      {/* Header */}
      <header className="header">

        <h1>
          CS AI Assistant
        </h1>

        <Link
          className="header-home-link"
          href="/"
        >
          หน้าหลัก
        </Link>

      </header>


      <section className="content">

        {/* ================================
            LEFT : CAMERA
        ================================= */}

        <div className="panel camera-panel">

          <div className="camera-wrapper">

            <video
              ref={videoRef}
              className="camera"
              autoPlay
              muted
              playsInline
            />

          </div>


          {/* Canvas ใช้ capture ภาพ
              แต่ไม่แสดงให้ผู้ใช้เห็น */}
          <canvas
            ref={canvasRef}
            style={{
              display: "none",
            }}
          />


          <div className="status">

            <div className="user-name">

              {recognizedUser
                ? recognizedUser.name
                : claimedName ?? "Guest"}

            </div>


            <div className="user-role">

              {recognizedUser
                ? roleLabel(
                    recognizedUser.role
                  )
                : "ผู้ใช้ทั่วไป"}

            </div>


            <div className="status-text">

              {faceStatus}

            </div>

          </div>


          <div
            className={
              listening
                ? "microphone listening"
                : "microphone"
            }
          >

            {processing
              ? "AI กำลังประมวลผล..."
              : listening
                ? "🎙 กำลังฟัง..."
                : "🎤 พร้อมรับเสียง"}

          </div>

        </div>


        {/* ================================
            RIGHT : CHAT
        ================================= */}

        <div className="panel chat-panel">

          <div className="chat-title">

            Conversation

          </div>


          <div className="messages">

            {messages.length === 0 && (

              <div
                style={{
                  color: "#9ca3af",
                  textAlign: "center",
                  marginTop: "40px",
                }}
              >

                การสนทนาจะแสดงที่นี่

              </div>

            )}


            {messages.map(
              (message, index) => (

                <div
                  key={index}
                  className={
                    `message ${message.role}`
                  }
                >

                  <div className="message-label">

                    {message.role === "user"
                      ? "คุณ"
                      : "CS AI Assistant"}

                  </div>


                  <div className="message-bubble">

                    {message.text}

                  </div>

                </div>

              )
            )}


            <div
              ref={messagesEndRef}
            />

          </div>

        </div>

      </section>

    </main>
  );
}
