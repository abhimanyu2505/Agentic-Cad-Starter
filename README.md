# Agentic CAD Intelligence Platform

> Hybrid Agentic CAD Builder: LLM reasoning + deterministic CAD accuracy

## 🚀 Quick Start

```bash
# 1. Set your OpenAI API key
export OPENAI_API_KEY="sk-your-key"  # Linux/macOS
$env:OPENAI_API_KEY="sk-your-key"   # Windows PowerShell

# 2. Start the system
docker-compose up --build

# 3. Open your browser
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
```

## ✨ Features

- **Natural Language CAD** - "Create a shaft 100mm long" → Instant geometry
- **Real-time 3D Preview** - React Three Fiber viewer with orbit controls
- **Parametric Editing** - Adjust parameters and see instant updates
- **Engineering Validation** - Ensures mechanical manufacturability
- **Export Ready** - STEP, STL, GLB formats for CAD software

## 📸 Screenshots

### Initial Interface
![Initial UI](screenshots/01_initial_ui.png)
*Clean three-panel layout: Chat (left), 3D Viewer (center), Inspector (right)*

### Creating Components with Natural Language
![Shaft Created](screenshots/02_shaft_created.png)
*Just type "Create a shaft 100mm long and 20mm diameter" - the system generates it instantly*

### Interactive 3D Viewer
![3D Viewer](screenshots/03_3d_viewer.png)
*Real-time 3D preview with orbit controls, lighting, and smooth rendering*

### Wireframe Mode
![Wireframe Mode](screenshots/04_wireframe_mode.png)
*Toggle wireframe to inspect internal geometry and edge definitions*

### Component Inspector
![Inspector Panel](screenshots/05_inspector_panel.png)
*Select components, view properties, and modify parameters in real-time*

### Multi-Component Assembly
![Gear Created](screenshots/07_gear_created.png)
*Build complex assemblies through conversational interaction - gears, shafts, bearings automatically positioned*

### Explode View
![Explode View](screenshots/08_explode_view.png)
*Slide explode control to separate components and understand assembly structure*

## 📚 Documentation

See the [`docs/`](./docs/) folder for comprehensive documentation:

- [Quick Start Guide](./docs/QUICK_START.md)
- [Screenshots & Features](./docs/SCREENSHOTS.md)
- [Example Prompts](./docs/EXAMPLE_PROMPTS.md)
- [Project Analysis](./docs/PROJECT_ANALYSIS.md)
- [Migration Summary](./docs/MIGRATION_SUMMARY.md)

## 🏗️ Architecture

```
├── backend/          FastAPI + CadQuery engine
├── frontend/         React + Three.js viewer
├── gear_engineering/ CAD pipeline & components
├── cq_gears/         Gear geometry library
├── outputs/          Generated CAD files
├── docs/             Documentation
└── archive/          Old Streamlit app
```

## 🎯 Supported Components

- Gears (spur/helical)
- Shafts
- Bearings
- Bolts
- Flanges
- Plates
- Housings
- Couplings
- Brackets
- Cylinders
- Nuts

## 🎮 UI Controls

### Chat Panel (Left)
- Natural language input
- Conversational flow
- Press Enter to send

### 3D Viewer (Center)
- Orbit: Left drag
- Pan: Right drag
- Zoom: Scroll
- Wireframe toggle
- Axis helper
- Grid toggle
- Explode view
- Screenshot capture
- Camera reset

### Inspector (Right)
- Component selection
- Property viewer
- Parameter editor
- Apply changes

## 📦 Output Files

All generated files saved to `outputs/`:
- `*.step` - Industry-standard CAD format
- `*.stl` - 3D printing ready
- `*.glb` - Web 3D viewer format

## 🛠️ Development

```bash
# Backend only
docker-compose up backend

# Frontend only
docker-compose up frontend

# Run tests
cd tests && python -m pytest
```

## 📄 License

MIT License - See LICENSE file

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md first.

---

**Made with ❤️ using FastAPI, React, and CadQuery**
