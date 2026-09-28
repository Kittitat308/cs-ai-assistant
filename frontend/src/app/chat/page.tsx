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
  id: number;
  name: string;
  role: string;
};


type CameraSource =
  | "ip"
  | "local"
  | null;


/* =========================================
   Config
========================================= */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL
  ?? "http://localhost:8000";

const FACE_CHECK_INTERVAL_MS = 2000;
const REQUIRED_FACE_DETECTIONS = 3;
const FACE_SESSION_DURATION_MS = 10000;


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

  const ipCameraFrameRef =
    useRef<Blob | null>(null);

  const ipCameraFrameTimeRef =
    useRef(0);

  const ipCameraRequestRef =
    useRef(false);

  const ipCameraActiveRef =
    useRef(false);

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

  const recognizingRef =
    useRef(false);

  const sessionTokenRef =
    useRef<string | null>(null);

  const detectedFaceCountRef =
    useRef(0);

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

  const [cameraReady, setCameraReady] =
    useState(false);

  const [cameraSource, setCameraSource] =
    useState<CameraSource>(null);

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

  const [hasSession, setHasSession] =
    useState(false);

  const [messages, setMessages] =
    useState<ChatMessage[]>([]);


  /* =========================================
     Camera
  ========================================= */

  function updateIpCameraFrame(
    image: Blob,
  ) {
    ipCameraFrameRef.current = image;
    ipCameraFrameTimeRef.current = Date.now();
  }


  async function refreshIpCameraFrame():
    Promise<boolean> {
    if (ipCameraRequestRef.current) {
      return ipCameraFrameRef.current !== null;
    }

    ipCameraRequestRef.current = true;

    try {
      const response = await fetch(
        `${API_URL}/api/face/camera/snapshot?t=${Date.now()}`,
        { cache: "no-store" },
      );

      if (!response.ok) {
        return false;
      }

      const image = await response.blob();

      if (!image.type.startsWith("image/") || image.size === 0) {
        return false;
      }

      updateIpCameraFrame(image);
      return true;
    } catch (error) {
      console.warn("IP camera error:", error);
      return false;
    } finally {
      ipCameraRequestRef.current = false;
    }
  }


  function stopIpCamera() {
    ipCameraActiveRef.current = false;
    ipCameraFrameRef.current = null;
    ipCameraFrameTimeRef.current = 0;
  }


  async function startIpCamera():
    Promise<boolean> {
    const opened =
      await refreshIpCameraFrame();

    if (!opened) {
      stopIpCamera();
      return false;
    }

    ipCameraActiveRef.current = true;
    setCameraSource("ip");
    setCameraReady(true);
    setFaceStatus(
      "กล้อง IP พร้อม กำลังตรวจสอบใบหน้า..."
    );

    return true;
  }


  async function startLocalCamera() {

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

      setCameraSource("local");


      if (videoRef.current) {

        videoRef.current.srcObject =
          stream;

        await videoRef.current.play();

        setCameraReady(true);

        setFaceStatus(
          "กล้องเครื่องพร้อม กำลังตรวจสอบใบหน้า..."
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


  async function startCamera() {
    const ipCameraOpened =
      await startIpCamera();

    if (!ipCameraOpened) {
      await startLocalCamera();
    }
  }


  /* =========================================
     Capture camera frame
  ========================================= */

  async function captureFrame():
    Promise<Blob | null> {

    if (ipCameraActiveRef.current) {
      const frameIsFresh = (
        ipCameraFrameRef.current !== null
        && Date.now() - ipCameraFrameTimeRef.current < 1000
      );

      if (
        frameIsFresh
        || await refreshIpCameraFrame()
      ) {
        return ipCameraFrameRef.current;
      }

      stopIpCamera();
      setCameraReady(false);
      setFaceStatus(
        "กล้อง IP ใช้งานไม่ได้ กำลังเปลี่ยนเป็นกล้องเครื่อง..."
      );
      await startLocalCamera();
      return null;
    }

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

  function switchSessionToken(
    nextToken: string,
  ) {
    const previousToken =
      sessionTokenRef.current;

    if (
      previousToken
      && previousToken !== nextToken
    ) {
      setMessages([]);
      setClaimedName(null);
    }

    sessionTokenRef.current =
      nextToken;
    setHasSession(true);
  }

  function appendCameraTransform(formData: FormData) {
    const usingIpCamera = ipCameraActiveRef.current;
    formData.append(
      "rotation",
      usingIpCamera ? "ccw" : "none",
    );
    formData.append(
      "enhance",
      usingIpCamera ? "true" : "false",
    );
  }

  function startFaceSessionTimer() {
    faceSessionActiveRef.current = true;
    faceSessionPausedRef.current = false;
    faceSessionExpiresAtRef.current =
      Date.now() + FACE_SESSION_DURATION_MS;
    detectedFaceCountRef.current = 0;
  }

  function pauseFaceSessionTimer() {
    if (!faceSessionActiveRef.current) {
      return;
    }

    faceSessionPausedRef.current = true;
    faceSessionExpiresAtRef.current = 0;
  }

  function resumeFaceSessionTimer() {
    if (!faceSessionActiveRef.current) {
      return;
    }

    faceSessionPausedRef.current = false;
    faceSessionExpiresAtRef.current =
      Date.now() + FACE_SESSION_DURATION_MS;
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
    detectedFaceCountRef.current = 0;

    const expiredToken = sessionTokenRef.current;
    sessionTokenRef.current = null;
    recordingSessionTokenRef.current = null;
    setHasSession(false);
    setRecognizedUser(null);
    setClaimedName(null);
    setMessages([]);
    setFaceStatus("หมดเวลาใช้งาน กำลังตรวจหาใบหน้า...");

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

  async function recognizeFace(image: Blob) {

    /*
     * ป้องกัน request ซ้อน
     */
    if (recognizingRef.current) {
      return;
    }


    recognizingRef.current = true;


    try {

      const formData =
        new FormData();


      formData.append(
        "image",
        image,
        "face.jpg",
      );
      appendCameraTransform(formData);


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
        switchSessionToken(
          data.session_token,
        );
        startFaceSessionTimer();
      }


      /* ---------------------------------------
         Recognized
      --------------------------------------- */

      if (data.status === "recognized") {

        setClaimedName(null);

        setRecognizedUser({
          id: data.user_id,
          name: data.name,
          role: data.role,
        });


        setFaceStatus(
          `ยืนยันตัวตนแล้ว (${Math.round(
            data.similarity * 100
          )}%)`
        );


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

  async function checkFace() {
    if (
      recognizingRef.current
      || faceSessionActiveRef.current
      || endingSessionRef.current
    ) {
      return;
    }

    recognizingRef.current = true;

    try {
      const image = await captureFrame();

      if (!image) {
        detectedFaceCountRef.current = 0;
        return;
      }

      const formData = new FormData();
      formData.append("image", image, "face.jpg");
      appendCameraTransform(formData);

      const response = await fetch(
        `${API_URL}/api/face/detect`,
        { method: "POST", body: formData },
      );

      if (!response.ok) {
        detectedFaceCountRef.current = 0;
        return;
      }

      const data = await response.json();

      if (!data.face_detected) {
        detectedFaceCountRef.current = 0;
        setFaceStatus("ไม่พบใบหน้า");
        return;
      }

      detectedFaceCountRef.current += 1;
      const count = detectedFaceCountRef.current;
      setFaceStatus(
        `ตรวจพบใบหน้า ${count}/${REQUIRED_FACE_DETECTIONS}`,
      );

      if (count >= REQUIRED_FACE_DETECTIONS) {
        detectedFaceCountRef.current = 0;
        recognizingRef.current = false;
        setFaceStatus("กำลังระบุตัวผู้ใช้...");
        await recognizeFace(image);
      }
    } catch (error) {
      detectedFaceCountRef.current = 0;
      console.error("Face detection error:", error);
    } finally {
      recognizingRef.current = false;
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
      setFaceStatus(
        "ไม่สามารถเปิดไมโครโฟนได้",
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

      if (
        data.claimed_name
        && sessionTokenRef.current === requestSessionToken
      ) {
        setClaimedName(data.claimed_name);
      }

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
    stopIpCamera();
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

    // เริ่มและ cleanup media เฉพาะตอน mount/unmount
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


  /*
   * เมื่อกล้องพร้อม
   * ตรวจใบหน้าทุก 2 วินาที และ recognize เมื่อพบติดกัน 3 ครั้ง
   */
  useEffect(() => {

    if (!cameraReady) {
      return;
    }

    const firstRecognitionTimer =
      window.setTimeout(
        () => {
          void checkFace();
        },
        0,
      );

    const interval =
      window.setInterval(
        checkFace,
        FACE_CHECK_INTERVAL_MS,
      );

    return () => {
      window.clearTimeout(
        firstRecognitionTimer
      );
      window.clearInterval(interval);
    };

    // checkFace ใช้เฉพาะ refs ซึ่งคงที่ตลอดอายุ component
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraReady]);


  /* หมด session หลังไม่มีคำสั่งเสียง 10 วินาที */
  useEffect(() => {
    const interval = window.setInterval(() => {
      if (
        faceSessionActiveRef.current
        && !faceSessionPausedRef.current
        && faceSessionExpiresAtRef.current > 0
        && Date.now() >= faceSessionExpiresAtRef.current
      ) {
        void endCurrentFaceSession();
      }
    }, 250);

    return () => window.clearInterval(interval);

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
              autoPlay
              muted
              playsInline
              aria-hidden="true"
              style={{
                position: "absolute",
                width: "1px",
                height: "1px",
                opacity: 0,
                pointerEvents: "none",
              }}
            />

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "100%",
                height: "100%",
                color: "#94a3b8",
                textAlign: "center",
                padding: "24px",
              }}
            >
              {cameraSource === "ip"
                ? "ระบบกำลังตรวจสอบใบหน้าจากกล้อง IP"
                : cameraSource === "local"
                  ? "ระบบกำลังตรวจสอบใบหน้าจากกล้องเครื่อง"
                  : "กำลังเชื่อมต่อกล้อง"}
            </div>

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
                : hasSession
                  ? "🎤 กด Spacebar ค้างเพื่อพูด"
                  : "กำลังรอการตรวจสอบใบหน้า"}

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
