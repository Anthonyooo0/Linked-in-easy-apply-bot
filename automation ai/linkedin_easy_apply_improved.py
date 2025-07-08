"""
linkedin_easy_apply_improved.py

A robust, state-machine–driven LinkedIn Easy Apply bot using Playwright + OpenAI.
Enhanced with pre-filled field detection, better modal navigation, and timeout mechanisms.
"""

import os
import sys
import time
import random
import logging
import csv
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Set

from dotenv import load_dotenv
import openai
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, Locator, Page
from docx import Document

print("Enhanced LinkedIn Easy Apply Bot started")

load_dotenv()

EMAIL = os.getenv("LINKEDIN_EMAIL")
PASSWORD = os.getenv("LINKEDIN_PASSWORD")
RESUME_PATH = os.getenv("RESUME_PATH")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
MAX_APPLIES = int(os.getenv("MAX_APPLIES", "5"))
CSV_PATH = os.getenv("CSV_PATH", "applications.csv")
MODAL_TIMEOUT = int(os.getenv("MODAL_TIMEOUT", "300"))

print("ENV CHECK:")
print("EMAIL:", EMAIL)
print("PASSWORD:", "OK" if PASSWORD else "MISSING")
print("RESUME_PATH:", RESUME_PATH)
print("OPENAI_KEY:", "OK" if OPENAI_KEY else "MISSING")
print("MAX_APPLIES:", MAX_APPLIES)
print("CSV_PATH:", CSV_PATH)
print("MODAL_TIMEOUT:", MODAL_TIMEOUT)

if not EMAIL:
    raise ValueError("LINKEDIN_EMAIL missing in .env")
if not PASSWORD:
    raise ValueError("LINKEDIN_PASSWORD missing in .env")
if not OPENAI_KEY:
    raise ValueError("OPENAI_API_KEY missing in .env")
if not os.path.isfile(RESUME_PATH):
    raise FileNotFoundError(f"Resume not found at {RESUME_PATH}")

openai.api_key = OPENAI_KEY

def verify_openai():
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'ready' if you're working."}],
            timeout=10
        )
        answer = resp.choices[0].message.content.strip().lower()
        if "ready" in answer:
            logging.info("OpenAI is responding correctly.")
        else:
            logging.warning(f"Unexpected OpenAI response: {answer}")
    except Exception as e:
        logging.error(f"OpenAI check failed: {e}")
        raise

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
    "require sponsorship": "No",
    "relocate": "Yes",
    "minimum salary": "0",
    "start date": "Immediately",
    "years of experience": "0",
    "notice period": "Immediately",
    "willing to relocate": "Yes",
    "authorized to work": "Yes",
    "visa sponsorship": "No",
}

def human_pause(a=0.8, b=1.5):
    time.sleep(random.uniform(a, b))

def is_field_empty(field: Locator) -> bool:
    """Check if a field is empty or contains only whitespace"""
    try:
        current_value = field.input_value() or ""
        return current_value.strip() == ""
    except Exception:
        return True

def get_smart_fallback(question: str) -> str:
    """Provide context-aware fallback answers based on question content"""
    q_lower = question.lower()
    
    if any(word in q_lower for word in ["year", "experience", "salary", "number"]):
        return "0"
    elif any(word in q_lower for word in ["authorized", "eligible", "legal"]):
        return "Yes"
    elif any(word in q_lower for word in ["sponsor", "visa", "h1b"]):
        return "No"
    elif any(word in q_lower for word in ["relocate", "move", "willing"]):
        return "Yes"
    elif any(word in q_lower for word in ["start", "available", "notice"]):
        return "Immediately"
    elif any(word in q_lower for word in ["degree", "education", "university"]):
        return "Bachelor's Degree"
    elif any(word in q_lower for word in ["cover letter", "why", "interest"]):
        return "I am excited about this opportunity and believe my skills align well with the requirements."
    else:
        return "Yes"

