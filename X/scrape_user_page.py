from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import os
import time
def scrape_tweets_and_save_html(max_results=10):
    """
    Scrapes tweets from a specific user's Twitter timeline using Selenium and saves the HTML.
    Args:
        max_results (int): Maximum number of tweets to scrape.
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service("/opt/homebrew/bin/chromedriver") 
    driver = webdriver.Chrome(service=service, options=options)
    try:
        url = f"https://x.com/TheFightAgent"
        driver.get(url)
        time.sleep(5)  
        html_content = driver.page_source
        os.makedirs('data', exist_ok=True)
        file_path = os.path.join('data', "TheFightAgent.html")
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(html_content)
        print(f"HTML content saved to {file_path}")
        tweets = []
        last_height = driver.execute_script("return document.body.scrollHeight")
        while len(tweets) < max_results:
            tweet_elements = driver.find_elements(By.XPATH, '//div[@data-testid="tweet"]')
            for tweet in tweet_elements:
                try:
                    text = tweet.find_element(By.XPATH, './/div[@lang]').text
                    if text not in tweets:  
                        tweets.append(text)
                        if len(tweets) >= max_results:
                            break
                except:
                    continue
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        return tweets
    finally:
        driver.quit()
scrape_tweets_and_save_html(max_results=5)
