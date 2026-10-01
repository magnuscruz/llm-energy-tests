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

REGIMES = {
    # Short output, whole page in the prompt: prefill and image encoding dominate.
    "ocr": "Transcribe all of the text in this image exactly as it appears. "
           "Output only the transcribed text.",
    # Long output from the same image: decode should dominate instead.
    "describe": "Describe this document image in exhaustive detail: its layout, "
                "the structure of the text, the subject matter it discusses, the "
                "arguments it makes, and anything notable about its presentation. "
                "Write at least three hundred words.",
}


def generate(model, prompt, image_b64, timeout=900):
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "keep_alive": "30m",
    }).encode()
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
    a = ap.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    corpus = a.corpus or os.path.join(repo, "logs", "ocr_corpus")
    images = sorted(f for f in os.listdir(corpus) if f.endswith(".png"))
    if not images:
        sys.exit(f"no images in {corpus}; run scripts/make_ocr_corpus.py first")
    print(f"  model {a.model}, {len(images)} images, {a.reps} reps per regime\n")

    results = {}
    for regime, prompt in REGIMES.items():
        rows = []
        for rep in range(a.reps):
            for img in images:
                with open(os.path.join(corpus, img), "rb") as fh:
                    b64 = base64.b64encode(fh.read()).decode()
                try:
                    d, wall = generate(a.model, prompt, b64)
                except Exception as e:
                    print(f"  {regime:<9} {img:<16} FAILED: {type(e).__name__}: {e}")
                    continue
                pf = d.get("prompt_eval_count", 0)
                dc = d.get("eval_count", 0)
                pf_s = d.get("prompt_eval_duration", 0) / 1e9
                dc_s = d.get("eval_duration", 0) / 1e9
                rows.append((pf, dc, pf_s, dc_s, wall))
                print(f"  {regime:<9} {img:<16} prefill {pf:>5} tok / {pf_s:6.1f}s   "
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
        sep = ratios["ocr"] / ratios["describe"] if ratios["describe"] else float("inf")
        print(f"\n  separacao dos regimes: {sep:.1f}x no racio prefill/decode")
        if ratios["ocr"] > 1 and ratios["describe"] < 1:
            print("  OK: a transcricao e dominada por prefill e a descricao por decode.")
            print("  A manipulacao funciona e o desenho pre-registado pode avancar.")
        else:
            print("  ATENCAO: os regimes nao se separam como o desenho assume.")
            print("  Ler o pre-registo: a comparacao seria nula. Ajustar os prompts")
            print("  (saida mais curta na transcricao, mais longa na descricao) ou o corpus.")


if __name__ == "__main__":
    main()
