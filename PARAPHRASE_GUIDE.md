# Paraphrase Pipeline — what it is and how to run it

## The problem it solves

Each category currently contains words that appear in it and nowhere else:
AePS has "biometric", Damage has "ransomware", Job Fraud has "consultancy".
The classifier learned those keywords, not the crimes. That is why it scores 1.0.

A real complaint says "money gone, thumb impression used, no OTP came" — none of
your distinctive words. The model has never seen that and will guess.

## What the pipeline does

Sends each complaint to an LLM: "rewrite this, keep every fact, change the words".
Three styles per complaint:

  plain    — how an ordinary person would tell a police officer
  detailed — longer, with background and worry, as a real complainant writes
  terse    — blunt, essential facts only, typed in a hurry

Same facts. Different words. The keyword shortcut stops working, so the model
has to learn the pattern instead.

## Setup

    pip install anthropic

Get a key from console.anthropic.com, then:

    Windows   :  setx ANTHROPIC_API_KEY "sk-ant-..."     (reopen the terminal)
    Mac/Linux :  export ANTHROPIC_API_KEY="sk-ant-..."

## Run — three steps

    python paraphrase.py --demo                # preview, no key needed
    python paraphrase.py --per-category 100    # ~6,300 rewrites, start here
    python make_para_split.py                  # build honest splits
    python train_baseline_para.py              # the real score

If it stops partway, add --resume to continue where it left off.

## What to expect

Scale     : 100/category = 6,300 rewrites; --all = 31,500
Time      : roughly 1-2 seconds per rewrite
The score : it WILL drop. That is the point.

The output ends with ACCURACY BY WRITING STYLE:

    original     high    <- generator wording, the easy case
    plain        lower   <- natural language, the real test
    detailed     lower
    terse        lower

A big gap proves the model was leaning on generator vocabulary.
A small gap means it genuinely learned the patterns.

Either result is useful — right now you know neither.

## Why this also builds Module A

Module A takes a messy real complaint and produces a clean narrative.
This pipeline does the same job in reverse. Building it advances the dataset
AND the AI Assistant at the same time.

## Files

    paraphrase.py            calls the LLM, writes dataset/paraphrased/
    make_para_split.py       splits it (template-disjoint AND family-intact)
    train_baseline_para.py   scores it, with the per-style breakdown

## One safeguard worth knowing

make_para_split.py keeps an original and all its rewrites in the SAME split.
Without that rule the model would see a complaint in training and its reworded
twin in test — leakage in disguise. The script verifies this and prints OK/FAIL.
