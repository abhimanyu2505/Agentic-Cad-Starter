# Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Set Your OpenAI API Key

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="sk-your-api-key-here"

# Linux / macOS / WSL
export OPENAI_API_KEY="sk-your-api-key-here"
```

### Step 2: Start the Application

```bash
docker-compose up --build
```

Wait for both services to start:
- ✅ Backend ready: `http://localhost:8000`
- ✅ Frontend ready: `http://localhost:5173`

### Step 3: Open Your Browser

Navigate to: **http://localhost:5173**

---

## 💬 Try These Examples

### Example 1: Simple Shaft
```
Create a shaft 100mm long and 15mm diameter
```

### Example 2: Gear
```
Create a module 2 gear with 30 teeth
```

### Example 3: Gear on Shaft
```
Create a shaft 75mm long with a module 2 gear mounted on it
```

### Example 4: Gearbox
```
Design a 4:1 gearbox at 1500 RPM
```

### Example 5: Bearing
```
Add a bearing with 20mm inner diameter and 40mm outer diameter
```

---

## 🎨 UI Overview

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌──────────┐  ┌────────────────────┐  ┌──────────────┐   │
│  │          │  │                    │  │              │   │
│  │  CHAT    │  │    3D VIEWER       │  │  INSPECTOR   │   │
│  │          │  │                    │  │              │   │
│  │  Type    │  │  Rotate, zoom,     │  │  View and    │   │
│  │  natural │  │  pan the 3D        │  │  edit        │   │
│  │  language│  │  model             │  │  component   │   │
│  │  prompts │  │                    │  │  properties  │   │
│  │          │  │                    │  │              │   │
│  └──────────┘  └────────────────────┘  └──────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Left Panel: Chat
- Type natural language descriptions
- See conversation history
- Get feedback and questions

### Center Panel: 3D Viewer
- View generated CAD models
- Rotate: Left mouse drag
- Pan: Right mouse drag
- Zoom: Mouse wheel

### Right Panel: Inspector
- Select components from dropdown
- View all properties
- Edit parameters (length, diameter, etc.)
- Click "Apply changes" to regenerate

---

## 🔧 Editing Components

1. Generate a component (e.g., "Create a shaft 100mm long")
2. In the right panel, select the component
3. Edit parameters (e.g., change length to 150)
4. Click "Apply changes"
5. Watch the 3D model update!

---

## 📁 Output Files

All generated CAD files are saved to:
```
outputs/
├── agentic_assembly_output.step  # Full assembly (STEP format)
├── shaft_1.glb                   # Individual components (GLB)
├── shaft_1.stl                   # Individual components (STL)
├── gear_1.glb
└── ...
```

Open `.step` files in:
- FreeCAD
- Fusion 360
- SolidWorks
- Any CAD software

---

## 🛑 Stopping the Application

```bash
# Press Ctrl+C in the terminal, then:
docker-compose down
```

---

## 🐛 Troubleshooting

### "Failed to connect to backend"
- Make sure both services are running: `docker-compose up`
- Check backend health: `curl http://localhost:8000/health`

### "OpenAI API key not configured"
- Set the environment variable (see Step 1)
- Restart: `docker-compose down && docker-compose up`

### 3D model not showing
- Wait a few seconds for generation to complete
- Check browser console (F12) for errors
- Verify files exist in `outputs/` directory

### Generation takes too long
- Complex assemblies (gearboxes) can take 10-15 seconds
- Check backend logs: `docker-compose logs backend`

---

## 📚 Learn More

- **API Documentation:** http://localhost:8000/docs
- **Migration Details:** See `MIGRATION_SUMMARY.md`
- **Verification Report:** See `VERIFICATION_REPORT.md`

---

## 🎯 Tips

1. **Be specific:** "Create a shaft 100mm long and 15mm diameter" works better than "make a shaft"
2. **One component at a time:** Generate one component, then add more
3. **Use the inspector:** Edit parameters visually instead of re-typing prompts
4. **Check outputs:** All files are saved to `outputs/` directory

---

## ✨ What Makes This Special?

- **Hybrid Intelligence:** LLM for understanding + CadQuery for precision
- **Conversational:** Ask follow-up questions naturally
- **Real-time 3D:** See your designs instantly
- **Engineering-grade:** Export to professional CAD software
- **Memory:** Remembers past designs for faster generation

---

**Ready to build? Start typing in the chat!** 🚀
