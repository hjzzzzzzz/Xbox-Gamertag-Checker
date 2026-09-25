import sys
import os
import re
import time
import random
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

INPUT_FILE   = "tags.txt"
OUTPUT_FILE  = "results.txt"
DELAY_MIN    = 2.0
DELAY_MAX    = 4.0
RETRY_DELAY  = 15.0
CHROMEDRIVER = "chromedriver.exe"
RESTART_EVERY = 50

stop_flag = threading.Event()

def make_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    import subprocess
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--memory-pressure-off")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--mute-audio")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    service = Service(executable_path=CHROMEDRIVER, stderr=subprocess.DEVNULL)
    driver = webdriver.Chrome(service=service, options=opts)
    return driver

def safe_quit(driver):
    try: driver.quit()
    except: pass

def sanitize(text):
    if text is None: return None
    return text.encode("ascii", errors="replace").decode("ascii")

def check_tag(driver, tag):
    from selenium.webdriver.common.by import By
    url = f"https://www.xboxgamertag.com/search/{tag}"
    try:
        driver.get(url)
        time.sleep(2)
        page = driver.find_element(By.TAG_NAME, "body").text
        if "403" in driver.title or "403" in page[:50]:
            return "RETRY", None, None
        if "set to private" in page.lower():
            return "PRIVATE", None, None
        if "not found" in page.lower() or "couldn't find" in page.lower():
            return "NOT FOUND", None, None
        last_game = last_played = None
        elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Last played')]")
        if elements:
            el = elements[0]
            last_played = el.text.strip()
            try:
                card = el.find_element(By.XPATH, "./ancestor::div[2]")
                for h in card.find_elements(By.XPATH, ".//h2|.//h3|.//h4|.//strong|.//a"):
                    t = h.text.strip()
                    if t and len(t) > 1:
                        last_game = t
                        break
            except: pass
        return "PUBLIC", last_game, last_played
    except:
        return "RETRY", None, None

def format_line(tag, status, last_game, last_played):
    if status == "PRIVATE":    return f"{tag} - Private"
    elif status == "NOT FOUND": return f"{tag} - Not found"
    elif status == "PUBLIC":
        parts = [tag]
        if last_game:   parts.append(f"Last game: {sanitize(last_game)}")
        if last_played: parts.append(sanitize(last_played))
        if not last_game and not last_played: parts.append("No activity found")
        return " | ".join(parts)
    else: return f"{tag} - {status}"

