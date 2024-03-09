# Import necessary libraries and modules
from flask import Flask, render_template, request, redirect, url_for, session
import requests
import nltk
from bs4 import BeautifulSoup
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.tag import pos_tag
from collections import Counter
import psycopg2
import json
import re
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from authlib.integrations.flask_client import OAuth

# Function to connect to PostgreSQL database
database_url = "dpg-cnmanvmv3ddc73fivf50-a.oregon-postgres.render.com"
database_name = "database_url_f9ed"
user = "database_url_f9ed_user"
password = "5Hee9QKXB0L5tJX2VRrPyl8AHdfDLL5k"
host = f"{database_url}"
port = "5432"  # Replace with your actual port if different
conn = psycopg2.connect(
    database=database_name,
    user=user,
    password=password,
    host=host,
    port=port
    )

# Define a cursor to execute PostgreSQL commands
cursor = conn.cursor()

# Create a table to store news data if it does not exist already
cursor.execute("""
    CREATE TABLE IF NOT EXISTS news_data (
        url TEXT,
        title varchar,
        newstype TEXT,
        count_stop INT,
        num_sentences INT,
        num_words INT,
        pos_tags JSON,
        reading_time_minutes FLOAT,
        summary varchar            
    )
""")

# Commit the changes to the database
conn.commit()

# Initialize the Flask application
app = Flask(__name__)

# Initialize OAuth for authentication
oauth = OAuth(app)

# Configure app settings
app.config['SECRET_KEY'] = "nikhilydv09"
app.config['GITHUB_CLIENT_ID'] = "27ac982ee8028eab3d61"
app.config['GITHUB_CLIENT_SECRET'] = "b77e9096c62c8c5a7044f73847c358ec4f127802"

# Register GitHub OAuth
github = oauth.register(
    name='github',
    client_id=app.config["GITHUB_CLIENT_ID"],
    client_secret=app.config["GITHUB_CLIENT_SECRET"],
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

# Define English stopwords
nltk.download("stopwords")
stopwords = nltk.corpus.stopwords.words('english')

# Function to clean text extracted from a URL
def clean_text(url):
    # Fetch HTML content from the URL
    response = requests.get(url)
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract title from the HTML
    titles = soup.title.text
    title = re.search(r'^(.*?)\|', titles).group(1).strip()

    # Extract news type from the title
    news_type = re.search(r'\|(.*?)\-', titles).group(1).strip()

    # Extract text from all <p> tags
    all_p_tags = soup.find('div', {'class': 'story_details'}).find_all('p')
    texts = ''
    for p_tag in all_p_tags:
        texts += p_tag.get_text() + ' '  # Add a space between paragraphs

    # Clean text to remove unwanted content and special characters
    cleaned_text = re.sub('.*[@#$].*[\.\?!](?=\s|$)', '', texts)

    # Count stopwords in the cleaned text
    count_stop = 0
    for word in cleaned_text:
        if word in stopwords:
            count_stop += 1

    # Tokenize sentences and words
    sentences = sent_tokenize(cleaned_text)
    num_sentences = len(sentences)
    words = word_tokenize(cleaned_text.lower())
    num_words = len(words)

    # Perform Part-of-Speech tagging
    pos_tags = pos_tag(words, tagset="universal")
    pos_counts = Counter(tag for word, tag in pos_tags)

    # Summarize the news content
    summary = summarize_news(cleaned_text)

    # Estimate reading time
    reading_time_minutes = estimate_reading_time(cleaned_text)

    return title, news_type, summary, cleaned_text, num_sentences, count_stop, num_words, pos_counts, reading_time_minutes

# Function to estimate reading time based on word count
def estimate_reading_time(text, words_per_minute=200):
    words = re.findall(r'\w+', text)
    word_count = len(words)
    reading_time_minutes = word_count / words_per_minute
    return reading_time_minutes

# Function to summarize news content
def summarize_news(text):
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary = summarizer(parser.document, 10)  # Get top 10 sentences as summary
    summary_text = " ".join(str(sentence) for sentence in summary)
    return summary_text


# Function to store URL, news text, and analysis summary in PostgreSQL
def store_data(url,title ,newstype ,num_sentences,num_words,count_stop,pos_tags,reading_time_minutes ,summary ):
    # Convert pos_tags to a dictionary and then serialize to JSON
    pos_tags = json.dumps(dict(pos_tags))
    cursor.execute("INSERT INTO news_data (url,title ,newstype ,num_sentences,num_words,count_stop,pos_tags,reading_time_minutes ,summary) VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s)", 
    (url,title ,newstype ,num_sentences,num_words,count_stop,pos_tags,reading_time_minutes ,summary))
    conn.commit()

# Route for the home page
@app.route('/')
def index():
    return render_template('index.html')

# Route for submitting URL
@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.form.get('submit') == 'abc':
        url = request.form.get('url')
        try:
            if 'https://indianexpress.com/article/' not in url:
                errors = 'PLEASE put the URL of Indian express Articles'
                return render_template('index.html', errors=errors)

            title, newstype, summary, cleaned_text, count_stop, num_sentences, num_words, pos_tags, reading_time_minutes = clean_text(url)
            store_data(url, title, newstype, num_sentences, num_words, count_stop, pos_tags, reading_time_minutes, summary)
            return render_template('index.html', summary=summary, cleaned_text=cleaned_text, num_sentences=num_sentences, num_words=num_words, pos_tags=pos_tags, title=title, count_stop=count_stop, newstype=newstype, reading_time_minutes=reading_time_minutes)
        
        # except Exception as e:
        #     errors = 'please input the correct URL'
        #     return render_template('index.html', errors=errors)
        except Exception as e:
            errors = 'An error occurred: {}'.format(str(e))
            return render_template('index.html', errors=errors)

    
    return render_template('index.html')

# Route for viewing history of submitted URLs
@app.route('/history')
def history():
    cursor.execute("SELECT * FROM news_data")
    data = cursor.fetchall()
    return render_template('history.html', data=data)

# Route for GitHub login
@app.route('/login/github')
def github_login():
    github = oauth.create_client('github')
    redirect_uri = url_for('github_authorize', _external=True)
    return github.authorize_redirect(redirect_uri)

# Route for GitHub authorization
@app.route('/login/github/authorize')
def github_authorize():
    github = oauth.create_client('github')
    token = github.authorize_access_token()
    session['github_token'] = token
    
    # Retrieve user info from GitHub
    resp = github.get('user')
    user_info = resp.json()
    github_username = user_info['login']
    
    # Check if the logged-in user is you
    if github_username == "nikhilyadav09":
        cursor.execute("SELECT * FROM news_data")
        data = cursor.fetchall()
        return render_template('history.html', data=data)
    else:
        # Redirect the user to the home page
        return redirect(url_for('index'))

# Route for GitHub logout
@app.route('/logout/github')
def github_logout():
    session.pop('github_token', None)
    return redirect(url_for('index'))

# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)
