"""
Paraphrase pipeline - rewrites complaints in natural, varied language.

WHY: each category contains words that appear nowhere else (AePS has "biometric",
Damage has "ransomware"). The classifier learned those keywords instead of the
underlying pattern, which is why it scores 1.0. Real complaints will not use that
vocabulary, so the score is meaningless.

THREE PROVIDERS - pick whichever you can access
------------------------------------------------
  ollama     FREE, unlimited, runs on your laptop, no key at all
             Install from ollama.com, then:  ollama pull llama3.1:8b
             pip install requests

  gemini     FREE tier from aistudio.google.com (rate limited but real quota)
             pip install google-generativeai
             setx GEMINI_API_KEY "your-key"      (reopen terminal)

  anthropic  Best quality, needs paid API credit
             pip install anthropic
             setx ANTHROPIC_API_KEY "sk-ant-..."

NOTE: a Gemini Advanced or Claude Pro SUBSCRIPTION does NOT include API access.
Those are separate products. The free tiers above are what you want.

USAGE
-----
    python paraphrase.py --demo
    python paraphrase.py --provider ollama --per-category 2
    python paraphrase.py --provider ollama --per-category 100
    python paraphrase.py --provider gemini --per-category 100 --sleep 4 --resume

Every rewrite is fact-checked: if an amount or year went missing it is rejected
rather than saved. Free-tier models need this; frontier models rarely trip it.

Reads : dataset/generated/*_all.jsonl
Writes: dataset/paraphrased/*_para.jsonl
Safe to interrupt; --resume continues where it stopped.
"""

import argparse, glob, json, os, random, re, sys, time

SRC = os.path.join("dataset", "generated")
DST = os.path.join("dataset", "paraphrased")
SEED = 20260825

# 3 styles, so one complaint yields three differently-worded versions.
STYLES = {
    "plain": (
        "Rewrite it the way an ordinary person would describe what happened to a "
        "police officer: simple everyday words, short sentences, no formal or "
        "legal phrasing."
    ),
    "detailed": (
        "Rewrite it as a longer, more detailed account with a little background "
        "and some emotion, as a worried complainant might actually write."
    ),
    "terse": (
        "Rewrite it as a short, blunt account of only the essential facts, the way "
        "someone in a hurry would type it. Two to four sentences."
    ),
}

SYSTEM = """You rewrite cybercrime complaints for a training dataset.

RULES:
1. Keep EVERY fact identical - amounts, dates, platforms, sequence of events, who did what.
   AMOUNTS ARE CRITICAL: copy every rupee figure EXACTLY as written, digit for digit.
   "Rs. 20,00,000" must stay "Rs. 20,00,000". Never convert to words ("twenty lakh"),
   never round, never summarise as "a large sum". Same for every date and year.
2. Change the WORDING as much as possible. Replace formal or technical terms with
   how a normal person would say the same thing.
   For example: "biometric authentication" -> "my fingerprint"; "unauthorised debit"
   -> "money was taken without me knowing"; "collect request" -> "a request to pay
   that showed up in the app".
3. Do NOT add facts that are not in the original. Do NOT remove facts.
4. Do NOT mention the crime category or use any label.
5. Output ONLY the rewritten complaint. No preamble, no quotes, no explanation."""


# --- fact checking -------------------------------------------------------
# Free-tier models are less reliable at "keep every fact identical", so every
# rewrite is verified before being saved.

def facts_survived(original, rewrite):
    """Return (ok, reason). Checks that numbers >=4 digits and years carried through."""
    def nums(t):
        t = t.replace("\u20b9", "Rs. ")
        return {re.sub(r"[^\d]", "", x) for x in re.findall(r"[\d,]{4,}", t)}
    o, r = nums(original), nums(rewrite)
    missing = {n for n in o if len(n) >= 4} - r
    if missing:
        return False, f"amount(s) lost: {sorted(missing)[:3]}"
    oy = set(re.findall(r"\b20\d{2}\b", original))
    ry = set(re.findall(r"\b20\d{2}\b", rewrite))
    if oy and not (oy & ry):
        return False, f"year lost: {sorted(oy)}"
    return True, ""


