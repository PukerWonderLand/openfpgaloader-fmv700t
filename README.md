# openfpgaloader-fmv700t

Use [openFPGALoader](https://github.com/trabucayre/openFPGALoader) — the
open-source JTAG tool — to program the **FMSH fmv700t** (Shanghai Fudan
Microelectronics): SRAM configuration **and** SPI flash, **without any vendor
toolchain**.

The `fmv700t` is a Virtex-7-class device that is pin- and bitstream-compatible
with the Xilinx **XC7VX690T** in the **FFG1927** package, but it reports a
*different* JTAG IDCODE — **`0x02291143`** instead of `0x03691093`. That single
difference is why a stock Xilinx flow does not talk to it. This repository closes
the last gap.

## Quick start

```bash
# 0) an openFPGALoader that knows the device
#    (upstream, or: git clone openFPGALoader && git am patches/*.patch)

# 1) build the SPI-over-JTAG bridge from openFPGALoader's own RTL
cd openFPGALoader/spiOverJtag
python3 build.py xc7vx690tffg1927 spi      # -> spiOverJtag_xc7vx690tffg1927.bit.gz
gunzip -k spiOverJtag_xc7vx690tffg1927.bit.gz

# 2) match the bridge's IDCODE to the device
python3 <this-repo>/tools/patch_bit_idcode.py \
        spiOverJtag_xc7vx690tffg1927.bit --set 0x02291143 -o my_bridge.bit

# 3) use it
openFPGALoader -c <cable> -B my_bridge.bit --detect -f       # identify
openFPGALoader -c <cable> -B my_bridge.bit my_design.bit     # SRAM
openFPGALoader -c <cable> -B my_bridge.bit -f firmware.mcs   # SPI flash
```

## Why a patch step is needed

Adding the device IDCODE to openFPGALoader is enough for **SRAM configuration**.
**SPI flash programming** is done by a small *bridge* loaded into the fabric, and
that bridge's bitstream carries the IDCODE of the device it was built for:

* openFPGALoader ships and prebuilds the bridge RTL — it carries the Xilinx
  IDCODE `0x03691093`;
* the fmv700t reports `0x02291143` and refuses that bitstream (status register
  reads `ID Error`, `DONE` never asserts);
* rebuilding the bridge *and* adjusting its four IDCODE bytes fixes it.

That adjustment is a four-byte field in a standard, publicly documented file
format (Xilinx UG470) — see [`docs/bitstream-idcode.md`](docs/bitstream-idcode.md).
It is the only piece that cannot live in openFPGALoader itself, which is why it
lives here.

See [`docs/why.md`](docs/why.md) for the full breakdown.

## What's in here

| Path | What it is |
|---|---|
| `patches/` | The upstream changes: fmv700t + fixed XC7VX690T IDCODE (`part.hpp`), GD25LQ256D flash (`spiFlashdb.hpp`), FFG1927 pin constraints (`spiOverJtag/`). Apply on an openFPGALoader checkout. |
| `tools/patch_bit_idcode.py` | Reads/rewrites the IDCODE field of a `.bit`/`.bit.gz`/`.bin` so a bitstream matches your device. |
| `soj/` | The FFG1927 pin constraints and a one-shot Vivado build script for the bridge. |
| `docs/` | Why it works, how the IDCODE is handled, known limitations. |

## Building the bridge yourself

Requires Vivado with the `xc7vx690tffg1927` part (2019.x and later work). Two
equivalent ways:

```bash
# a) openFPGALoader's own build.py (needs patches/ applied first)
cd openFPGALoader/spiOverJtag && python3 build.py xc7vx690tffg1927 spi

# b) the standalone script in this repo
vivado -mode batch -source soj/build.tcl -tclargs /path/to/openFPGALoader/spiOverJtag
```

Both produce `spiOverJtag_xc7vx690tffg1927.bit[.gz]`. Then match its IDCODE:

```bash
python3 tools/patch_bit_idcode.py spiOverJtag_xc7vx690tffg1927.bit \
        --set 0x02291143 -o my_bridge.bit
```

Prefer building the bridge yourself rather than trusting a binary. If you do use
a prebuilt one, it must be built for the IDCODE your device reports.

## Verified on hardware

* `--detect` reports the device.
* SRAM configuration reaches `DONE`.
* Erase + program + read-back verify of a full **32 MiB** image passes
  byte-for-byte.
* JTAG at ~15 MHz is reliable; 30 MHz was not.
* Local programming of 32 MiB ≈ 5.5 min; read-back ≈ 100 s.

## Limitations

See [`docs/limitations.md`](docs/limitations.md). Briefly:

* `--verify` is not available on the SPI-over-JTAG path — read back and compare
  hashes yourself.
* The bridge is IDCODE-bound.
* FTDI-based cables are single-client: stop any XVC gateway on the same host first.

## Credits & license

The bridge RTL is part of the
[openFPGALoader](https://github.com/trabucayre/openFPGALoader) project. This
repository only adds the FFG1927 pin constraints, the IDCODE handling and this
documentation. Licensed under **Apache-2.0**, same as upstream.
