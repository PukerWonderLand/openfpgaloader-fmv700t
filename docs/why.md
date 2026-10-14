# Why this repository exists

openFPGALoader already knows how to talk to Xilinx 7-series devices. A
drop-in compatible part should therefore "just work" — and for **SRAM
configuration** it does, as soon as the part's IDCODE is in `part.hpp`. But
**SPI flash programming** needs one more thing, and that one thing cannot be
carried upstream. This document explains the split.

## The three layers

Programming an SPI flash through JTAG is not a built-in FPGA feature — it is
done by loading a small *SPI-over-JTAG bridge* into the FPGA fabric:

```
JTAG cable ──▶ [ bridge design in the fabric ] ──▶ SPI pins ──▶ flash
```

openFPGALoader ships the bridge RTL itself (`spiOverJtag/`) and the prebuilt
bitstreams (`spiOverJtag_*.bit.gz`). Using it is:

```bash
openFPGALoader -c <cable> -B spiOverJtag_<part>.bit.gz -f firmware.mcs
```

So there are three distinct pieces involved, and they belong in two places:

| # | Piece | Where it belongs | Why |
|---|---|---|---|
| 1 | **Device IDCODE** in `part.hpp` (`--detect`, SRAM config) | **upstream** | pure data; shared by everyone |
| 2 | **Bridge pin constraints** for the package (`spiOverJtag/constr_*.xdc`, `build.py` entry) | **upstream** | derived from the public package map; also useful for the original part |
| 3 | **Bitstream IDCODE matched to the device** | **this repository** | only needed by drop-in parts; not a change to openFPGALoader at all |

Layers 1 and 2 are submitted as an upstream pull request (see `patches/`).
Layer 3 is what this repo documents and ships as a small tool.

## Why layer 3 cannot go upstream

openFPGALoader's bundled bridge bitstreams are built for the Xilinx part, so they
carry the Xilinx IDCODE. A drop-in device reports a *different* IDCODE and
rejects that bitstream. Upstream would have to ship one prebuilt bridge per
`(device, package, IDCODE)` combination — an unbounded set — so this is best
handled where the specific device is known: here.

## What actually happens without it

You load the upstream bridge, and the device's status register reads back:

```
ID Error       (and DONE never asserts)
```

The device is not bricked and nothing is written; it simply does not accept a
bitstream whose IDCODE is not its own. Re-patching the bridge's IDCODE (four
bytes — see [`bitstream-idcode.md`](bitstream-idcode.md)) and re-loading it
fixes this immediately.

## The whole flow, end to end

```bash
# 1. openFPGALoader that knows the device (upstream, or patches/ applied)
# 2. build the bridge from openFPGALoader's own RTL for the FFG1927 package
python3 openFPGALoader/spiOverJtag/build.py xc7vx690tffg1927 spi
gunzip -k spiOverJtag_xc7vx690tffg1927.bit.gz

# 3. match the bridge IDCODE to the device
python3 tools/patch_bit_idcode.py spiOverJtag_xc7vx690tffg1927.bit \
        --set 0x02291143 -o my_bridge.bit

# 4. now everything works
openFPGALoader -c <cable> -B my_bridge.bit --detect -f      # identify
openFPGALoader -c <cable> -B my_bridge.bit my_design.bit    # SRAM
openFPGALoader -c <cable> -B my_bridge.bit -f firmware.mcs  # SPI flash
```
