#!/usr/bin/env python3
import json
from playwright.sync_api import sync_playwright



def run(playwright):
    browser = playwright.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US")
    button = page.locator('.highcharts-contextbutton')
    button.click()
    menu = page.get_by_text('Download CSV')
    with page.expect_download() as download_info:
        menu.click()
    download = download_info.value
    download.save_as('./chart.csv')
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
