#!/usr/bin/env python3
"""patch_bit_idcode.py -- read or rewrite the IDCODE field of a Xilinx .bit file.

A configuration bitstream carries the IDCODE of the device it targets. Some
devices are designed as drop-in, pin/bitstream-compatible parts -- for example
the FMSH fmv700t, which is compatible with the Xilinx XC7VX690T in FFG1927 --
but they report a *different* IDCODE. A bitstream built for the Xilinx part
therefore has to be adjusted before such a device will accept it.

This tool locates the IDCODE by parsing the bitstream (it does not assume a
fixed file offset) and rewrites exactly those four bytes. Nothing else in the
file is touched.

Usage
-----
    # print the IDCODE currently embedded in a bitstream
    patch_bit_idcode.py design.bit --get
    patch_bit_idcode.py design.bit.gz --get

    # write a new file whose IDCODE is 0x02291143
    patch_bit_idcode.py design.bit --set 0x02291143 -o design_fmv700t.bit

    # rewrite in place (a .bak is kept)
    patch_bit_idcode.py design.bit --set 0x02291143 --in-place

`.gz` files are handled transparently (by extension); the output keeps the
input's compression.

The IDCODE lives in the raw configuration data, in the mandatory first packet
after the sync word:

    AA 99 55 66            sync word
    ...
    30 01 80 01            Type-1 write, 1 word, to the IDCODE register (0x0C)
    xx xx xx xx            <-- the IDCODE, big-endian

See docs/bitstream-idcode.md and Xilinx UG470 for details.
"""

import argparse
import gzip
import os
import struct
import sys

MAGIC = bytes([0x00, 0x09, 0x0F, 0xF0, 0x0F, 0xF0, 0x0F, 0xF0, 0x0F, 0xF0, 0x00, 0x00, 0x01])
SYNC = bytes([0xAA, 0x99, 0x55, 0x66])
IDCODE_PKT = bytes([0x30, 0x01, 0x80, 0x01])  # write 1 word to IDCODE register


def is_gz(path):
    return path.lower().endswith(".gz")


def read_file(path):
    if is_gz(path):
        with gzip.open(path, "rb") as fh:
            return fh.read()
    with open(path, "rb") as fh:
        return fh.read()


def write_file(path, data, gz):
    if gz:
        with gzip.open(path, "wb", compresslevel=9) as fh:
            fh.write(data)
    else:
        with open(path, "wb") as fh:
            fh.write(data)


def find_config_data(data):
    """Return (config_bytes, absolute_offset_of_config_bytes).

    Parses the .bit header records (a/b/c/d carry a 2-byte length, e carries a
    4-byte length). If the file has no recognisable header it is assumed to be
    raw configuration data.
    """
    if data[:13] != MAGIC:
        # Not a .bit container: assume raw configuration data (e.g. a .bin).
        return data, 0

    off = 13
    while off < len(data):
        tag = data[off : off + 1]
        if tag == b"e":
            (length,) = struct.unpack(">I", data[off + 1 : off + 5])
            start = off + 5
            return data[start : start + length], start
        if tag in (b"a", b"b", b"c", b"d"):
            (length,) = struct.unpack(">H", data[off + 1 : off + 3])
            off += 3 + length
            continue
        raise SystemExit(
            "error: malformed .bit header at offset %d (unexpected byte 0x%02x)"
            % (off, data[off])
        )
    raise SystemExit("error: could not find the configuration-data ('e') record")


def locate_idcode(data):
    """Return (byte_offset_of_idcode, idcode_int_for_a_7series_file)."""
    cfg, base = find_config_data(data)

    sync = cfg.find(SYNC)
    if sync < 0:
        raise SystemExit("error: sync word AA995566 not found -- not a 7-series bitstream?")

    pkt = cfg.find(IDCODE_PKT, sync + len(SYNC))
    if pkt < 0:
        raise SystemExit(
            "error: IDCODE register write (30 01 80 01) not found after the sync word"
        )

    # Guard against a coincidental match deeper in the (possibly compressed)
    # payload: the real packet must be within the first few words after sync.
    if pkt > sync + 512:
        raise SystemExit("error: IDCODE packet far from the sync word -- refusing to patch")

    at = base + pkt + len(IDCODE_PKT)
    (idcode,) = struct.unpack(">I", data[at : at + 4])
    return at, idcode


def parse_idcode(text):
    text = text.strip().replace("_", "")
    try:
        value = int(text, 16)
    except ValueError:
        raise argparse.ArgumentTypeError("'%s' is not a hex number (e.g. 0x02291143)" % text)
    if not 0 <= value <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("IDCODE must fit in 32 bits")
    return value


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Read or rewrite the IDCODE field of a Xilinx .bit/.bin bitstream.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("file", help="input .bit / .bit.gz / .bin")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--get", action="store_true", help="print the embedded IDCODE and exit")
    g.add_argument(
        "--set",
        metavar="IDCODE",
        type=parse_idcode,
        help="new IDCODE, hex (e.g. 0x02291143)",
    )
    ap.add_argument("-o", "--output", help="output file (default: stdout for --get)")
    ap.add_argument(
        "--in-place",
        action="store_true",
        help="rewrite the input file, keeping a .bak copy",
    )
    args = ap.parse_args(argv)

    data = read_file(args.file)
    at, old = locate_idcode(data)

    if args.get:
        print("0x%08x" % old)
        return 0

    new = args.set
    if new == old:
        print("IDCODE already 0x%08x, nothing to do" % old, file=sys.stderr)
        return 0

    patched = bytearray(data)
    patched[at : at + 4] = struct.pack(">I", new)

    if args.in_place:
        backup = args.file + ".bak"
        if not os.path.exists(backup):
            write_file(backup, data, is_gz(args.file))
            print("backup: %s" % backup, file=sys.stderr)
        write_file(args.file, bytes(patched), is_gz(args.file))
        print("0x%08x -> 0x%08x  (%s)" % (old, new, args.file), file=sys.stderr)
        return 0

    if not args.output:
        raise SystemExit("error: --set needs -o/--output (or --in-place)")

    write_file(args.output, bytes(patched), is_gz(args.output))
    print("0x%08x -> 0x%08x  (%s)" % (old, new, args.output), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
