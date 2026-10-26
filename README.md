<div align="center">

# Fail-Loud OCR for Purchase Orders

**Safety layer from a production PO-to-ERP automation tool, built on one rule: _a wrong value must never pass silently._**

Python · PaddleOCR · PyQt6 · Flask · PyInstaller

</div>

---

## The problem

Sales coordinators were typing purchase orders into an ERP by hand: PO number, item code, quantity, for dozens of customers, each with a different layout, language and scan quality. Most documents arrive as **scanned copies** (skewed, blurry, stamped), so plain OCR is not enough.

I built an internal desktop tool that reads a PO PDF, picks the right customer format, extracts the fields from zones a person marked once on a sample, lets an operator verify each row, and exports a CSV the ERP can import. It is in daily production use.

> The full application is private (it contains customer layouts and internal systems). This repository publishes the **parts that show the engineering**: the independent verification layer and the design notes behind it.

## Design principle: wrong is acceptable, silent is not

OCR will never be 100% right. A wrong quantity that looks green is far worse than a red cell that asks for a human. Every stage either produces the right value or raises a visible warning.

| Idea | How |
|---|---|
| Read only from marked zones | Find an anchor, measure shift / scale / rotation, map the marked zone onto this page, read inside it. No whole-page regex guessing. |
| Independent quantity cross-check | [`src/qty_guard.py`](src/qty_guard.py) re-reads each quantity a second way and **flags** disagreement. It never edits a value. |
| Second opinion from the PDF text layer | [`src/text_layer.py`](src/text_layer.py) compares OCR output with embedded text when the PDF has it. |
| Silent-drop guards | Total-line and row-number checks catch rows that disappeared. |
| Fail loud | An unreadable zone becomes `Unknown` / red, never a value borrowed from elsewhere. |
| Human in the loop | Review screen shows confidence, warnings and the source crop; export asks again while warnings remain. |

## Pipeline

```
PDF -> page images -> OCR -> route template -> calibrate zones
    -> per-customer engine -> qty_guard (flags only)
    -> verification UI -> ERP CSV
```

One independent engine per customer format, so fixing one customer cannot break another.

## Try it (about 10 seconds, no OCR install)

```bash
pip install -r requirements.txt
python demo/gui.py             # review screen in your browser: http://127.0.0.1:8765
python demo/demo.py            # same scenarios as plain terminal output
```

![Review screen: a missing row is caught by the table-total check and export is held](docs/screenshot-flagged.jpg)

The screen mimics the tool's review step on a fictional PO. Pick a scenario to inject an OCR failure; extraction reads **only from the marked zones**, and [`qty_guard`](src/qty_guard.py) judges each row. While anything is flagged, **Export is disabled**. (The real app is a PyQt6 desktop program; this demo is a small web version of the same idea.)

The demo reads a fictional 4-line PO, extracts rows **only from the marked zones**, then replays the page under five failure modes and runs [`qty_guard`](src/qty_guard.py) on each. Sample output (guard messages are in Thai, the working language of the tool; the glosses are mine):

```
== Clean scan
   [OK  ] AX-1001  qty=90 ...                                   -> all green, values correct

== OCR misreads a digit: qty 90 -> 96
   [FLAG] AX-1001  qty=96   Qty x unit price != line amount (amount / price = 90)
== OCR misses an entire line (row 3 vanishes)
   [PAGE] Table total (270, 3927) != sum of rows read (qty 120 / amount 3297)
== Quantity inflated x100 (24 -> 2400)
   [PAGE] Table total (270, 3927) != sum of rows read (qty 2646 / amount 94215)
== Engine bug: qty read from the unit-price column
   [FLAG] qty=12.50   number 12.50 not found in the Quantity column
```

Every injected failure ends in a flag; none passes as green. The OCR stand-in is the PDF's embedded text, so the demo is deterministic; the real tool uses PaddleOCR on scans.

## How it was tested

- ~150 real PO files replayed from cached OCR output through every stage (fast and deterministic).
- Before/after **snapshot diffs**: a change may alter only the values it intended to.
- **Fuzzing** of OCR labels (jitter, split/merged words, dropped punctuation, dropped rows), measuring *silent failures*, which must be zero.
- **Rotation stress tests** (+/-1 to 10 degrees) before deskew is enabled for a format.

## What is in this repo

| Path | What |
|---|---|
| [`src/qty_guard.py`](src/qty_guard.py) | Quantity parsing, OCR digit repair, independent cross-check, total-line and row-number guards. Flags only. |
| [`src/text_layer.py`](src/text_layer.py) | PDF text-layer comparison. |
| [`demo/`](demo) | Runnable demo: browser review screen (`gui.py`), terminal version (`demo.py`), fictional PO generator. |

Per-template switches (`TOTAL_CHECK_TEMPLATES`, `PO_FORMATS`, ...) are empty here; in the private tool they are opt-in per customer format after verification on real files.

## Skills shown

Document understanding on noisy real-world scans · fail-safe design and making uncertainty visible · regression discipline (snapshots, fuzzing, stress tests) · PyQt6 / Flask tooling · Windows packaging and update flow.

## Author

Nattawat · [@mroatder](https://github.com/mroatder)
