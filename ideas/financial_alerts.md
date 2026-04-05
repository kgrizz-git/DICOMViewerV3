# Financial Alerts & Portfolio Summary System

## Overview
Automated system to pull positions from brokerage accounts (focusing on Schwab), generate daily/weekly summaries with changes in recommendations, and deliver via email and audio formats.

## Core Requirements
1. Retrieve watchlist/positions from Schwab (or other brokerages)
2. Generate daily email summaries with portfolio changes and recommendations
3. Generate custom audio roundups for weekly stock summaries
4. Track price changes, news, and analyst recommendations
5. Customizable alerts based on user-defined thresholds

---

## Email Summary Implementation

### Approach 1: Python Script with Email Services

**Technical Stack**:
- Data retrieval: `schwab-api`, `schwab-py`, or web scraping
- Email sending: `smtplib` (built-in) or third-party services
- Scheduling: `cron` (Linux/Mac) or Task Scheduler (Windows)
- Data sources: Yahoo Finance (`yfinance`), Alpha Vantage, Polygon.io

**Implementation Options**:

#### Option A: Gmail SMTP (Free)
```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Simple email sending via Gmail
smtp_server = "smtp.gmail.com"
port = 587
sender_email = "your-email@gmail.com"
# Use App Password (not regular password)
```

**Pros**:
- Free for personal use
- Simple setup
- Reliable delivery
- Native Python support

**Cons**:
- Gmail daily limit (500 emails/day)
- Requires App Password setup
- May flag as spam if not configured properly
- Less suitable for production/commercial use

**Cost**: Free  
**Ease of Implementation**: Easy (2-3 hours)  
**Customizability**: High (full control over email content and formatting)

#### Option B: SendGrid API
```python
import sendgrid
from sendgrid.helpers.mail import Mail

# Professional email API service
sg = sendgrid.SendGridAPIClient(api_key='YOUR_API_KEY')
```

**Pros**:
- Professional email delivery
- Better deliverability rates
- Email templates and analytics
- Higher sending limits
- Transactional email expertise

**Cons**:
- Requires API key setup
- Cost for higher volumes
- Learning curve for advanced features

**Cost**: 
- Free tier: 100 emails/day
- Essentials: $19.95/month (50,000 emails)
- Pro: $89.95/month (100,000 emails)

**Ease of Implementation**: Easy to Moderate (3-5 hours)  
**Customizability**: High (templates, dynamic content, HTML emails)

#### Option C: AWS SES (Simple Email Service)
```python
import boto3

# Enterprise-grade email service
ses_client = boto3.client('ses', region_name='us-east-1')
```

**Pros**:
- Very cost-effective at scale
- Excellent deliverability
- Integration with AWS ecosystem
- High sending limits

**Cons**:
- AWS account required
- Requires domain verification
- More complex setup
- Need to request production access

**Cost**: 
- $0.10 per 1,000 emails
- First 62,000 emails/month free if sent from EC2

**Ease of Implementation**: Moderate (5-8 hours including AWS setup)  
**Customizability**: High (full programmatic control)

#### Option D: Mailgun
**Pros**:
- Developer-friendly API
- Good documentation
- Reliable delivery
- Email validation features

**Cons**:
- Requires domain setup
- Limited free tier

**Cost**:
- Free: 5,000 emails/month for 3 months
- Foundation: $35/month (50,000 emails)

**Ease of Implementation**: Easy to Moderate (3-5 hours)  
**Customizability**: High

### Approach 2: Cloud Function/Lambda with Scheduled Execution

**Services**:
- AWS Lambda + EventBridge (scheduled triggers)
- Google Cloud Functions + Cloud Scheduler
- Azure Functions + Timer trigger

**Example with AWS Lambda**:
```python
import json
import boto3

def lambda_handler(event, context):
    # Fetch portfolio data
    # Generate summary
    # Send email via SES
    return {
        'statusCode': 200,
        'body': json.dumps('Email sent successfully')
    }
```

