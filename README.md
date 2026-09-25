# Xbox Gamertag Checker

A small Tkinter desktop tool that looks up a list of Xbox gamertags and records their public activity — last game played and how long ago — by reading the public profile pages on [xboxgamertag.com](https://www.xboxgamertag.com/).

It does not log in to Xbox Live, does not touch credentials of any kind, and only reads information that's already public on each profile's search page. If a profile is set to private, it's logged as private and nothing further is pulled.

## What it does

- Reads a list of gamertags from `tags.txt` (one per line)
- Opens each profile page in a headless Chrome browser via Selenium
- Records status as one of: public (with last game + last played, when shown), private, not found, or failed
- Writes results to `results.txt`, appending as it goes so you can stop and resume
- Has a simple GUI: add/edit tags, start/stop the run, view and search results, and filter results by how long an account has been inactive
- Randomizes delay between requests and restarts the browser periodically to avoid hammering the site

## Requirements

- Python 3.9+
- Google Chrome installed
- [ChromeDriver](https://googlechromedriver.chromium.org/downloads) matching your installed Chrome version, placed in the same folder as `xbox_checker.py` and named `chromedriver.exe` (or update `CHROMEDRIVER` in the script for your platform)

## Setup

```bash
git clone https://github.com/<your-username>/xbox-gamertag-checker.git
cd xbox-gamertag-checker
pip install -r requirements.txt
```

Then place a matching `chromedriver` binary next to `xbox_checker.py`.

## Usage

```bash
python xbox_checker.py
```

1. Go to the **Tags** tab and paste in gamertags, one per line, then save.
2. Hit **Start** to begin checking. Progress and log output show live.
3. Check the **Results** tab to view or search what's been found so far.
4. Use **Filter** to narrow results by inactivity window (e.g. accounts inactive 6 months to 2 years).

Progress is saved incrementally to `results.txt`, so if you stop partway through, restarting will skip gamertags already checked.

## Notes

- This scrapes a third-party public lookup site rather than an official Xbox API, so page structure changes on their end can break parsing — the XPath selectors may need updating over time.
- Be considerate with large tag lists. The delay/restart settings are there to keep request volume reasonable; check xboxgamertag.com's terms before running this against large lists.

## License

MIT — see [LICENSE](LICENSE).
