import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date

import google.auth
from google.cloud import secretmanager
from google.oauth2 import service_account
from googleapiclient.discovery import build

def get_service_account_credentials() -> service_account.Credentials:
    _, project_id = google.auth.default()
    client = secretmanager.SecretManagerServiceClient()

    # Assumes the first secret is the service account JSON
    secret = list(client.list_secrets(parent=f"projects/{project_id}"))[0]
    payload = client.access_secret_version(
        name=f"{secret.name}/versions/latest"
    ).payload.data.decode("UTF-8")
    
    return service_account.Credentials.from_service_account_info(
        json.loads(payload),
        scopes=["https://www.googleapis.com/auth/calendar"]
    )

class PrayerTimesScraper:
    def convert_to_dt(self, time_str: str, format: str = "%H:%M") -> datetime:
        return datetime.combine(
            date.today(),
            datetime.strptime(time_str, format).time()
        ).isoformat()

    def get_LGM_prayer_times(self) -> dict[str, datetime]:
        soup = BeautifulSoup(
            requests.get("https://www.leedsgrandmosque.com/").text,
            "html.parser"
        )
        return {
            i.text.title():self.convert_to_dt(i.find_next_sibling().text)
            for i in soup.find_all(class_="prayer-name")
        }

    def get_MWHS_prayer_times(self) -> dict[str, datetime]:
        response = requests.get("https://docs.google.com/spreadsheets/d/e/2PACX-1vQCLtCIx0MMIyqrgmxcLHYYAAc8kWBeG4_pRNJyF3CRavIdmFjzqpyTrGHBM35wL238McSb5CT59VB0/pub?gid=1620370804&single=true&output=csv").text.splitlines()
        response2 = requests.get("https://docs.google.com/spreadsheets/d/e/2PACX-1vQCLtCIx0MMIyqrgmxcLHYYAAc8kWBeG4_pRNJyF3CRavIdmFjzqpyTrGHBM35wL238McSb5CT59VB0/pub?gid=1368650003&single=true&output=csv").text.splitlines()
        return {
            "Fajr": self.convert_to_dt(response[0]),
            "Shurooq": self.convert_to_dt(response2[1]),
            "Dhuhr": self.convert_to_dt(response[1]),
            "Asr": self.convert_to_dt(response[2]),
            "Maghrib": self.convert_to_dt(response[3]),
            "Isha": self.convert_to_dt(response[4]),
        }

    def get_Mcdougall_prayer_times(self) -> dict[str, datetime]:
        soup = BeautifulSoup(
            requests.get("https://www.manchesterisoc.com/").text,
            "html.parser"
        )
        return {
            i.text: self.convert_to_dt(i.next_sibling.text, "%I:%M %p")
            for i in soup.find_all(class_="prayerName")[:6]
        }
 
def create_calendar_id(service: service_account.Credentials, calendar_name: str, timezone: str = "Europe/London") -> str:
    calendar_id = service.calendars().insert(
        body={"summary": calendar_name, "timeZone": timezone}
    ).execute()["id"]

    service.acl().insert(
        calendarId=calendar_id,
        body={"role": "reader", "scope": {"type": "default"}}
    ).execute()

    print(f"✅ Created new public calendar: {calendar_id}")
    return calendar_id

def get_calendar_id(service: service_account.Credentials, calendar_name: str, timezone: str = "Europe/London") -> str:
    calendars = service.calendarList().list().execute().get("items", [])
    for calendar in calendars:
        if calendar_name in calendar["summary"]:
            return calendar["id"]
        
    return create_calendar_id(service, calendar_name, timezone)

def clear_calendar_events(service: service_account.Credentials, calendar_id: str) -> None:
    page_token = None
    while True:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMax=datetime.combine(date.today(), datetime.min.time()).isoformat() + "Z",
            singleEvents=True,
            pageToken=page_token
        ).execute()

        events = events_result.get("items", [])
        for event in events:
            service.events().delete(
                calendarId=calendar_id,
                eventId=event["id"]
            ).execute()
            print(f"❌ Deleted event: {event.get('summary')}")

        page_token = events_result.get("nextPageToken")
        if not page_token:
            break

def event_exists(service, calendar_id, prayer):
    return bool(service.events().list(
        calendarId=calendar_id,
        timeMin=datetime.combine(date.today(), datetime.min.time()).isoformat() + "Z",
        timeMax=datetime.combine(date.today(), datetime.max.time()).isoformat() + "Z",
        singleEvents=True,
        q=prayer
    ).execute().get("items", []))

def create_event(service, calendar_id, prayer, time):
    if event_exists(service, calendar_id, prayer):
        print(f"⏩ Skipping existing event: {prayer} at {time}")
        return
    
    event = {
        "summary": prayer,
        "start": {"dateTime": time, "timeZone": "Europe/London"},
        "end": {"dateTime": time, "timeZone": "Europe/London"},
    }
    created = service.events().insert(
        calendarId=calendar_id,
        body=event
    ).execute()

    print("Event created:", created.get('htmlLink'))

def share_calendar(service: service_account.Credentials, calendar_id: str, email: str) -> None:
    service.acl().insert(
        calendarId=calendar_id,
        body={"role": "reader", "scope": {"type": "user", "value": email}}
    ).execute()
    print(f"✅ Calendar is shared with {email}")

if __name__ == "__main__":
    scraper = PrayerTimesScraper()

    MASJIDS = {
        "Leeds Grand Mosque": scraper.get_LGM_prayer_times,
        "Muslim Welfare House Sheffield": scraper.get_MWHS_prayer_times,
        "Mcdougall Prayer Hall": scraper.get_Mcdougall_prayer_times,
    }

    service = build('calendar', 'v3', credentials=get_service_account_credentials())

    for masjid, get_prayer_times in MASJIDS.items():
        calendar_name = f"{masjid} Prayer Times"
        print(f"\n🕌 {calendar_name}\n")
        calendar_id = get_calendar_id(service, calendar_name)

        clear_calendar_events(service, calendar_id)
        prayer_times = get_prayer_times()
        for prayer, time in prayer_times.items():
            create_event(service, calendar_id, prayer, time)

        print(f"\n📅 View Live Calendar: https://calendar.google.com/calendar/embed?src={calendar_id}")
        print(f"🔗 Subscribe to Calendar: https://calendar.google.com/calendar/u/0/r?cid={calendar_id}")
        print(f"🔗 iCal Subscription (for non-Google calendars): https://calendar.google.com/calendar/ical/{calendar_id}/public/basic.ics")