**Pros**:
- Serverless (no server maintenance)
- Automatic scaling
- Pay only for execution time
- Built-in scheduling
- High reliability

**Cons**:
- Requires cloud provider setup
- Cold start latency
- Debugging can be harder
- Vendor lock-in

**Cost**:
- AWS Lambda: Free tier 1M requests/month, then $0.20 per 1M requests
- Google Cloud Functions: 2M invocations/month free
- Extremely low cost for daily/weekly emails

**Ease of Implementation**: Moderate to Hard (8-16 hours for initial setup)  
**Customizability**: Very High (full programmatic control)

### Approach 3: No-Code/Low-Code Solutions

#### Zapier + Email
**Flow**: Schwab/Broker → Google Sheets → Zapier → Gmail/Email

**Pros**:
- No coding required
- Quick setup
- Visual workflow builder
- Many integrations

**Cons**:
- Limited customization
- Monthly subscription cost
- Dependent on third-party service
- May not support complex logic

**Cost**: $19.99-$69/month depending on task volume  
**Ease of Implementation**: Very Easy (1-2 hours)  
**Customizability**: Low to Moderate

#### IFTTT (If This Then That)
**Pros**:
- Simple automation
- Free tier available
- Mobile app integration

**Cons**:
- Very limited customization
- Basic conditional logic only
- Limited financial data integrations

**Cost**: Free tier available, Pro at $2.50/month  
**Ease of Implementation**: Very Easy (30 minutes - 1 hour)  
**Customizability**: Low

### Email Content Recommendations

**Essential Information**:
1. Current portfolio value and daily/weekly change ($ and %)
2. Individual position changes
3. Notable news affecting your holdings
4. Analyst rating changes
5. Price alerts (user-defined thresholds)
6. Upcoming earnings dates
7. Dividend announcements

**Example Email Structure**:
```
Subject: Daily Portfolio Summary - [Date] (+2.3% / +$1,234)

Portfolio Overview:
- Total Value: $53,234 (+2.3% / +$1,234)
- Day's Best: AAPL +5.2%
- Day's Worst: TSLA -3.1%

Position Updates:
[Table with ticker, shares, current price, day change, total value]

Alerts:
- MSFT crossed above $400 (your alert threshold)
- GOOGL earnings in 3 days

News Highlights:
- AAPL: New product announcement...
- TSLA: Production numbers released...

Analyst Changes:
- NVDA: Upgraded by Goldman Sachs to Buy
```

---

## Audio Summary Implementation

### Approach 1: Google NotebookLM (Recommended for Personal Use)

**Overview**: Google's AI-powered notebook that can generate audio overviews from documents.

**Implementation**:
1. Generate daily/weekly text summary of portfolio
2. Upload to NotebookLM as a source document
3. Use "Audio Overview" feature to generate podcast-style discussion
4. Download MP3 file or listen directly

**Pros**:
- Free (as of 2024-2026)
- Natural-sounding AI voices (two hosts discussing content)
- Engaging podcast-style format
- Handles complex financial information well
- No API integration needed
- Easy to use

**Cons**:
- Manual upload required (not fully automated)
- Limited customization of voice/style
- Dependent on Google service availability
- May have usage limits in future
- Generated audio can be longer than desired
- Cannot control specific talking points emphasis

**Cost**: Free (currently)  
**Ease of Implementation**: Very Easy (manual process, 5-10 minutes per summary)  
**Customizability**: Low (content-driven, limited voice control)  
**Quality**: Excellent (natural, conversational)

**Workflow**:
```
1. Run Python script to generate portfolio summary (markdown/text)
2. Open NotebookLM
3. Create new notebook or add to existing
4. Upload/paste the summary
5. Click "Generate Audio Overview"
6. Wait 3-5 minutes for generation
7. Download or listen to MP3
```

### Approach 2: Text-to-Speech APIs (Programmatic)

