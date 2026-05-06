import { useEffect, useState, useRef } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { Bounds, Environment, Grid, OrbitControls, useGLTF, Center, GizmoHelper, GizmoViewport, PerspectiveCamera } from "@react-three/drei";
import { API_BASE, generate, getState, modify } from "./api";
import * as THREE from "three";

function Model({ url, wireframe = false, position = [0, 0, 0] }) {
  const gltf = useGLTF(url);
  const scene = gltf.scene.clone();
  
  useEffect(() => {
    scene.traverse((child) => {
      if (child.isMesh) {
        child.material = child.material.clone();
        child.material.wireframe = wireframe;
        child.material.side = THREE.DoubleSide;
        if (!wireframe) {
          child.material.metalness = 0.3;
          child.material.roughness = 0.4;
        }
      }
    });
  }, [scene, wireframe]);
  
  return <primitive object={scene} position={position} />;
}

function CameraReset({ trigger }) {
  const { camera, controls } = useThree();
  
  useEffect(() => {
    if (trigger > 0 && controls) {
      camera.position.set(60, 60, 60);
      camera.lookAt(0, 0, 0);
      controls.target.set(0, 0, 0);
      controls.update();
    }
  }, [trigger, camera, controls]);
  
  return null;
}

function Viewer({ assets, explodeDistance = 0, wireframe = false, showAxis = true, showGrid = true, onScreenshot, resetTrigger = 0 }) {
  const canvasRef = useRef();
  const urls = Object.values(assets || {}).map((asset) => `${API_BASE}${asset.url}`);

  if (!urls.length) {
    return <div className="viewer-empty">No assembly loaded</div>;
  }

  return (
    <Canvas ref={canvasRef} camera={{ position: [60, 60, 60], fov: 50 }} shadows>
      <color attach="background" args={["#f2f4f7"]} />
      <ambientLight intensity={0.8} />
      <directionalLight position={[50, 80, 50]} intensity={1.5} castShadow />
      <directionalLight position={[-50, -80, -50]} intensity={0.8} />
      <pointLight position={[0, 50, 0]} intensity={0.5} />
      <Center>
        <Bounds fit clip observe margin={2}>
          {urls.map((url, index) => {
            const offset = explodeDistance * (index - urls.length / 2);
            return <Model key={url} url={url} wireframe={wireframe} position={[offset, offset, offset]} />;
          })}
        </Bounds>
      </Center>
      {showGrid && (
        <Grid 
          args={[100, 100]} 
          cellSize={5}
          cellThickness={0.5}
          sectionSize={20}
          sectionThickness={1}
          sectionColor="#9ca3af" 
          cellColor="#d1d5db" 
          fadeDistance={200} 
          fadeStrength={1}
          position={[0, -0.01, 0]}
        />
      )}
      {showAxis && (
        <>
          <axesHelper args={[50]} />
          <GizmoHelper alignment="bottom-right" margin={[80, 80]}>
            <GizmoViewport axisColors={['#ef4444', '#22c55e', '#3b82f6']} labelColor="white" />
          </GizmoHelper>
        </>
      )}
      <OrbitControls makeDefault enableDamping dampingFactor={0.05} minDistance={10} maxDistance={500} />
      <Environment preset="city" />
      <ScreenshotHelper onScreenshot={onScreenshot} />
      <CameraReset trigger={resetTrigger} />
    </Canvas>
  );
}

function ScreenshotHelper({ onScreenshot }) {
  const { gl, scene, camera } = useThree();
  
  useEffect(() => {
    if (onScreenshot) {
      onScreenshot(() => {
        gl.render(scene, camera);
        return gl.domElement.toDataURL('image/png');
      });
    }
  }, [gl, scene, camera, onScreenshot]);
  
  return null;
}

function MessageList({ messages }) {
  return (
    <div className="chat-messages">
      {messages.length === 0 ? <div className="empty-copy">Describe the part or assembly you want to build.</div> : null}
      {messages.map((message, index) => (
        <div
          key={`${message.role}-${index}`}
          className={`message message-${message.role === "assistant" ? "assistant" : message.role}`}
        >
          {message.content}
        </div>
      ))}
    </div>
  );
}

