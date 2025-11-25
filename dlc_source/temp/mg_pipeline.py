#!/usr/bin/env python3
import argparse, os, re, subprocess, concurrent.futures, yaml, csv
from pathlib import Path

# -----------------------------
# Helper Functions
# -----------------------------

def load_mapping(path):
    if not os.path.exists(path):
        return {"gamecode": {}, "region": {}, "fallbacks": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data

def load_event_csv(path):
    events = []
    if not os.path.exists(path):
        return events
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append({
                "name": row["EventName"],
                "gamecodes": [c.strip() for c in row["GameCodes"].split(",")],
                "regions": [r.strip() for r in row["Regions"].split(",")],
                "year": row.get("Year", "")
            })
    return events

def gather_tokens(path: Path):
    toks = []
    toks += re.split(r"[^A-Za-z0-9]+", path.name)
    for p in path.parent.parts:
        toks += re.split(r"[^A-Za-z0-9]+", p)
    return [t for t in toks if t]

def normalize(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

def match_event(filename_tokens, events):
    fn = normalize(" ".join(filename_tokens))
    for ev in events:
        if normalize(ev["name"]) in fn:
            return ev
    return None

def detect_gamecode(path_tokens, mapping):
    for pattern, code in mapping.get("gamecode", {}).items():
        try:
            if re.search(pattern, "/".join(path_tokens), re.IGNORECASE):
                return code
        except re.error:
            pass
    return mapping.get("fallbacks", {}).get("default_gamecode", "ADAE")

def find_inputs(root: Path, exts):
    exts_set = {e.lower() for e in exts}
    files = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts_set:
            files.append(p)
    return files

def convert_one(mgc_bin, src: Path, dst_dir: Path):
    """
    Calls MysteryGiftConvert and lets it generate the filename itself.
    The generated .myg file is then moved to the target directory.
    """
    import shutil, tempfile

    dst_dir.mkdir(parents=True, exist_ok=True)

    # Temporary working directory for conversion
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_src = Path(tmpdir) / src.name
        shutil.copy2(src, tmp_src)

        try:
            # Call MysteryGiftConvert without output path
            # It generates the .myg in the same directory as the input file
            subprocess.run([mgc_bin, str(tmp_src)], check=True, cwd=tmpdir)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Conversion failed for {src}: {e}")
        except FileNotFoundError:
            raise RuntimeError(f"Converter binary not found: {mgc_bin}")

        # Find the generated .myg file
        myg_files = list(Path(tmpdir).glob("*.myg"))
        if not myg_files:
            raise RuntimeError(f"No .myg file generated for {src}")
        if len(myg_files) > 1:
            raise RuntimeError(f"Multiple .myg files generated for {src}: {myg_files}")

        generated_myg = myg_files[0]
        final_path = dst_dir / generated_myg.name

        # Move the generated file to the target directory
        shutil.move(str(generated_myg), str(final_path))

        return generated_myg.name  # Return the generated filename

# -----------------------------
# Main Logic
# -----------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enable-mapping-override", action="store_true")
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--bin-mgc", required=True)
    ap.add_argument("--exts", default=".pcd,.pgt,.pgf,.wc4,.wc5")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--mapping", default="")
    ap.add_argument("--events-csv", default="")
    args = ap.parse_args()

    exts = [e.strip() for e in args.exts.split(",") if e.strip()]
    mapping = load_mapping(args.mapping)
    events = load_event_csv(args.events_csv)

    in_root = Path(args.input_root)
    out_root = Path(args.output_root)

    inputs = find_inputs(in_root, exts)
    print(f"[mg] Found {len(inputs)} inputs with {exts}")

    def process(src: Path):
        toks = gather_tokens(src)
        ev = match_event(toks, events)
        if ev:
            results = []
            for gc in ev["gamecodes"]:
                out_dir = out_root / gc
                try:
                    generated_name = convert_one(args.bin_mgc, src, out_dir)
                    results.append(f"{src.name} -> {gc}/{generated_name}")
                except Exception as e:
                    results.append(f"ERR {src.name}: {e}")
            return "; ".join(results)
        else:
            # Fallback: YAML mapping
            gamecode = detect_gamecode(toks, mapping)
            out_dir = out_root / gamecode
            try:
                generated_name = convert_one(args.bin_mgc, src, out_dir)
                return f"{src.name} -> {gamecode}/{generated_name} (fallback)"
            except Exception as e:
                return f"ERR {src.name}: {e}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for res in ex.map(process, inputs):
            print(res)

if __name__ == "__main__":
    main()
