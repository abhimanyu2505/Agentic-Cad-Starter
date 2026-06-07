import { useEffect, useState } from "react";
import { API_BASE, generate, getState, modify } from "./api";
import ChatPanel from "./components/ChatPanel";
import Viewer3D from "./components/Viewer3D";
import ViewerControls from "./components/ViewerControls";
import Inspector from "./components/Inspector";

function App() {
  const [session, setSession] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  
  // Viewer controls
  const [explodeDistance, setExplodeDistance] = useState(0);
  const [wireframe, setWireframe] = useState(false);
  const [showAxis, setShowAxis] = useState(true);
  const [showGrid, setShowGrid] = useState(true);
  const [resetTrigger, setResetTrigger] = useState(0);
  const [screenshotFn, setScreenshotFn] = useState(null);

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

  async function handlePromptSubmit(prompt) {
    setBusy(true);
    setError(null);
    try {
      const next = await generate(prompt);
      setSession(next);
      if (!selectedId) {
        setSelectedId(next.design_state?.components?.[0]?.id || null);
      }
    } catch (err) {
      console.error("Generation failed:", err);
      setError("Failed to generate component. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleParameterChange(componentId, parameters) {
    setBusy(true);
    setError(null);
    try {
      const next = await modify({ componentId, parameters });
      setSession(next);
    } catch (err) {
      console.error("Modification failed:", err);
      setError("Failed to apply changes. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function handleResetCamera() {
    setResetTrigger(prev => prev + 1);
  }

  function handleScreenshot() {
    if (screenshotFn) {
      const dataUrl = screenshotFn();
      const link = document.createElement('a');
      link.download = `agentic-cad-${Date.now()}.png`;
      link.href = dataUrl;
      link.click();
    }
  }

  return (
    <div className="app-shell">
      <ChatPanel 
        messages={session?.messages || []} 
        onSubmit={handlePromptSubmit}
        busy={busy}
        error={error}
      />

      <main className="viewer-panel">
        <div className="viewer-header">
          <div>
            <div className="eyebrow">Workspace</div>
            <h2>3D Viewer</h2>
          </div>
          <ViewerControls
            wireframe={wireframe}
            setWireframe={setWireframe}
            showAxis={showAxis}
            setShowAxis={setShowAxis}
            showGrid={showGrid}
            setShowGrid={setShowGrid}
            explodeDistance={explodeDistance}
            setExplodeDistance={setExplodeDistance}
            componentsExist={components.length > 0}
            onReset={handleResetCamera}
            onScreenshot={handleScreenshot}
            apiBase={API_BASE}
          />
        </div>
        <div className="viewer-frame">
          <Viewer3D 
            assets={session?.viewer_assets || {}} 
            explodeDistance={explodeDistance} 
            wireframe={wireframe}
            showAxis={showAxis}
            showGrid={showGrid}
            resetTrigger={resetTrigger}
            onScreenshot={setScreenshotFn}
            apiBase={API_BASE}
          />
        </div>
      </main>

      <Inspector 
        components={components}
        selectedId={selectedId}
        setSelectedId={setSelectedId}
        onParameterChange={handleParameterChange}
        busy={busy}
      />
    </div>
  );
}

export default App;
