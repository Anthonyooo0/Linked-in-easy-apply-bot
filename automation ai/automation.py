
"""
linkedin_easy_apply_state_machine.py

A robust, state-machine–driven LinkedIn Easy Apply bot using Playwright + OpenAI.
"""

import os
import sys
import time
import random
import logging
import csv
from datetime import datetime

from dotenv import load_dotenv
import openai
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from docx import Document

print("Script started")

# ─── CONFIG ───────────────────────────────────────────────────────────────────────
load_dotenv()

EMAIL       = os.getenv("LINKEDIN_EMAIL")
PASSWORD    = os.getenv("LINKEDIN_PASSWORD")
RESUME_PATH = os.getenv("RESUME_PATH")
OPENAI_KEY  = os.getenv("OPENAI_API_KEY")
MAX_APPLIES = int(os.getenv("MAX_APPLIES", "5"))
CSV_PATH    = os.getenv("CSV_PATH", "applications.csv")

print("ENV CHECK:")
print("EMAIL:", EMAIL)
print("PASSWORD:", "OK" if PASSWORD else "MISSING")
print("RESUME_PATH:", RESUME_PATH)
print("OPENAI_KEY:", "OK" if OPENAI_KEY else "MISSING")
print("MAX_APPLIES:", MAX_APPLIES)
print("CSV_PATH:", CSV_PATH)

if not EMAIL:
    raise ValueError("LINKEDIN_EMAIL missing in .env")
if not PASSWORD:
    raise ValueError("LINKEDIN_PASSWORD missing in .env")
if not OPENAI_KEY:
    raise ValueError("OPENAI_API_KEY missing in .env")
if not os.path.isfile(RESUME_PATH):
    raise FileNotFoundError(f"Resume not found at {RESUME_PATH}")

openai.api_key = OPENAI_KEY

# ─── HELPER: VERIFY OPENAI STATUS ────────────────────────────────────────────────
def verify_openai():
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'ready' if you're working."}]
        )
        answer = resp.choices[0].message.content.strip().lower()
        if "ready" in answer:
            logging.info("OpenAI is responding correctly.")
        else:
            logging.warning(f"Unexpected OpenAI response: {answer}")
    except Exception as e:
        logging.error(f"OpenAI check failed: {e}")
        raise

# ─── HELPERS ─────────────────────────────────────────────────────────────────────
def load_resume_text(path: str) -> str:
    try:
        doc = Document(path)
        lines = []
        for para in doc.paragraphs:
            if para.text.strip():
                prefix = "- " if para.style.name.lower().startswith("list") else ""
                lines.append(f"{prefix}{para.text.strip()}")
        result = "\n".join(lines)
        print("📄 RESUME PREVIEW:", result[:500], "...\n")
        return result
    except Exception as e:
        print(f"Failed to read resume: {e}")
        raise

RESUME_TEXT = load_resume_text(RESUME_PATH)

ANSWER_MAP = {
    "legally authorized to work": "Yes",
    "require sponsorship":       "No",
    "relocate":                  "Yes",
    "minimum salary":            "0",
    "start date":                "Immediately",
}

def human_pause(a=0.8, b=1.5):
    time.sleep(random.uniform(a, b))

def answer_text(q: str) -> str:
    try:
        print(f"\n[AI] Answering TEXT Q: {q}")
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", temperature=0.5, max_tokens=80,
            messages=[{"role": "user", "content":
                f"You are applying for a Software Engineer Intern.\n"
                f"Use my resume to answer concisely:\n\n{RESUME_TEXT}\n\nQuestion: {q}\nAnswer:"
            }]
        )
        answer = resp.choices[0].message.content.strip()
        print(f"[AI] TEXT Answer: {answer}")
        return answer
    except Exception as e:
        logging.error(f"GPT answer_text failed for: {q} – {e}")
        print(f"[AI] TEXT Answer ERROR: {e}")
        return "N/A"

def answer_select(q: str, options: list[str]) -> str:
    try:
        print(f"\n[AI] Answering SELECT Q: {q}\nOptions: {options}")
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", temperature=0.3, max_tokens=40,
            messages=[{"role": "user", "content":
                f"You are applying for a Software Engineer Intern.\n"
                f"Use my resume to choose the best option:\n\n{RESUME_TEXT}\n\n"
                f"Question: {q}\nOptions:\n" + "\n".join(f"- {o}" for o in options) + "\nReply exactly with the best option."
            }]
        )
        answer = resp.choices[0].message.content.strip()
        print(f"[AI] SELECT Answer: {answer}")
        return answer
    except Exception as e:
        logging.error(f"GPT answer_select failed for: {q} – {e}")
        print(f"[AI] SELECT Answer ERROR: {e}")
        return options[0] if options else ""

