# UI screenshots

Captured from the running DEMO_MODE=true app using isolated headless Microsoft Edge.
These depict synthetic data and simulated booking, not the historical example/ images
or a successful cloud run.

- [Group and shortlist](screenshots/01-group.png)
- [Itinerary](screenshots/02-itinerary.png)
- [Fixture sources](screenshots/03-sources.png)
- [Explicit confirmation](screenshots/04-confirmation.png)
- [Mobile layout](screenshots/05-mobile.png)

Desktop viewport: 1440 x 1100. Mobile: 390 x 844. Streamlit's internal scroller means
each PNG captures a viewport, not every chat item.

Regenerate with the demo server running:
python scripts/capture_ui.py --channel msedge

The integrated Browser reported no available session. Captures used the optional local
headless tool. No real signed-in profile was accessed.
