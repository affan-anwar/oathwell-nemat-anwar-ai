import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import { H, W, detectSwipe, motionCentroid } from "./gesture.js";
import { Modal } from "./ui.jsx";

const Ctx = createContext(null);
export const useGesture = () => useContext(Ctx);

export function GestureProvider({ children, onSwipe }) {
  const [status, setStatus] = useState("off"); // off, requesting, on, denied, unsupported, error
  const [message, setMessage] = useState("");
  const [last, setLast] = useState(null);
  const stream = useRef(null), timer = useRef(null), prev = useRef(null), samples = useRef([]), cool = useRef(0), video = useRef(null), canvas = useRef(null);
  const swipeRef = useRef(onSwipe);
  swipeRef.current = onSwipe;

  const stop = useCallback(() => {
    clearInterval(timer.current);
    stream.current?.getTracks().forEach((t) => t.stop()); // the camera light goes off
    stream.current = null; video.current = null; prev.current = null; samples.current = [];
    setStatus("off");
  }, []);

  const tick = useCallback(() => {
    const v = video.current, c = canvas.current;
    if (!v || !c || v.readyState < 2) return;
    const ctx = c.getContext("2d", { willReadFrequently: true });
    if (!ctx) return;
    ctx.drawImage(v, 0, 0, W, H);
    const px = ctx.getImageData(0, 0, W, H).data, gray = new Array(W * H);
    for (let i = 0; i < W * H; i++) gray[i] = (px[i * 4] + px[i * 4 + 1] + px[i * 4 + 2]) / 3;
    if (prev.current) {
      const m = motionCentroid(prev.current, gray);
      const now = performance.now();
      samples.current = [...samples.current.filter((s) => now - s.t < 1100), { t: now, ...m }];
      const dir = now > cool.current ? detectSwipe(samples.current) : null;
      if (dir) { cool.current = now + 1300; samples.current = []; setLast(dir); swipeRef.current?.(dir); }
    }
    prev.current = gray;
  }, []);

  const start = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) { setStatus("unsupported"); setMessage("This browser cannot use a camera here. Use the keyboard shortcuts instead."); return; }
    setStatus("requesting"); setMessage("");
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: false });
      stream.current = s;
      const v = document.createElement("video");
      v.muted = true; v.playsInline = true; v.srcObject = s;
      await Promise.resolve(v.play?.()).catch(() => {});
      video.current = v;
      const c = document.createElement("canvas");
      c.width = W; c.height = H; canvas.current = c;
      timer.current = setInterval(tick, 80);
      setStatus("on");
    } catch (e) {
      setStatus(e?.name === "NotAllowedError" || e?.name === "SecurityError" ? "denied" : "error");
      setMessage(e?.name === "NotAllowedError" ? "Camera permission was not given. Gestures stay off. You can use the mouse, keyboard or touch." : "The camera could not be started. Check that it is connected and not used by another app.");
    }
  }, [tick]);

  useEffect(() => stop, [stop]);
  return <Ctx.Provider value={{ status, message, last, start, stop }}>{children}</Ctx.Provider>;
}

export function CameraIndicator() {
  const g = useGesture();
  if (!g || g.status !== "on") return null;
  return <span className="pillbtn" role="status" style={{ borderColor: "#ef4444" }}><span className="recdot" />Camera on<button className="btn sm" onClick={g.stop}>Stop</button></span>;
}

function useCameraPermission() {
  const [state, setState] = useState("unknown");
  useEffect(() => {
    let p;
    navigator.permissions?.query({ name: "camera" }).then((r) => { p = r; setState(r.state); r.onchange = () => setState(r.state); }).catch(() => {});
    return () => { if (p) p.onchange = null; };
  }, []);
  return state;
}

export function GesturePanel() {
  const g = useGesture();
  const perm = useCameraPermission();
  const [help, setHelp] = useState(false);
  if (!g) return null;
  const on = g.status === "on";
  const shown = on ? "granted" : perm;
  return (
    <>
      <div className="sw2"><span>Enable gesture controls</span>
        <button className="toggle" role="switch" aria-checked={on} aria-label="Enable gesture controls" disabled={g.status === "requesting"} onClick={on ? g.stop : g.start} /></div>
      <div className="sw2"><span>Hand swipe (left and right)</span>
        <button className="toggle" role="switch" aria-checked={on} aria-label="Hand swipe" disabled title="Turns on with the camera" /></div>
      <div className="sw2"><span>Face gestures <small className="mu">not available</small></span>
        <button className="toggle" role="switch" aria-checked={false} aria-label="Face gestures" disabled title="Needs a face-landmark model that is not included" /></div>
      <div className="sw2"><span>Camera permission</span><span className={shown === "granted" ? "pillok" : "chip2"}>{shown}</span></div>
      {g.message && <p className="small" role="alert" style={{ color: "var(--wn)" }}>{g.message}</p>}
      {on && g.last && <p className="small mu" role="status">Last gesture: swipe {g.last}</p>}
      <button className="link" onClick={() => setHelp(true)}>How to use gestures</button>
      {help && <Modal title="How gestures work" onClose={() => setHelp(false)}>
        <p><b>Camera:</b> nothing starts until you switch it on and allow the browser's camera prompt. A red "Camera on" indicator stays visible while it runs. Switching it off stops the camera.</p>
        <p><b>Swipe:</b> move your hand across the camera view. Swipe to your left for the next page, to your right for the previous page. It detects movement, not a particular hand, so keep the background still and use good light.</p>
        <p><b>Privacy:</b> frames are analysed in this browser only. They are never recorded, stored or sent anywhere.</p>
        <p><b>Safety:</b> gestures only change pages. They can never publish, approve, delete, pay or change permissions.</p>
        <p><b>Without a camera:</b> use Alt + Left Arrow and Alt + Right Arrow, the mouse, or touch.</p>
        <p className="mu small">Face gestures such as blinking need a face-landmark model and are not available.</p></Modal>}
    </>
  );
}
