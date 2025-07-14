# 📀 Pro-Ject Turntable to Raspberry Pi Integration Guide

Integrating a Raspberry Pi music recognition system with your Pro-Ject Debut Carbon EVO turntable and Tube Box S2 preamp requires careful attention to signal routing, impedance matching, and audio quality preservation.

---

## 🔎 Current Setup Analysis

### Pro-Ject Debut Carbon EVO Specifications

- Output signal: **5.0–5.5mV (phono level)**
- Load impedance: **47kΩ**
- Connections: **RCA L/R + ground**
- SNR: **68dB**
- Cable: **Connect IT E**, dual twisted pair, foil shielding

### Tube Box S2 Preamp Specifications

- Input impedance: **47kΩ** (matches turntable perfectly)
- Gain range: **40–63dB** (recommended: 40–43dB for MM cartridges)
- Output: **Line-level RCA (~1–2V RMS)**
- Tubes: **2× ECC83 (12AX7A)**

Signal flow:

```
Cartridge → Tonearm → RCA output → Tube Box S2 input → RIAA equalization → Amplification → Line output
```

---

## 🔌 Signal Routing Options

### Recommended Approach: RCA Y-Splitter from Preamp Output

- Taps stable line-level output
- Preserves main listening chain
- Clean audio feed for Raspberry Pi

### Benefits of Y-Splitter over Dedicated Tape Output

- Minimal loss (<1% amplitude difference)
- No equipment mods required
- Maintains impedance balance

---

## 🔁 Direct Connection Methods

### Adapter Strategy

- Use **individual RCA to TRS adapters** (Hosa GPR-101)
- TRS tip → RCA center
- TRS sleeve → RCA ground
- TRS ring → leave unconnected

---

## 🧩 Physical Connection Flow

**Method 1 (Recommended): Tap from Tube Box S2 Line Output**

```text
Tube Box S2 → Hosa CYR-109 Y-cables
├─> Main amplifier
└─> Raspberry Pi
      └─> Hosa GPR-101 adapters
      └─> UMC22 Inputs 1 & 2
      └─> USB → Raspberry Pi
```

Signal level: **~2V RMS**, within UMC22’s max input of **+22dBU (~9.8V RMS)**

---

## 🧼 Cable Management Tips

- Keep RCA runs <10ft
- Isolate from power lines and digital gear
- Use double-shielded, grounded cables
- Maintain **single-point grounding**

---

## 🐛 Troubleshooting Common Issues

- **Hum/Buzz**: Grounding fixes, use ground lift adapters
- **Signal mismatch**: Confirm line input on UMC22
- **Noise floor**: Limit UMC22 gain to <70%

---

## 🎚️ UMC22 Integration

### Input Compatibility

- Max input: **+22dBU (~9.8V RMS)**
- Input impedance: **3kΩ**
- Sample rate: **48kHz/24-bit**

Minimal impedance mismatch is acceptable for recognition tasks.

### Required Adapters

- Hosa GPR-101 RCA→TRS (2-pack)
- Proper wiring:
  - Tip: RCA center
  - Sleeve: RCA ground
  - Ring: unconnected

### Gain Staging Tips

- Use **line input** (not mic)
- Keep gain low to reduce noise
- Use UMC22’s Signal and Clip LEDs to verify levels

---

## 🍓 Raspberry Pi Compatibility

- USB Audio Class-compliant
- Appears as "USB Audio CODEC" via ALSA
- Compatible with **PulseAudio** and **JACK**
- Requires USB Type-B → USB-A (included)

---

## 🧭 Complete Wiring Diagram

```
TURNTABLE → PREAMP → Y-SPLITTER → [MAIN AMP + RASPBERRY PI]

Pro-Ject Debut Carbon EVO
├── RCA L/R outputs (phono level)
├── Ground wire
↓
Tube Box S2
├── Phono input (47kΩ)
├── RIAA EQ + gain
├── Line output (~2V RMS)
↓
Hosa CYR-109 Y-cables
├── → Amplifier
└── → Raspberry Pi
     └── Hosa GPR-101 adapters
     └── UMC22 inputs
     └── USB to Raspberry Pi
```

---

## 📦 Recommended Components

### Primary Setup

- **RCA Y-Splitters**:
  - Hosa CYA-103 (3ft) – $8.95
  - Hosa CYA-105 (5ft) – $15.49
- **RCA to TRS Adapters**:
  - Hosa GPR-101 (2-pack) – $4.95
- **USB Cable**:
  - Standard A-B (included or $6.99)

### Pro Upgrade Options

- Mogami 2549 RCA cables – $35+
- Worlds Best Cables – $75–150
- Neutrik NP2X-B Series TRS connectors

**Total cost**: ~$28.89 (basic setup)

---

## 🎧 Audio Quality Considerations

- Minimal signal loss via proper Y-splitting
- Preserved impedance relationships
- Short, shielded cables reduce noise
- Professional shielding avoids RF interference

---

## ⚡ Grounding and Noise Prevention

- Connect turntable ground to Tube Box S2 terminal
- Use single-point grounding strategy
- Shield at equipment endpoints only
- Separate signal and power paths

---

## 🔍 Monitoring Audio Impact

- **A/B testing**: Compare direct vs tapped signal
- Watch for noise increase at high gain
- Validate frequency response via test tones
- Ensure dynamic range is preserved

---

## ✅ Conclusion

This setup delivers high-quality audio capture for your Raspberry Pi music recognition while preserving the fidelity of your main analog listening chain. With a ~$70–80 budget and attention to gain staging, grounding, and component quality, this approach is robust, transparent, and ideal for automated scrobbling applications.

---
