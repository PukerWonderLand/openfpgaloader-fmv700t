# Known limitations

These are properties of the SPI-over-JTAG path and of the device, not bugs.
They are listed so nobody mistakes them for "something is missing".

## `--verify` is not available on the SPI-over-JTAG path

`openFPGALoader … -f image.bin --verify` is not supported when programming via a
bridge. Verify by reading the flash back and comparing hashes:

```bash
openFPGALoader -c <cable> -B my_bridge.bit -f firmware.mcs
openFPGALoader -c <cable> -B my_bridge.bit --read  firmware_readback.bin
sha256sum firmware.mcs firmware_readback.bin   # compare the relevant range
```

## The bridge is IDCODE-bound

A bridge built for the Xilinx IDCODE will **not** configure a device that
reports a different IDCODE (`ID Error`, `DONE` never asserts). Rebuild the bridge
for the detected IDCODE, or patch the bridge's IDCODE (see
[`bitstream-idcode.md`](bitstream-idcode.md)). This applies to any drop-in
compatible device.

## FTDI-based cables are single-client

If an XVC gateway or another tool already holds the FTDI device, openFPGALoader
cannot open it. Stop the other client first.

## Speed

Measured on the reference setup:

| Operation | Time |
|---|---|
| write a full 32 MiB image, local (no network round-trip) | ≈ 5.5 min |
| read 32 MiB back | ≈ 100 s |

JTAG clock: ~15 MHz works reliably; 30 MHz was not reliable. Going through a
network XVC gateway is much slower than a local adapter, because the protocol is
latency-bound (many small round-trips), not bandwidth-bound — a local adapter
removes that entirely.

## Speed grade

Vivado parts are `part-package-speedgrade`. `spiOverJtag/build.py` uses `-1` for
Virtex-7; the bitstream produced for `-1` and `-2` carries the same device
IDCODE, so either configures the device. Adjust the speed grade in `soj/build.tcl`
if your installation only has a specific speed grade for this part.

## Compression

The bridge constraints enable bitstream compression
(`BITSTREAM.GENERAL.COMPRESS TRUE`). This is what openFPGALoader's own
constraints use and keeps the `.bit.gz` small; it is not required for
correctness.
