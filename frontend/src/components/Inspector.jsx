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

export default function Inspector({ 
  components, 
  selectedId, 
  setSelectedId, 
  onParameterChange,
  busy 
}) {
  const selected = components.find((c) => c.id === selectedId) || components[0] || null;

  if (!components.length) {
    return (
      <aside className="panel panel-right">
        <div className="panel-header">
          <div>
            <div className="eyebrow">Inspector</div>
            <h2>Properties</h2>
          </div>
        </div>
        <div className="panel-body">
          <div className="empty-copy">Generate something to inspect and edit it here.</div>
        </div>
      </aside>
    );
  }

  return (
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
          <select value={selected?.id || ""} onChange={(e) => setSelectedId(e.target.value)}>
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

            <ParameterEditor 
              selected={selected} 
              onParameterChange={onParameterChange}
              busy={busy}
            />
          </>
        ) : null}
      </div>
    </aside>
  );
}

function ParameterEditor({ selected, onParameterChange, busy }) {
  const editableFields = PARAMETER_FIELDS[selected.type] || [];
  const [draftParameters, setDraftParameters] = useState({});

  useEffect(() => {
    const nextDraft = {};
    for (const field of editableFields) {
      if (selected[field] !== undefined) {
        nextDraft[field] = selected[field];
      }
    }
    setDraftParameters(nextDraft);
  }, [selected, editableFields]);

  function handleApply() {
    const parameters = {};
    for (const [field, value] of Object.entries(draftParameters)) {
      const typedValue = field.includes("teeth") ? Number.parseInt(value, 10) : Number.parseFloat(value);
      parameters[field] = Number.isNaN(typedValue) ? value : typedValue;
    }
    onParameterChange(selected.id, parameters);
  }

  if (!editableFields.length) return null;

  return (
    <div className="editor-block">
      <div className="editor-title">Edit parameters</div>
      {editableFields.map((field) => {
        const value = selected[field] ?? "";
        if (value === "") return null;
        
        return (
          <label className="field" key={field}>
            <span>{field}</span>
            <input
              type="number"
              step={field === "teeth" ? "1" : "0.5"}
              value={draftParameters[field] ?? value}
              onChange={(e) =>
                setDraftParameters((current) => ({
                  ...current,
                  [field]: e.target.value,
                }))
              }
            />
          </label>
        );
      })}
      <button 
        className="apply-button" 
        type="button" 
        onClick={handleApply}
        disabled={busy}
      >
        {busy ? "Applying..." : "Apply changes"}
      </button>
    </div>
  );
}

// Need to import useState and useEffect
import { useState, useEffect } from "react";
