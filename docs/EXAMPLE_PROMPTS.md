# Example Prompts Guide

## 🎯 Quick Start Examples

### Gears
```
Design a gear
→ helical
→ 2.0 (module)
→ 20 (teeth)
→ 16mm (face width)
```

**One-line prompts:**
- `Create a module 2 gear with 30 teeth`
- `Design a helical gear with module 3 and 25 teeth`
- `Make a spur gear, module 2.5, 40 teeth, 20mm face width`

---

### Shafts
```
Create a shaft
→ 100mm (length)
→ 15mm (diameter)
```

**One-line prompts:**
- `Create a shaft 100mm long and 15mm diameter`
- `Design a shaft of length 75mm with diameter 12mm`
- `Make a 120mm long shaft with 20mm diameter`

---

### Bearings
```
Add a bearing
→ 20mm (inner diameter)
→ 40mm (outer diameter)
→ 12mm (width)
```

**One-line prompts:**
- `Create a bearing with 20mm inner diameter and 40mm outer diameter`
- `Add a bearing: inner 15mm, outer 35mm, width 10mm`
- `Design a bearing 25mm ID, 52mm OD, 15mm wide`

---

### Bolts
```
Add a bolt
→ 6 (diameter for M6)
→ 30mm (length)
→ coarse (thread type)
```

**One-line prompts:**
- `Create an M6 bolt 30mm long`
- `Add an M8 bolt with 40mm length`
- `Design a coarse thread M10 bolt, 50mm long`

---

### Flanges
```
Create a flange
→ 80mm (diameter)
→ 10mm (thickness)
```

**One-line prompts:**
- `Create a flange 80mm diameter and 10mm thick`
- `Design a flange: 100mm diameter, 12mm thickness`
- `Make a 60mm flange with 8mm thickness`

---

### Plates
```
Create a plate
→ 100mm (length)
→ 80mm (width)
```

**One-line prompts:**
- `Create a plate 100mm by 80mm`
- `Design a rectangular plate 120mm x 100mm`
- `Make a plate 150mm long and 120mm wide with 5mm thickness`

---

### Housing
```
Create a housing
→ 150mm (length)
→ 100mm (width)
→ 80mm (height)
```

**One-line prompts:**
- `Create a housing 150mm x 100mm x 80mm`
- `Design a housing box 200mm long, 150mm wide, 100mm tall`
- `Make a housing 180 x 120 x 90mm with 6mm wall thickness`

---

### Couplings
```
Create a coupling
→ 50mm (length)
→ 25mm (diameter)
```

**One-line prompts:**
- `Create a coupling 50mm long and 25mm diameter`
- `Design a shaft coupling: 60mm length, 30mm diameter`
- `Make a coupling 40mm x 20mm`

---

### Brackets
```
Create a bracket
→ 80mm (length)
→ 60mm (width)
→ 40mm (height)
```

**One-line prompts:**
- `Create a bracket 80mm x 60mm x 40mm`
- `Design an L-bracket 100mm long, 80mm wide, 50mm tall`
- `Make a mounting bracket 90 x 70 x 45mm`

---

### Cylinders
```
Create a cylinder
→ 25mm (radius)
→ 50mm (height)
```

**One-line prompts:**
- `Create a cylinder with 25mm radius and 50mm height`
- `Design a cylindrical part: radius 30mm, height 60mm`
- `Make a cylinder 20mm radius, 40mm tall`

---

## 🔧 Complex Assemblies

### Gear on Shaft
```
Create a shaft 100mm long and 15mm diameter with a module 2 gear mounted on it
```

### Gearbox
```
Design a 4:1 gearbox at 1500 RPM
```

**Variations:**
- `Create a 5:1 reduction gearbox`
- `Design a 3:1 gearbox with 2000 RPM input`
- `Make a single-stage 2:1 gearbox`

---

## 💡 Tips for Best Results

### 1. Be Specific with Units
✅ Good: `Create a shaft 100mm long and 15mm diameter`
❌ Vague: `Create a shaft`