def answer_text_with_retry(q: str, max_retries: int = 3) -> str:
    """Answer text questions with retry logic and smart fallbacks"""
    for attempt in range(max_retries):
        try:
            print(f"\n[AI] Answering TEXT Q (attempt {attempt + 1}): {q}")
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                temperature=0.5,
                max_tokens=80,
                timeout=15,
                messages=[{"role": "user", "content":
                    f"You are applying for a Software Engineer Intern position.\n"
                    f"Use my resume to answer concisely (max 50 words):\n\n{RESUME_TEXT}\n\nQuestion: {q}\nAnswer:"
                }]
            )
            answer = resp.choices[0].message.content.strip()
            print(f"[AI] TEXT Answer: {answer}")
            return answer
        except Exception as e:
            logging.warning(f"GPT attempt {attempt + 1} failed for: {q} – {e}")
            if attempt == max_retries - 1:
                fallback = get_smart_fallback(q)
                print(f"[AI] Using smart fallback: {fallback}")
                return fallback
            time.sleep(2 ** attempt)
    
    return get_smart_fallback(q)

def answer_select_with_retry(q: str, options: List[str], max_retries: int = 3) -> str:
    """Answer select questions with retry logic and smart fallbacks"""
    if not options:
        return ""
    
    for key, val in ANSWER_MAP.items():
        if key in q.lower():
            for option in options:
                if val.lower() in option.lower():
                    print(f"[AI] Using mapped answer for '{key}': {option}")
                    return option
    
    for attempt in range(max_retries):
        try:
            print(f"\n[AI] Answering SELECT Q (attempt {attempt + 1}): {q}\nOptions: {options}")
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                temperature=0.3,
                max_tokens=40,
                timeout=15,
                messages=[{"role": "user", "content":
                    f"You are applying for a Software Engineer Intern position.\n"
                    f"Use my resume to choose the best option:\n\n{RESUME_TEXT}\n\n"
                    f"Question: {q}\nOptions:\n" + "\n".join(f"- {o}" for o in options) + 
                    "\nReply exactly with the best option text."
                }]
            )
            answer = resp.choices[0].message.content.strip()
            
            for option in options:
                if answer.lower() in option.lower() or option.lower() in answer.lower():
                    print(f"[AI] SELECT Answer: {option}")
                    return option
            
            print(f"[AI] SELECT Answer (first option fallback): {options[0]}")
            return options[0]
            
        except Exception as e:
            logging.warning(f"GPT select attempt {attempt + 1} failed for: {q} – {e}")
            if attempt == max_retries - 1:
                fallback = get_smart_fallback(q)
                for option in options:
                    if fallback.lower() in option.lower():
                        print(f"[AI] Using smart fallback select: {option}")
                        return option
                print(f"[AI] Using first option fallback: {options[0]}")
                return options[0]
            time.sleep(2 ** attempt)
    
    return options[0]

def find_easy_apply_button(page: Page) -> Optional[Locator]:
    """Find Easy Apply button with multiple selector fallbacks"""
    selectors = [
        "button[data-test-job-apply-button]",
        "button[data-control-name='jobdetails_topcard_inapply']",
        
        "button:has-text('Easy Apply')",
        "button:has-text('Apply now')",
        "button:has-text('Apply')",
        
        "button[aria-label*='Easy Apply']",
        "button[aria-label*='Apply']",
        
        ".jobs-apply-button",
        ".jobs-s-apply",
        ".artdeco-button--primary:has-text('Easy Apply')",
        ".artdeco-button:has-text('Easy Apply')",
        
        "[data-test-id*='apply']",
        "[data-test*='apply']",
        "[data-automation-id*='apply']",
        
        "button[class*='apply']:has-text('Easy Apply')",
        "button[class*='apply']:has-text('Apply')",
        
        "button[type='button']:has-text('Easy Apply')",
        "a[role='button']:has-text('Easy Apply')"
    ]
    
    for i, selector in enumerate(selectors):
        try:
            print(f"[DEBUG] Trying selector {i+1}/{len(selectors)}: {selector}")
            btn = page.locator(selector).first
            if btn.count() > 0 and btn.is_visible():
                print(f"[DEBUG] ✅ Found Easy Apply button with selector: {selector}")
                return btn
            elif btn.count() > 0:
                print(f"[DEBUG] ❌ Selector found element but not visible: {selector}")
            else:
                print(f"[DEBUG] ❌ Selector found no elements: {selector}")
        except Exception as e:
            print(f"[DEBUG] ❌ Selector failed: {selector} - {str(e)}")
            continue
    
    print(f"[DEBUG] ⚠️ No Easy Apply button found with any of {len(selectors)} selectors")
    return None