# --- providers -----------------------------------------------------------

class Ollama:
    """Local model. Free, unlimited, no key."""
    name = "ollama"

    def __init__(self, model=None):
        try:
            import requests
        except ImportError:
            sys.exit("Missing package. Run:  pip install requests")
        self.requests = requests
        self.model = model or "llama3.1:8b"
        base = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.url = base + "/api/chat"
        try:
            requests.get(base + "/api/tags", timeout=5)
        except Exception:
            sys.exit("Cannot reach Ollama at localhost:11434.\n"
                     "Install from ollama.com, then run:  ollama pull llama3.1:8b")

    def __call__(self, prompt):
        r = self.requests.post(self.url, timeout=180, json={
            "model": self.model, "stream": False,
            "options": {"temperature": 0.9},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["message"]["content"].strip()


class Gemini:
    """Google AI Studio free tier."""
    name = "gemini"

    def __init__(self, model=None):
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            sys.exit("GEMINI_API_KEY not set.\n"
                     "Get a FREE key at aistudio.google.com, then:\n"
                     '  setx GEMINI_API_KEY "your-key"   (reopen the terminal)')
        try:
            import google.generativeai as genai
        except ImportError:
            sys.exit("Missing package. Run:  pip install google-generativeai")
        genai.configure(api_key=key)
        self.model = genai.GenerativeModel(model or "gemini-3.6-flash",
                                           system_instruction=SYSTEM)

    def __call__(self, prompt):
        res = self.model.generate_content(prompt).text.strip()
        # Clean typical model preambles if present
        res = re.sub(r"^(?:Here (?:is|are|'s) (?:the |a )?(?:rewritten |simplified )?(?:complaint|version)[^\n]*:\s*)", "", res, flags=re.IGNORECASE).strip()
        return res.strip('"\n ')


class Claude:
    """Anthropic API. Needs paid credit."""
    name = "anthropic"

    def __init__(self, model=None):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit('ANTHROPIC_API_KEY not set.  setx ANTHROPIC_API_KEY "sk-ant-..."')
        try:
            import anthropic
        except ImportError:
            sys.exit("Missing package. Run:  pip install anthropic")
        self.client = anthropic.Anthropic()
        self.model = model or "claude-sonnet-4-6"

    def __call__(self, prompt):
        m = self.client.messages.create(model=self.model, max_tokens=1000,
              system=SYSTEM, messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in m.content if b.type == "text").strip()


PROVIDERS = {"ollama": Ollama, "gemini": Gemini, "anthropic": Claude}


def demo():
    """Show what the pipeline does, without calling the API."""
    print("DEMO MODE - no API key used, no files written.\n")
    files = sorted(glob.glob(os.path.join(SRC, "*_all.jsonl")))
    if not files:
        sys.exit(f"No files in {SRC}/ - run this from the classifier_project folder.")
    random.seed(SEED)
    for path in random.sample(files, min(3, len(files))):
        rows = [json.loads(l) for l in open(path, encoding="utf-8")]
        r = random.choice(rows)
        print("=" * 72)
        print(f"CATEGORY : {r['sub_category']}")
        print("=" * 72)
        print("ORIGINAL:")
        print(" ", r["complaint_text"][:400])
        print("\nWould be rewritten in 3 styles: plain / detailed / terse")
        print("Keeping the same facts, changing the words.\n")
    n = sum(len(open(f, encoding='utf-8').readlines()) for f in files)
    print(f"Dataset: {n} complaints across {len(files)} categories.")
    print(f"--per-category 100  ->  ~{100*len(files)*3} rewrites")
    print(f"--all               ->  ~{n*3} rewrites")
    print("\nSet ANTHROPIC_API_KEY, then run without --demo.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(PROVIDERS), default="ollama",
                    help="ollama (free/local) | gemini (free tier) | anthropic (paid)")
    ap.add_argument("--model", default=None, help="override the model name")
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="seconds between calls (use ~4 for the Gemini free tier)")
    ap.add_argument("--no-factcheck", action="store_true")
    ap.add_argument("--per-category", type=int, default=100,
                    help="complaints to paraphrase per category (default 100)")
    ap.add_argument("--all", action="store_true", help="paraphrase everything")
    ap.add_argument("--resume", action="store_true", help="skip work already done")
    ap.add_argument("--demo", action="store_true", help="preview without API calls")
    ap.add_argument("--styles", default="plain,detailed,terse")
    args = ap.parse_args()

    if args.demo:
        return demo()

    llm = PROVIDERS[args.provider](args.model)
    print(f"Provider: {llm.name}   styles: {args.styles}\n")
    styles = [s.strip() for s in args.styles.split(",") if s.strip() in STYLES]
    os.makedirs(DST, exist_ok=True)
    random.seed(SEED)

    files = sorted(glob.glob(os.path.join(SRC, "*_all.jsonl")))
    if not files:
        sys.exit(f"No files in {SRC}/ - run this from the classifier_project folder.")

    grand_done = grand_fail = grand_rej = 0
    t_start = time.time()

    for fi, path in enumerate(files, 1):
        base = os.path.basename(path).replace("_all.jsonl", "")
        out_path = os.path.join(DST, f"{base}_para.jsonl")

        rows = [json.loads(l) for l in open(path, encoding="utf-8")]
        picked = rows if args.all else random.sample(rows, min(args.per_category, len(rows)))

        already = set()
        if args.resume and os.path.exists(out_path):
            for l in open(out_path, encoding="utf-8"):
                r = json.loads(l)
                if r.get("paraphrase_of"):
                    already.add((r["paraphrase_of"], r.get("style")))

        mode = "a" if (args.resume and os.path.exists(out_path)) else "w"
        with open(out_path, mode, encoding="utf-8") as out:
            # keep the originals too, so the model sees both registers
            if mode == "w":
                for r in rows:
                    r2 = dict(r); r2["style"] = "original"; r2["paraphrase_of"] = None
                    out.write(json.dumps(r2, ensure_ascii=False) + "\n")

            done = fail = rej = 0
            for i, r in enumerate(picked, 1):
                for style in styles:
                    if (r["id"], style) in already:
                        continue
                    prompt = f"{STYLES[style]}\n\nComplaint to rewrite:\n{r['complaint_text']}"
                    try:
                        new_text = llm(prompt)
                        if len(new_text) < 100:      # implausibly short -> treat as failure
                            raise ValueError("response too short")
                        if not args.no_factcheck:
                            ok, why = facts_survived(r["complaint_text"], new_text)
                            if not ok:
                                rej += 1
                                if rej <= 2:
                                    print(f"    ~ rejected {r['id']}/{style}: {why}")
                                continue
                        rec = dict(r)
                        rec["id"] = f"{r['id']}_{style[:2]}"
                        rec["complaint_text"] = new_text
                        rec["style"] = style
                        rec["paraphrase_of"] = r["id"]
                        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        out.flush()
                        done += 1
                    except Exception as e:
                        fail += 1
                        if fail <= 3:
                            print(f"    ! {r['id']}/{style}: {type(e).__name__} {str(e)[:70]}")
                        time.sleep(2)
                    if args.sleep:
                        time.sleep(args.sleep)
                if i % 10 == 0 or i == len(picked):
                    print(f"  [{fi}/{len(files)}] {base[:36]:<38} {i}/{len(picked)}"
                          f"  ok={done} rejected={rej} failed={fail}")

        grand_done += done; grand_fail += fail; grand_rej += rej

    mins = (time.time() - t_start) / 60
    print("\n" + "=" * 72)
    print(f"Rewrites written        : {grand_done}")
    print(f"Rejected (facts changed): {grand_rej}")
    print(f"Failed (errors)         : {grand_fail}")
    print(f"Time             : {mins:.1f} min")
    print(f"Output           : {DST}/")
    print("=" * 72)
    print("\nNext:")
    print("  python make_para_split.py       # build template-disjoint splits from this")
    print("  python train_baseline_para.py   # the honest score")


if __name__ == "__main__":
    main()