def get_already_done():
    done = set()
    if not os.path.exists(OUTPUT_FILE): return done
    with open(OUTPUT_FILE, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("Xbox") or line.startswith("="): continue
            tag = line.split(" -")[0].split(" |")[0].strip()
            if tag: done.add(tag)
    return done

def run_checker(log_fn, progress_fn):
    if not os.path.exists(INPUT_FILE):
        log_fn("ERROR: tags.txt not found!")
        return
    with open(INPUT_FILE, "r") as f:
        all_tags = [l.strip() for l in f if l.strip()]
    if not all_tags:
        log_fn("ERROR: tags.txt is empty!")
        return

    done = get_already_done()
    queue = [t for t in all_tags if t not in done]
    total_all = len(all_tags)

    if not queue:
        log_fn("All tags already checked!")
        return

    if not done:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(f"Xbox Activity Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")

    log_fn(f"Resuming... {len(done)} done, {len(queue)} remaining." if done else f"Starting {len(queue)} tags...")

    retried = set()
    driver = make_driver()
    tags_since_restart = 0
    total = len(queue)
    i = 0

    with open(OUTPUT_FILE, "a", encoding="utf-8") as out:
        while queue and not stop_flag.is_set():
            tag = queue.pop(0)
            i += 1

            if tags_since_restart >= RESTART_EVERY:
                log_fn("[Restarting browser...]")
                safe_quit(driver)
                time.sleep(2)
                driver = make_driver()
                tags_since_restart = 0

            try:
                status, last_game, last_played = check_tag(driver, tag)
            except:
                safe_quit(driver)
                time.sleep(3)
                driver = make_driver()
                tags_since_restart = 0
                status, last_game, last_played = check_tag(driver, tag)

            tags_since_restart += 1

            if status == "RETRY" and tag not in retried:
                log_fn(f"({i}/{total}) {tag} - connection issue, retrying later...")
                retried.add(tag)
                queue.append(tag)
                total = len(queue) + i
                time.sleep(RETRY_DELAY)
                continue
            elif status == "RETRY":
                line = f"{tag} - Failed (connection refused)"
                log_fn(f"({i}/{total}) {line}")
                out.write(line + "\n")
                out.flush()
                continue

            line = format_line(tag, status, last_game, last_played)
            log_fn(f"({i}/{total}) {line}")
            out.write(line + "\n")
            out.flush()
            progress_fn(len(get_already_done()), total_all)

            if queue and not stop_flag.is_set():
                time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    safe_quit(driver)
    if stop_flag.is_set():
        log_fn("Stopped.")
    else:
        log_fn("All done!")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Xbox Gamertag Checker")
        self.geometry("800x560")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")
        self._build_ui()

    def _build_ui(self):
        tk.Label(self, text="Xbox Gamertag Checker", font=("Segoe UI", 18, "bold"),
                 bg="#1a1a2e", fg="white").pack(pady=(20, 5))

        nav = tk.Frame(self, bg="#1a1a2e")
        nav.pack(pady=10)
        btn_style = {"font": ("Segoe UI", 11, "bold"), "width": 10, "height": 2,
                     "bd": 0, "cursor": "hand2", "activeforeground": "white"}
        colors = {"Tags": "#0f3460", "Results": "#0f3460", "Filter": "#0f3460",
                  "Start": "#16213e", "Stop": "#7b1818"}
        fg = {"Tags": "white", "Results": "white", "Filter": "white", "Start": "#00d4aa", "Stop": "#ff6b6b"}
        cmds = {"Tags": self.show_tags, "Results": self.show_results,
                "Filter": self.show_filter, "Start": self.start_checker, "Stop": self.stop_checker}
        for label in ["Tags", "Results", "Filter", "Start", "Stop"]:
            tk.Button(nav, text=label, bg=colors[label], fg=fg[label],
                      activebackground=colors[label], command=cmds[label],
                      **btn_style).pack(side="left", padx=6)

        self.progress_var = tk.DoubleVar()
        self.progress_label = tk.Label(self, text="", font=("Segoe UI", 9),
                                       bg="#1a1a2e", fg="#aaaaaa")
        self.progress_label.pack()
        self.progress_bar = ttk.Progressbar(self, variable=self.progress_var,
                                            maximum=100, length=760)
        self.progress_bar.pack(pady=(0, 8))

        self.content = tk.Frame(self, bg="#16213e", width=760, height=340)
        self.content.pack(padx=20, pady=5)
        self.content.pack_propagate(False)

        self.show_log()

    def clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def show_log(self):
        self.clear_content()
        self.log_box = scrolledtext.ScrolledText(self.content, bg="#0d0d1a", fg="#00d4aa",
                                                  font=("Consolas", 10), bd=0, state="disabled",
                                                  insertbackground="white")
        self.log_box.pack(fill="both", expand=True, padx=4, pady=4)

    def log(self, msg):
        def _do():
            self.log_box.config(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        self.after(0, _do)

    def update_progress(self, done, total):
        def _do():
            pct = min((done / total * 100) if total else 0, 100)
            self.progress_var.set(pct)
            self.progress_label.config(text=f"{done} / {total} tags checked ({pct:.1f}%)")
        self.after(0, _do)

    def show_tags(self):
        self.clear_content()
        tk.Label(self.content, text="Tags (one per line) - auto-saves as you type", font=("Segoe UI", 11, "bold"),
                 bg="#16213e", fg="white").pack(pady=(8, 4))
        self.tags_box = scrolledtext.ScrolledText(self.content, bg="#0d0d1a", fg="white",
                                                   font=("Consolas", 10), bd=0)
        self.tags_box.pack(fill="both", expand=True, padx=4)
        if os.path.exists(INPUT_FILE):
            with open(INPUT_FILE, "r") as f:
                self.tags_box.insert("1.0", f.read())
        # Auto-save on any key press
        self.tags_box.bind("<KeyRelease>", lambda e: self.auto_save_tags())
        btn_row = tk.Frame(self.content, bg="#16213e")
        btn_row.pack(pady=6)
        tk.Button(btn_row, text="Save Tags", bg="#0f3460", fg="white", font=("Segoe UI", 10, "bold"),
                  bd=0, padx=16, pady=6, command=self.save_tags).pack(side="left", padx=6)
        tk.Button(btn_row, text="Clear", bg="#3a1a1a", fg="#ff6b6b", font=("Segoe UI", 10, "bold"),
                  bd=0, padx=16, pady=6, command=lambda: self.tags_box.delete("1.0", "end")).pack(side="left", padx=6)
    
    def auto_save_tags(self):
        content = self.tags_box.get("1.0", "end").strip()
        if content:
            with open(INPUT_FILE, "w") as f:
                f.write(content + "\n")

    def save_tags(self):
        content = self.tags_box.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("Empty", "No tags to save")
            return
        with open(INPUT_FILE, "a") as f:
            for line in content.split("\n"):
                line = line.strip()
                if line:
                    f.write(line + "\n")
        messagebox.showinfo("Saved", f"Tags appended to {INPUT_FILE}")
        self.tags_box.delete("1.0", "end")
        # Reset progress bar
        self.progress_var.set(0)
        with open(INPUT_FILE, "r") as f:
            total = len([l for l in f if l.strip()])
        self.progress_label.config(text=f"0 / {total} tags checked (0.0%)")

    def show_results(self):
        self.clear_content()
        
        # Header with search
        header = tk.Frame(self.content, bg="#16213e")
        header.pack(fill="x", padx=4, pady=(8, 4))
        tk.Label(header, text="Results", font=("Segoe UI", 11, "bold"),
                 bg="#16213e", fg="white").pack(side="left")
        tk.Label(header, text="Search:", font=("Segoe UI", 9),
                 bg="#16213e", fg="#aaaaaa").pack(side="left", padx=(20, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.filter_results_display())
        search_entry = tk.Entry(header, textvariable=self.search_var, bg="#0d0d1a", fg="white",
                                font=("Consolas", 10), insertbackground="white", width=20)
        search_entry.pack(side="left", padx=4)
        
        # Results display
        self.results_box = scrolledtext.ScrolledText(self.content, bg="#0d0d1a", fg="#00d4aa",
                                                      font=("Consolas", 9), bd=0)
        self.results_box.pack(fill="both", expand=True, padx=4)
        
        # Load results
        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "r", encoding="utf-8", errors="replace") as f:
                self.raw_results = f.read()
        else:
            self.raw_results = "No results yet."
        
        self.filter_results_display()
        self.results_box.config(state="disabled")
        
        # Buttons
        btn_row = tk.Frame(self.content, bg="#16213e")
        btn_row.pack(pady=6)
        tk.Button(btn_row, text="Refresh", bg="#0f3460", fg="white", font=("Segoe UI", 10, "bold"),
                  bd=0, padx=16, pady=6, command=self.show_results).pack(side="left", padx=6)

    def filter_results_display(self):
        search_term = self.search_var.get().lower()
        self.results_box.config(state="normal")
        self.results_box.delete("1.0", "end")
        
        if not self.raw_results:
            self.results_box.insert("1.0", "No results yet.")
            self.results_box.config(state="disabled")
            return
        
        lines = self.raw_results.split("\n")
        if search_term:
            filtered = []
            for l in lines:
                if l.strip() and not l.startswith("="):
                    tag = l.split(" -")[0].split(" |")[0].strip()
                    if search_term in tag.lower():
                        filtered.append(l)
            if filtered:
                self.results_box.insert("end", "\n".join(filtered))
            else:
                self.results_box.insert("end", f"No tags matching '{search_term}'")
        else:
            self.results_box.insert("1.0", self.raw_results)
        
        self.results_box.config(state="disabled")

    def show_filter(self):
        self.clear_content()
        tk.Label(self.content, text="Filter Results by Inactivity", font=("Segoe UI", 11, "bold"),
                 bg="#16213e", fg="white").pack(pady=(12, 4))
        row1 = tk.Frame(self.content, bg="#16213e")
        row1.pack(pady=4)
        tk.Label(row1, text="Min inactivity:", bg="#16213e", fg="#aaaaaa",
                 font=("Segoe UI", 10)).pack(side="left", padx=(0, 6))
        self.min_entry = tk.Entry(row1, bg="#0d0d1a", fg="white", font=("Consolas", 10),
                                   insertbackground="white", width=16)
        self.min_entry.insert(0, "6 months")
        self.min_entry.pack(side="left")
        row2 = tk.Frame(self.content, bg="#16213e")
        row2.pack(pady=4)
        tk.Label(row2, text="Max inactivity:", bg="#16213e", fg="#aaaaaa",
                 font=("Segoe UI", 10)).pack(side="left", padx=(0, 6))
        self.max_entry = tk.Entry(row2, bg="#0d0d1a", fg="white", font=("Consolas", 10),
                                   insertbackground="white", width=16)
        self.max_entry.insert(0, "leave blank for no limit")
        self.max_entry.pack(side="left")
        tk.Label(self.content, text="Examples: 6 months, 1 year, 2 years, 3 months",
                 bg="#16213e", fg="#666666", font=("Segoe UI", 9)).pack(pady=2)
        tk.Button(self.content, text="Run Filter", bg="#0f3460", fg="white",
                  font=("Segoe UI", 10, "bold"), bd=0, padx=20, pady=8,
                  command=self.run_filter).pack(pady=8)
        self.filter_result = scrolledtext.ScrolledText(self.content, bg="#0d0d1a", fg="#00d4aa",
                                                        font=("Consolas", 10), bd=0, height=8)
        self.filter_result.pack(fill="both", expand=True, padx=4, pady=4)

    def run_filter(self):
        def parse_time(text):
            text = text.strip().lower()
            if not text or "blank" in text: return None
            match = re.match(r'(\d+\.?\d*)\s*(minute|hour|day|week|month|year)s?', text)
            if not match: return None
            amount, unit = float(match.group(1)), match.group(2)
            conv = {"minute": 1/525600, "hour": 1/8760, "day": 1/365, "week": 1/52, "month": 1/12, "year": 1}
            return amount * conv.get(unit, 0)
        
        min_text = self.min_entry.get().strip()
        max_text = self.max_entry.get().strip()
        min_years = parse_time(min_text) if min_text else 0.0
        max_years = parse_time(max_text) if max_text else float("inf")
        if min_years is None:
            messagebox.showerror("Error", f"Couldn't parse min: '{min_text}'")
            return
        if not os.path.exists(OUTPUT_FILE):
            messagebox.showerror("Error", "No results.txt found")
            return
        with open(OUTPUT_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        matches = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("Xbox") or line.startswith("="): continue
            match = re.search(r'last played (\d+)\s*(minute|hour|day|week|month|year)s?\s*ago', line.lower())
            if match:
                amount, unit = int(match.group(1)), match.group(2)
                conv = {"minute": 1/525600, "hour": 1/8760, "day": 1/365, "week": 1/52, "month": 1/12, "year": 1}
                years = amount * conv.get(unit, 0)
                if min_years <= years <= max_years:
                    matches.append((years, line))
        matches.sort(key=lambda x: x[0])
        self.filter_result.config(state="normal")
        self.filter_result.delete("1.0", "end")
        self.filter_result.insert("end", f"Found {len(matches)} tags:\n\n")
        for _, line in matches:
            self.filter_result.insert("end", line + "\n")
        self.filter_result.config(state="disabled")

    def start_checker(self):
        if not os.path.exists(INPUT_FILE):
            messagebox.showerror("Error", "tags.txt not found! Add tags first.")
            return
        stop_flag.clear()
        self.show_log()
        self.log("Starting checker...")
        done = get_already_done()
        with open(INPUT_FILE, "r") as f:
            total = len([l for l in f if l.strip()])
        self.update_progress(len(done), total)
        t = threading.Thread(target=run_checker, args=(self.log, self.update_progress), daemon=True)
        t.start()

    def stop_checker(self):
        stop_flag.set()
        self.log("Stop requested — finishing current tag...")

if __name__ == "__main__":
    app = App()
    app.mainloop()