def find_navigation_button(modal: Locator) -> Tuple[Optional[Locator], str]:
    """Find the appropriate navigation button with fallbacks"""
    button_configs = [
        ("submit", [
            "button:has-text('Submit')",
            "button[type='submit']",
            "button:has-text('Submit application')",
            "button[aria-label*='Submit']"
        ]),
        ("review", [
            "button:has-text('Review')",
            "button[aria-label*='Review']",
            "button:has-text('Review application')"
        ]),
        ("next", [
            "button:has-text('Next')",
            "button[aria-label*='Next']",
            "button:has-text('Continue')",
            "button:has-text('Save and continue')"
        ])
    ]
    
    for button_type, selectors in button_configs:
        for selector in selectors:
            try:
                btn = modal.locator(selector).first
                if btn.is_visible():
                    print(f"[DEBUG] Found {button_type} button with selector: {selector}")
                    return btn, button_type
            except Exception:
                continue
    
    return None, "none"

def get_modal_state(modal: Locator) -> str:
    """Get a string representation of the current modal state for loop detection"""
    try:
        header_text = ""
        headers = modal.locator("h1, h2, h3, h4")
        if headers.count() > 0:
            header_text = headers.first.inner_text().strip()
        
        button_text = ""
        buttons = modal.locator("button")
        if buttons.count() > 0:
            button_texts = []
            for i in range(min(buttons.count(), 5)):
                try:
                    btn_text = buttons.nth(i).inner_text().strip()
                    if btn_text:
                        button_texts.append(btn_text)
                except Exception:
                    continue
            button_text = "|".join(button_texts)
        
        return f"{header_text}::{button_text}"
    except Exception:
        return "unknown_state"

def process_form_fields(section: Locator) -> bool:
    """Process all form fields in a section with pre-filled detection"""
    did_fill = False
    
    try:
        selects = section.locator("select")
        for sel_idx in range(selects.count()):
            sel = selects.nth(sel_idx)
            try:
                current_value = sel.input_value() or ""
                if current_value.strip():
                    print(f"[DEBUG] SELECT {sel_idx+1} already filled with: {current_value}")
                    continue
                
                label = section.inner_text().strip()
                options = []
                option_elements = sel.locator("option")
                for opt_idx in range(option_elements.count()):
                    opt = option_elements.nth(opt_idx)
                    value = opt.get_attribute("value")
                    text = opt.inner_text().strip()
                    if value and text and text.lower() not in ["select", "choose", "pick"]:
                        options.append(text)
                
                if options:
                    print(f"[DEBUG] SELECT {sel_idx+1}: {label} options: {options}")
                    ans = answer_select_with_retry(label, options)
                    sel.select_option(label=ans)
                    did_fill = True
                    print(f"[DEBUG] Filled SELECT with: {ans}")
            except Exception as e:
                print(f"[WARN] Failed to process select {sel_idx+1}: {e}")
    
    except Exception as e:
        print(f"[WARN] Failed to process selects: {e}")
    
    try:
        radios = section.locator("input[type=radio]")
        processed_groups = set()
        
        for radio_idx in range(radios.count()):
            radio = radios.nth(radio_idx)
            try:
                name = radio.get_attribute("name")
                if name in processed_groups:
                    continue
                processed_groups.add(name)
                
                if radio.is_checked():
                    print(f"[DEBUG] RADIO group '{name}' already has selection")
                    continue
                
                group_radios = section.locator(f"input[type=radio][name='{name}']")
                labels = []
                for group_idx in range(group_radios.count()):
                    group_radio = group_radios.nth(group_idx)
                    try:
                        label_element = section.locator(f"label[for='{group_radio.get_attribute('id')}']")
                        if label_element.count() > 0:
                            labels.append(label_element.first.inner_text().strip())
                        else:
                            value = group_radio.get_attribute("value")
                            if value:
                                labels.append(value)
                    except Exception:
                        continue
                
                if labels:
                    question = section.inner_text().strip()
                    print(f"[DEBUG] RADIO group '{name}': {question} options: {labels}")
                    choice = answer_select_with_retry(question, labels)
                    
                    for group_idx in range(group_radios.count()):
                        group_radio = group_radios.nth(group_idx)
                        try:
                            label_element = section.locator(f"label[for='{group_radio.get_attribute('id')}']")
                            if label_element.count() > 0:
                                label_text = label_element.first.inner_text().strip()
                                if choice.lower() in label_text.lower():
                                    group_radio.check()
                                    did_fill = True
                                    print(f"[DEBUG] Selected RADIO: {label_text}")
                                    break
                        except Exception:
                            continue
            except Exception as e:
                print(f"[WARN] Failed to process radio {radio_idx+1}: {e}")
    
    except Exception as e:
        print(f"[WARN] Failed to process radios: {e}")
    
    try:
        numbers = section.locator("input[type=number]")
        for num_idx in range(numbers.count()):
            num = numbers.nth(num_idx)
            try:
                if not is_field_empty(num):
                    current_value = num.input_value()
                    print(f"[DEBUG] NUMBER {num_idx+1} already filled with: {current_value}")
                    continue
                
                label = section.inner_text().strip()
                print(f"[DEBUG] NUMBER {num_idx+1}: {label}")
                
                if any(word in label.lower() for word in ["year", "experience", "salary"]):
                    ans = "0"
                    print(f"[DEBUG] Using default '0' for number field")
                else:
                    ans = answer_text_with_retry(label)
                    if not ans.isdigit():
                        ans = "0"
                
                num.fill(ans)
                did_fill = True
                print(f"[DEBUG] Filled NUMBER with: {ans}")
            except Exception as e:
                print(f"[WARN] Failed to process number {num_idx+1}: {e}")
    
    except Exception as e:
        print(f"[WARN] Failed to process numbers: {e}")
    
    try:
        texts = section.locator("textarea, input[type=text]")
        for txt_idx in range(texts.count()):
            fld = texts.nth(txt_idx)
            try:
                if not is_field_empty(fld):
                    current_value = fld.input_value()
                    print(f"[DEBUG] TEXT {txt_idx+1} already filled with: {current_value}")
                    continue
                
                label = section.inner_text().strip()
                lw = label.lower()
                print(f"[DEBUG] TEXT {txt_idx+1}: {label}")
                
                mapped = False
                for key, val in ANSWER_MAP.items():
                    if key in lw:
                        print(f"[DEBUG] Using mapped answer for '{key}': {val}")
                        fld.fill(val)
                        mapped = True
                        did_fill = True
                        break
                
                if not mapped:
                    ans = answer_text_with_retry(label)
                    fld.fill(ans)
                    did_fill = True
                    print(f"[DEBUG] Filled TEXT with: {ans}")
            except Exception as e:
                print(f"[WARN] Failed to process text {txt_idx+1}: {e}")
    
    except Exception as e:
        print(f"[WARN] Failed to process text fields: {e}")
    
    return did_fill