#### Option A: Google Cloud Text-to-Speech

```python
from google.cloud import texttospeech

client = texttospeech.TextToSpeechClient()

synthesis_input = texttospeech.SynthesisInput(text="Your portfolio summary...")
voice = texttospeech.VoiceSelectionParams(
    language_code="en-US",
    name="en-US-Neural2-A"  # High-quality neural voice
)
audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3
)

response = client.synthesize_speech(
    input=synthesis_input,
    voice=voice,
    audio_config=audio_config
)

with open("portfolio_summary.mp3", "wb") as out:
    out.write(response.audio_content)
```

**Pros**:
- Fully automated
- High-quality neural voices (WaveNet/Neural2)
- 220+ voices in 40+ languages
- SSML support for fine control (emphasis, pauses, pitch)
- Reliable Google infrastructure

**Cons**:
- Requires Google Cloud account
- API key management
- Costs for usage
- Less engaging than NotebookLM's conversation style

**Cost**:
- Standard voices: $4 per 1M characters
- WaveNet voices: $16 per 1M characters
- Neural2 voices: $16 per 1M characters
- Free tier: 0-4M characters/month (Standard voices)
- Typical 500-word summary ≈ 3,000 characters ≈ $0.05/summary (WaveNet)

**Ease of Implementation**: Moderate (4-6 hours including GCP setup)  
**Customizability**: High (voice selection, speed, pitch, SSML)

#### Option B: Amazon Polly

```python
import boto3

polly_client = boto3.client('polly', region_name='us-east-1')

response = polly_client.synthesize_speech(
    Text='Your portfolio summary...',
    OutputFormat='mp3',
    VoiceId='Joanna',  # Or Matthew, Salli, etc.
    Engine='neural'  # Neural voices sound better
)

with open('portfolio_summary.mp3', 'wb') as file:
    file.write(response['AudioStream'].read())
```

**Pros**:
- Fully automated
- Good voice quality (especially neural)
- AWS integration
- Long-form audio support
- Lexicon support for pronunciation

**Cons**:
- AWS account required
- Setup complexity
- Costs for neural voices

**Cost**:
- Standard voices: $4 per 1M characters
- Neural voices: $16 per 1M characters
- Free tier: 5M characters/month for 12 months (standard), 1M characters/month (neural)

**Ease of Implementation**: Moderate (4-6 hours including AWS setup)  
**Customizability**: High (SSML, voice selection, speed)

#### Option C: Azure Cognitive Services Speech

```python
import azure.cognitiveservices.speech as speechsdk

speech_config = speechsdk.SpeechConfig(
    subscription="YourSubscriptionKey",
    region="YourServiceRegion"
)
speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"

synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
result = synthesizer.speak_text_async("Your portfolio summary...").get()
```

**Pros**:
- High-quality neural voices
- Multilingual support
- Custom neural voice training available
- SSML support

**Cons**:
- Azure account required
- Similar pricing to competitors

**Cost**:
- Neural voices: $16 per 1M characters
- Free tier: 0.5M characters/month for neural

**Ease of Implementation**: Moderate (4-6 hours)  
**Customizability**: High

#### Option D: ElevenLabs (Premium Quality)

```python
from elevenlabs import generate, set_api_key

set_api_key("your-api-key")

audio = generate(
    text="Your portfolio summary...",
    voice="Adam",  # Very natural voice
    model="eleven_monolingual_v1"
)

with open('portfolio_summary.mp3', 'wb') as f:
    f.write(audio)
```

**Pros**:
- Exceptional voice quality (most realistic)
- Emotional expression and intonation
- Voice cloning capabilities
- Very natural-sounding
- Growing library of voices

**Cons**:
- More expensive than cloud providers
- Smaller company (less established)
- API rate limits on free tier
- Requires separate API management

**Cost**:
- Free: 10,000 characters/month
- Starter: $5/month (30,000 characters)
- Creator: $22/month (100,000 characters)
- Pro: $99/month (500,000 characters)

