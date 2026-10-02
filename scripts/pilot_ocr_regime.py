#!/usr/bin/env python3
"""Pilot for the compute-bound boundary test: does the prompt actually move the regime?

The pre-registration commits to verifying the prefill-to-decode token ratio
before any efficiency figure is interpreted. If the transcription prompt does
not make prefill dominate, the comparison is void whatever the energy does, and
that is worth finding out in thirty minutes rather than after days of node time.

This answers two questions and nothing else:

  1. Do the two prompt regimes separate on the prefill/decode ratio, and by how
     much? Paper 1's text-only workload sits far on the decode side; the OCR
     regime has to land clearly on the other.
  2. What is the event rate? A vision encoder on a CPU may be slow enough that a
     condition yields too few inferences for a stable mean. That rate sets the
     observation window for the real campaign.

No power is measured here. This is a feasibility check, not a measurement.

Usage:
    python3 scripts/pilot_ocr_regime.py [--model M] [--reps N] [--corpus DIR]
"""
import argparse
import base64
import json
import os
import statistics
import sys
import time
import urllib.request

OLLAMA = "http://localhost:11434/api/generate"

# The first pilot tried to move the regime by prompt length and could not. The
# image encoder produced about 7,330 prompt tokens whatever was asked, so both
# arms sat deep in the prefill-dominated regime and the "long description" arm
# was in fact MORE prefill-dominated than transcription, having generated fewer
# tokens. Prefill differed between the two by 24 tokens: the prompt text. The
# image was everything else.
#
# The manipulation is therefore the presence of the image, not the wording. One
# model, one engine, one node; the only thing that varies is whether an image is
# in the request. That keeps the control the pre-registration insists on, and it
# works, because removing the image removes the whole prefill mass.
REGIMES = {
    "image": dict(
        with_image=True,
        prompt="Transcribe all of the text in this image exactly as it appears. "
               "Output only the transcribed text.",
    ),
    "text": dict(
        with_image=False,
        prompt="Write a detailed technical explanation, of at least eight hundred "
               "words, of how sustained inference load affects energy consumption "
               "and thermal behaviour on CPU-only edge hardware. Cover frequency "
               "scaling, memory bandwidth, and long-run throughput stability.",
    ),
}


def generate(model, prompt, image_b64, timeout=1800):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",
    }
    if image_b64 is not None:
        payload["images"] = [image_b64]
    body = json.dumps(payload).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    return d, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="granite3.2-vision:2b")
    ap.add_argument("--reps", type=int, default=2, help="passes over the corpus, per regime")
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--profile", default="compact")
    a = ap.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    corpus = a.corpus or os.path.join(repo, "logs", f"ocr_corpus_{a.profile}")
    images = sorted(f for f in os.listdir(corpus) if f.endswith(".png"))
    if not images:
        sys.exit(f"no images in {corpus}; run scripts/make_ocr_corpus.py first")
    print(f"  model {a.model}, {len(images)} images, {a.reps} reps per regime\n")

    results = {}
    for regime, spec in REGIMES.items():
        prompt = spec["prompt"]
        rows = []
        for rep in range(a.reps):
            # The text arm has no image, so it iterates the same number of times
            # rather than over the corpus, keeping the sample sizes comparable.
            for img in (images if spec["with_image"] else [None] * len(images)):
                if img is None:
                    b64 = None
                else:
                    with open(os.path.join(corpus, img), "rb") as fh:
                        b64 = base64.b64encode(fh.read()).decode()
                try:
                    d, wall = generate(a.model, prompt, b64)
                except Exception as e:
                    print(f"  {regime:<9} {str(img):<16} FAILED: {type(e).__name__}: {e}")
                    continue
                pf = d.get("prompt_eval_count", 0)
                dc = d.get("eval_count", 0)
                pf_s = d.get("prompt_eval_duration", 0) / 1e9
                dc_s = d.get("eval_duration", 0) / 1e9
                rows.append((pf, dc, pf_s, dc_s, wall))
                print(f"  {regime:<9} {str(img):<16} prefill {pf:>5} tok / {pf_s:6.1f}s   "
                      f"decode {dc:>5} tok / {dc_s:6.1f}s   wall {wall:6.1f}s")
        results[regime] = rows

    print("\n  === o que o piloto responde ===")
    print(f"  {'regime':<10}{'n':>4}{'prefill tok':>13}{'decode tok':>12}"
          f"{'pf:dc':>9}{'tempo medio':>13}{'eventos/h':>11}")
    ratios = {}
    for regime, rows in results.items():
        if not rows:
            print(f"  {regime:<10}   0  (nenhuma inferencia concluiu)")
            continue
        pf = statistics.mean(r[0] for r in rows)
        dc = statistics.mean(r[1] for r in rows)
        wall = statistics.mean(r[4] for r in rows)
        ratio = pf / dc if dc else float("inf")
        ratios[regime] = ratio
        print(f"  {regime:<10}{len(rows):>4}{pf:>13.0f}{dc:>12.0f}"
              f"{ratio:>9.2f}{wall:>12.1f}s{3600/wall:>11.1f}")

    if len(ratios) == 2:
        sep = ratios["image"] / ratios["text"] if ratios["text"] else float("inf")
        print(f"\n  separacao dos regimes: {sep:.1f}x no racio prefill/decode")
        if ratios["image"] > 1 and ratios["text"] < 1:
            print("  OK: com imagem domina o prefill, sem imagem domina o decode.")
            print("  A manipulacao funciona e o desenho pre-registado pode avancar.")
        else:
            print("  ATENCAO: os regimes nao se separam como o desenho assume.")
            print("  Ler o pre-registo: a comparacao seria nula. Ajustar os prompts")
            print("  (saida mais curta na transcricao, mais longa na descricao) ou o corpus.")


if __name__ == "__main__":
    main()