def process_modal_with_timeout(page: Page, modal: Locator, max_duration: int = 300) -> bool:
    """Process modal with timeout and duplicate state detection"""
    start_time = time.monotonic()
    seen_states: Set[str] = set()
    loop_count = 0
    max_loops = 20
    
    while time.monotonic() - start_time < max_duration and loop_count < max_loops:
        loop_count += 1
        
        try:
            if not modal.is_visible():
                print("[DEBUG] Modal no longer visible, breaking")
                break
            
            current_state = get_modal_state(modal)
            if current_state in seen_states:
                logging.warning(f"Duplicate modal state detected: {current_state}")
                break
            seen_states.add(current_state)
            
            header_elements = modal.locator("h1, h2, h3, h4")
            header_text = ""
            if header_elements.count() > 0:
                header_text = header_elements.first.inner_text().strip().lower()
            
            print(f"[DEBUG] Modal state {loop_count}: {header_text}")
            
            if any(keyword in header_text for keyword in ["contact info", "resume", "cv"]):
                print("[DEBUG] Contact/Resume page - clicking next")
                nav_btn, btn_type = find_navigation_button(modal)
                if nav_btn and btn_type in ["next", "review"]:
                    nav_btn.click()
                    human_pause(1, 2)
                    continue
                else:
                    print("[DEBUG] No navigation button found on contact/resume page")
                    break
            
            elif any(keyword in header_text for keyword in ["question", "education", "work", "additional", "experience"]):
                print("[DEBUG] Questions page - processing fields")
                sections = modal.locator("section, div.form-section, .artdeco-modal__section")
                
                if sections.count() == 0:
                    sections = modal.locator("div").filter(has_text="")
                
                fields_processed = False
                for j in range(min(sections.count(), 10)):
                    section = sections.nth(j)
                    try:
                        section_text = section.inner_text().strip()
                        if len(section_text) > 10:
                            print(f"[DEBUG] Processing section {j+1}/{sections.count()}")
                            if process_form_fields(section):
                                fields_processed = True
                    except Exception as e:
                        print(f"[WARN] Failed to process section {j+1}: {e}")
                
                nav_btn, btn_type = find_navigation_button(modal)
                if nav_btn:
                    print(f"[DEBUG] Clicking {btn_type} after processing fields")
                    nav_btn.click()
                    human_pause(1, 2)
                    if btn_type == "submit":
                        return True
                else:
                    print("[DEBUG] No navigation button found after processing fields")
                    break
            
            else:
                nav_btn, btn_type = find_navigation_button(modal)
                if nav_btn:
                    print(f"[DEBUG] Found {btn_type} button on unknown page")
                    nav_btn.click()
                    human_pause(1, 2)
                    if btn_type == "submit":
                        return True
                else:
                    print("[DEBUG] No navigation options found, attempting to close modal")
                    cancel_selectors = [
                        "button:has-text('Cancel')",
                        "button:has-text('Dismiss')",
                        "button:has-text('Close')",
                        "button[aria-label*='Close']",
                        ".artdeco-modal__dismiss"
                    ]
                    
                    closed = False
                    for selector in cancel_selectors:
                        try:
                            cancel_btn = modal.locator(selector).first
                            if cancel_btn.is_visible():
                                cancel_btn.click()
                                closed = True
                                break
                        except Exception:
                            continue
                    
                    if not closed:
                        try:
                            page.keyboard.press("Escape")
                        except Exception:
                            pass
                    break
        
        except Exception as e:
            logging.error(f"Error in modal processing loop {loop_count}: {e}")
            break
    
    if loop_count >= max_loops:
        logging.warning(f"Modal processing exceeded max loops ({max_loops})")
    
    if time.monotonic() - start_time >= max_duration:
        logging.warning(f"Modal processing timed out after {max_duration} seconds")
    
    return False