**Ease of Implementation**: Easy (2-3 hours)  
**Customizability**: Moderate (voice selection, stability, similarity sliders)  
**Quality**: Exceptional (best-in-class)

### Approach 3: Open-Source TTS Solutions

#### Option A: Coqui TTS (Free, Self-Hosted)

```python
from TTS.api import TTS

tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
tts.tts_to_file(
    text="Your portfolio summary...",
    file_path="output.wav"
)
```

**Pros**:
- Completely free
- No API costs
- Full control
- Privacy (runs locally)
- Open-source

**Cons**:
- Lower voice quality than commercial options
- Requires local compute resources
- Setup complexity
- Limited voice options
- May need GPU for reasonable speed

**Cost**: Free  
**Ease of Implementation**: Hard (8-12 hours for setup and optimization)  
**Customizability**: Very High (can train custom voices)

#### Option B: Piper TTS

**Pros**:
- Fast and lightweight
- Free and open-source
- Runs on CPU efficiently
- Good quality for free option

**Cons**:
- Still below commercial quality
- Limited documentation
- Smaller community

**Cost**: Free  
**Ease of Implementation**: Moderate to Hard (6-10 hours)  
**Customizability**: Moderate

### Approach 4: Hybrid Approach - AI-Generated Script + TTS

**Workflow**:
1. Use GPT-4, Claude, or Gemini to create engaging audio script
2. Format as conversational dialogue if desired
3. Feed to TTS service

**Example Prompt**:
```
Create a 2-minute engaging audio script summarizing this portfolio:
- Make it conversational and easy to understand
- Highlight the most important changes
- Include brief context for major moves
- End with a look-ahead to upcoming events

Portfolio data: [Your data here]
```

**Pros**:
- More engaging content than raw data
- Can adapt tone and style
- Emphasizes important information
- Can include analogies and explanations

**Cons**:
- Additional API cost for LLM
- Extra processing step
- Potential for AI hallucinations (verify facts)

**Cost**: LLM cost + TTS cost (typically $0.10-0.30 per summary)  
**Ease of Implementation**: Moderate (6-8 hours)  
**Customizability**: Very High

### Audio Delivery Methods

1. **Email Attachment**: Attach MP3 to daily email
2. **Cloud Storage**: Upload to Dropbox/Google Drive with shared link
3. **Podcast RSS Feed**: Create private podcast feed for phone apps
4. **Direct Phone Call**: Use Twilio to call and play audio
5. **Smart Speaker**: Integrate with Alexa/Google Home for voice briefing

---

## Obtaining Watchlist Data from Schwab

### Approach 1: Official Schwab API (Recommended)

**Charles Schwab API**: Schwab provides an official API for developers.

**Setup Process**:
1. Register for a developer account at https://developer.schwab.com
2. Create an application and obtain API credentials
3. Implement OAuth 2.0 authentication
4. Use API endpoints to retrieve account data

**API Capabilities**:
- Account positions and balances
- Order history
- Market data
- Trading (place orders)

**Python Implementation**:
```python
# Using schwab-py library (community-maintained)
import schwab

# Setup OAuth2 flow
client = schwab.client.Client(
    api_key='YOUR_API_KEY',
    app_secret='YOUR_APP_SECRET',
    callback_url='YOUR_CALLBACK_URL'
)

# Get account information
account_info = client.get_account(account_id)
positions = account_info['securitiesAccount']['positions']
```

**Pros**:
- Official, supported API
- Reliable and secure
- Real-time data
- Comprehensive account information
- No terms of service violations

**Cons**:
- OAuth setup complexity (not beginner-friendly)
- Developer account approval required
- API rate limits
- Learning curve for authentication flow

**Cost**: Free (for approved developers)  
**Ease of Implementation**: Moderate to Hard (10-16 hours for first-time setup)  
**Customizability**: High (full programmatic access)

