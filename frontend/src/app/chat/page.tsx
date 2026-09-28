"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import { useRouter } from "next/navigation";

import {
  clearStoredChatSession,
  readStoredChatSession,
  writeStoredChatSession,
} from "../session";


/* =========================================
   Types
========================================= */

type ChatMessage = {
  role: "user" | "ai";
  text: string;
};


/* =========================================
   Config
========================================= */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL
  ?? "http://localhost:8000";

const FACE_SESSION_DURATION_MS = 10000;


/* =========================================
   Main Component
========================================= */

export default function Home() {

  const router = useRouter();

  /* ---------------------------------------
     HTML references
  --------------------------------------- */

  const messagesEndRef =
    useRef<HTMLDivElement | null>(null);


  /* ---------------------------------------
     Media references
  --------------------------------------- */

  const microphoneStreamRef =
    useRef<MediaStream | null>(null);

  const mediaRecorderRef =
    useRef<MediaRecorder | null>(null);

  const activeAudioRef =
    useRef<HTMLAudioElement | null>(null);


  const audioChunksRef =
    useRef<Blob[]>([]);

  const isRecordingRef =
    useRef(false);

  const startingMicrophoneRef =
    useRef(false);

  const pushToTalkHeldRef =
    useRef(false);

  const recordingSessionTokenRef =
    useRef<string | null>(null);

  const processingRef =
    useRef(false);

  const audioOutputDeviceIdRef =
    useRef<string | null>(null);


  /* ---------------------------------------
     Face Recognition
  --------------------------------------- */

  const sessionTokenRef =
    useRef<string | null>(null);

  const faceSessionActiveRef =
    useRef(false);

  const faceSessionPausedRef =
    useRef(false);

  const faceSessionExpiresAtRef =
    useRef(0);

  const endingSessionRef =
    useRef(false);


  /* ---------------------------------------
     React state
  --------------------------------------- */

  const [listening, setListening] =
    useState(false);

  const [processing, setProcessing] =
    useState(false);

  const [messages, setMessages] =
    useState<ChatMessage[]>([]);

  const [remainingSeconds, setRemainingSeconds] =
    useState(FACE_SESSION_DURATION_MS / 1000);


  /* =========================================
     Session
  ========================================= */

  function updateStoredSessionExpiry(expiresAt: number) {
    const storedSession = readStoredChatSession();

    if (
      !storedSession
      || storedSession.token !== sessionTokenRef.current
    ) {
      return;
    }

    writeStoredChatSession({
      ...storedSession,
      expiresAt,
    });
  }

  function startFaceSessionTimer(
    expiresAt = Date.now() + FACE_SESSION_DURATION_MS,
  ) {
    faceSessionActiveRef.current = true;
    faceSessionPausedRef.current = false;
    faceSessionExpiresAtRef.current = expiresAt;
    setRemainingSeconds(
      Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000)),
    );
    updateStoredSessionExpiry(expiresAt);
  }

  function pauseFaceSessionTimer() {
    if (!faceSessionActiveRef.current) {
      return;
    }

    faceSessionPausedRef.current = true;
    faceSessionExpiresAtRef.current = 0;
    setRemainingSeconds(FACE_SESSION_DURATION_MS / 1000);
    updateStoredSessionExpiry(0);
  }

  function resumeFaceSessionTimer() {
    if (!faceSessionActiveRef.current) {
      return;
    }

    faceSessionPausedRef.current = false;
    const expiresAt = Date.now() + FACE_SESSION_DURATION_MS;
    faceSessionExpiresAtRef.current = expiresAt;
    setRemainingSeconds(FACE_SESSION_DURATION_MS / 1000);
    updateStoredSessionExpiry(expiresAt);
  }

  async function endCurrentFaceSession() {
    if (
      endingSessionRef.current
      || !faceSessionActiveRef.current
    ) {
      return;
    }

    endingSessionRef.current = true;
    faceSessionActiveRef.current = false;
    faceSessionPausedRef.current = false;
    faceSessionExpiresAtRef.current = 0;
    setRemainingSeconds(0);

    const expiredToken = sessionTokenRef.current;
    clearStoredChatSession();
    sessionTokenRef.current = null;
    recordingSessionTokenRef.current = null;
    setMessages([]);
    router.replace("/");

    try {
      if (expiredToken) {
        const formData = new FormData();
        formData.append("session_token", expiredToken);
        await fetch(`${API_URL}/api/face/session/end`, {
          method: "POST",
          body: formData,
        });
      }
    } catch (error) {
      console.warn("End face session error:", error);
    } finally {
      endingSessionRef.current = false;
    }
  }

  /* =========================================
     Push-to-talk microphone
  ========================================= */

  function preferredAudioDevice(
    devices: MediaDeviceInfo[],
  ): MediaDeviceInfo | undefined {
    const score = (device: MediaDeviceInfo) => {
      const label = device.label.toLowerCase();
      let value = 0;

      if (/usb|headset|headphone|ab13x/.test(label)) {
        value += 10;
      }
      if (device.deviceId !== "default") {
        value += 1;
      }
      return value;
    };

    return [...devices].sort(
      (left, right) => score(right) - score(left),
    )[0];
  }

  async function discoverPreferredAudioOutput() {
    try {
      const devices = await Promise.race([
        navigator.mediaDevices.enumerateDevices(),
        new Promise<MediaDeviceInfo[]>((resolve) => {
          window.setTimeout(() => resolve([]), 1000);
        }),
      ]);
      const output = preferredAudioDevice(
        devices.filter((device) => device.kind === "audiooutput"),
      );
      audioOutputDeviceIdRef.current = output?.deviceId ?? null;
    } catch (error) {
      console.warn("Audio device discovery error:", error);
    }
  }

  async function openPreferredMicrophone(): Promise<MediaStream> {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: { ideal: 1 },
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });

    // อุปกรณ์ USB ถูกตั้งเป็น system default บน Raspberry Pi อยู่แล้ว
    // การค้นหา output ทำเบื้องหลังเพื่อไม่ให้ขวางการเริ่มอัดเสียง
    void discoverPreferredAudioOutput();
    return stream;
  }

  async function preparePushToTalk() {
    const requestedSessionToken =
      sessionTokenRef.current;

    if (
      startingMicrophoneRef.current
      || isRecordingRef.current
      || processingRef.current
      || !requestedSessionToken
    ) {
      return;
    }

    startingMicrophoneRef.current = true;
    pauseFaceSessionTimer();

    try {
      const stream =
        await openPreferredMicrophone();

      if (
        !pushToTalkHeldRef.current
      ) {
        stream.getTracks().forEach(
          (track) => track.stop(),
        );
        resumeFaceSessionTimer();
        return;
      }

      microphoneStreamRef.current = stream;

      const recorderOptions = MediaRecorder.isTypeSupported(
        "audio/webm;codecs=opus",
      )
        ? { mimeType: "audio/webm;codecs=opus" }
        : undefined;
      const recorder = new MediaRecorder(stream, recorderOptions);

      mediaRecorderRef.current = recorder;
      recordingSessionTokenRef.current =
        requestedSessionToken;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const recordedSessionToken =
          recordingSessionTokenRef.current;

        isRecordingRef.current = false;
        setListening(false);
        microphoneStreamRef.current
          ?.getTracks()
          .forEach((track) => track.stop());
        microphoneStreamRef.current = null;
        mediaRecorderRef.current = null;

        const audioBlob = new Blob(
          audioChunksRef.current,
          { type: "audio/webm" },
        );
        audioChunksRef.current = [];

        if (
          audioBlob.size > 500
          && recordedSessionToken
        ) {
          await sendVoice(
            audioBlob,
            recordedSessionToken,
          );
        } else {
          resumeFaceSessionTimer();
        }
      };

      if (pushToTalkHeldRef.current) {
        startRecording();
      } else {
        stream.getTracks().forEach(
          (track) => track.stop(),
        );
        microphoneStreamRef.current = null;
        mediaRecorderRef.current = null;
        resumeFaceSessionTimer();
      }
    } catch (error) {
      console.error(
        "Microphone error:",
        error,
      );
      resumeFaceSessionTimer();
    } finally {
      startingMicrophoneRef.current = false;
    }
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
    audioBlob: Blob,
    requestSessionToken: string,
  ) {

    if (!requestSessionToken) {
      return;
    }


    processingRef.current =
      true;

    setProcessing(true);


    try {
      const transcriptionForm = new FormData();
      transcriptionForm.append(
        "session_token",
        requestSessionToken,
      );
      transcriptionForm.append(
        "audio",
        audioBlob,
        "speech.webm",
      );

      const transcriptionResponse = await fetch(
          `${API_URL}/api/voice/transcribe`,
          {
            method: "POST",
            body: transcriptionForm,
          }
        );

      if (!transcriptionResponse.ok) {
        console.error(
          "STT API:",
          await transcriptionResponse.text(),
        );
        return;
      }

      const transcription =
        await transcriptionResponse.json();

      if (transcription.stt_failed) {
        setMessages((current) => [
          ...current,
          {
            role: "ai",
            text: transcription.assistant_text,
          },
        ]);
        await playBase64Audio(
          transcription.audio,
          transcription.audio_mime_type,
        );
        return;
      }

      setMessages((current) => [
        ...current,
        {
          role: "user",
          text: transcription.user_text,
        },
        {
          role: "ai",
          text: "...",
        },
      ]);

      const responseForm = new FormData();
      responseForm.append("session_token", requestSessionToken);
      responseForm.append("user_text", transcription.user_text);

      const response = await fetch(
        `${API_URL}/api/voice/respond`,
        {
          method: "POST",
          body: responseForm,
        },
      );

      if (!response.ok) {
        setMessages((current) => [
          ...current.slice(0, -1),
          {
            role: "ai",
            text: "ขออภัยครับ ระบบไม่สามารถประมวลผลคำตอบได้",
          },
        ]);
        console.error("AI API:", await response.text());
        return;
      }

      const data = await response.json();
      setMessages((current) => [
        ...current.slice(0, -1),
        {
          role: "ai",
          text: data.assistant_text,
        },
      ]);

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
      resumeFaceSessionTimer();
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

    const selectableAudio = audio as HTMLAudioElement & {
      setSinkId?: (deviceId: string) => Promise<void>;
    };

    if (
      audioOutputDeviceIdRef.current
      && selectableAudio.setSinkId
    ) {
      try {
        await selectableAudio.setSinkId(
          audioOutputDeviceIdRef.current,
        );
      } catch (error) {
        console.warn("Audio output selection error:", error);
      }
    }

    activeAudioRef.current = audio;

    await new Promise<void>(
      (resolve, reject) => {
        let finished = false;

        const finish = () => {
          if (finished) {
            return;
          }

          finished = true;

          if (activeAudioRef.current === audio) {
            activeAudioRef.current = null;
          }
          URL.revokeObjectURL(
            url
          );
          resolve();
        };

        audio.onended = finish;
        audio.onpause = finish;

        void audio.play().catch((error) => {
          if (!finished) {
            finished = true;
            activeAudioRef.current = null;
            URL.revokeObjectURL(url);
          }
          reject(error);
        });
      }
    );
  }


  /* =========================================
     Cleanup
  ========================================= */

  function stopAllMedia() {
    pushToTalkHeldRef.current = false;
    stopRecording();
    activeAudioRef.current?.pause();
    microphoneStreamRef.current
      ?.getTracks()
      .forEach(
        (track) =>
          track.stop()
      );
  }

  async function playGreeting(sessionToken: string) {
    pauseFaceSessionTimer();

    try {
      const formData = new FormData();
      formData.append("session_token", sessionToken);

      const response = await fetch(
        `${API_URL}/api/voice/greeting`,
        {
          method: "POST",
          body: formData,
        },
      );

      if (!response.ok) {
        console.error("Greeting TTS API:", await response.text());
        return;
      }

      const data = await response.json();

      if (sessionTokenRef.current !== sessionToken) {
        return;
      }

      await playBase64Audio(
        data.audio,
        data.audio_mime_type,
      );
    } catch (error) {
      console.error("Greeting TTS error:", error);
    } finally {
      if (sessionTokenRef.current === sessionToken) {
        resumeFaceSessionTimer();
      }
    }
  }


  /* =========================================
     Start application
  ========================================= */

  useEffect(() => {
    const initializeTimer = window.setTimeout(() => {
      const storedSession = readStoredChatSession();

      if (
        !storedSession
        || storedSession.expiresAt <= Date.now()
      ) {
        clearStoredChatSession();
        router.replace("/");
        return;
      }

      sessionTokenRef.current = storedSession.token;
      startFaceSessionTimer(storedSession.expiresAt);
      const recognizedUser = storedSession.recognizedUser;
      const greeting = (
        recognizedUser
        && ["student", "lecturer"].includes(recognizedUser.role)
      )
        ? `สวัสดีครับคุณ ${recognizedUser.name} cs ai assistant พร้อมใช้งานแล้ว`
        : "สวัสดีครับ cs ai assistant พร้อมใช้งานแล้ว";

      setMessages([
        {
          role: "ai",
          text: greeting,
        },
      ]);
      void playGreeting(storedSession.token);
    }, 0);

    return () => window.clearTimeout(initializeTimer);

    // ตรวจ session ที่ส่งมาจากหน้าเข้าสู่ระบบครั้งเดียวตอน mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => stopAllMedia();

    // cleanup เฉพาะไมโครโฟนและเสียงเมื่อออกจากหน้าแชต
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  /*
   * Push-to-talk: กด Spacebar ค้างเพื่ออัดเสียง
   * และปล่อย Spacebar เพื่อหยุดและส่ง STT
   */
  useEffect(() => {
    const handleKeyDown = (
      event: KeyboardEvent,
    ) => {
      if (
        event.code !== "Space"
        || event.repeat
      ) {
        return;
      }

      event.preventDefault();
      pushToTalkHeldRef.current = true;
      void preparePushToTalk();
    };

    const handleKeyUp = (
      event: KeyboardEvent,
    ) => {
      if (event.code !== "Space") {
        return;
      }

      event.preventDefault();
      pushToTalkHeldRef.current = false;
      stopRecording();
    };

    const handleBlur = () => {
      pushToTalkHeldRef.current = false;
      stopRecording();
    };

    window.addEventListener(
      "keydown",
      handleKeyDown,
    );
    window.addEventListener(
      "keyup",
      handleKeyUp,
    );
    window.addEventListener(
      "blur",
      handleBlur,
    );

    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown,
      );
      window.removeEventListener(
        "keyup",
        handleKeyUp,
      );
      window.removeEventListener(
        "blur",
        handleBlur,
      );
    };

    // handlers ใช้ refs ซึ่งคงที่ตลอดอายุ component
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  /* หมด session หลังไม่มีคำสั่งเสียง 10 วินาที */
  useEffect(() => {
    const interval = window.setInterval(() => {
      if (
        faceSessionActiveRef.current
        && !faceSessionPausedRef.current
        && faceSessionExpiresAtRef.current > 0
      ) {
        const remaining = Math.max(
          0,
          Math.ceil(
            (faceSessionExpiresAtRef.current - Date.now()) / 1000,
          ),
        );

        setRemainingSeconds((current) => (
          current === remaining ? current : remaining
        ));

        if (remaining === 0) {
          void endCurrentFaceSession();
        }
      }
    }, 250);

    return () => window.clearInterval(interval);

    // endCurrentFaceSession ใช้ refs และ router ของ component instance นี้
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


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
          <span>CS</span> AI Assistant
        </h1>

        <div
          aria-label={`เหลือเวลา ${remainingSeconds} วินาที`}
          className="session-countdown"
        >
          {remainingSeconds}
        </div>

      </header>


      <section className="content">

        {/* ================================
            CHAT
        ================================= */}

        <div className="panel chat-panel">

          <div className="chat-title">

            บทสนทนา

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

          <div
            aria-live="polite"
            className={
              listening
                ? "microphone listening"
                : processing
                  ? "microphone processing"
                  : "microphone"
            }
          >
            {processing
              ? "AI กำลังประมวลผล..."
              : listening
                ? "🎙 กำลังฟัง..."
                : "🎤 กด Spacebar ค้างเพื่อพูด"}
          </div>

        </div>

      </section>

    </main>
  );
}
