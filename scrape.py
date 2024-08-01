#!/usr/bin/env python3
import argparse
import datetime
import json
from playwright.sync_api import sync_playwright

DATE_FORMAT = '%Y-%m-%d'


def run(playwright, time_range, **kwargs):
    browser = playwright.chromium.launch(headless=False)

    if kwargs['start']:
        scrape_range(browser, kwargs['start'], kwargs['end'])
    else:
        scrape_page(browser, time_range)

def scrape_page(browser, time_range):
    page = browser.new_page()
    page.goto("https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US")
    page.wait_for_timeout(1000)
    range_selector = page.locator(f'#date-range-button-{time_range}')
    range_selector.click()
    button = page.locator('.highcharts-contextbutton')
    button.click()
    menu = page.get_by_text('Download CSV')
    with page.expect_download() as download_info:
        menu.click()
    download = download_info.value
    download.save_as(f'./chart-{time_range}.csv')
    browser.close()


def scrape_range(browser, start, end):
    end = datetime.datetime.now() if end == None else end
    page = browser.new_page()
    page.goto("https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US")
    page.wait_for_timeout(3000)
    range_selector = page.locator('#date-range-button-day')
    range_selector.click()
    page.wait_for_timeout(3000)

    for day in daterange(start, end):

        current_date_text = page.locator('#date-range-dialog-selector').text_content()
        current_date = datetime.datetime.strptime(current_date_text.split('-')[0].strip(), '%b %d, %Y')
        while current_date.strftime(DATE_FORMAT) != day.strftime(DATE_FORMAT):
            if current_date < day:
                page.locator('#date-time-picker-button-right-arrow').click()
            else:
                page.locator('#date-time-picker-button-left-arrow').click()
            page.wait_for_timeout(100)
            current_date_text = page.locator('#date-range-dialog-selector').text_content()
            current_date = datetime.datetime.strptime(current_date_text.split('-')[0].strip(), '%b %d, %Y')

        button = page.locator('.highcharts-contextbutton')
        button.click()
        menu = page.get_by_text('Download CSV')
        with page.expect_download() as download_info:
            menu.click()
        download = download_info.value
        download.save_as(f'./chart-{day.strftime('%Y-%m-%d')}.csv')
    browser.close()
    
def daterange(start_date, end_date):
    days = int((end_date - start_date).days) + 1
    for n in range(days):
        yield end_date - datetime.timedelta(n)

def parse_date(s):
    return datetime.datetime.strptime(s, '%Y-%m-%d')

parser = argparse.ArgumentParser(description="scrape dry bridge solar data")
parser.add_argument("-r", dest="range", choices=["day", "3day", "month", "year", "lifetime"], help="range for csv", default="3day")
parser.add_argument("-s", dest="start", type=parse_date, help="start date")
parser.add_argument("-e", dest="end", type=parse_date, help="end date")
args = parser.parse_args()

with sync_playwright() as playwright:
    run(playwright, args.range, start=args.start, end=args.end)
