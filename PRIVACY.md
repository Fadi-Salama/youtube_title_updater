# Privacy Policy — Saint Mary Titlebot

This application is a personal automation tool used solely by its owner to
manage YouTube live broadcasts (creating, renaming, and starting/stopping
broadcasts) for a single YouTube channel belonging to Saint Mary and
Archangel Michael Coptic Orthodox Church.

## Data collected

This application does not collect, store, or share any personal data
belonging to other users. It only interacts with the YouTube account of
its owner via the YouTube Data API, using the `youtube.force-ssl` scope to:

- Create, list, and update live broadcasts and their titles
- Bind broadcasts to an existing live stream
- Transition broadcasts between lifecycle states (e.g. testing, live, complete)

## Data storage

OAuth credentials obtained through Google's consent flow are stored locally
on the owner's machine (`token.pickle`) and are never transmitted to any
third party. No data collected from the YouTube API is shared with, sold
to, or processed by any external service other than Google's own APIs.

## Contact

Questions about this tool can be directed to the app's listed support
contact in the Google Cloud OAuth consent screen configuration.
