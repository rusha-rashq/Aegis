# AEGIS — Setup Guide for New Collaborators

This guide walks you through setting up AEGIS from scratch on your machine. Follow every step in order — don't skip ahead.

---

## What You'll Need

- A Mac or Windows computer
- An internet connection
- Access to the GitHub repo (you should have received a collaborator invite via email — accept it first)
- ~30 minutes

---

## Step 1 — Install Python

### Check if Python is already installed
Open your Terminal (Mac) or Command Prompt (Windows) and run:
```bash
python3 --version
```

If you see something like `Python 3.11.x` you're good — skip to Step 2.

If you get an error, install Python:
- Go to **https://www.python.org/downloads/**
- Download the latest version (3.11 or higher)
- Run the installer
- **Windows users**: on the first screen of the installer, make sure to check **"Add Python to PATH"** before clicking Install

After installing, close and reopen your terminal, then run `python3 --version` again to confirm.

---

## Step 2 — Install Git

### Check if Git is already installed
```bash
git --version
```

If you see a version number, skip to Step 3.

If not:
- **Mac**: run `xcode-select --install` in your terminal and follow the prompts
- **Windows**: download from **https://git-scm.com/download/win** and install with default settings

---

## Step 3 — Clone the Repository

This downloads the project code to your computer.

```bash
cd Desktop
git clone https://github.com/YOUR_TEAMMATE_USERNAME/aegis.git
cd aegis
```

Replace `YOUR_TEAMMATE_USERNAME` with Rushali's actual GitHub username.

You should now see an `aegis` folder on your Desktop. Confirm by running:
```bash
ls
```

You should see files like `app.py`, `test_nova.py`, and an `agents/` folder.

---

## Step 4 — Create a Virtual Environment

A virtual environment keeps this project's dependencies isolated from the rest of your computer.

**Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python3 -m venv venv
venv\Scripts\activate
```

You'll know it worked when your terminal prompt changes to show `(venv)` at the beginning, like:
```
(venv) your-computer:aegis yourname$
```

> **Important**: Every time you open a new terminal window to work on this project, you need to run the activate command again. The `(venv)` prefix will disappear when you close your terminal.

---

## Step 5 — Install Dependencies

With your virtual environment active, run:
```bash
pip install boto3 yfinance requests python-dotenv streamlit
```

This installs all the libraries the project needs. It may take 1-2 minutes.

To confirm everything installed correctly:
```bash
pip list
```

You should see `boto3`, `yfinance`, `requests`, `python-dotenv`, and `streamlit` in the list.

---

## Step 6 — Set Up AWS Account and Credentials

AEGIS uses Amazon Nova (via AWS Bedrock) as its AI brain. You need an AWS account to access it.

### 6a — Create an AWS Account
1. Go to **https://aws.amazon.com** and click **"Create an AWS Account"**
2. Follow the signup steps — you'll need an email address and a credit card
3. AWS has a free tier and Bedrock usage at hackathon scale will cost very little (usually under $1)
4. Choose the **Basic (free) support plan** when asked

### 6b — Enable Amazon Nova in Bedrock
1. Log into the AWS Console at **https://console.aws.amazon.com**
2. In the search bar at the top, type **Bedrock** and click it
3. In the top-right corner, make sure your region is set to **us-east-1 (N. Virginia)**
4. In the left sidebar, find **"Foundation models"**
5. Find **Amazon Nova Pro** and click on it
6. If there's a button to request or enable access, click it — approval is usually instant

### 6c — Create an IAM User and Get API Keys
IAM (Identity and Access Management) lets you create credentials to access AWS from your code.

1. In the AWS Console search bar, type **IAM** and click it
2. Left sidebar → **Users** → click **"Create user"**
3. Username: `aegis-dev` → click Next
4. Select **"Attach policies directly"**
5. Search for `AmazonBedrockFullAccess` and check the box next to it → Next → Create user
6. Click on the newly created `aegis-dev` user
7. Click the **"Security credentials"** tab
8. Scroll to **"Access keys"** → click **"Create access key"**
9. Select **"Local code"** as the use case → Next → Create access key
10. You'll see an **Access key ID** and a **Secret access key**
11. **Copy both of these right now** — you will not be able to see the secret key again after you leave this page

---

## Step 7 — Get a NewsAPI Key

AEGIS uses NewsAPI to fetch live geopolitical headlines.

1. Go to **https://newsapi.org**
2. Click **"Get API Key"** and sign up for a free account
3. After signing up, your API key will be shown on your dashboard
4. Copy it

---

## Step 8 — Create Your `.env` File

The `.env` file stores your secret credentials locally. It is never uploaded to GitHub.

In the root `aegis/` folder, create a file called exactly `.env` (note the dot at the start):

**Mac — run this in your terminal:**
```bash
touch .env
open .env
```
This opens the file in TextEdit. Paste the following inside it:

**Windows — open Notepad and save the file as `.env` in the aegis folder.**

```
AWS_ACCESS_KEY_ID=PASTE_YOUR_ACCESS_KEY_HERE
AWS_SECRET_ACCESS_KEY=PASTE_YOUR_SECRET_KEY_HERE
AWS_DEFAULT_REGION=us-east-1
NEWS_API_KEY=PASTE_YOUR_NEWSAPI_KEY_HERE
```

Replace the placeholder values with your actual keys. Save and close the file.

> **Never share this file or commit it to GitHub.** It should already be listed in `.gitignore`.

---

## Step 9 — Test That Everything Works

### Test Nova connection
Run the test file:
```bash
python3 test_nova.py
```

You should see a message like:
```
Hello from AEGIS! It's great to connect with you...
```

If you see that, Nova is connected and working.

### Test the full agent pipeline
```bash
python3 -c "from agents.orchestrator import run; import json; print(json.dumps(run(), indent=2))"
```

You should see the 3 agents fire in sequence:
```
🔍 Running Commodity Agent...
🌍 Running Geo Agent...
⚡ Global Stress Index: XX/100
🛡️ Running Hedge Agent...
```

Followed by a large JSON output with commodity data, geopolitical analysis, and hedging strategies.

If both of these work, **you are fully set up.**

---

## Step 10 — Launch the Dashboard

```bash
streamlit run app.py
```

This opens the AEGIS dashboard in your browser at `http://localhost:8501`.

