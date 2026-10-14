# Matching the bitstream IDCODE to your device

A `.bit` file is not a raw memory image — it is a small container with a text
header followed by the raw configuration bitstream. That raw bitstream carries
the **IDCODE of the device it was generated for**, and a device refuses any
bitstream whose IDCODE is not its own.

For a drop-in compatible part this is the one thing that needs adjusting: the
device answers `--detect` fine (once its IDCODE is known to openFPGALoader),
SRAM configuration of a *matching* bitstream works, but a helper bridge that was
built for the original part still carries the original IDCODE.

## Where the IDCODE lives

The `.bit` container (see Xilinx UG470):

| Offset | Content |
|---|---|
| 0 | 13-byte magic `00 09 0F F0 …` |
| 13 | `a` + 2-byte length + design name |
| … | `b` + 2-byte length + part name |
| … | `c` + 2-byte length + build date |
| … | `d` + 2-byte length + build time |
| … | `e` + **4-byte** length + raw configuration data |

(`a`–`d` use a 2-byte length, `e` uses 4 bytes.)

Inside the raw configuration data (the `e` payload):

```
FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF FF     pad
AA 99 55 66                                          sync word
20 00 00 00                                          NOP
…
30 01 80 01                                          Type-1 write, 1 word,
                                                     to the IDCODE register
xx xx xx xx                                          <-- THE IDCODE (big-endian)
```

The `30 01 80 01` packet is mandatory and always the first register write after
the sync word, so the IDCODE is found by *parsing*, not by a fixed file offset.
Its absolute offset varies with the header length (design name, part string,
date/time), which is why hard-coding an offset is fragile.

For the FFG1927 bridge built from openFPGALoader's own RTL, this puts the IDCODE
at file offset 252 — but do not rely on that number.

## What the tool does

`tools/patch_bit_idcode.py`:

1. parses the header to find the `e` record;
2. finds the sync word, then the first `30 01 80 01` packet after it;
3. rewrites the following four bytes (big-endian), and **nothing else**.

```bash
# read
python3 tools/patch_bit_idcode.py my_bridge.bit --get            # -> 0x03691093

# rewrite (copy)
python3 tools/patch_bit_idcode.py my_bridge.bit --set 0x02291143 -o my_bridge_700t.bit
```

Because only four bytes change, the result is byte-identical to a bridge that was
generated for the target IDCODE in the first place.

## Is this legitimate?

Yes. The IDCODE is a plain data field of a standard, publicly documented file
format (UG470). Nothing is encrypted, signed, or otherwise protected, and device
vendors that ship compatible parts expose an equivalent "revise the bitstream
IDCODE" step in their own tooling. The step is required for *any* drop-in
compatible device, not specific to one vendor.

Note that this only makes a bitstream for the **same fabric** acceptable to a
device that reports a different IDCODE. It does not turn one device's bitstream
into another's — a bitstream for a different part will still be rejected during
configuration.
