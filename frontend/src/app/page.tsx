"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { writeStoredChatSession } from "./session";


const API_URL =
  process.env.NEXT_PUBLIC_API_URL
  ?? "http://localhost:8000";

const FACE_CHECK_INTERVAL_MS = 2000;
const REQUIRED_FACE_DETECTIONS = 3;
const FACE_SESSION_DURATION_MS = 10000;

type CameraSource = "ip" | "local" | null;


export default function LoginPage() {
  const router = useRouter();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const ipCameraFrameRef = useRef<Blob | null>(null);
  const ipCameraFrameTimeRef = useRef(0);
  const ipCameraRequestRef = useRef(false);
  const ipCameraActiveRef = useRef(false);
  const previewUrlRef = useRef<string | null>(null);
  const scanningRef = useRef(false);
  const navigatingRef = useRef(false);
  const detectedFaceCountRef = useRef(0);

  const [cameraReady, setCameraReady] = useState(false);
  const [cameraSource, setCameraSource] = useState<CameraSource>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [detectedFaceCount, setDetectedFaceCount] = useState(0);
  const [status, setStatus] = useState("กำลังเชื่อมต่อกล้อง...");

  function setFaceCount(count: number) {
    detectedFaceCountRef.current = count;
    setDetectedFaceCount(count);
  }

  function updateIpCameraFrame(image: Blob) {
    ipCameraFrameRef.current = image;
    ipCameraFrameTimeRef.current = Date.now();

    const nextPreviewUrl = URL.createObjectURL(image);
    const previousPreviewUrl = previewUrlRef.current;
    previewUrlRef.current = nextPreviewUrl;
    setPreviewUrl(nextPreviewUrl);

    if (previousPreviewUrl) {
      URL.revokeObjectURL(previousPreviewUrl);
    }
  }

  async function refreshIpCameraFrame(): Promise<boolean> {
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

    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
      setPreviewUrl(null);
    }
  }

  async function startLocalCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: "user",
        },
        audio: false,
      });

      cameraStreamRef.current = stream;
      setCameraSource("local");

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraReady(true);
        setStatus("กล้องพร้อม กรุณามองตรงมาที่กล้อง");
      }
    } catch (error) {
      console.error("Camera error:", error);
      setStatus("ไม่สามารถเปิดกล้องได้ กรุณาตรวจสอบสิทธิ์การใช้งานกล้อง");
    }
  }

  async function startCamera() {
    const ipCameraOpened = await refreshIpCameraFrame();

    if (ipCameraOpened) {
      ipCameraActiveRef.current = true;
      setCameraSource("ip");
      setCameraReady(true);
      setStatus("กล้องพร้อม กรุณามองตรงมาที่กล้อง");
      return;
    }

    stopIpCamera();
    await startLocalCamera();
  }

  async function captureFrame(): Promise<Blob | null> {
    if (ipCameraActiveRef.current) {
      const frameIsFresh = (
        ipCameraFrameRef.current !== null
        && Date.now() - ipCameraFrameTimeRef.current < 1000
      );

      if (frameIsFresh || await refreshIpCameraFrame()) {
        return ipCameraFrameRef.current;
      }

      stopIpCamera();
      setCameraReady(false);
      setStatus("กล้อง IP ใช้งานไม่ได้ กำลังเปลี่ยนเป็นกล้องเครื่อง...");
      await startLocalCamera();
      return null;
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (!video || !canvas || video.videoWidth === 0) {
      return null;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const context = canvas.getContext("2d");

    if (!context) {
      return null;
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    return new Promise((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", 0.8);
    });
  }

  function appendCameraTransform(formData: FormData) {
    const usingIpCamera = ipCameraActiveRef.current;
    formData.append("rotation", usingIpCamera ? "ccw" : "none");
    formData.append("enhance", usingIpCamera ? "true" : "false");
  }

  async function recognizeAndLogin(image: Blob) {
    const formData = new FormData();
    formData.append("image", image, "login-face.jpg");
    appendCameraTransform(formData);

    const response = await fetch(`${API_URL}/api/face/recognize`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Face recognition request failed");
    }

    const data = await response.json();

    if (data.status === "multiple_faces") {
      setFaceCount(0);
      setStatus("กรุณาให้มีผู้ใช้เพียงหนึ่งคนหน้ากล้อง");
      return;
    }

    if (
      (data.status !== "recognized" && data.status !== "unknown")
      || !data.session_token
    ) {
      setFaceCount(0);
      setStatus("ไม่สามารถระบุตัวผู้ใช้ได้ กรุณาลองใหม่");
      return;
    }

    navigatingRef.current = true;
    const recognizedUser = data.status === "recognized"
      ? {
          id: data.user_id,
          name: data.name,
          role: data.role,
        }
      : null;

    writeStoredChatSession({
      token: data.session_token,
      recognizedUser,
      claimedName: data.claimed_name ?? null,
      expiresAt: Date.now() + FACE_SESSION_DURATION_MS,
    });

    setStatus(
      recognizedUser
        ? `ยืนยันตัวตนแล้ว: ${recognizedUser.name}`
        : "เข้าสู่ระบบในสถานะผู้ใช้ทั่วไป",
    );
    router.replace("/chat");
  }

  async function checkFace() {
    if (scanningRef.current || navigatingRef.current) {
      return;
    }

    scanningRef.current = true;

    try {
      const image = await captureFrame();

      if (!image) {
        setFaceCount(0);
        return;
      }

      const formData = new FormData();
      formData.append("image", image, "login-face.jpg");
      appendCameraTransform(formData);

      const response = await fetch(`${API_URL}/api/face/detect`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        setFaceCount(0);
        setStatus("ระบบตรวจจับใบหน้าไม่พร้อม กรุณาลองใหม่");
        return;
      }

      const data = await response.json();

      if (!data.face_detected) {
        setFaceCount(0);
        setStatus("ยังไม่พบใบหน้า กรุณามองตรงมาที่กล้อง");
        return;
      }

      const nextCount = Math.min(
        REQUIRED_FACE_DETECTIONS,
        detectedFaceCountRef.current + 1,
      );
      setFaceCount(nextCount);
      setStatus("ตรวจพบใบหน้า กรุณาอยู่นิ่งสักครู่");

      if (nextCount >= REQUIRED_FACE_DETECTIONS) {
        setStatus("กำลังระบุตัวผู้ใช้...");
        await recognizeAndLogin(image);
      }
    } catch (error) {
      console.error("Login face scan error:", error);
      setFaceCount(0);
      setStatus("ไม่สามารถติดต่อระบบได้ กรุณาตรวจสอบ Backend");
    } finally {
      scanningRef.current = false;
    }
  }

  useEffect(() => {
    const startTimer = window.setTimeout(() => {
      void startCamera();
    }, 0);

    return () => {
      window.clearTimeout(startTimer);
      cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
      stopIpCamera();
    };

    // เริ่มและ cleanup กล้องเฉพาะตอน mount/unmount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!cameraReady || cameraSource !== "ip") {
      return;
    }

    const previewInterval = window.setInterval(() => {
      void refreshIpCameraFrame();
    }, 500);

    return () => window.clearInterval(previewInterval);

    // refreshIpCameraFrame ใช้ refs ซึ่งคงที่ตลอดอายุ component
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraReady, cameraSource]);

  useEffect(() => {
    if (!cameraReady) {
      return;
    }

    const firstCheck = window.setTimeout(() => {
      void checkFace();
    }, 0);
    const interval = window.setInterval(() => {
      void checkFace();
    }, FACE_CHECK_INTERVAL_MS);

    return () => {
      window.clearTimeout(firstCheck);
      window.clearInterval(interval);
    };

    // checkFace ใช้ refs ซึ่งคงที่ตลอดอายุ component
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cameraReady]);

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-brand" aria-hidden="true">CS</div>
        <p className="login-eyebrow">CS AI Assistant</p>
        <h1 id="login-title">สแกนใบหน้าเข้าใช้งาน</h1>
        <p className="login-description">
          มองตรงมาที่กล้อง ระบบจะเข้าสู่หน้าสนทนาโดยอัตโนมัติ
        </p>

        <div className="login-camera-frame">
          {cameraSource === "ip" && previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              alt="ภาพจากกล้องสำหรับเข้าสู่ระบบ"
              className="login-camera-image login-camera-ip"
              src={previewUrl}
            />
          ) : (
            <video
              ref={videoRef}
              autoPlay
              className="login-camera-image login-camera-local"
              muted
              playsInline
            />
          )}

          <div className="login-face-guide" aria-hidden="true" />
          {!cameraReady && (
            <div className="login-camera-loading">กำลังเปิดกล้อง...</div>
          )}
        </div>

        <canvas ref={canvasRef} className="login-capture-canvas" />

        <p className="login-face-count" aria-live="polite">
          พบใบหน้า {detectedFaceCount}/{REQUIRED_FACE_DETECTIONS} ครั้ง
        </p>
        <p className="login-status" aria-live="polite">{status}</p>
      </section>
    </main>
  );
}
