from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time
from dotenv import load_dotenv
import os
import random

load_dotenv()
username = os.getenv("TWITTER_USERNAME")
password = os.getenv("TWITTER_PASSWORD")

# List of User-Agent strings for rotation
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"
]
# Randomly select a User-Agent
selected_user_agent = random.choice(user_agents)
options = Options()
options.headless = True  # Enable headless mode
options.add_argument(f"user-agent={selected_user_agent}")
service = Service('/opt/homebrew/bin/chromedriver')  # Update this path if needed
driver = webdriver.Chrome(service=service, options=options)

# driver = webdriver.Chrome()  
driver.get("https://twitter.com/login")
time.sleep(5)  

### Scrape User Page ###
username_field = driver.find_element(By.NAME, "text")
username_field.send_keys(username)
username_field.send_keys(Keys.RETURN)
time.sleep(5)  
password_field = driver.find_element(By.NAME, "password")
password_field.send_keys(password)
password_field.send_keys(Keys.RETURN)
time.sleep(5)  

driver.get("https://twitter.com/TheFightAgent")
time.sleep(5)  
html_content = driver.page_source
driver.quit()

# ### Parse for Tweets ###
with open("page.html", "w", encoding="utf-8") as f:
    f.write(html_content)
from bs4 import BeautifulSoup
def extract_tweets_from_html(file_path, output_path):
    """
    Extracts all tweets from a raw HTML file and saves them to a text file.
    Parameters:
        file_path (str): Path to the HTML file.
        output_path (str): Path to save the extracted tweets.
    Returns:
        list: A list of extracted tweets.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        html_content = file.read()
    soup = BeautifulSoup(html_content, "html.parser")
    tweets = []
    tweet_elements = soup.find_all("div", {"data-testid": "tweetText"})
    for tweet in tweet_elements:
        tweet_text = tweet.get_text(strip=True)
        if tweet_text:
            tweets.append(tweet_text)
    with open(output_path, "w", encoding="utf-8") as output_file:
        for tweet in tweets:
            output_file.write(tweet + "\n")
    return tweets

if __name__ == "__main__":
    input_file = "page.html"  
    output_file = "extracted_tweets.txt"  
    tweets = extract_tweets_from_html(input_file, output_file)
    print(f"Extracted {len(tweets)} tweets. Saved to {output_file}")