# ─── SELECTORS & URLS ───────────────────────────────────────────────────────────
LOGIN_URL = "https://www.linkedin.com/login"
JOBS_URL  = "https://www.linkedin.com/jobs/search/?f_AL=true&keywords=Software%20Engineer%20Intern"

JOB_CARD   = "li[data-occludable-job-id], li.job-card-container--clickable"
APPLY_BTN  = "button[data-control-name='jobdetails_topcard_inapply']"
NEXT_BTN   = "button:has-text('Next')"
REVIEW_BTN = "button:has-text('Review')"
SUBMIT_BTN = "button:has-text('Submit')"
NOT_NOW    = "button:has-text('Not now')"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ─── MAIN ────────────────────────────────────────────────────────────────────────
def main():
    logging.info("🔍 Verifying OpenAI status…")
    verify_openai()

    results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        page    = browser.new_page()

        logging.info("▶ Logging into LinkedIn…")
        page.goto(LOGIN_URL)
        page.fill("input#username", EMAIL)
        page.fill("input#password", PASSWORD)
        page.click("button[type='submit']")
        try:
            page.wait_for_url("**/feed/**", timeout=10000)
        except PWTimeout:
            input("🔒 Complete LinkedIn checkpoint, then press ENTER…")
        page.wait_for_selector("div.feed-outlet", timeout=60000)
        logging.info("✅ Logged in.")

        logging.info("▶ Loading Easy Apply jobs…")
        for _ in range(3):
            try:
                page.goto(JOBS_URL, timeout=10000)
                break
            except PWTimeout:
                logging.warning("Retrying navigation…")
        page.wait_for_selector(JOB_CARD, timeout=30000)

        # Scroll until we have enough
        prev = 0
        while True:
            cards = page.locator(JOB_CARD)
            count = cards.count()
            if count >= MAX_APPLIES or count == prev:
                break
            prev = count
            cards.nth(count - 1).scroll_into_view_if_needed()
            human_pause(0.4, 0.9)
        total = min(count, MAX_APPLIES)
        logging.info(f"✅ Found {count} jobs; will apply to first {total}.")

        for i in range(total):
            card = page.locator(JOB_CARD).nth(i)
            # extract title & company
            title_el   = card.locator("h3")
            company_el = card.locator("h4")
            title      = title_el.first.inner_text().strip() if title_el.count() else "company title hidden"
            company    = company_el.first.inner_text().strip() if company_el.count() else "company name hidden"
            link = card.locator("a[href*='/jobs/view/']").first.get_attribute("href")
            card.click()
            human_pause(0.8, 1.5)

            # click Easy Apply
            try:
                page.wait_for_selector(APPLY_BTN, timeout=10000)
                page.locator(APPLY_BTN).click()
            except PWTimeout:
                btn = page.get_by_role("button", name="Easy Apply")
                if btn.is_visible():
                    btn.click()
                else:
                    logging.warning(f"'{title}' has no Easy Apply")
                    continue
            human_pause(1, 2)

            # application modal
            page.wait_for_selector("div[role='dialog']", timeout=15000)
            modal = page.locator("div[role='dialog']").first

            start = time.monotonic()
            while True:
                hdr = modal.locator("h2, h3")
                txt = hdr.first.inner_text().strip().lower() if hdr.count() else ""

                if any(k in txt for k in ["contact info", "resume"]):
                    modal.locator(NEXT_BTN).click()

                elif any(k in txt for k in ["questions", "education", "work", "additional"]):
                    secs = modal.locator("section.artdeco-modal__section")
                    for j in range(secs.count()):
                        sec = secs.nth(j)
                        print(f"[DEBUG] Section {j+1}/{secs.count()} text: {sec.inner_text().strip()}")
                        did_fill = False

                        # Handle all selects
                        for sel_idx in range(sec.locator("select").count()):
                            sel = sec.locator("select").nth(sel_idx)
                            label = sec.inner_text().strip()
                            opts = [o.inner_text().strip() for o in sel.locator("option").all() if o.get_attribute("value")]
                            print(f"[DEBUG] SELECT {sel_idx+1}: {label} options: {opts}")
                            ans = answer_select(label, opts)
                            print(f"[DEBUG] Filling SELECT with: {ans}")
                            sel.select_option(label=ans)
                            did_fill = True

                        # Handle all radio groups
                        for radio_idx in range(sec.locator("input[type=radio]").count()):
                            # Find the label for this radio
                            radio = sec.locator("input[type=radio]").nth(radio_idx)
                            labels = [lbl.inner_text().strip() for lbl in sec.locator("label").all() if lbl.inner_text().strip()]
                            label = sec.inner_text().strip()
                            print(f"[DEBUG] RADIO {radio_idx+1}: {label} options: {labels}")
                            choice = answer_select(label, labels)
                            print(f"[DEBUG] Clicking RADIO: {choice}")
                            lbl = sec.locator(f"label:has-text('{choice}')")
                            if lbl.count():
                                lbl.first.click()
                            else:
                                radio.check()
                            did_fill = True


                        # Handle all number inputs (input[type=number])
                        for num_idx in range(sec.locator("input[type=number]").count()):
                            num = sec.locator("input[type=number]").nth(num_idx)
                            label = sec.inner_text().strip()
                            print(f"[DEBUG] NUMBER {num_idx+1}: {label}")
                            # Always fill 0 for years of experience or if error message is present
                            fill_zero = False
                            if "year" in label.lower() and "experience" in label.lower():
                                fill_zero = True
                            # Check for error message
                            error_msg = num.evaluate("el => el.parentElement && el.parentElement.querySelector('.artdeco-inline-feedback__message') ? el.parentElement.querySelector('.artdeco-inline-feedback__message').innerText : ''")
                            if error_msg and "whole number" in error_msg:
                                print(f"[DEBUG] Detected error message for number input: {error_msg}")
                                fill_zero = True
                            if fill_zero:
                                ans = "0"
                            else:
                                ans = answer_text(label)
                            print(f"[DEBUG] Filling NUMBER with: {ans}")
                            num.fill(ans)
                            did_fill = True

                        # Handle all textareas and text inputs (input[type=text])
                        for txt_idx in range(sec.locator("textarea, input[type=text]").count()):
                            fld = sec.locator("textarea, input[type=text]").nth(txt_idx)
                            label = sec.inner_text().strip()
                            lw = label.lower()
                            print(f"[DEBUG] TEXT {txt_idx+1}: {label}")
                            mapped = False
                            # If the label asks for years of experience, or error message/placeholder indicates number, fill 0
                            fill_zero = False
                            if ("year" in lw and "experience" in lw) or ("years" in lw and "work" in lw):
                                fill_zero = True
                            # Check for error message
                            error_msg = fld.evaluate("el => el.parentElement && el.parentElement.querySelector('.artdeco-inline-feedback__message') ? el.parentElement.querySelector('.artdeco-inline-feedback__message').innerText : ''")
                            if error_msg and "whole number" in error_msg:
                                print(f"[DEBUG] Detected error message for text input: {error_msg}")
                                fill_zero = True
                            # Check for placeholder
                            placeholder = fld.get_attribute("placeholder") or ""
                            if "number" in placeholder.lower():
                                print(f"[DEBUG] Detected number placeholder: {placeholder}")
                                fill_zero = True
                            if fill_zero:
                                print(f"[DEBUG] Detected years/number input, filling 0")
                                fld.fill("0")
                                mapped = True
                                did_fill = True
                            else:
                                for key, val in ANSWER_MAP.items():
                                    if key in lw:
                                        print(f"[DEBUG] Using mapped answer for '{key}': {val}")
                                        fld.fill(val)
                                        mapped = True
                                        did_fill = True
                                        break
                            if not mapped:
                                ans = answer_text(label)
                                print(f"[DEBUG] Filling TEXT with: {ans}")
                                fld.fill(ans)
                                did_fill = True

                        if not did_fill:
                            print(f"[WARN] No fillable field detected in section {j+1}")

                    if modal.locator(NEXT_BTN).is_visible():
                        print("[DEBUG] Clicking NEXT after questions page.")
                        modal.locator(NEXT_BTN).click()
                    else:
                        print("[DEBUG] Clicking REVIEW after questions page.")
                        modal.locator(REVIEW_BTN).click()

                elif modal.locator(SUBMIT_BTN).is_visible():
                    modal.locator(SUBMIT_BTN).click()
                    break

                else:
                    if modal.locator(NEXT_BTN).is_visible():
                        modal.locator(NEXT_BTN).click()
                    else:
                        cancel = modal.locator("button:has-text('Cancel'), button:has-text('Dismiss')")
                        if cancel.count():
                            cancel.first.click()
                        else:
                            page.keyboard.press("Escape")
                        # Removed logging for unknown modal state as requested
                        break

                human_pause(0.7, 1.2)

            # dismiss follow-up
            if page.locator(NOT_NOW).count():
                page.locator(NOT_NOW).click()

            dur = f"{int(time.monotonic() - start)} sec"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            results.append({
                "Title":    title,
                "Company":  company,
                "Link":     link,
                "DateApplied": timestamp,
                "Runtime":  dur
            })
            logging.info(f"Applied #{i+1}: {title} at {company} ({dur})")
            human_pause(1.2, 2.0)

        # write results
        fieldnames = ["Title", "Company", "Link", "DateApplied", "Runtime"]
        exists = os.path.isfile(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            writer.writerows(results)

        logging.info(f"Saved {len(results)} records to {CSV_PATH}")
        browser.close()

if __name__ == "__main__":
    main()





























