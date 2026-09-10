"""Measure what a worker actually costs, and whether the workers fit the instance.

gunicorn.conf.py carries a budget of the form

    1 x (peak decode)  +  (N-1) x (idle worker)  <=  instance - safety margin

and picks WEB_CONCURRENCY from it. The numbers in that file were measured by
`imagelab/07_memory.py`, which is not in the repo -- so the budget cannot be
re-derived when something changes it, and two things since have: enabling S3/R2
media (boto3 lives in every worker) and raising the image dimensions (a larger
target defeats JPEG draft-mode decoding). This measures all of it again.

Every figure is a peak RSS taken in a FRESH SUBPROCESS. ru_maxrss is a
high-water mark that never comes down, so measuring several configurations in
one process would report the largest one for all of them.

    .venv/bin/python script/memory_budget.py
    .venv/bin/python script/memory_budget.py --instance 1024 --workers 4
    .venv/bin/python script/memory_budget.py --source path/to/big.jpg
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DJANGO_DIR = os.path.join(REPO, "djangotutorial")
CACHED_PHOTO = os.path.join(HERE, "image_compare_out", ".source-cache", "photo.jpg")

# Run in the child, printed as one JSON line on the last line of stdout.
CHILD = r'''
import io, json, os, resource, sys

def rss():
    kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return kb / 1048576 if sys.platform == "darwin" else kb / 1024

mode = sys.argv[1]
out = {"start": rss()}

sys.path.insert(0, os.environ["GOL_DJANGO_DIR"])
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.test_settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "x")
import django
django.setup()
out["django"] = rss()

if mode == "baseline":
    pass

elif mode == "s3":
    from storages.backends.s3 import S3Storage
    out["import_s3"] = rss()
    import boto3
    boto3.session.Session().client(
        "s3", region_name="auto",
        endpoint_url="https://example.r2.cloudflarestorage.com",
        aws_access_key_id="x", aws_secret_access_key="y",
    )
    out["s3_client"] = rss()

elif mode == "decode":
    from PIL import Image
    from leaderboard import image_utils as iu
    side = int(sys.argv[2])
    src = sys.argv[3]
    with open(src, "rb") as fh:
        data = fh.read()
    out["source_bytes"] = len(data)
    img = Image.open(io.BytesIO(data))
    out["source_px"] = list(img.size)
    # What the JPEG decoder is asked to materialise, before any LANCZOS pass.
    # This is the number the draft() optimisation moves, and it is NOT the final
    # size -- measure it on a throwaway open so the real run is unaffected.
    probe = Image.open(io.BytesIO(data))
    probe.draft("RGB", (side, side))
    out["draft_px"] = list(probe.size)
    probe.close()
    frames = iu._prepare_still(img, side, side)
    out["decoded_px"] = list(frames[0].size)
    out["after_decode"] = rss()
    payload = iu._encode_under_cap(frames, iu.CAP_EVENT_IMAGE)
    out["out_bytes"] = len(payload)
    out["after_encode"] = rss()

elif mode == "worstpng":
    from PIL import Image
    from leaderboard import image_utils as iu
    mp = float(sys.argv[2])
    side = int((mp * 1_000_000) ** 0.5)
    # RGBA: the alpha channel is what makes this the expensive case.
    img = Image.new("RGBA", (side, side), (120, 30, 90, 200))
    out["source_px"] = [side, side]
    out["after_synth"] = rss()
    frames = iu._prepare_still(img, 2400, 2400)
    out["after_decode"] = rss()
    payload = iu._encode_under_cap(frames, iu.CAP_EVENT_IMAGE)
    out["out_bytes"] = len(payload)
    out["after_encode"] = rss()

out["peak"] = rss()
print(json.dumps(out))
'''


def run(*args):
    env = dict(os.environ, GOL_DJANGO_DIR=DJANGO_DIR, PYTHONWARNINGS="ignore")
    proc = subprocess.run(
        [sys.executable, "-c", CHILD, *[str(a) for a in args]],
        capture_output=True, text=True, env=env, cwd=DJANGO_DIR,
    )
    for line in reversed(proc.stdout.strip().splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    sys.exit(f"child failed ({args}):\n{proc.stderr[-2000:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instance", type=int, default=512, help="Instance RAM in MB")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--margin", type=int, default=60, help="Safety margin MB")
    ap.add_argument("--source", default=CACHED_PHOTO)
    ap.add_argument("--megapixels", type=float, default=24.0,
                    help="Worst-case RGBA upload, matching IMAGE_MAX_MEGAPIXELS")
    args = ap.parse_args()

    print("Every number below is peak RSS in a fresh subprocess.\n")

    base = run("baseline")
    idle_plain = base["django"]
    print("IDLE WORKER")
    print(f"  interpreter                  {base['start']:6.1f} MB")
    print(f"  + django.setup()             {idle_plain:6.1f} MB")

    s3 = run("s3")
    idle_s3 = s3["s3_client"]
    print(f"  + S3 backend imported        {s3['import_s3']:6.1f} MB   (+{s3['import_s3'] - s3['django']:.1f})")
    print(f"  + S3 client built            {idle_s3:6.1f} MB   (+{idle_s3 - s3['import_s3']:.1f})")
    print(f"\n  idle worker WITHOUT R2       {idle_plain:6.1f} MB")
    print(f"  idle worker WITH R2          {idle_s3:6.1f} MB   (+{idle_s3 - idle_plain:.1f})")

    peak_by_side = {}
    if os.path.exists(args.source):
        print(f"\nJPEG UPLOAD  ({os.path.basename(args.source)})")
        print(f"  {'target':>7} {'decoder gives':>13} {'bitmap':>9} {'draft':>11} "
              f"{'peak RSS':>10} {'output':>9}")
        for side in (1200, 1600, 2000, 2400):
            r = run("decode", side, args.source)
            src_w = r["source_px"][0]
            dft_w = r["draft_px"][0]
            drafted = ("1/%d" % round(src_w / dft_w)) if dft_w < src_w else "none (full)"
            peak_by_side[side] = r["peak"]
            bitmap = r["draft_px"][0] * r["draft_px"][1] * 3 / 1048576
            print(f"  {side:>5}px {str(r['draft_px']):>13} {bitmap:>7.1f} MB "
                  f"{drafted:>11} {r['peak']:>8.1f} MB {r['out_bytes'] / 1024:>7.0f} kB")
    else:
        print(f"\n(no source image at {args.source} — skipping the JPEG ladder)")

    worst = run("worstpng", args.megapixels)
    peak_worst = worst["peak"]
    print(f"\nWORST CASE  ({args.megapixels:g} MP RGBA, matching IMAGE_MAX_MEGAPIXELS)")
    print(f"  synthesised {worst['source_px'][0]}x{worst['source_px'][1]}")
    print(f"  peak RSS                     {peak_worst:6.1f} MB")

    # The decode lock (IMAGE_DECODE_SLOTS=1) means only ONE worker can be in the
    # expensive state at a time; the others sit at the idle floor.
    print(f"\nBUDGET  ({args.instance} MB instance, {args.margin} MB safety margin)")
    print(f"  {'workers':>8} {'no R2':>12} {'with R2':>12}")
    usable = args.instance - args.margin
    for n in range(1, 6):
        no_r2 = peak_worst + (n - 1) * idle_plain
        # The worker holding the peak also carries boto3 once R2 is on.
        with_r2 = (peak_worst + (idle_s3 - idle_plain)) + (n - 1) * idle_s3
        mark = "  <- current" if n == args.workers else ""
        f1 = "ok " if no_r2 <= usable else "OVER"
        f2 = "ok " if with_r2 <= usable else "OVER"
        print(f"  {n:>8} {no_r2:>8.0f} MB {f1} {with_r2:>8.0f} MB {f2}{mark}")
    print(f"\n  usable = {args.instance} - {args.margin} = {usable} MB")

    if peak_by_side:
        lo, hi = peak_by_side.get(1200), peak_by_side.get(2400)
        if lo and hi:
            print(f"\n  Raising the poster target 1200 -> 2400 px cost "
                  f"{hi - lo:+.0f} MB of peak on this JPEG.")


if __name__ == "__main__":
    main()
