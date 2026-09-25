"use client";

import Link from "next/link";
import { FormEvent, useRef, useState } from "react";


const API_URL =
  process.env.NEXT_PUBLIC_API_URL
  ?? "http://localhost:8000";

type ModalStep = "form" | "schedule" | "scan" | "success" | null;

type RoomOption = {
  id: number;
  name: string;
  floor: number;
  room_type: string;
  building: string;
};

type MeetingDraft = {
  id: number;
  dayOfWeek: string;
  startTime: string;
  endTime: string;
  roomId: string;
};

type ScheduleDraft = {
  id: number;
  courseCode: string;
  subjectName: string;
  groupNumber: string;
  meetingCount: number;
  meetings: MeetingDraft[];
};


export default function HomePage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const nextScheduleIdRef = useRef(1);
  const nextMeetingIdRef = useRef(1);

  const [modalStep, setModalStep] = useState<ModalStep>(null);
  const [name, setName] = useState("");
  const [externalId, setExternalId] = useState("");
  const [role, setRole] = useState("student");
  const [schedules, setSchedules] = useState<ScheduleDraft[]>([]);
  const [rooms, setRooms] = useState<RoomOption[]>([]);
  const [loadingRooms, setLoadingRooms] = useState(false);
  const [studentIdError, setStudentIdError] = useState("");
  const [checkingStudentId, setCheckingStudentId] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [cameraStatus, setCameraStatus] = useState("กำลังเปิดกล้อง...");

  function openRegistration() {
    setName("");
    setExternalId("");
    setRole("student");
    setSchedules([]);
    setStudentIdError("");
    setError("");
    setModalStep("form");
  }

  function stopCamera() {
    cameraStreamRef.current
      ?.getTracks()
      .forEach((track) => track.stop());

    cameraStreamRef.current = null;
  }

  function closeRegistration() {
    stopCamera();
    setModalStep(null);
    setError("");
    setSubmitting(false);
  }

  async function startCamera() {
    try {
      const stream =
        await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 640 },
            height: { ideal: 480 },
            facingMode: "user",
          },
          audio: false,
        });

      cameraStreamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraStatus("พร้อมสแกนใบหน้า");
      }
    } catch (cameraError) {
      console.error("Registration camera error:", cameraError);
      setCameraStatus("ไม่สามารถเปิดกล้องได้");
      setError("กรุณาอนุญาตการใช้กล้อง แล้วลองใหม่อีกครั้ง");
    }
  }

  async function checkStudentId(): Promise<boolean> {
    if (role !== "student") {
      setStudentIdError("");
      return true;
    }

    if (!/^\d{10}$/.test(externalId)) {
      setStudentIdError("รหัสนักศึกษาต้องเป็นตัวเลข 10 หลัก");
      return false;
    }

    setCheckingStudentId(true);

    try {
      const response = await fetch(
        `${API_URL}/api/registration/student-id/${externalId}/availability`,
      );
      const data = await response.json();

      if (!response.ok || !data.available) {
        setStudentIdError("รหัสนักศึกษานี้ถูกใช้งานไปแล้ว");
        return false;
      }

      setStudentIdError("");
      return true;
    } catch (studentIdCheckError) {
      console.error("Student ID check error:", studentIdCheckError);
      setStudentIdError("ไม่สามารถตรวจสอบรหัสนักศึกษาได้");
      return false;
    } finally {
      setCheckingStudentId(false);
    }
  }

  async function loadRooms(): Promise<boolean> {
    if (rooms.length > 0) {
      return true;
    }

    setLoadingRooms(true);

    try {
      const response = await fetch(`${API_URL}/api/rooms`);

      if (!response.ok) {
        throw new Error("Room request failed");
      }

      const data: RoomOption[] = await response.json();

      if (data.length === 0) {
        setError("ยังไม่มีข้อมูลห้องในระบบ กรุณาเพิ่มข้อมูลห้องก่อน");
        return false;
      }

      setRooms(data);
      return true;
    } catch (roomError) {
      console.error("Room loading error:", roomError);
      setError("ไม่สามารถโหลดข้อมูลห้องได้ กรุณาตรวจสอบว่า Backend เปิดอยู่");
      return false;
    } finally {
      setLoadingRooms(false);
    }
  }

  async function continueToSchedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const cleanName = name.trim().replace(/\s+/g, " ");

    if (!cleanName) {
      setError("กรุณาป้อนชื่อและนามสกุล");
      return;
    }

    if (!(await checkStudentId())) {
      return;
    }

    if (!(await loadRooms())) {
      return;
    }

    setName(cleanName);
    setModalStep("schedule");
  }

  function createScheduleRow() {
    const id = nextScheduleIdRef.current;
    const meetingId = nextMeetingIdRef.current;
    nextScheduleIdRef.current += 1;
    nextMeetingIdRef.current += 1;

    setSchedules((current) => [
      ...current,
      {
        id,
        courseCode: "",
        subjectName: "",
        groupNumber: "",
        meetingCount: 1,
        meetings: [{
          id: meetingId,
          dayOfWeek: "",
          startTime: "",
          endTime: "",
          roomId: "",
        }],
      },
    ]);
  }

  function updateSchedule(
    id: number,
    field: "courseCode" | "subjectName" | "groupNumber",
    value: string,
  ) {
    setSchedules((current) =>
      current.map((schedule) =>
        schedule.id === id
          ? { ...schedule, [field]: value }
          : schedule,
      ),
    );
  }

  function updateMeeting(
    scheduleId: number,
    meetingId: number,
    field: "dayOfWeek" | "startTime" | "endTime" | "roomId",
    value: string,
  ) {
    setSchedules((current) =>
      current.map((schedule) =>
        schedule.id === scheduleId
          ? {
              ...schedule,
              meetings: schedule.meetings.map((meeting) =>
                meeting.id === meetingId
                  ? { ...meeting, [field]: value }
                  : meeting,
              ),
            }
          : schedule,
      ),
    );
  }

  function updateMeetingCount(id: number, rawValue: string) {
    const parsedValue = Number.parseInt(rawValue, 10);
    const meetingCount = Number.isNaN(parsedValue)
      ? 1
      : Math.min(30, Math.max(1, parsedValue));

    setSchedules((current) =>
      current.map((schedule) => {
        if (schedule.id !== id) {
          return schedule;
        }

        const meetings = schedule.meetings.slice(0, meetingCount);

        while (meetings.length < meetingCount) {
          const meetingId = nextMeetingIdRef.current;
          nextMeetingIdRef.current += 1;
          meetings.push({
            id: meetingId,
            dayOfWeek: "",
            startTime: "",
            endTime: "",
            roomId: "",
          });
        }

        return { ...schedule, meetingCount, meetings };
      }),
    );
  }

  function removeSchedule(id: number) {
    setSchedules((current) =>
      current.filter((schedule) => schedule.id !== id),
    );
  }

  function scheduleIsComplete(schedule: ScheduleDraft) {
    return Boolean(
      schedule.courseCode.trim()
      && schedule.subjectName.trim()
      && /^\d+$/.test(schedule.groupNumber)
      && Number(schedule.groupNumber) >= 1
      && schedule.meetingCount >= 1
      && schedule.meetings.length === schedule.meetingCount
      && schedule.meetings.every((meeting) => (
        meeting.dayOfWeek
        && meeting.startTime
        && meeting.endTime
        && meeting.roomId
        && meeting.endTime > meeting.startTime
      )),
    );
  }

  function continueToScan() {
    if (schedules.length > 0 && !schedules.every(scheduleIsComplete)) {
      setError("กรุณากรอกข้อมูลตารางเรียนให้ครบและตรวจสอบเวลา");
      return;
    }

    setError("");
    setCameraStatus("กำลังเปิดกล้อง...");
    setModalStep("scan");

    window.setTimeout(
      () => {
        void startCamera();
      },
      0,
    );
  }

  async function captureFace(): Promise<Blob | null> {
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

    context.drawImage(
      video,
      0,
      0,
      canvas.width,
      canvas.height,
    );

    return new Promise((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", 0.9);
    });
  }

  async function registerWithFace() {
    setError("");
    setSubmitting(true);

    try {
      const image = await captureFace();

      if (!image) {
        setError("กล้องยังไม่พร้อม กรุณารอสักครู่แล้วลองใหม่");
        return;
      }

      const formData = new FormData();
      formData.append("name", name);
      formData.append("student_id", role === "student" ? externalId : "");
      formData.append("role", role);
      formData.append(
        "schedules",
        JSON.stringify(
          schedules.map((schedule) => ({
            course_code: schedule.courseCode.trim(),
            subject_name: schedule.subjectName.trim(),
            group_number: Number(schedule.groupNumber),
            meeting_count: schedule.meetingCount,
            meetings: schedule.meetings.map((meeting) => ({
              day_of_week: meeting.dayOfWeek,
              start_time: meeting.startTime,
              end_time: meeting.endTime,
              room_id: Number(meeting.roomId),
            })),
          })),
        ),
      );
      formData.append("image", image, "registration-face.jpg");

      const response = await fetch(
        `${API_URL}/api/registration`,
        {
          method: "POST",
          body: formData,
        },
      );

      const data = await response.json();

      if (!response.ok) {
        setError(
          typeof data.detail === "string"
            ? data.detail
            : "ลงทะเบียนไม่สำเร็จ กรุณาลองใหม่",
        );
        return;
      }

      stopCamera();
      setModalStep("success");
    } catch (registrationError) {
      console.error("Registration error:", registrationError);
      setError("ติดต่อระบบไม่ได้ กรุณาตรวจสอบว่า Backend เปิดอยู่");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="home-page">
      <nav className="home-navbar">
        <Link className="brand" href="/">
          <span className="brand-mark">CS</span>
          <span>AI Assistant</span>
        </Link>

        <div className="nav-actions">
          <button
            className="button button-secondary"
            onClick={openRegistration}
            type="button"
          >
            ลงทะเบียน
          </button>

          <Link className="button button-primary" href="/chat">
            เข้าใช้งาน
          </Link>
        </div>
      </nav>

      <section className="home-hero">
        <div className="hero-copy">
          <div className="eyebrow">Computer Science Department</div>
          <h1>ผู้ช่วยอัจฉริยะ<br />สำหรับสาขาวิทยาการคอมพิวเตอร์</h1>
          <p>
            ถามข้อมูลด้วยเสียง รับคำตอบทันที และจดจำผู้ใช้งาน
            ด้วยระบบรู้จำใบหน้าที่เชื่อมต่อกับข้อมูลของสาขา
          </p>

          <div className="hero-actions">
            <Link className="button button-primary button-large" href="/chat">
              เริ่มสนทนา
            </Link>
            <button
              className="button button-ghost button-large"
              onClick={openRegistration}
              type="button"
            >
              ลงทะเบียนใบหน้า
            </button>
          </div>
        </div>

        <div className="hero-visual" aria-hidden="true">
          <div className="visual-orbit orbit-one" />
          <div className="visual-orbit orbit-two" />
          <div className="assistant-core">
            <span className="core-dot" />
            <span className="core-wave wave-one" />
            <span className="core-wave wave-two" />
            <span className="core-wave wave-three" />
          </div>
          <div className="floating-card card-identity">
            <span>✓</span> Face identity
          </div>
          <div className="floating-card card-voice">
            <span>◉</span> Voice ready
          </div>
        </div>
      </section>

      <section className="feature-strip">
        <div><strong>รู้จักผู้ใช้</strong><span>ระบุตัวตนจากใบหน้า</span></div>
        <div><strong>สนทนาด้วยเสียง</strong><span>พูดและฟังได้อย่างเป็นธรรมชาติ</span></div>
        <div><strong>จำบทสนทนา</strong><span>เข้าใจบริบทและชื่อของคุณ</span></div>
      </section>

      {modalStep && (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="registration-title"
            aria-modal="true"
            className={
              modalStep === "schedule"
                ? "registration-modal schedule-modal"
                : "registration-modal"
            }
            role="dialog"
          >
            {modalStep !== "success" && (
              <button
                aria-label="ปิด"
                className="modal-close"
                onClick={closeRegistration}
                type="button"
              >
                ×
              </button>
            )}

            {modalStep === "form" && (
              <>
                <div className="modal-step">ขั้นตอนที่ 1 จาก 3</div>
                <h2 id="registration-title">ลงทะเบียนผู้ใช้งาน</h2>
                <p className="modal-description">
                  กรอกข้อมูลผู้ใช้งานให้ครบก่อนเพิ่มตารางเรียน
                </p>

                <form className="registration-form" onSubmit={(event) => void continueToSchedule(event)}>
                  <label>
                    ชื่อและนามสกุล
                    <input
                      maxLength={255}
                      onChange={(event) => setName(event.target.value)}
                      placeholder="เช่น สมชาย ใจดี"
                      required
                      value={name}
                    />
                  </label>

                  <label>
                    สถานะ
                    <select
                      onChange={(event) => {
                        const nextRole = event.target.value;
                        setRole(nextRole);
                        setStudentIdError("");

                        if (nextRole !== "student") {
                          setExternalId("");
                        }
                      }}
                      value={role}
                    >
                      <option value="lecturer">อาจารย์</option>
                      <option value="student">นักศึกษา</option>
                      <option value="guest">ผู้ใช้ทั่วไป</option>
                    </select>
                  </label>

                  {role === "student" && (
                    <label>
                      รหัสนักศึกษา 10 หลัก
                      <input
                        aria-describedby="student-id-error"
                        inputMode="numeric"
                        maxLength={10}
                        onChange={(event) => {
                          setExternalId(
                            event.target.value.replace(/\D/g, "").slice(0, 10),
                          );
                          setStudentIdError("");
                        }}
                        placeholder="6500000001"
                        required
                        value={externalId}
                      />
                      {studentIdError ? (
                        <span
                          aria-live="polite"
                          className="field-error-inline"
                          id="student-id-error"
                        >
                          {studentIdError}
                        </span>
                      ) : (
                        <span className="field-hint field-hint-right">
                          ตัวเลขเท่านั้นและห้ามซ้ำในระบบ
                        </span>
                      )}
                    </label>
                  )}

                  {error && <div className="form-error">{error}</div>}

                  <button
                    className="button button-primary modal-submit"
                    disabled={checkingStudentId || loadingRooms}
                    type="submit"
                  >
                    {checkingStudentId
                      ? "กำลังตรวจสอบรหัส..."
                      : loadingRooms
                        ? "กำลังโหลดข้อมูลห้อง..."
                        : "ถัดไป"}
                  </button>
                </form>
              </>
            )}

            {modalStep === "schedule" && (
              <>
                <div className="schedule-step-header">
                  <div>
                    <div className="modal-step">ขั้นตอนที่ 2 จาก 3</div>
                    <h2 id="registration-title">เพิ่มตารางเรียน</h2>
                  </div>
                  <button
                    className="button schedule-create-button"
                    onClick={createScheduleRow}
                    type="button"
                  >
                    + สร้าง
                  </button>
                </div>

                <p className="modal-description">
                  เพิ่มรายวิชาและช่วงเวลาเรียน หรือข้ามขั้นตอนนี้ได้
                </p>

                {schedules.length === 0 ? (
                  <div className="schedule-empty">
                    ยังไม่มีข้อมูลตารางเรียน<br />กด “สร้าง” เพื่อเพิ่มรายวิชา
                  </div>
                ) : (
                  <div className="schedule-list">
                    {schedules.map((schedule, index) => (
                        <div className="schedule-row" key={schedule.id}>
                          <div className="schedule-row-title">
                            <span>รายวิชาที่ {index + 1}</span>
                            <button
                              aria-label={`ลบรายวิชาที่ ${index + 1}`}
                              onClick={() => removeSchedule(schedule.id)}
                              type="button"
                            >
                              ×
                            </button>
                          </div>

                          <div className="schedule-course-grid">
                            <label>
                              รหัสวิชา
                              <input
                                maxLength={50}
                                onChange={(event) => updateSchedule(
                                  schedule.id,
                                  "courseCode",
                                  event.target.value,
                                )}
                                placeholder="เช่น CS101"
                                value={schedule.courseCode}
                              />
                              {!schedule.courseCode.trim() && (
                                <span className="schedule-field-error">กรุณาป้อนรหัสวิชา</span>
                              )}
                            </label>

                            <label>
                              ชื่อวิชา
                              <input
                                maxLength={255}
                                onChange={(event) => updateSchedule(
                                  schedule.id,
                                  "subjectName",
                                  event.target.value,
                                )}
                                placeholder="เช่น โครงสร้างข้อมูล"
                                value={schedule.subjectName}
                              />
                              {!schedule.subjectName.trim() && (
                                <span className="schedule-field-error">กรุณาป้อนชื่อวิชา</span>
                              )}
                            </label>

                            <label>
                              กลุ่ม
                              <input
                                min="1"
                                onChange={(event) => updateSchedule(
                                  schedule.id,
                                  "groupNumber",
                                  event.target.value.replace(/\D/g, ""),
                                )}
                                placeholder="เช่น 1"
                                type="number"
                                value={schedule.groupNumber}
                              />
                              {(!/^\d+$/.test(schedule.groupNumber) || Number(schedule.groupNumber) < 1) && (
                                <span className="schedule-field-error">กรุณาป้อนกลุ่ม</span>
                              )}
                            </label>

                            <label>
                              จำนวนครั้งที่เรียน
                              <input
                                min="1"
                                onChange={(event) => updateMeetingCount(
                                  schedule.id,
                                  event.target.value,
                                )}
                                type="number"
                                value={schedule.meetingCount}
                              />
                            </label>
                          </div>

                          <div className="schedule-meetings">
                            {schedule.meetings.map((meeting, meetingIndex) => {
                              const invalidTime = Boolean(
                                meeting.startTime
                                && meeting.endTime
                                && meeting.endTime <= meeting.startTime,
                              );

                              return (
                                <div className="schedule-meeting-row" key={meeting.id}>
                                  <span className="schedule-meeting-label">
                                    ครั้งที่ {meetingIndex + 1}
                                  </span>
                                  <label>
                                    วัน
                                    <select
                                      onChange={(event) => updateMeeting(
                                        schedule.id,
                                        meeting.id,
                                        "dayOfWeek",
                                        event.target.value,
                                      )}
                                      value={meeting.dayOfWeek}
                                    >
                                      <option value="">เลือกวัน</option>
                                      <option value="monday">จันทร์</option>
                                      <option value="tuesday">อังคาร</option>
                                      <option value="wednesday">พุธ</option>
                                      <option value="thursday">พฤหัสบดี</option>
                                      <option value="friday">ศุกร์</option>
                                      <option value="saturday">เสาร์</option>
                                      <option value="sunday">อาทิตย์</option>
                                    </select>
                                  </label>
                                  <label>
                                    เวลาเริ่มเรียน
                                    <input
                                      onChange={(event) => updateMeeting(
                                        schedule.id,
                                        meeting.id,
                                        "startTime",
                                        event.target.value,
                                      )}
                                      type="time"
                                      value={meeting.startTime}
                                    />
                                  </label>
                                  <label>
                                    เวลาเลิก
                                    <input
                                      onChange={(event) => updateMeeting(
                                        schedule.id,
                                        meeting.id,
                                        "endTime",
                                        event.target.value,
                                      )}
                                      type="time"
                                      value={meeting.endTime}
                                    />
                                  </label>
                                  <label>
                                    ห้องเรียน
                                    <select
                                      onChange={(event) => updateMeeting(
                                        schedule.id,
                                        meeting.id,
                                        "roomId",
                                        event.target.value,
                                      )}
                                      value={meeting.roomId}
                                    >
                                      <option value="">เลือกห้อง</option>
                                      {rooms.map((room) => (
                                        <option key={room.id} value={room.id}>
                                          {room.name} — ชั้น {room.floor}
                                        </option>
                                      ))}
                                    </select>
                                  </label>
                                  {(
                                    !meeting.dayOfWeek
                                    || !meeting.startTime
                                    || !meeting.endTime
                                    || !meeting.roomId
                                  ) && (
                                    <span className="schedule-field-error schedule-meeting-error">
                                      กรุณาป้อนวัน เวลา และห้องเรียนให้ครบ
                                    </span>
                                  )}
                                  {invalidTime && (
                                    <span className="schedule-field-error schedule-meeting-error">
                                      เวลาเลิกต้องอยู่หลังเวลาเริ่มเรียน
                                    </span>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                    ))}
                  </div>
                )}

                {error && <div className="form-error">{error}</div>}

                <div className="schedule-footer">
                  <button
                    className="back-button schedule-back"
                    onClick={() => {
                      setError("");
                      setModalStep("form");
                    }}
                    type="button"
                  >
                    ← ย้อนกลับ
                  </button>
                  <button
                    className="button button-primary schedule-next"
                    disabled={
                      schedules.length > 0
                      && !schedules.every(scheduleIsComplete)
                    }
                    onClick={continueToScan}
                    type="button"
                  >
                    {schedules.length === 0 ? "ข้าม" : "ถัดไป"}
                  </button>
                </div>
              </>
            )}

            {modalStep === "scan" && (
              <>
                <div className="modal-step">ขั้นตอนที่ 3 จาก 3</div>
                <h2 id="registration-title">สแกนใบหน้า</h2>
                <p className="modal-description">
                  จัดใบหน้าให้อยู่กึ่งกลาง มองตรง และให้มีเพียงคนเดียวในภาพ
                </p>

                <div className="registration-camera-wrap">
                  <video
                    autoPlay
                    className="registration-camera"
                    muted
                    playsInline
                    ref={videoRef}
                  />
                  <div className="face-guide" />
                  <div className="camera-caption">{cameraStatus}</div>
                </div>

                <canvas ref={canvasRef} style={{ display: "none" }} />

                <div className="registration-summary">
                  <span>{name}</span>
                  <span>{role === "student" ? externalId : "ไม่มีรหัสนักศึกษา"}</span>
                </div>

                {error && <div className="form-error">{error}</div>}

                <button
                  className="button button-primary modal-submit"
                  disabled={submitting || cameraStatus !== "พร้อมสแกนใบหน้า"}
                  onClick={() => void registerWithFace()}
                  type="button"
                >
                  {submitting ? "กำลังตรวจสอบและบันทึก..." : "สแกนและลงทะเบียน"}
                </button>

                <button
                  className="back-button"
                  disabled={submitting}
                  onClick={() => {
                    stopCamera();
                    setError("");
                    setModalStep("schedule");
                  }}
                  type="button"
                >
                  ← กลับไปตารางเรียน
                </button>
              </>
            )}

            {modalStep === "success" && (
              <div className="success-state">
                <div className="success-icon">✓</div>
                <h2 id="registration-title">เพิ่มข้อมูลสำเร็จแล้ว</h2>
                <p>
                  บันทึกข้อมูลและใบหน้าของ <strong>{name}</strong> เรียบร้อยแล้ว
                </p>
                <button
                  className="button button-primary modal-submit"
                  onClick={closeRegistration}
                  type="button"
                >
                  กลับหน้าหลัก
                </button>
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
