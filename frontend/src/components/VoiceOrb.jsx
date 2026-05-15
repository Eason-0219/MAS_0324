// frontend/src/components/VoiceOrb.jsx
import { useState, useEffect, useRef, useCallback } from 'react';

const VOICE_WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://localhost:8000/ws/voice`;

const STATE_COLORS = {
  idle:            { primary: '#6366f1', secondary: '#4f46e5', glow: 'rgba(99,102,241,0.3)' },
  listening:       { primary: '#22c55e', secondary: '#16a34a', glow: 'rgba(34,197,94,0.4)'  },
  speech_detected: { primary: '#3b82f6', secondary: '#2563eb', glow: 'rgba(59,130,246,0.5)' },
  processing:      { primary: '#f59e0b', secondary: '#d97706', glow: 'rgba(245,158,11,0.5)' },
  speaking:        { primary: '#10b981', secondary: '#059669', glow: 'rgba(16,185,129,0.5)' },
};

export default function VoiceOrb({ onResponse, autoStart = false, onClose }) {
  const [voiceState, setVoiceState] = useState('idle');   // idle = 未啟動
  const [isActive, setIsActive]     = useState(autoStart);    // 使用者是否已點擊啟動
  const [transcript, setTranscript] = useState('');
  const [lastResponse, setLastResponse] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState('');

  const canvasRef    = useRef(null);
  const wsRef        = useRef(null);
  const mediaRef     = useRef(null);   // MediaStream
  const processorRef = useRef(null);   // ScriptProcessorNode
  const audioCtxRef  = useRef(null);
  const analyserRef  = useRef(null);
  const animRef      = useRef(null);
  const ttsChunksRef = useRef([]);
  const isPlayingRef = useRef(false);
  const transcriptRef = useRef('');    // 給 onResponse 用的 ref

  // 同步 transcript ref
  useEffect(() => { transcriptRef.current = transcript; }, [transcript]);

  // ── WebSocket ──────────────────────────────────────────────────────
  const connectWS = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) return;

    const ws = new WebSocket(VOICE_WS_URL);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      setIsConnected(true);
      setError('');
    };

    ws.onmessage = async (e) => {
      if (e.data instanceof ArrayBuffer) {
        ttsChunksRef.current.push(e.data);
        return;
      }
      try {
        const msg = JSON.parse(e.data);
        switch (msg.type) {
          case 'state':
            setVoiceState(msg.state);
            if (msg.state === 'speaking') ttsChunksRef.current = [];
            break;
          case 'transcript':
            setTranscript(msg.text);
            break;
          case 'response':
            setLastResponse(msg.text);
            onResponse?.({ role: 'user', content: transcriptRef.current },
                         { role: 'assistant', content: msg.text,
                           route: msg.route, model_used: msg.model_used,
                           latency_ms: msg.latency_ms, tool_name: msg.tool_name });
            break;
          case 'tts_end':
            playTTS();
            break;
          case 'timeout':
            console.log("⏱️ 靜音5秒，後端要求退出語音模式");
            setIsActive(false);
            setVoiceState('idle');
            stopMic();
            stopTTS();
            if (wsRef.current) {
              wsRef.current.onclose = null; // 防止 zombie 重連迴圈
              wsRef.current.close();
            }
            onClose?.(); // 退出 VoiceOrb
            break;
          case 'error':
            setError(msg.message);
            setTimeout(() => setError(''), 5000);
            break;
        }
      } catch {}
    };

    ws.onclose = () => {
      setIsConnected(false);
      setVoiceState('idle');
      // 只在 active 時重連
      if (isActive) setTimeout(connectWS, 3000);
    };

    ws.onerror = () => setError('語音 WebSocket 連線失敗');
    wsRef.current = ws;
  }, [isActive]);

  // ── TTS 播放 ───────────────────────────────────────────────────────
  const playTTS = async () => {
    if (isPlayingRef.current) return;
    isPlayingRef.current = true;

    const chunks = ttsChunksRef.current;
    if (!chunks.length) { isPlayingRef.current = false; return; }

    const total = chunks.reduce((s, c) => s + c.byteLength, 0);
    const merged = new Uint8Array(total);
    let off = 0;
    for (const c of chunks) { merged.set(new Uint8Array(c), off); off += c.byteLength; }
    
    // Clear chunks buffer for next time
    ttsChunksRef.current = [];

    const url = URL.createObjectURL(new Blob([merged], { type: 'audio/mpeg' }));
    const audio = new Audio(url);
    window._ttsAudio = audio;

    audio.onended = () => {
      URL.revokeObjectURL(url);
      isPlayingRef.current = false;
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'tts_played' })); // 通知後端播放完畢
        setVoiceState('listening');
      }
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      isPlayingRef.current = false;
    };
    try { await audio.play(); } catch (e) {
      console.error('TTS play error:', e);
      isPlayingRef.current = false;
    }
  };

  const stopTTS = () => {
    window._ttsAudio?.pause();
    window._ttsAudio = null;
    isPlayingRef.current = false;
    ttsChunksRef.current = [];
  };

  // ── 麥克風（由 user gesture 觸發）────────────────────────────────
  const startMic = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: {
        channelCount: 1, 
        echoCancellation: true,
        noiseSuppression: false, 
        autoGainControl: false,
      }});
      mediaRef.current = stream;

      const ctx = new AudioContext();   // 不指定 sampleRate，用系統預設
      audioCtxRef.current = ctx;
      if (ctx.state === 'suspended') await ctx.resume();

      const nativeSR = ctx.sampleRate;
      const TARGET   = 16000;
      console.log(`🎙️ AudioContext sampleRate=${nativeSR}, state=${ctx.state}`);

      const source   = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;

      const proc = ctx.createScriptProcessor(2048, 1, 1);
      let dbgFrame = 0;
      proc.onaudioprocess = (e) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) return;
        const f32 = e.inputBuffer.getChannelData(0);

        dbgFrame++;
        if (dbgFrame % 30 === 0) {
          const mx = f32.reduce((m, v) => Math.max(m, Math.abs(v)), 0);
          console.log(`🔊 frame=${dbgFrame} maxAmp=${mx.toFixed(4)}`);
        }

        // Downsample 到 16kHz
        const ratio  = nativeSR / TARGET;
        const outLen = Math.floor(f32.length / ratio);
        const rs     = new Float32Array(outLen);
        for (let i = 0; i < outLen; i++) {
          const si = i * ratio, lo = Math.floor(si), hi = Math.min(lo + 1, f32.length - 1);
          rs[i] = f32[lo] * (1 - (si - lo)) + f32[hi] * (si - lo);
        }

        // Float32 → Int16
        const i16 = new Int16Array(outLen);
        for (let i = 0; i < outLen; i++) {
          const s = Math.max(-1, Math.min(1, rs[i]));
          i16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        wsRef.current.send(i16.buffer);
      };

      // source → analyser（動畫用）
      // source → proc → destination（PCM 擷取）
      source.connect(analyser);
      source.connect(proc);
      proc.connect(ctx.destination);
      processorRef.current = proc;

      const t = stream.getAudioTracks()[0];
      console.log(`🎤 track: enabled=${t?.enabled}, muted=${t?.muted}, state=${t?.readyState}`);

    } catch (e) {
      console.error('麥克風錯誤:', e);
      setError('無法存取麥克風: ' + e.message);
      setIsActive(false);
    }
  };

  const stopMic = () => {
    processorRef.current?.disconnect();
    processorRef.current = null;
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
    mediaRef.current?.getTracks().forEach(t => t.stop());
    mediaRef.current = null;
  };

  // 初始載入如果自動啟動，取得麥克風與連線
  useEffect(() => {
    if (autoStart) {
      setVoiceState('listening');
      connectWS();
      startMic().catch(e => {
        console.error('啟動麥克風失敗:', e);
        setIsActive(false);
        setVoiceState('idle');
      });
    }
  }, []); // eslint-disable-line

  // ── 啟動 / 停止語音模式（user gesture）──────────────────────────
  const toggleVoice = async () => {
    if (isActive) {
      // 停止
      setIsActive(false);
      setVoiceState('idle');
      stopMic();
      stopTTS();
      wsRef.current?.close();
      onClose?.();
    } else {
      // 啟動（這裡是 click handler，符合 user gesture 要求）
      setIsActive(true);
      setVoiceState('listening');
      connectWS();
      await startMic();
    }
  };

  // WS 在 isActive 變化時重連
  useEffect(() => {
    if (!isActive) return;
    connectWS();
  }, [isActive]);

  // 清理
  useEffect(() => {
    return () => {
      stopMic();
      stopTTS();
      if (wsRef.current) {
        wsRef.current.onclose = null; // 防止 unmount 時觸發重連
        wsRef.current.close();
      }
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, []);

  // ── Canvas 動畫 ────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const W = 400, H = 400;
    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    ctx.scale(dpr, dpr);
    const cx = W / 2, cy = H / 2;
    let t = 0;

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      t += 0.02;

      const colors = STATE_COLORS[voiceState] || STATE_COLORS.idle;
      const base   = voiceState === 'speaking' ? 90 : 75;

      let vol = 0;
      if (analyserRef.current && isActive) {
        const d = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(d);
        vol = d.reduce((s, v) => s + v, 0) / d.length / 255;
      }

      const pulse = voiceState === 'speech_detected' ? 1 + vol * 0.6
                  : voiceState === 'speaking'         ? 1 + Math.sin(t * 3) * 0.08
                  : voiceState === 'processing'       ? 1 + Math.sin(t * 5) * 0.05
                  : isActive                          ? 1 + Math.sin(t * 1.5) * 0.03
                  : 1;

      // 光暈
      const gr = ctx.createRadialGradient(cx, cy, base * 0.5, cx, cy, base * pulse * 1.8);
      gr.addColorStop(0, colors.glow);
      gr.addColorStop(1, 'transparent');
      ctx.fillStyle = gr;
      ctx.fillRect(0, 0, W, H);

      // 流體層
      for (const [amp, freq, spd, alpha] of [[12,4,2,.3],[8,6,3,.2],[15,3,1.5,.4]]) {
        ctx.beginPath();
        const a = amp * pulse + vol * 20;
        for (let ang = 0; ang <= Math.PI * 2; ang += 0.02) {
          const r = base * pulse + Math.sin(ang * freq + t * spd) * a;
          const x = cx + Math.cos(ang) * r, y = cy + Math.sin(ang) * r;
          ang === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.fillStyle = colors.primary + Math.round(alpha * 255).toString(16).padStart(2, '0');
        ctx.fill();
      }

      // 核心
      const cg = ctx.createRadialGradient(cx-15, cy-15, 10, cx, cy, base * pulse * 0.7);
      cg.addColorStop(0, colors.primary + 'cc');
      cg.addColorStop(1, colors.secondary + '88');
      ctx.beginPath();
      ctx.arc(cx, cy, base * pulse * 0.65, 0, Math.PI * 2);
      ctx.fillStyle = cg;
      ctx.fill();

      // 高光
      ctx.beginPath();
      ctx.arc(cx - 12, cy - 18, 12, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,0.15)';
      ctx.fill();

      // 未啟動時顯示播放圖示
      if (!isActive) {
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.font = '36px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('🎙️', cx, cy);
      }

      // 處理中旋轉環
      if (voiceState === 'processing') {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(t * 3);
        ctx.strokeStyle = colors.primary;
        ctx.lineWidth = 3;
        ctx.setLineDash([20, 15]);
        ctx.beginPath();
        ctx.arc(0, 0, base * 1.3, 0, Math.PI * 1.5);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();
      }

      // 粒子
      if (voiceState === 'speech_detected' || voiceState === 'speaking') {
        for (let i = 0; i < 8; i++) {
          const ang  = (i / 8) * Math.PI * 2 + t;
          const dist = base * 1.4 + Math.sin(t * 2 + i) * 15;
          ctx.beginPath();
          ctx.arc(cx + Math.cos(ang) * dist, cy + Math.sin(ang) * dist,
                  2 + Math.sin(t * 3 + i) * 1.5, 0, Math.PI * 2);
          ctx.fillStyle = colors.primary + '99';
          ctx.fill();
        }
      }

      animRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [voiceState, isActive]);

  const stateLabel = !isActive ? '點擊球體啟動語音模式'
    : { listening: '🎙️ 聆聽中 — 直接開口說話',
        speech_detected: '🔊 偵測到語音...',
        processing: '🤔 思考中...',
        speaking: '🔈 回答中...',
      }[voiceState] || '初始化中...';

  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center',
                  justifyContent:'center', height:'100%', position:'relative' }}>

      {isActive && !isConnected && (
        <div style={{ position:'absolute', top:20, color:'#f87171', fontSize:'0.85rem',
                      background:'rgba(248,113,113,0.1)', padding:'6px 16px', borderRadius:20 }}>
          ⚠️ 語音服務連線中...
        </div>
      )}

      {error && (
        <div style={{ position:'absolute', top:60, color:'#fbbf24', fontSize:'0.8rem',
                      maxWidth:350, textAlign:'center' }}>
          {error}
        </div>
      )}

      <canvas
        ref={canvasRef}
        style={{ width:400, height:400, cursor:'pointer' }}
        onClick={() => {
          if (voiceState === 'speaking') {
            stopTTS();
            wsRef.current?.send(JSON.stringify({ type: 'interrupt' }));
          } else {
            toggleVoice();
          }
        }}
      />

      <div style={{ color:'rgba(255,255,255,0.6)', fontSize:'0.9rem',
                    marginTop:-20, textAlign:'center' }}>
        {stateLabel}
      </div>

      {isActive && (
        <button onClick={toggleVoice} style={{
          marginTop: 12, padding: '6px 18px', borderRadius: 20,
          border: '1px solid rgba(255,255,255,0.2)',
          background: 'rgba(255,255,255,0.05)',
          color: 'rgba(255,255,255,0.5)', fontSize: '0.8rem',
          cursor: 'pointer', fontFamily: 'inherit',
        }}>
          ⏹ 停止語音模式
        </button>
      )}

      {transcript && (
        <div style={{ marginTop:16, padding:'8px 20px',
                      background:'rgba(99,102,241,0.15)',
                      border:'1px solid rgba(99,102,241,0.3)',
                      borderRadius:12, maxWidth:500,
                      color:'rgba(255,255,255,0.9)', fontSize:'0.9rem',
                      textAlign:'center' }}>
          🎤 {transcript}
        </div>
      )}

      {lastResponse && (
        <div style={{ marginTop:12, padding:'10px 20px',
                      background:'rgba(16,185,129,0.1)',
                      border:'1px solid rgba(16,185,129,0.2)',
                      borderRadius:12, maxWidth:500,
                      color:'rgba(255,255,255,0.8)', fontSize:'0.85rem',
                      textAlign:'center', maxHeight:120, overflow:'auto' }}>
          {lastResponse}
        </div>
      )}

      {voiceState === 'speaking' && (
        <div style={{ marginTop:12, color:'rgba(255,255,255,0.4)', fontSize:'0.75rem' }}>
          💡 點擊球體可打斷回答
        </div>
      )}
    </div>
  );
}