### 2. Use Standard Terminology
- **Gears:** module, teeth, face width, spur/helical
- **Shafts:** length, diameter
- **Bearings:** inner diameter (ID), outer diameter (OD), width
- **Bolts:** M6, M8, M10 (metric), length, coarse/fine thread

### 3. One Component at a Time
✅ Good: 
1. `Create a shaft 100mm long`
2. `Add a gear with module 2 and 20 teeth`

❌ Confusing: `Create a shaft and gear and bearing all together`

### 4. Modify Existing Components
After creating a component, you can modify it:
- Select the component in the right panel
- Edit parameters (module, teeth, length, etc.)
- Click "Apply changes"

### 5. Use the Conversational Flow
If you're unsure of parameters, just say:
- `Design a gear` → System will ask for details
- `Create a shaft` → System will guide you
- `Add a bearing` → System will prompt for dimensions

---

## 📐 Parameter Ranges

### Gears
- **Module:** 0.5 - 10 (typical: 1-5)
- **Teeth:** 6+ (typical: 12-80)
- **Face Width:** 5-100mm (typical: 8-40mm)
- **Types:** spur, helical

### Shafts
- **Length:** 10-500mm (typical: 50-200mm)
- **Diameter:** 5-100mm (typical: 10-40mm)

### Bearings
- **Inner Diameter:** 5-100mm
- **Outer Diameter:** 10-200mm (must be > ID)
- **Width:** 5-50mm

### Bolts
- **Sizes:** M3, M4, M5, M6, M8, M10, M12, M16, M20
- **Length:** 10-200mm
- **Thread:** coarse, fine

---

## 🎨 Viewer Controls

### Mouse Controls
- **Left Drag:** Rotate view
- **Right Drag:** Pan view
- **Scroll:** Zoom in/out

### Toolbar Controls
- **Wireframe:** Toggle wireframe mode (see internal structure)
- **Explode Slider:** Separate components to see assembly
- **Export STEP:** Download CAD file for FreeCAD, Fusion360, etc.

---

## 🚀 Advanced Examples

### Multi-Component Assembly
```
1. Create a shaft 120mm long and 20mm diameter
2. Add a module 2.5 gear with 30 teeth
3. Add a bearing with 20mm inner and 47mm outer diameter
4. Create a flange 100mm diameter and 12mm thick
```

### Parametric Design
```
1. Create a gear with module 2 and 25 teeth
2. (Select gear in right panel)
3. Change teeth to 30
4. Click "Apply changes"
5. (Gear regenerates with new parameters)
```

### Gearbox Design
```
Design a 6:1 gearbox at 1800 RPM with 15 Nm torque
```
This will automatically generate:
- Multiple gear stages
- Shafts for each stage
- Bearings at shaft ends
- Housing enclosure

---

## ❓ Troubleshooting

### "I didn't recognise a component type"
→ Use standard names: gear, shaft, bearing, bolt, flange, plate, housing, coupling, bracket, cylinder

### "All components failed to generate"
→ Check parameter values (e.g., gear teeth must be 6+, bearing OD > ID)

### "What face width in mm?" (keeps asking)
→ Answer with just the number: `16` or `16mm`

### Gear looks incomplete
→ Try increasing face width: `20mm` instead of `2mm`
→ Use wireframe mode to see internal structure
→ Zoom in closer with mouse scroll

---

## 📁 Output Files

All generated files are saved to `outputs/` directory:

- `agentic_assembly_output.step` - Full assembly (STEP format)
- `gear_1.glb` - Individual component (3D viewer)
- `gear_1.stl` - Individual component (3D printing)
- `gear_1.step` - Individual component (CAD software)

**Open STEP files in:**
- FreeCAD (free)
- Fusion 360
- SolidWorks
- Onshape
- Any professional CAD software

---

## 🎓 Learning Path

### Beginner
1. Start with simple components: `Create a shaft 100mm long`
2. Try different types: gear, bearing, bolt
3. Use the conversational flow (let system ask questions)

### Intermediate
4. Create multi-component assemblies
5. Modify parameters using the inspector panel
6. Experiment with explode view and wireframe

### Advanced
7. Design complete gearboxes
8. Export and edit in professional CAD software
9. Combine multiple assemblies

---

**Happy Designing! 🎉**
