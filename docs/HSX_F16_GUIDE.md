# 🔢 HSX f16 Guide

---

## 🧭 Purpose
HSX uses **IEEE 754 binary16 (f16)** as its *primary storage and communication format* for floating-point values.  
It provides a compact, deterministic, and fast-to-serialize representation suitable for embedded systems (e.g. AVR).

---

## 📐 Binary Layout

| Field | Bits | Description |
|-------|------|--------------|
| Sign | 1 | 0 = positive, 1 = negative |
| Exponent | 5 | Bias = 15 |
| Mantissa | 10 | Implicit leading 1 for normalized numbers |

**Encoding formula**
```
value = (-1)^sign × (1.mantissa) × 2^(exponent − 15)
```

---

## 📊 Numeric Characteristics

| Property | f16 | f32 | Notes |
|-----------|------|------|------|
| Total bits | 16 | 32 | 2 bytes vs 4 bytes |
| Decimal digits precision | 3 – 4 | 6 – 7 | |
| Max finite value | 65 504 | 3.4 × 10³⁸ | |
| Min normal | 6.1035 × 10⁻⁵ | 1.175 × 10⁻³⁸ | |
| Min subnormal | 5.96 × 10⁻⁸ | 1.4 × 10⁻⁴⁵ | |
| Epsilon (Δ near 1.0) | 9.77 × 10⁻⁴ | 1.19 × 10⁻⁷ | |
| Exact integer range | ±2048 | ±16 777 216 | |
| NaN / ±Inf | supported | supported | same semantics |

---

## ⚙️ Performance Considerations

| Platform | f16 Benefit | Comment |
|-----------|--------------|---------|
| **AVR (no FPU)** | ✅ 2–5× faster soft-float for +, −, × | Simpler normalization/rounding |
| **ARM Cortex-M (with FPU)** | ✅ native support on M7 +, else f32 same cost | |
| **Host VM (Python/C)** | ⚙️ negligible difference | storage-only advantage |

---

## 🧮 Recommended HSX Usage

| Layer | Type | Reason |
|-------|------|--------|
| ISA / Values / CAN / FRAM | **f16** | compact wire format |
| Calculations / Filters / PID | **f32 (internal)** | accuracy & stability |
| Conversion ops | `F2H`, `H2F` | explicit, cheap |
| AVR build | optional `f16_soft.c` lib | minimal +/−/× support |

---

## 💡 Conversion Routines (C)

```c
#include <stdint.h>
#include <math.h>

// Convert float32 → float16
uint16_t f32_to_f16(float f) {
    uint32_t x = *(uint32_t*)&f;
    uint32_t sign = (x >> 16) & 0x8000;
    int exp = ((x >> 23) & 0xFF) - 127 + 15;
    uint32_t mant = x & 0x7FFFFF;

    if (exp <= 0) return sign;              // underflow → 0
    if (exp >= 0x1F) return sign | 0x7C00;  // overflow → Inf
    return sign | (exp << 10) | (mant >> 13);
}

// Convert float16 → float32
float f16_to_f32(uint16_t h) {
    uint32_t sign = (h & 0x8000) << 16;
    int exp = (h >> 10) & 0x1F;
    uint32_t mant = h & 0x3FF;
    uint32_t out;
    if (exp == 0) {
        if (mant == 0) out = sign;              // zero
        else {                                  // subnormal
            exp = 1;
            while (!(mant & 0x400)) { mant <<= 1; exp--; }
            mant &= 0x3FF;
            out = sign | ((exp + (127 - 15)) << 23) | (mant << 13);
        }
    } else if (exp == 0x1F) {
        out = sign | 0x7F800000 | (mant << 13); // Inf/NaN
    } else {
        out = sign | ((exp + (127 - 15)) << 23) | (mant << 13);
    }
    return *(float*)&out;
}
```

---

## ✅ Decision Summary

| Decision | Status |
|-----------|---------|
| f16 as primary storage type | ✅ |
| f32 internal compute precision | ✅ |
| f16-only build option for AVR | ⚙️ planned |
| Drop double precision entirely | ✅ |
| Conversion ops in ISA (F2H/H2F) | ✅ |

**Rationale:**  
- Half the memory footprint for all “Value” objects.  
- Fits deterministic, lightweight HSX philosophy.  
- Can be transparently up-converted to f32 in computations.  

---

**Maintainer:** Hans Einar (HSX Project)  
**Updated:** 2025-10-04  
