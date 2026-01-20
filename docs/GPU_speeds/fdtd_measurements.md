# FDTD Performance Measurements

*Personal measurements from TensorDock GPU rentals*

## Simulation Configurations

### Phantoms
- **Thelonious**: Smaller phantom
- **Eartha**: Larger phantom

### Simulation Regions
- **by cheek**: Phone near cheek (smaller bounding box)
- **by belly**: Phone near belly (medium bounding box)  
- **front of eyes**: Phone in front of eyes (different bounding box)

### Frequency/Grid Relationship
From `configs/far_field_FR3_barebones.json`:
| Frequency (MHz) | Cell Size (mm) | Notes |
|-----------------|----------------|-------|
| 7,000 | 0.6 | |
| 9,000 | 0.5 | |
| 11,000 | 0.5 | |
| 13,000 | 0.45 | |
| 15,000 | 0.4 | **~2 BCells grid** |

---

## Main Measurements Table

| GPU | Cell Size (mm) | Phantom | MCells/s | VRAM Used (GB) | VRAM Max (GB) | Price ($/hr) |
|-----|----------------|---------|----------|----------------|---------------|--------------|
| RTX 4000 | 2.5 | Thelonious | 3,000 | 6 | 16 | $0.32 |
| RTX 4090 | 1.4 | Thelonious | 6,700 | 15 | 24 | $0.50 |
| RTX 4090 | 1.0 | Thelonious | 8,356 | 17 | 24 | $0.50 |
| RTX 6000 Ada | 2.5 | Eartha | 4,367 | 10 | 48 | $0.50 |
| RTX 6000 Ada | 1.4 | Eartha | 5,319 | 14 | 48 | $0.50 |
| L40S | 1.0 | Eartha | 5,000 | 26 | 46 | $0.75 |

*Note: Grid sizes vary by simulation region (cheek: 420M, 750M noted)*

---

## Multi-GPU Measurements

| # GPUs | GPU | Config | MCells/s | VRAM Used (GB) | VRAM Max (GB) | Price ($/hr) | Notes |
|--------|-----|--------|----------|----------------|---------------|--------------|-------|
| 5 | H100 | by belly, 1mm, Eartha | 16,000 | 26 | 82 | $2.00 | Needs env var in Windows+bash, ECC off! |
| 2 | A100 | by cheek | 8,500 | 20 | 80 | $1.00 | |

---

## Measurements Single GPU Comparison

| # GPUs | GPU | Cell Size (mm) | Phantom | MCells/s |
|--------|-----|----------------|---------|----------|
| 0 | RTX 4090 | 2.5 | Thelonious | 7,000 |
| 1 | A100 | 1.5 | Thelonious | 9,200 |
| 2 | H100 | 1.3 | Thelonious | 18,000 |
| 3 | RTX 4090 | 2.5 | Eartha | 7,000 |
| 4 | A100 | 1.5 | Eartha | - |
| 5 | H100 | 1.3 | Eartha | - |

---

## Key Observations

### Multi-GPU Scaling
- **6× H100** on 15 GHz (0.4mm, ~2 BCells): ~49k MCells/s
  - This is only **~1/2 of perfect 6× parallelism** (would expect ~108k MCells/s if linear)
  - Communication overhead becomes significant at this scale

### VRAM Limitations
- **4× RTX 4090** (24GB each = 96GB total): **Not enough memory** for 15 GHz/0.4mm simulation
- **3× RTX 4090**: Speed increase 6K→13K MCells/s, but not at full utilization often
- **RTX 4090 memory**: Tops out around Thelonious at ~10 GHz

### Grid Size Scaling (Cubic!)
Cell size reduction scales **cubically**:
```
2.5mm → 1.0mm = 2.5³ = 15.6× more cells
2.5mm → 0.4mm = 6.25³ = 244× more cells!
```
Note that the CFL condition adds another scaling OOM on the number of timesteps.

---

## GPU Specs Reference

| GPU | Memory BW (GB/s) | VRAM | Price ($/hr) |
|-----|------------------|------|--------------|
| RTX 4000 | ~416 | 16GB | $0.32 |
| RTX 4090 | 1,008 | 24GB | $0.33 |
| RTX 6000 Ada | 960 | 48GB | $0.70 |
| L40S | 864 | 48GB | $0.65 |
| A100 80GB | 2,039 | 80GB | $0.75 |
| H100 | 3,350 | 80GB | ~$2.00 |