const PARAMETER_FIELDS = {
  gear: ["module", "teeth", "thickness", "face_width"],
  shaft: ["length", "diameter"],
  bearing: ["inner_diameter", "outer_diameter", "width"],
  bolt: ["diameter", "length", "pitch"],
  flange: ["diameter", "thickness"],
  coupling: ["length", "diameter"],
  housing: ["length", "width", "height", "wall_thickness"],
  plate: ["length", "width", "thickness"],
  bracket: ["length", "width", "height", "thickness"],
  cylinder: ["radius", "height"],
  nut: ["diameter", "pitch"],
};

function App() {
  const [session, setSession] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [draftParameters, setDraftParameters] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [explodeDistance, setExplodeDistance] = useState(0);
  const [wireframe, setWireframe] = useState(false);
  const [screenshotFn, setScreenshotFn] = useState(null);
  const [showAxis, setShowAxis] = useState(true);
  const [showGrid, setShowGrid] = useState(true);
  const [resetTrigger, setResetTrigger] = useState(0);

  function takeScreenshot() {
    if (screenshotFn) {
      const dataUrl = screenshotFn();
      const link = document.createElement('a');
      link.download = `agentic-cad-${Date.now()}.png`;
      link.href = dataUrl;
      link.click();
    }
  }

  function resetCamera() {
    setResetTrigger(prev => prev + 1);
  }

  useEffect(() => {
    getState()
      .then((data) => {
        setSession(data);
        const first = data.design_state?.components?.[0]?.id || null;
        setSelectedId(first);
      })
      .catch((err) => {
        console.error("Failed to load initial state:", err);
        setError("Failed to connect to backend. Make sure the server is running.");
      });
  }, []);

  const components = session?.design_state?.components || [];
  const selected = components.find((component) => component.id === selectedId) || components[0] || null;

  useEffect(() => {
    if (!selected) {
      setDraftParameters({});
      return;
    }
    const nextDraft = {};
    for (const field of PARAMETER_FIELDS[selected.type] || []) {
      if (selected[field] !== undefined) {
        nextDraft[field] = selected[field];
      }
    }
    setDraftParameters(nextDraft);
  }, [selected]);

  async function submitPrompt(event) {
    event.preventDefault();
    if (!prompt.trim()) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await generate(prompt.trim());
      setSession(next);
      if (!selectedId) {
        setSelectedId(next.design_state?.components?.[0]?.id || null);
      }
      setPrompt("");
    } catch (err) {
      console.error("Generation failed:", err);
      setError("Failed to generate component. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitPrompt(event);
    }
  }

  async function applyParameterChanges() {
    if (!selected) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const parameters = {};
      for (const [field, value] of Object.entries(draftParameters)) {
        const typedValue = field.includes("teeth") ? Number.parseInt(value, 10) : Number.parseFloat(value);
        parameters[field] = Number.isNaN(typedValue) ? value : typedValue;
      }
      const next = await modify({
        componentId: selected.id,
        parameters,
      });
      setSession(next);
    } catch (err) {
      console.error("Modification failed:", err);
      setError("Failed to apply changes. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="panel panel-left">
        <div className="panel-header">
          <div>
            <div className="eyebrow">Agentic CAD</div>
            <h1>Chat</h1>
          </div>
          <span className="pill">{components.length} items</span>
        </div>
        <MessageList messages={session?.messages || []} />
        {error && <div className="message message-error">{error}</div>}
        <form className="chat-form" onSubmit={submitPrompt}>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Design a gear, add a shaft, or modify an assembly..."
            rows={3}
          />
          <div className="form-footer">
            <span className="keyboard-hint">Press Enter to send, Shift+Enter for new line</span>
            <button type="submit" disabled={busy}>
              {busy ? "Working..." : "Send"}
            </button>
          </div>
        </form>
      </aside>

      <main className="viewer-panel">
        <div className="viewer-header">
          <div>
            <div className="eyebrow">Workspace</div>
            <h2>3D Viewer</h2>
          </div>
          <div className="viewer-controls">
            <label className="control-item">
              <input
                type="checkbox"
                checked={wireframe}
                onChange={(e) => setWireframe(e.target.checked)}
              />
              <span>Wireframe</span>
            </label>
            <label className="control-item">
              <input
                type="checkbox"
                checked={showAxis}
                onChange={(e) => setShowAxis(e.target.checked)}
              />
              <span>Axis</span>
            </label>
            <label className="control-item">
              <input
                type="checkbox"
                checked={showGrid}
                onChange={(e) => setShowGrid(e.target.checked)}
              />
              <span>Grid</span>
            </label>
            <label className="control-item">
              <span>Explode</span>
              <input
                type="range"
                min="0"
                max="50"
                value={explodeDistance}
                onChange={(e) => setExplodeDistance(Number(e.target.value))}
              />
            </label>
            {components.length > 0 && (
              <>
                <button className="icon-button" onClick={resetCamera} title="Reset Camera">
                  🎯
                </button>
                <button className="icon-button" onClick={takeScreenshot} title="Take Screenshot">
                  📷
                </button>
                <a 
                  href={`${API_BASE}/outputs/agentic_assembly_output.step`} 
                  download
                  className="export-button"
                >
                  ⬇ Export STEP
                </a>
              </>
            )}
          </div>
        </div>
        <div className="viewer-frame">
          <Viewer 
            assets={session?.viewer_assets || {}} 
            explodeDistance={explodeDistance} 
            wireframe={wireframe}
            showAxis={showAxis}
            showGrid={showGrid}
            resetTrigger={resetTrigger}
            onScreenshot={setScreenshotFn}
          />
        </div>
      </main>

      <aside className="panel panel-right">
        <div className="panel-header">
          <div>
            <div className="eyebrow">Inspector</div>
            <h2>Properties</h2>
          </div>
        </div>

        <div className="panel-body">
          <label className="field">
            <span>Selected component</span>
            <select value={selected?.id || ""} onChange={(event) => setSelectedId(event.target.value)}>
              {components.map((component) => (
                <option key={component.id} value={component.id}>
                  {component.id}
                </option>
              ))}
            </select>
          </label>

          {selected ? (
            <>
              <div className="component-meta">
                <div className="component-name">{selected.id}</div>
                <div className="component-type">{selected.type}</div>
              </div>

              <div className="property-list">
                {Object.entries(selected)
                  .filter(([key]) => !["id", "type", "extracted_parameters"].includes(key))
                  .map(([key, value]) => (
                    <div className="property-row" key={key}>
                      <span>{key}</span>
                      <span>{String(value)}</span>
                    </div>
                  ))}
              </div>

              <div className="editor-block">
                <div className="editor-title">Edit parameters</div>
                {(PARAMETER_FIELDS[selected.type] || []).map((field) => {
                  const value = selected[field] ?? "";
                  if (value === "") {
                    return null;
                  }
                  return (
                    <label className="field" key={field}>
                      <span>{field}</span>
                      <input
                        type="number"
                        step={field === "teeth" ? "1" : "0.5"}
                        value={draftParameters[field] ?? value}
                        onChange={(event) =>
                          setDraftParameters((current) => ({
                            ...current,
                            [field]: event.target.value,
                          }))
                        }
                      />
                    </label>
                  );
                })}
                {(PARAMETER_FIELDS[selected.type] || []).length ? (
                  <button className="apply-button" type="button" onClick={applyParameterChanges} disabled={busy}>
                    {busy ? "Applying..." : "Apply changes"}
                  </button>
                ) : null}
              </div>
            </>
          ) : (
            <div className="empty-copy">Generate something to inspect and edit it here.</div>
          )}
        </div>
      </aside>
    </div>
  );
}

export default App;
