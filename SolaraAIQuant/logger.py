"""
Solara AI Quant - Terminal Logger (logger.py)

Rich, colorized terminal output using colorama + ANSI cursor control.

Key behaviour:
  Each timeframe (M5, H4, etc.) gets its own pipeline block that
  UPDATES IN PLACE on every cycle — no repeated scrolling output.
  The block is overwritten using ANSI cursor-up + line-clear sequences.
"""

import logging
import threading
from datetime import datetime
from typing import Optional, Dict, List

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORAMA = True
except ImportError:
    COLORAMA = False
    class _Stub:
        def __getattr__(self, _): return ""
    Fore = Style = _Stub()

G    = Fore.GREEN
Y    = Fore.YELLOW
R    = Fore.RED
C    = Fore.CYAN
B    = Fore.BLUE
W    = Fore.WHITE
RST  = Style.RESET_ALL
BRT  = Style.BRIGHT
GRAY = "\033[90m"

# ANSI cursor controls
UP   = "\033[{}A"     # move cursor up N lines
CLR  = "\033[2K\r"    # erase entire current line


def _ts() -> str:
    return f"{GRAY}{datetime.now().strftime('%H:%M:%S')}{RST}"


class SAQLogger:
    VERSION = "1.0.0"

    def __init__(self):
        self._lock = threading.Lock()
        # tracks how many lines each TF block occupies so we can overwrite it
        self._tf_block_lines: Dict[str, int] = {}
        # the rendered lines for each TF (so we can reprint cleanly)
        self._tf_block_content: Dict[str, List[str]] = {}
        # whether the "watching" line has been printed (one global line)
        self._watching_printed = False

    # ── Startup ───────────────────────────────────────────────────────────────

    def startup_banner(self):
        sep = f"{GRAY}{'━' * 62}{RST}"
        print()
        print(sep)
        print(f"  {C}{BRT}🤖  SOLARA AI QUANT  v{self.VERSION}{RST}")
        print(sep)
        print()

    def startup_item(self, label: str, ok: bool = True, detail: str = ""):
        icon = f"{G}✔{RST}" if ok else f"{GRAY}—{RST}"
        det  = f"  {GRAY}{detail}{RST}" if detail else ""
        print(f"  {_ts()}  {icon}  {W}{label}{RST}{det}")

    def startup_mode(self, mode: str, dry_run: bool):
        mode_color = R if mode == "PRODUCTION" else C
        dr = f"  {GRAY}dry-run{RST}" if dry_run else ""
        print(f"  {_ts()}  {GRAY}⚙️   Mode{RST}    "
              f"{mode_color}{BRT}{mode}{RST}{dr}")

    def startup_watched_files(self, files: list):
        print(f"  {_ts()}  {G}✔{RST}  {W}File observer{RST}  "
              f"{GRAY}MQL5/Files/{RST}")
        for f in files:
            print(f"  {' ' * 11}     {GRAY}📄 {f}{RST}")

    def startup_ready(self):
        sep = f"{GRAY}{'━' * 62}{RST}"
        print()
        print(sep)
        print(f"  {G}{BRT}  ✅  READY — watching for CSV updates…{RST}")
        print(sep)
        print()

    def startup_failed(self, reason: str):
        sep = f"{GRAY}{'━' * 62}{RST}"
        print()
        print(sep)
        print(f"  {R}{BRT}  ❌  STARTUP FAILED{RST}")
        print(f"  {R}  {reason}{RST}")
        print(sep)
        print()

    # ── In-place pipeline block ───────────────────────────────────────────────

    def render_pipeline_block(
        self,
        timeframe: str,
        stages: List[dict],       # list of {step, name, status, detail}
        signals: List[dict],      # list of {symbol, direction, confidence, detail}
        outcome: str,
        elapsed: float,
        footer_detail: str = "",
    ):
        """
        Render (or re-render) the full pipeline block for a timeframe.
        If this TF has been printed before, cursor moves up and overwrites it.

        stages: list of dicts with keys: step, name, status, detail
        signals: list of dicts with keys: symbol, direction, confidence, detail
        outcome: "no signal" | "N signals" | "warning" | "failed"
        """
        with self._lock:
            lines = self._build_block(timeframe, stages, signals, outcome, elapsed, footer_detail)
            n_new = len(lines)

            # If we already have a block for this TF, go back and overwrite it
            if timeframe in self._tf_block_lines:
                n_old = self._tf_block_lines[timeframe]
                # Move cursor up past the old block
                # (+1 for the "watching…" line if it was printed)
                total_up = n_old + (1 if self._watching_printed else 0)
                print(UP.format(total_up), end="", flush=True)
                # Erase old lines
                for _ in range(n_old):
                    print(CLR, end="", flush=True)
                    if _ < n_old - 1:
                        print(f"\033[1B", end="", flush=True)
                # Go back to start of block
                print(UP.format(n_old - 1), end="", flush=True)

            # Print new block
            for line in lines:
                print(CLR + line, flush=True)

            self._tf_block_lines[timeframe] = n_new
            self._watching_printed = False

    def _build_block(self, timeframe, stages, signals, outcome, elapsed, footer_detail):
        """Build list of terminal lines for a pipeline block."""
        lines = []

        # Header trigger line
        lines.append(
            f"  {_ts()}  {B}📂  {timeframe} CSV updated{RST}  "
            f"{GRAY}every cycle — updating in place{RST}"
        )

        # Box top
        bar = '─' * max(1, 46 - len(timeframe))
        lines.append(f"  {GRAY}  ┌─ pipeline: {W}{timeframe}{GRAY} {bar}┐{RST}")

        # Stage rows
        for s in stages:
            step   = s['step']
            name   = s['name']
            status = s['status']
            detail = s.get('detail', '')

            if status == "ok":
                sc = W;    icon = f"{G}✔{RST}"
            elif status == "warn":
                sc = Y;    icon = f"{Y}⚠{RST}"
            elif status == "error":
                sc = R;    icon = f"{R}✖{RST}"
            else:
                sc = GRAY; icon = f"{GRAY}—{RST}"

            det = f"  {GRAY}{detail}{RST}" if detail else ""
            lines.append(
                f"  {_ts()}  {GRAY}│{RST}  "
                f"{sc}{step}/8{RST}  {sc}{name:<10}{RST}{icon}{det}"
            )

        # Signal rows (inside the box)
        for sig in signals:
            dir_color = G if sig['direction'] == "LONG" else R
            arrow     = "▲" if sig['direction'] == "LONG" else "▼"
            conf_col  = G if sig['confidence'] >= 0.65 else Y
            det       = f"  {GRAY}{sig.get('detail', '')}{RST}" if sig.get('detail') else ""
            lines.append(
                f"  {' ':11}  {G}│{RST}  {G}📡{RST}  "
                f"{W}{BRT}{sig['symbol']:<8}{RST}  "
                f"{dir_color}{arrow} {sig['direction']:<5}{RST}  "
                f"{conf_col}conf {sig['confidence']:.3f}{RST}{det}"
            )

        # Footer
        if "signal" in outcome and outcome != "no signal":
            pill = f"{G}{BRT}{outcome}{RST}"
        elif outcome == "no signal":
            pill = f"{GRAY}{outcome}{RST}"
        elif outcome == "warning":
            pill = f"{Y}{outcome}{RST}"
        else:
            pill = f"{R}{BRT}{outcome}{RST}"

        fd  = f"  {GRAY}{footer_detail}{RST}" if footer_detail else ""
        lines.append(
            f"  {_ts()}  {GRAY}  └─{RST}  {pill}  "
            f"{GRAY}{elapsed:.2f}s{RST}{fd}"
        )

        return lines

    def watching(self):
        """Print the idle watching line (one line, after the block)."""
        with self._lock:
            print(f"  {_ts()}  {GRAY}👁  watching…{RST}", flush=True)
            self._watching_printed = True

    # ── Standalone messages ───────────────────────────────────────────────────

    def ok(self, message: str, detail: str = ""):
        det = f"  {GRAY}{detail}{RST}" if detail else ""
        print(f"  {_ts()}  {G}✔{RST}  {message}{det}")

    def info(self, message: str, detail: str = ""):
        det = f"  {GRAY}{detail}{RST}" if detail else ""
        print(f"  {_ts()}  {B}ℹ{RST}  {message}{det}")

    def warn(self, message: str, detail: str = ""):
        det = f"  {GRAY}{detail}{RST}" if detail else ""
        print(f"  {_ts()}  {Y}⚠{RST}  {Y}{message}{RST}{det}")

    def error(self, message: str, detail: str = ""):
        det = f"  {GRAY}{detail}{RST}" if detail else ""
        print(f"  {_ts()}  {R}✖{RST}  {R}{message}{RST}{det}")

    # Legacy methods kept for compatibility
    def file_trigger(self, timeframe: str, filename: str): pass
    def pipeline_open(self, timeframe: str, model_count: int): pass
    def pipeline_stage(self, step, name, status, detail=""): pass
    def pipeline_highlight(self, line, style="signal"): pass
    def pipeline_footer(self, outcome, elapsed, detail=""): pass
    def signal(self, symbol, direction, confidence, detail=""): pass
    def startup_item_skip(self, label, detail=""): pass


saq_log = SAQLogger()


def configure_stdlib_logging(log_file: Optional[str] = None, level: str = "INFO"):
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(logging.NullHandler())

    if log_file:
        from logging.handlers import RotatingFileHandler
        from pathlib import Path
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024,
            backupCount=5, encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(fh)