---

## Common Errors and Fixes

**`zsh: command not found: python`**
Use `python3` instead of `python` on Mac.

**`ModuleNotFoundError: No module named 'boto3'`**
Your virtual environment isn't active. Run `source venv/bin/activate` (Mac) or `venv\Scripts\activate` (Windows) first.

**`botocore.exceptions.NoCredentialsError`**
Your `.env` file is missing or the credentials are wrong. Double-check Step 8.

**`ValidationException: Malformed input request`**
Nova's message format is wrong. Make sure content is wrapped as an array: `[{"text": "your message"}]`

**`KeyError: articles`**
Your NewsAPI key is missing or incorrect in the `.env` file.

**`(venv)` disappeared from my terminal prompt**
You opened a new terminal window. Run the activate command again (Step 4).

---

## Daily Workflow

Every time you sit down to work on the project:

```bash
# 1. Navigate to the project folder
cd Desktop/aegis

# 2. Activate the virtual environment
source venv/bin/activate        # Mac
venv\Scripts\activate           # Windows

# 3. Pull the latest code from GitHub
git pull

# 4. Do your work, then push your changes
git add .
git commit -m "describe what you changed"
git push
```

---

## Project Structure

```
aegis/
├── agents/
│   ├── __init__.py          # Makes agents a Python package
│   ├── orchestrator.py      # Coordinates all agents, computes stress index
│   ├── commodity_agent.py   # Fetches market data, scores commodity stress
│   ├── geo_agent.py         # Fetches news, scores geopolitical risk
│   └── hedge_agent.py       # Generates hedging strategies
├── app.py                   # Streamlit dashboard UI
├── test_nova.py             # Quick test to verify Nova connection
├── .env                     # Your secret credentials (never commit this)
├── .gitignore               # Tells Git to ignore .env and venv/
└── README.md                # Project overview
```

---

## Need Help?

If you hit an error not listed above, copy the full error message and share it — the exact wording matters for debugging.