LOGIN_URL = "https://www.linkedin.com/login"
JOBS_URL = "https://www.linkedin.com/jobs/search/?f_AL=true&keywords=Software%20Engineer%20Intern"

JOB_CARD = "li[data-occludable-job-id], li.job-card-container--clickable, .job-card-container, .jobs-search-results__list-item"
NOT_NOW = "button:has-text('Not now'), button:has-text('Skip'), button:has-text('Maybe later')"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    logging.info("🔍 Verifying OpenAI status…")
    verify_openai()

    results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        page = browser.new_page()

        logging.info("▶ Logging into LinkedIn…")
        page.goto(LOGIN_URL)
        page.fill("input#username", EMAIL)
        page.fill("input#password", PASSWORD)
        page.click("button[type='submit']")
        
        try:
            page.wait_for_url("**/feed/**", timeout=15000)
        except PWTimeout:
            print("🔒 Manual intervention may be required (checkpoint/captcha)")
            try:
                page.wait_for_url("**/feed/**", timeout=60000)
            except PWTimeout:
                input("🔒 Complete LinkedIn checkpoint manually, then press ENTER…")
        
        page.wait_for_selector("div.feed-outlet, .global-nav", timeout=60000)
        logging.info("✅ Logged in successfully.")

        logging.info("▶ Loading Easy Apply jobs…")
        for attempt in range(3):
            try:
                page.goto(JOBS_URL, timeout=15000)
                break
            except PWTimeout:
                logging.warning(f"Navigation attempt {attempt + 1} failed, retrying...")
                if attempt == 2:
                    raise
        
        page.wait_for_selector(JOB_CARD, timeout=30000)

        prev_count = 0
        scroll_attempts = 0
        max_scroll_attempts = 10
        
        while scroll_attempts < max_scroll_attempts:
            cards = page.locator(JOB_CARD)
            count = cards.count()
            
            if count >= MAX_APPLIES:
                break
            
            if count == prev_count:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
            
            prev_count = count
            
            if count > 0:
                cards.nth(count - 1).scroll_into_view_if_needed()
            else:
                page.evaluate("window.scrollBy(0, 1000)")
            
            human_pause(0.5, 1.0)
        
        total = min(count, MAX_APPLIES)
        logging.info(f"✅ Found {count} jobs; will apply to first {total}.")
        print(f"\n🤖 MANUAL EASY APPLY MODE")
        print(f"📝 The bot will navigate to each job and pause for you to manually click 'Easy Apply'")
        print(f"🔄 After you click, the bot will automatically fill out the application form")
        print(f"⚡ This bypasses any Easy Apply button detection issues!")
        print(f"\n" + "="*60)

        for i in range(total):
            try:
                cards = page.locator(JOB_CARD)
                if i >= cards.count():
                    logging.warning(f"Job card {i+1} no longer available")
                    continue
                
                card = cards.nth(i)
                
                title_selectors = ["h3", ".job-card-list__title", "[data-test-id*='title']"]
                company_selectors = ["h4", ".job-card-container__company-name", "[data-test-id*='company']"]
                
                title = "hidden title"
                for selector in title_selectors:
                    try:
                        title_el = card.locator(selector).first
                        if title_el.is_visible():
                            title = title_el.inner_text().strip()
                            break
                    except Exception:
                        continue
                
                company = "hidden company"
                for selector in company_selectors:
                    try:
                        company_el = card.locator(selector).first
                        if company_el.is_visible():
                            company = company_el.inner_text().strip()
                            break
                    except Exception:
                        continue
                
                link = ""
                try:
                    link_el = card.locator("a[href*='/jobs/view/']").first
                    link = link_el.get_attribute("href") or ""
                except Exception:
                    pass
                
                print(f"\n[JOB {i+1}] {title} at {company}")
                
                card.click()
                human_pause(1, 2)

                current_url = page.url
                print(f"📋 Job URL: {current_url}")
                print(f"👆 Please manually click the 'Easy Apply' button for this job")
                print(f"⏳ Press ENTER after you've clicked the Easy Apply button and the modal has opened...")
                
                input()
                
                print(f"[DEBUG] Waiting for Easy Apply modal to appear...")
                human_pause(1, 2)

                try:
                    print(f"[DEBUG] Looking for application modal...")
                    page.wait_for_selector("div[role='dialog'], .artdeco-modal", timeout=15000)
                    modal = page.locator("div[role='dialog'], .artdeco-modal").first
                    
                    if not modal.is_visible():
                        print(f"[DEBUG] Modal not visible, trying alternative selectors...")
                        modal_selectors = [
                            "div[role='dialog']",
                            ".artdeco-modal",
                            ".jobs-easy-apply-modal",
                            "[data-test-modal]"
                        ]
                        
                        modal_found = False
                        for selector in modal_selectors:
                            try:
                                modal = page.locator(selector).first
                                if modal.is_visible():
                                    print(f"[DEBUG] Found modal with selector: {selector}")
                                    modal_found = True
                                    break
                            except Exception:
                                continue
                        
                        if not modal_found:
                            print(f"❌ No application modal found for '{title}' - skipping")
                            print(f"💡 Make sure you clicked the Easy Apply button and the modal opened")
                            continue
                    
                    print(f"[DEBUG] ✅ Modal detected! Processing application for: {title}")
                    start_time = time.monotonic()
                    success = process_modal_with_timeout(modal, page)
                    
                    if success:
                        logging.info(f"✅ Successfully applied to '{title}'")
                    else:
                        logging.warning(f"⚠️ Application process incomplete for '{title}'")
                    
                    try:
                        not_now_buttons = page.locator(NOT_NOW)
                        if not_now_buttons.count() > 0:
                            not_now_buttons.first.click()
                            human_pause(0.5, 1)
                    except Exception:
                        pass
                    
                    duration = f"{int(time.monotonic() - start_time)} sec"
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    title_safe = title.replace(",", " -")
                    company_safe = company.replace(",", " -")

                    results.append({
                        "Title": title_safe,
                        "Company": company_safe,
                        "Link": link,
                        "DateApplied": timestamp,
                        "Runtime": duration,
                        "Status": "Success" if success else "Incomplete"
                    })
                    
                    logging.info(f"Applied #{i+1}: {title} at {company} ({duration})")
                    
                except Exception as e:
                    logging.error(f"Error processing application for '{title}': {e}")
                    continue
                
                human_pause(1.5, 2.5)
            
            except Exception as e:
                logging.error(f"Error processing job {i+1}: {e}")
                continue

        fieldnames = ["Title", "Company", "Link", "DateApplied", "Runtime", "Status"]
        file_exists = os.path.isfile(CSV_PATH)
        
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(results)

        logging.info(f"✅ Saved {len(results)} application records to {CSV_PATH}")
        browser.close()

if __name__ == "__main__":
    main()