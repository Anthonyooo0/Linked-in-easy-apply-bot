"""
Test script for field detection logic without hitting LinkedIn
"""

import time
from playwright.sync_api import sync_playwright, Locator
from typing import Optional, List, Tuple, Dict, Set

def is_field_empty(field) -> bool:
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

def get_modal_state(modal) -> str:
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

def process_form_fields_simple(section) -> bool:
    """Simplified version of form processing for testing"""
    did_fill = False
    
    try:
        texts = section.locator("textarea, input[type=text]")
        for txt_idx in range(texts.count()):
            fld = texts.nth(txt_idx)
            try:
                if not is_field_empty(fld):
                    current_value = fld.input_value()
                    print(f"[DEBUG] TEXT {txt_idx+1} already filled with: {current_value}")
                    continue
                
                print(f"[DEBUG] TEXT {txt_idx+1} is empty, would fill")
                did_fill = True
            except Exception as e:
                print(f"[WARN] Failed to process text {txt_idx+1}: {e}")
    except Exception as e:
        print(f"[WARN] Failed to process text fields: {e}")
    
    try:
        numbers = section.locator("input[type=number]")
        for num_idx in range(numbers.count()):
            num = numbers.nth(num_idx)
            try:
                if not is_field_empty(num):
                    current_value = num.input_value()
                    print(f"[DEBUG] NUMBER {num_idx+1} already filled with: {current_value}")
                    continue
                
                print(f"[DEBUG] NUMBER {num_idx+1} is empty, would fill")
                did_fill = True
            except Exception as e:
                print(f"[WARN] Failed to process number {num_idx+1}: {e}")
    except Exception as e:
        print(f"[WARN] Failed to process numbers: {e}")
    
    return did_fill

def create_test_html():
    """Create test HTML with various form field scenarios"""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Form Test</title></head>
    <body>
        <div id="modal" role="dialog">
            <h2>Test Questions</h2>
            <section>
                <label>Years of Experience:</label>
                <input type="number" id="experience" value="2">
                
                <label>Empty Experience Field:</label>
                <input type="number" id="empty-experience" value="">
                
                <label>Pre-filled Text:</label>
                <input type="text" id="prefilled" value="Already filled">
                
                <label>Empty Text:</label>
                <input type="text" id="empty-text" value="">
                
                <label>Authorization Status:</label>
                <select id="auth-select">
                    <option value="">Select...</option>
                    <option value="yes" selected>Yes</option>
                    <option value="no">No</option>
                </select>
                
                <label>Empty Select:</label>
                <select id="empty-select">
                    <option value="">Select...</option>
                    <option value="option1">Option 1</option>
                    <option value="option2">Option 2</option>
                </select>
                
                <label>Radio Group (pre-selected):</label>
                <input type="radio" name="radio1" value="yes" checked> Yes
                <input type="radio" name="radio1" value="no"> No
                
                <label>Radio Group (empty):</label>
                <input type="radio" name="radio2" value="yes"> Yes
                <input type="radio" name="radio2" value="no"> No
            </section>
            
            <button>Next</button>
        </div>
    </body>
    </html>
    """

def test_field_detection():
    """Test the field detection logic"""
    print("🧪 Testing field detection logic...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.set_content(create_test_html())
        
        
        print("\n📋 Testing individual field detection:")
        
        experience_field = page.locator("#experience")
        empty_experience = page.locator("#empty-experience")
        prefilled_text = page.locator("#prefilled")
        empty_text = page.locator("#empty-text")
        
        print(f"Pre-filled experience field (value='2'): Empty = {is_field_empty(experience_field)}")
        print(f"Empty experience field: Empty = {is_field_empty(empty_experience)}")
        print(f"Pre-filled text field: Empty = {is_field_empty(prefilled_text)}")
        print(f"Empty text field: Empty = {is_field_empty(empty_text)}")
        
        print(f"\nActual values:")
        print(f"Experience field value: '{experience_field.input_value()}'")
        print(f"Empty experience value: '{empty_experience.input_value()}'")
        print(f"Pre-filled text value: '{prefilled_text.input_value()}'")
        print(f"Empty text value: '{empty_text.input_value()}'")
        
        print("\n🔄 Testing form processing (should skip pre-filled fields):")
        section = page.locator("section")
        result = process_form_fields_simple(section)
        print(f"Form processing completed: {result}")
        
        print("\n✅ Field detection test completed!")
        browser.close()

def test_modal_state_detection():
    """Test modal state detection for loop prevention"""
    print("\n🔄 Testing modal state detection...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.set_content(create_test_html())
        
        
        modal = page.locator("#modal")
        state1 = get_modal_state(modal)
        print(f"Initial modal state: {state1}")
        
        page.evaluate("document.querySelector('h2').textContent = 'Different Title'")
        state2 = get_modal_state(modal)
        print(f"Modified modal state: {state2}")
        
        print(f"States are different: {state1 != state2}")
        
        browser.close()

if __name__ == "__main__":
    test_field_detection()
    test_modal_state_detection()
    print("\n🎉 All tests completed!")
