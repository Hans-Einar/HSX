#!/usr/bin/env python3
"""
hld.py — HSX linker/packer (MVP)
- For now: pass-through single .hxe, or join raw code segments (future).
- Placeholder so pipeline exists; extend with .hxo object format later.
Usage:
  python3 hld.py -o app.hxe input1.hxe   # pass-through
"""
import argparse, shutil, sys
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o","--output", required=True)
    args = ap.parse_args()
    if len(args.inputs)==1 and args.inputs[0].endswith(".hxe"):
        shutil.copyfile(args.inputs[0], args.output)
        print(f"Copied {args.inputs[0]} -> {args.output}")
        return
    print("MVP linker: please provide a single .hxe for now.", file=sys.stderr)
    sys.exit(2)
if __name__ == "__main__":
    main()