### Approach 2: Web Scraping (Use with Caution)

**Tools**: Selenium, Playwright, or Puppeteer for browser automation

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

# Automated login and data extraction
driver = webdriver.Chrome()
driver.get("https://www.schwab.com")
# Login process
# Navigate to positions
# Extract data from page
```

**Pros**:
- No API approval needed
- Can access anything visible in web interface
- Works even without official API

**Cons**:
- Violates terms of service (risky)
- Brittle (breaks when website changes)
- Requires storing credentials
- Slower than API
- May trigger security alerts
- Account could be suspended
- Captcha challenges

**Cost**: Free (but risky)  
**Ease of Implementation**: Moderate (6-10 hours, but fragile)  
**Customizability**: Moderate  
**Risk**: High (not recommended)

### Approach 3: CSV Export + Manual Upload (Simple Start)

**Process**:
1. Log into Schwab web interface
2. Export positions to CSV file
3. Place CSV in specific folder monitored by script
4. Script reads CSV and generates reports

**Pros**:
- No API setup needed
- No terms of service violations
- Simple and reliable
- No authentication complexity

**Cons**:
- Manual export step required
- Not fully automated
- Requires regular user action
- Data could be stale

**Cost**: Free  
**Ease of Implementation**: Very Easy (1-2 hours)  
**Customizability**: Moderate  
**Best for**: Getting started or testing

### Approach 4: Plaid API (Account Aggregation)

**Overview**: Plaid provides a unified API to connect to thousands of financial institutions, including Schwab.

```python
import plaid
from plaid.api import plaid_api

configuration = plaid.Configuration(
    host=plaid.Environment.Production,
    api_key={
        'clientId': 'YOUR_CLIENT_ID',
        'secret': 'YOUR_SECRET',
    }
)

api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

# Get investment holdings
holdings_response = client.investments_holdings_get(
    plaid.InvestmentsHoldingsGetRequest(access_token=access_token)
)
```

**Pros**:
- Unified API for multiple brokerages
- Official partnership with financial institutions
- Good documentation
- Secure OAuth flow
- Support for multiple accounts

**Cons**:
- Requires Plaid account and approval
- Costs money for production use
- Investment data access requires higher tier
- Additional layer between you and Schwab
- May not have all Schwab-specific features

**Cost**:
- Development: Free (100 live Items)
- Launch: Pay-as-you-go ($0.60-0.99 per Item/month)
- Investments API: Additional cost

**Ease of Implementation**: Moderate (6-10 hours)  
**Customizability**: Moderate (limited to Plaid's API capabilities)

---

## Alternative Data Sources

### Broker Integrations

#### Interactive Brokers (IB)
**Library**: `ib_insync`

**Pros**:
- Excellent API support
- Real-time data included with account
- Professional-grade tools
- Well-documented

**Cons**:
- Requires IB account
- More complex platform
- Higher minimum balance for some features

#### Robinhood
**Library**: `robin_stocks`

**Pros**:
- Easy API (unofficial)
- Good for simple portfolios
- Free trading

**Cons**:
- Unofficial API (could break)
- Limited features vs. traditional brokers

#### TD Ameritrade
**Note**: Now part of Schwab - API being merged

**Library**: `tda-api` (Python)

**Pros**:
- Well-documented API
- Good market data access
- No minimum balance

#### Fidelity
**Status**: Limited API access, mostly institutional

**Options**:
- CSV export method (like Schwab approach)
- Plaid integration

### Market Data Sources (For Portfolio Analysis)

#### Option 1: Yahoo Finance (yfinance)
```python
import yfinance as yf

ticker = yf.Ticker("AAPL")
info = ticker.info
news = ticker.news
recommendations = ticker.recommendations
```

**Pros**:
- Free
- Easy to use
- Rich data (prices, news, recommendations)
- No API key needed

**Cons**:
- Unofficial (could break)
- Rate limits
- 15-minute delayed data (for real-time need subscription)

**Cost**: Free  
**Best for**: Personal projects, prototyping

#### Option 2: Alpha Vantage
```python
from alpha_vantage.timeseries import TimeSeries

