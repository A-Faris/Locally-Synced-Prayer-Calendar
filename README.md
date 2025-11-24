# Locally Synced Prayer Calendar

## Introduction

Muslims pray five times a day and the exact prayer times change daily based on location and astronomical calculations. Many people regularly check their local masjid’s website or timetable to stay updated. This project aims to simplify that daily routine by automatically collecting prayer times from local mosques and publishing them to a public Google Calendar. Anyone can subscribe to the calendar and instantly receive accurate, daily prayer times across all their devices.

## Features

🕒 Daily Synced Prayer Times – Automatically fetches updated prayer times from supported mosque websites and publishes them to their Google Calendar every day.

📅 Works With Any Calendar App – You can subscribe to these calendars with apps other than Google Calendar by adding the ICS file.

🔔 Prayer Notifications – Receive notifications on your devices when it’s time to pray.

## Subscribe to Your Mosque Prayer Calendar

| 🕌 Mosque | ➕ Add to Google Calendar | 🗺️ Location  | 📅 View Calendar |  ➕ Add to Other Calendar |
| ---------- | -------------------------- | ------------- | ---------------- | -------------------------- |
| <img src="https://www.leedsgrandmosque.com/favicon.ico" width="15"/> [Leeds Grand Mosque](https://www.leedsgrandmosque.com/) | [Subscribe](https://calendar.google.com/calendar/u/0/r?cid=80110e3124bdedfb7a61d57c33bfd69a3a2ee799c89ff186a3a5ee5850edf0bc@group.calendar.google.com) | Leeds | [View](https://calendar.google.com/calendar/embed?src=80110e3124bdedfb7a61d57c33bfd69a3a2ee799c89ff186a3a5ee5850edf0bc%40group.calendar.google.com&ctz=Europe%2FLondon) | [Download .ics](https://calendar.google.com/calendar/ical/80110e3124bdedfb7a61d57c33bfd69a3a2ee799c89ff186a3a5ee5850edf0bc%40group.calendar.google.com/public/basic.ics) |
| <img src="https://mwhs.org.uk/favicon.ico" width="15"/> [Muslim Welfare House Sheffield](https://www.mwhs.org.uk/)| [Subscribe](https://calendar.google.com/calendar/u/0/r?cid=2c41d01d3eba036595b9f9ffbc4d4df06b13c37c4da73962a06a0c3e920bb826@group.calendar.google.com) | Sheffield | [View](https://calendar.google.com/calendar/embed?src=2c41d01d3eba036595b9f9ffbc4d4df06b13c37c4da73962a06a0c3e920bb826@group.calendar.google.com) | [Download .ics](https://calendar.google.com/calendar/ical/2c41d01d3eba036595b9f9ffbc4d4df06b13c37c4da73962a06a0c3e920bb826@group.calendar.google.com/public/basic.ics) |
| <img src="https://www.manchesterisoc.com//favicon.ico" width="15"/> [Mcdougall Prayer Hall](https://www.manchesterisoc.com/) | [Subscribe](https://calendar.google.com/calendar/u/0/r?cid=c5bffac36dc5ee21ac0458788d7c82679f39a9d720fae79059c8ea1e496145fb@group.calendar.google.com) | Manchester | [View](https://calendar.google.com/calendar/embed?src=c5bffac36dc5ee21ac0458788d7c82679f39a9d720fae79059c8ea1e496145fb@group.calendar.google.com) | [Download .ics](https://calendar.google.com/calendar/ical/c5bffac36dc5ee21ac0458788d7c82679f39a9d720fae79059c8ea1e496145fb@group.calendar.google.com/public/basic.ics) |

## Architecture Diagram

<img width="2096" height="1303" alt="Prayer Times Architecture Diagram" src="https://github.com/user-attachments/assets/53c9bdbd-a169-41d2-9430-6cb95312d900" />

### Initial Setup (Terraform)

Terraform automatically provisions all the required infrastructure:
- Creates Artifact Registry repository
- Creates a Google Cloud Run Job to run the script
- Creates a Cloud Scheduler job to trigger the Cloud Run Job
- Creates a service account and stores its credentials in Secret Manager

### GitHub Actions CI/CD

On every push to the main branch, GitHub Action workflow:
- Builds Docker image
- Pushes the image to Artifact Registry
- Updates and runs Cloud Run Job with the new image

### Daily Run

Once deployed, everything runs automatically:
- Cloud Scheduler triggers the Cloud Run Job
- Cloud Run Job pulls the latest Docker image from Artifact Registry
- Cloud Run Job retrieves service account credentials from Secret Manager
- Prayer times are scraped from mosque websites
- Google Calendar Prayer Times are updated for each mosque

## 1. Install Required Tools

Download and install the following:
- Python: https://www.python.org/downloads/
- Git and Git Bash: https://git-scm.com/install/
- Docker Desktop: https://www.docker.com/products/docker-desktop/
- Google Cloud CLI: https://docs.cloud.google.com/sdk/docs/install-sdk
- Terraform: https://developer.hashicorp.com/terraform/install

Verify installation:

```bash
git --version
python --version
docker --version
gcloud --version
terraform --version
```

## 2. GitHub Repository

Create a GitHub repository: https://github.com/new

Link your local project to the GitHub repository:

```bash
git config --global user.email "your-email@example.com"
git init
git add .
git commit -m "Initial commit"
git remote add origin your-github-url
git branch -M main
git push -u origin main
git status
```

## 3. Create Virtual Environment 

Create and activate a virtual environment then install dependencies:

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
deactivate
```

## 4. Configuration

Create a `terraform.tfvars` file in the project root:

```hcl
project_id   = "your_project_id"
region       = "your_region"
sa_name      = "your_service_account_name"
secret_name  = "your_secret_name"
repo         = "your_repo_name"
image_name   = "your_image_name"
service_name = "your_service_name"
schedule     = "* * * * *"
timezone     = "your_timezone"
```

## 5. Authenticate Google Cloud CLI

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
gcloud config get-value project
```

## 6. Deploy Infrastructure via Terraform

```bash
terraform init
terraform plan
terraform apply
```

This will:
- Enable required Google Cloud APIs
- Create the service account and assign IAM roles
- Store service account credentials in Secret Manager
- Create Artifact Registry repository
- Create the Cloud Run job
- Schedule the job with Cloud Scheduler

## 7. Trigger Cloud Run Job Manually

```bash
bash run_job.sh
```

## 8. Run the Script Locally

```bash
source .venv/bin/activate
python main.py
```

This will:
- Scrape prayer times
- Create or update Google Calendar events
- Print subscription links
