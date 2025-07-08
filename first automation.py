import os                                    # 1. Gives us functions to interact with the operating system (file paths, existence checks)
import time                                  # 2. Lets us pause execution (sleep) so pages have time to load
import csv                                   # 3. Built-in module for reading/writing CSV files
import pandas as pd                          # 4. Third-party library for data structures (we’ll use it for Excel)
from selenium import webdriver               # 5. Selenium’s main module: controls the browser
from selenium.webdriver.common.by import By  # 6. Locator strategies (CSS_SELECTOR, XPATH, etc.)
from selenium.webdriver.chrome.options import Options  # 7. To set Chrome’s startup flags (e.g. headless)

# ——— Configuration ———
QUERY      = "Manufacturing Engineer Intern"  # 8. The job title you want to search
LOCATION   = "Newark, NJ"                     # 9. The location filter
NUM_JOBS   = 10                               # 10. How many listings to scrape per run
CSV_FILE   = "jobs.csv"                       # 11. Name of the CSV output file
EXCEL_FILE = "jobs.xlsx"                      # 12. Name of the Excel output file

def scrape_jobs():
    """Launches a headless browser, performs the search, and returns a list of job dicts."""
    # ——— Launch Chrome in headless mode ———
    chrome_opts = Options()                    # 13. Create a Chrome options object
    chrome_opts.add_argument("--headless")     # 14. Tell Chrome not to open a visible window
    driver = webdriver.Chrome(options=chrome_opts)
                                               # 15. Start a Chrome session with those options

    # ——— Build and visit the search URL ———
    url = (
        "https://www.indeed.com/jobs"
        f"?q={QUERY.replace(' ', '+')}"
        f"&l={LOCATION.replace(' ', '+')}"
    )                                          # 16. Indeed expects spaces as “+” in its query params
    driver.get(url)                            # 17. Navigate the browser to that URL
    time.sleep(2)                              # 18. Wait 2 seconds for all elements to render

    # ——— Find the job cards on the page ———
    cards = driver.find_elements(
        By.CSS_SELECTOR, "div.jobsearch-SerpJobCard"
    )[:NUM_JOBS]                               # 19. Grab the first NUM_JOBS matching elements

    rows = []                                  # 20. Prepare an empty list to hold our output dicts
    for card in cards:                         # 21. Loop over each job card element
        title_elem = card.find_element(By.CSS_SELECTOR, "h2.title")
                                               # 22. Inside that card, find the <h2 class="title"> element
        company_elem = card.find_element(By.CSS_SELECTOR, ".company")
                                               # 23. Find the element with class “company”
        location_elem = card.find_element(By.CSS_SELECTOR, ".location")
                                               # 24. Find the element with class “location”
        link = title_elem.find_element(By.TAG_NAME, "a").get_attribute("href")
                                               # 25. The <a> inside the title holds the job link in its href

        # 26. Build a simple dict with the fields we care about
        rows.append({
            "Title":    title_elem.text.strip(),
            "Company":  company_elem.text.strip(),
            "Location": location_elem.text.strip(),
            "Link":     link
        })

    driver.quit()                              # 27. Close the browser session
    return rows                                # 28. Return our list of job dicts

def save_results(rows):
    """
    Takes a list of dicts (Title, Company, Location, Link) and:
      1) Appends them to an Excel file (jobs.xlsx), creating it if needed.
      2) Also appends them to a CSV (jobs.csv).
    """
    # ——— Convert to a pandas DataFrame ———
    df_new = pd.DataFrame(rows)                # 29. Turn our list of dicts into a 2D table

    # ——— Excel handling ———
    if os.path.exists(EXCEL_FILE):             # 30. If jobs.xlsx already exists...
        df_existing = pd.read_excel(EXCEL_FILE, engine="openpyxl")
                                               # 31. …read it in…
        df_all = pd.concat([df_existing, df_new], ignore_index=True)
                                               # 32. …and stack the old + new data together
    else:
        df_all = df_new                        # 33. Otherwise, this run’s data is all we have

    df_all.to_excel(EXCEL_FILE, index=False, engine="openpyxl")
                                               # 34. Write (or overwrite) jobs.xlsx with df_all
    print(f"Saved {len(df_new)} jobs → {EXCEL_FILE}")  # 35. Quick console confirmation

    # ——— CSV fallback ———
    write_header = not os.path.exists(CSV_FILE)  # 36. If jobs.csv doesn’t exist yet, we need a header
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        df_new.to_csv(f, index=False, header=write_header)
                                               # 37. Append new rows; write header if file was missing
    print(f"Also appended to {CSV_FILE}")       # 38. Another console message

if __name__ == "__main__":
    # 39. Standard Python entry point: only runs when you execute this file directly
    jobs = scrape_jobs()                       # 40. Call our scraper; get back a list of dicts
    save_results(jobs)                         # 41. Persist them to Excel and CSV