ts = TimeSeries(key='YOUR_API_KEY')
data, meta = ts.get_quote_endpoint(symbol='AAPL')
```

**Pros**:
- Free tier available
- Official API
- Technical indicators included
- News sentiment analysis

**Cons**:
- Rate limits (5 calls/minute, 500/day on free tier)
- Need API key

**Cost**: Free tier available, premium from $49.99/month  
**Best for**: Moderate-scale personal projects

#### Option 3: Finnhub
```python
import finnhub
from datetime import datetime, timedelta

finnhub_client = finnhub.Client(api_key="YOUR_API_KEY")
# Get news from last 30 days
to_date = datetime.now().strftime('%Y-%m-%d')
from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
news = finnhub_client.company_news('AAPL', _from=from_date, to=to_date)
```

**Pros**:
- Comprehensive news data
- Earnings data
- Good free tier
- WebSocket for real-time

**Cons**:
- Rate limits on free tier
- Some features paid only

**Cost**: Free tier 60 calls/minute, paid from $0/month to enterprise  
**Best for**: News-focused alerts

#### Option 4: Polygon.io
**Pros**:
- High-quality data
- Real-time options
- Good API design

**Cons**:
- Paid only (after free tier)

**Cost**: Starting at $29/month  
**Best for**: Production applications

---

## Complete System Architecture Recommendations

### Recommended Approach for Beginners

**Phase 1: Manual/Semi-Automated (Week 1)**
1. Export Schwab positions to CSV manually
2. Python script reads CSV
3. Fetch price data from yfinance
4. Generate HTML email with summary
5. Send via Gmail SMTP
6. Generate text summary
7. Paste into NotebookLM for audio

**Tools**:
- Python + yfinance + smtplib
- Google NotebookLM
- CSV export from Schwab

**Cost**: $0/month  
**Time to implement**: 8-12 hours  
**Maintenance**: 2 minutes/day (manual CSV export)

### Recommended Approach for Intermediate

**Phase 2: Automated with Official API (Weeks 2-4)**
1. Register for Schwab API developer account
2. Implement OAuth authentication
3. Fetch positions via API
4. Enrich with market data (yfinance or Alpha Vantage)
5. Automated email via SendGrid
6. Automated audio via Google Cloud TTS
7. Schedule with cron or Windows Task Scheduler

**Tools**:
- schwab-py + yfinance
- SendGrid (free tier)
- Google Cloud TTS
- Cron/Task Scheduler

**Cost**: ~$0-5/month  
**Time to implement**: 20-30 hours  
**Maintenance**: None (fully automated)

### Recommended Approach for Advanced

**Phase 3: Cloud-Based Production System**
1. AWS Lambda function for data collection
2. Store data in DynamoDB or RDS
3. AWS SES for email delivery
4. Amazon Polly for audio generation
5. S3 for audio file storage
6. CloudWatch Events for scheduling
7. API Gateway for manual triggers via mobile app

**Tools**:
- AWS Lambda + EventBridge
- Schwab API
- AWS SES + Polly
- DynamoDB
- Optional: React Native mobile app

**Cost**: ~$10-20/month (scales with usage)  
**Time to implement**: 40-80 hours  
**Maintenance**: Low (cloud-managed)

---

## Comparison Matrix

| Approach | Cost/Month | Ease | Time to Build | Customization | Automation | Best For |
|----------|-----------|------|---------------|---------------|------------|----------|
| **Email: Gmail SMTP** | $0 | Easy | 2-3h | High | Full | Personal use |
| **Email: SendGrid** | $0-20 | Easy | 3-5h | High | Full | Small scale |
| **Email: AWS SES** | $0-5 | Moderate | 5-8h | Very High | Full | Scalable |
| **Email: Zapier** | $20-70 | Very Easy | 1-2h | Low | Full | Non-technical |
| **Audio: NotebookLM** | $0 | Very Easy | 0.5h | Low | Manual | Personal, quick start |
| **Audio: Google TTS** | $0-5 | Moderate | 4-6h | High | Full | Production |
| **Audio: ElevenLabs** | $5-22 | Easy | 2-3h | Moderate | Full | Premium quality |
| **Audio: Coqui (Open)** | $0 | Hard | 8-12h | Very High | Full | Self-hosted |
| **Data: Schwab API** | $0 | Moderate | 10-16h | High | Full | Recommended |
| **Data: CSV Export** | $0 | Very Easy | 1-2h | Moderate | Manual | Getting started |
| **Data: Plaid** | $20-50 | Moderate | 6-10h | Moderate | Full | Multi-broker |
| **Data: Web Scraping** | $0 | Moderate | 6-10h | Moderate | Fragile | Not recommended |

---

## Sample Implementation Timeline

### Weekend Project (8-10 hours)
- **Day 1 (4-5 hours)**:
  - Set up Python environment
  - Export CSV from Schwab
  - Write script to read CSV and fetch current prices
  - Generate basic email with HTML formatting
  - Test email sending via Gmail

- **Day 2 (4-5 hours)**:
  - Enhance email with news and recommendations
  - Generate text summary
  - Create audio using NotebookLM
  - Set up daily cron job
  - Test full workflow

**Result**: Functional system with manual CSV export, automated email, semi-automated audio

### Month-Long Project (30-40 hours)
- **Week 1**: CSV-based system (as above)
- **Week 2**: Register for Schwab API, implement OAuth, test API calls
- **Week 3**: Integrate Schwab API, remove CSV dependency
- **Week 4**: Add Google Cloud TTS for automated audio, polish and test

**Result**: Fully automated system

---

## Security Considerations

1. **API Keys**: Store in environment variables or secure key management service (AWS Secrets Manager, Azure Key Vault)
2. **OAuth Tokens**: Encrypt and store securely, implement token refresh
3. **Email Credentials**: Use app passwords, never commit to git
4. **Data Storage**: Encrypt sensitive portfolio data
5. **Access Control**: Limit access to systems with portfolio data
6. **Logging**: Log activities but not sensitive data
7. **Regular Updates**: Keep libraries and dependencies updated

---

## Maintenance and Monitoring

1. **Daily Checks**: Verify email delivery
2. **Weekly Reviews**: Check for API errors or data anomalies
3. **Monthly Updates**: Update dependencies and review costs
4. **Error Alerts**: Set up notifications for script failures
5. **Backup Strategy**: Regular backups of configuration and historical data

---

## Next Steps / Action Items

1. Choose your complexity level (beginner/intermediate/advanced)
2. Set up development environment
3. Register for necessary API accounts
4. Implement Phase 1 (basic functionality)
5. Test thoroughly with sample data
6. Deploy and schedule
7. Monitor and iterate

---

## References and Resources

**Schwab API**:
- https://developer.schwab.com
- schwab-py: https://github.com/itsjafer/schwab-py

**Email Services**:
- SendGrid: https://sendgrid.com
- AWS SES: https://aws.amazon.com/ses/
- Mailgun: https://www.mailgun.com

**Text-to-Speech**:
- Google Cloud TTS: https://cloud.google.com/text-to-speech
- Amazon Polly: https://aws.amazon.com/polly/
- ElevenLabs: https://elevenlabs.io
- Coqui TTS: https://github.com/coqui-ai/TTS

**Market Data**:
- yfinance: https://github.com/ranaroussi/yfinance
- Alpha Vantage: https://www.alphavantage.co
- Polygon.io: https://polygon.io
- Finnhub: https://finnhub.io

**Additional Tools**:
- Google NotebookLM: https://notebooklm.google.com
- Plaid: https://plaid.com