export default function ViewerControls({
  wireframe,
  setWireframe,
  showAxis,
  setShowAxis,
  showGrid,
  setShowGrid,
  explodeDistance,
  setExplodeDistance,
  componentsExist,
  onReset,
  onScreenshot,
  onExport,
  apiBase
}) {
  return (
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
      {componentsExist && (
        <>
          <button className="icon-button" onClick={onReset} title="Reset Camera">
            🎯
          </button>
          <button className="icon-button" onClick={onScreenshot} title="Take Screenshot">
            📷
          </button>
          <a 
            href={`${apiBase}/outputs/agentic_assembly_output.step`} 
            download
            className="export-button"
          >
            ⬇ Export STEP
          </a>
        </>
      )}
    </div>
  );
}
