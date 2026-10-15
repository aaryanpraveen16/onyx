"use client";

import { useState, useRef, useEffect } from "react";

interface ChatMessage {
  id: string;
  sender: "user" | "ai";
  text: string;
  isFinal?: boolean;
}

export default function Home() {
  const [status, setStatus] = useState<"idle" | "connecting" | "connected" | "listening" | "thinking">("idle");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [interimTranscript, setInterimTranscript] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Auto scroll to bottom of chat
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, interimTranscript]);

  // Convert Float32Array PCM audio from Web Audio API to Int16 Little-Endian PCM Buffer
  const floatTo16BitPCM = (float32Array: Float32Array): ArrayBuffer => {
    const buffer = new ArrayBuffer(float32Array.length * 2);
    const view = new DataView(buffer);
    let offset = 0;
    for (let i = 0; i < float32Array.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, float32Array[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return buffer;
  };

  const startInterview = async () => {
    setErrorMessage(null);
    setStatus("connecting");

    try {
      // 1. Request Microphone Permission & Audio Stream
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
          sampleRate: 16000,
        },
      });
      mediaStreamRef.current = stream;

      // 2. Connect WebSocket to FastAPI Python Backend
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/interview";
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("Connected to Python FastAPI WebSocket backend");
        setStatus("listening");

        // 3. Initialize Web Audio Context at 16kHz for 16-bit PCM streaming
        const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)({
          sampleRate: 16000,
        });
        if (audioCtx.state === "suspended") {
          audioCtx.resume();
        }
        audioContextRef.current = audioCtx;

        const source = audioCtx.createMediaStreamSource(stream);
        // 2048 samples per chunk (~128ms buffer at 16kHz)
        const processor = audioCtx.createScriptProcessor(2048, 1, 1);
        scriptProcessorRef.current = processor;

        source.connect(processor);
        processor.connect(audioCtx.destination);

        processor.onaudioprocess = (e) => {
          if (ws.readyState === WebSocket.OPEN) {
            const inputData = e.inputBuffer.getChannelData(0);
            const pcmBuffer = floatTo16BitPCM(inputData);
            ws.send(pcmBuffer);
          }
        };
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "transcript") {
            if (data.is_final) {
              setInterimTranscript("");
              setMessages((prev) => [
                ...prev,
                { id: Date.now().toString(), sender: "user", text: data.text, isFinal: true },
              ]);
            } else {
              setInterimTranscript(data.text);
            }
          } else if (data.type === "status") {
            if (data.state === "thinking") {
              setStatus("thinking");
            }
          } else if (data.type === "ai_response") {
            setMessages((prev) => [
              ...prev,
              { id: Date.now().toString(), sender: "ai", text: data.text },
            ]);
            setStatus("listening");
          }
        } catch (err) {
          console.error("Error parsing WebSocket message:", err);
        }
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        setErrorMessage("WebSocket connection error. Ensure FastAPI server is running on port 8000.");
        stopInterview();
      };

      ws.onclose = () => {
        console.log("WebSocket connection closed");
        stopInterview();
      };
    } catch (err) {
      console.error("Microphone access error:", err);
      setErrorMessage("Microphone access denied or unfulfilled. Please allow microphone permissions.");
      setStatus("idle");
    }
  };

  const stopInterview = () => {
    // Disconnect Web Audio nodes
    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect();
      scriptProcessorRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    // Stop microphone tracks
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    // Close WebSocket
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }

    setStatus("idle");
    setInterimTranscript("");
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="logo-group">
          <div className="logo-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="22"/>
            </svg>
          </div>
          <div>
            <h1 className="title">AI Interviewer</h1>
            <p className="subtitle">Real-Time Voice Technical Agent (Milestone 3)</p>
          </div>
        </div>

        {/* Status Pill */}
        <div className="status-pill">
          <div className={`status-dot ${status}`} />
          <span>
            {status === "idle" && "Disconnected"}
            {status === "connecting" && "Connecting..."}
            {status === "connected" && "Connected"}
            {status === "listening" && "Microphone Active"}
            {status === "thinking" && "AI Thinking & Synthesizing..."}
          </span>
        </div>
      </header>

      {/* Main Layout Grid */}
      <main className="main-grid">
        {/* Left Control Panel */}
        <section className="glass-card">
          <h2 className="panel-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
            </svg>
            Session Controls
          </h2>

          <div className="mic-hero-section">
            <button
              onClick={status === "idle" ? startInterview : stopInterview}
              className={`mic-orb-button ${status !== "idle" ? "connected" : ""} ${status === "listening" ? "listening" : ""}`}
              disabled={status === "connecting"}
              title={status === "idle" ? "Click to Start Interview" : "Click to End Interview"}
            >
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8" y1="23" x2="16" y2="23"/>
              </svg>
            </button>

            {/* Live Audio Visualizer Bars */}
            <div className={`audio-visualizer ${status === "listening" ? "active" : ""}`}>
              <div className="audio-bar" />
              <div className="audio-bar" />
              <div className="audio-bar" />
              <div className="audio-bar" />
              <div className="audio-bar" />
              <div className="audio-bar" />
              <div className="audio-bar" />
            </div>

            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "capitalize" }}>
              {status === "idle" ? "Click orb to join interview" : status}
            </p>
          </div>

          {errorMessage && (
            <div style={{ color: "#fca5a5", fontSize: "0.85rem", background: "rgba(244,63,94,0.1)", padding: "0.75rem", borderRadius: "10px", marginBottom: "1rem" }}>
              {errorMessage}
            </div>
          )}

          {status === "idle" ? (
            <button onClick={startInterview} className="btn btn-primary">
              Start Voice Interview
            </button>
          ) : (
            <button onClick={stopInterview} className="btn btn-danger">
              End Interview Session
            </button>
          )}
        </section>

        {/* Right Live Transcript & Response Stream */}
        <section className="glass-card conversation-card">
          <h2 className="panel-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            Live Conversation Transcript
          </h2>

          <div className="chat-history">
            {messages.length === 0 && !interimTranscript && (
              <div className="empty-state">
                <div className="empty-icon">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  </svg>
                </div>
                <div>
                  <h3 style={{ fontSize: "1.05rem", color: "var(--text-primary)" }}>Ready to begin interview</h3>
                  <p style={{ fontSize: "0.85rem", marginTop: "0.25rem" }}>
                    Click "Start Voice Interview" to capture microphone audio and stream live to Python server.
                  </p>
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`msg-bubble ${msg.sender}`}>
                <span className="msg-label">{msg.sender === "user" ? "Candidate" : "Interviewer AI"}</span>
                {msg.text}
              </div>
            ))}

            {interimTranscript && (
              <div className="msg-bubble user interim">
                <span className="msg-label">Candidate (Speaking...)</span>
                {interimTranscript}
              </div>
            )}

            <div ref={chatBottomRef} />
          </div>
        </section>
      </main>
    </div>
  );
}
