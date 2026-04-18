import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from abc import ABC, abstractmethod

import google.auth
from google.cloud import secretmanager
from google.oauth2 import service_account
from googleapiclient.discovery import build


# ----------------------------
# Google Service Account
# ----------------------------
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


# ----------------------------
# PrayerTimesScraper
# ----------------------------
class PrayerTimesScraper:
    def __init__(self, timeout: int = 10):
        self.session = requests.Session()
        self.timeout = timeout

    def get(self, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = self.session.get(url, timeout=self.timeout, headers=headers)
        response.raise_for_status()
        return response.text

    def convert_to_dt(self, time_str: str, format: str = "%H:%M") -> str:
        return datetime.combine(
            date.today(),
            datetime.strptime(time_str.strip(), format).time()
        ).isoformat()


# ----------------------------
# Masjid Base Class
# ----------------------------
class Masjid(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def get_prayer_times(self) -> dict[str, str]:
        pass


# ----------------------------
# Leeds Grand Mosque
# ----------------------------
class LeedsGrandMosque(Masjid):
    URL = "https://www.leedsgrandmosque.com/"

    def __init__(self, scraper: PrayerTimesScraper):
        super().__init__("Leeds Grand Mosque")
        self.scraper = scraper

    def get_prayer_times(self) -> dict[str, str]:
        html = self.scraper.get(self.URL)
        soup = BeautifulSoup(html, "html.parser")
        elements = soup.find_all(class_="prayer-name")
        if not elements:
            raise ValueError("Failed to scrape Leeds Grand Mosque prayer times")
        return {i.text.title(): self.scraper.convert_to_dt(i.find_next_sibling().text)
                for i in elements}


# ----------------------------
# Muslim Welfare House Sheffield
# ----------------------------
class MuslimWelfareHouseSheffield(Masjid):
    BASE_URL = (
        "https://docs.google.com/spreadsheets/d/e/"
        "2PACX-1vQCLtCIx0MMIyqrgmxcLHYYAAc8kWBeG4_pRNJyF3CRavIdmFjzqpyTrGHBM35wL238McSb5CT59VB0"
    )
    PRAYER_GID = "1620370804"
    SHUROOQ_GID = "1368650003"

    def __init__(self, scraper: PrayerTimesScraper):
        super().__init__("Muslim Welfare House Sheffield")
        self.scraper = scraper

    def get_prayer_times(self) -> dict[str, str]:
        prayers = self.scraper.get(
            f"{self.BASE_URL}/pub?gid={self.PRAYER_GID}&single=true&output=csv"
        ).splitlines()
        shurooq = self.scraper.get(
            f"{self.BASE_URL}/pub?gid={self.SHUROOQ_GID}&single=true&output=csv"
        ).splitlines()
        return {
            "Fajr": self.scraper.convert_to_dt(prayers[0]),
            "Shurooq": self.scraper.convert_to_dt(shurooq[1]),
            "Dhuhr": self.scraper.convert_to_dt(prayers[1]),
            "Asr": self.scraper.convert_to_dt(prayers[2]),
            "Maghrib": self.scraper.convert_to_dt(prayers[3]),
            "Isha": self.scraper.convert_to_dt(prayers[4]),
        }


# ----------------------------
# McDougall Prayer Hall
# ----------------------------
class McdougallPrayerHall(Masjid):
    URL = "https://www.manchesterisoc.com/"

    def __init__(self, scraper: PrayerTimesScraper):
        super().__init__("Mcdougall Prayer Hall")
        self.scraper = scraper

    def get_prayer_times(self) -> dict[str, str]:
        html = self.scraper.get(self.URL)
        soup = BeautifulSoup(html, "html.parser")
        elements = soup.find_all(class_="prayerName")[:6]
        if not elements:
            raise ValueError("Failed to scrape McDougall Prayer Hall prayer times")
        return {i.text: self.scraper.convert_to_dt(i.next_sibling.text, "%I:%M %p")
                for i in elements}


# ----------------------------
# Google Calendar Utilities
# ----------------------------
def create_calendar_id(service, calendar_name: str, timezone: str = "Europe/London") -> str:
    calendar_id = service.calendars().insert(
        body={"summary": calendar_name, "timeZone": timezone}
    ).execute()["id"]
    service.acl().insert(
        calendarId=calendar_id,
        body={"role": "reader", "scope": {"type": "default"}}
    ).execute()
    print(f"✅ Created new public calendar: {calendar_id}")
    return calendar_id


def get_calendar_id(service, calendar_name: str, timezone: str = "Europe/London") -> str:
    calendars = service.calendarList().list().execute().get("items", [])
    for calendar in calendars:
        if calendar_name == calendar["summary"]:
            return calendar["id"]
    return create_calendar_id(service, calendar_name, timezone)


def clear_calendar_events(service, calendar_id: str) -> None:
    page_token = None
    while True:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMax=datetime.combine(date.today(), datetime.min.time()).isoformat() + "Z",
            singleEvents=True,
            pageToken=page_token
        ).execute()
        for event in events_result.get("items", []):
            service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()
            print(f"❌ Deleted event: {event.get('summary')}")
        page_token = events_result.get("nextPageToken")
        if not page_token:
            break


def event_exists(service, calendar_id, prayer) -> bool:
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
    created = service.events().insert(calendarId=calendar_id, body=event).execute()
    print("Event created:", created.get("htmlLink"))


def share_calendar(service, calendar_id: str, email: str) -> None:
    service.acl().insert(
        calendarId=calendar_id,
        body={"role": "reader", "scope": {"type": "user", "value": email}}
    ).execute()
    print(f"✅ Calendar is shared with {email}")


# ----------------------------
# Main Execution
# ----------------------------
if __name__ == "__main__":
    scraper = PrayerTimesScraper()

    masjids = [
        LeedsGrandMosque(scraper),
        MuslimWelfareHouseSheffield(scraper),
        McdougallPrayerHall(scraper),
    ]

    service = build("calendar", "v3", credentials=get_service_account_credentials())

    for masjid in masjids:
        calendar_name = f"{masjid.name} Prayer Times"
        print(f"\n🕌 {calendar_name}\n")

        calendar_id = get_calendar_id(service, calendar_name)
        clear_calendar_events(service, calendar_id)

        try:
            prayer_times = masjid.get_prayer_times()
        except Exception as e:
            print(f"⚠️ Failed to fetch prayer times for {masjid.name}: {e}")
            continue

        for prayer, time in prayer_times.items():
            create_event(service, calendar_id, prayer, time)

        print(f"\n📅 View Live Calendar: https://calendar.google.com/calendar/embed?src={calendar_id}")
        print(f"🔗 Subscribe to Calendar: https://calendar.google.com/calendar/u/0/r?cid={calendar_id}")
        print(f"🔗 iCal Subscription: https://calendar.google.com/calendar/ical/{calendar_id}/public/basic.ics")
