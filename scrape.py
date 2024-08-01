#!/usr/bin/env python3
import argparse
import json
from playwright.sync_api import sync_playwright



def run(playwright, time_range):
    browser = playwright.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US")
    page.wait_for_timeout(1000)
    all_time = page.locator(f'#date-range-button-{time_range}')
    all_time.click()
    button = page.locator('.highcharts-contextbutton')
    button.click()
    menu = page.get_by_text('Download CSV')
    with page.expect_download() as download_info:
        menu.click()
    download = download_info.value
    download.save_as(f'./chart-{time_range}.csv')
    browser.close()

parser = argparse.ArgumentParser(description="scrape dry bridge solar data")
parser.add_argument("-r", dest="range", choices=["day", "3day", "month", "year", "lifetime"], help="range for csv", default="3day")
args = parser.parse_args()

with sync_playwright() as playwright:
    run(playwright, args.range)
