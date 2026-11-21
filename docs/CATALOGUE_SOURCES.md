# Curated regional catalogue sources

The following additions use public music videos from official artist or music-label YouTube channels. Playback links are external provider links; MannKiDhun does not host or sublicense the recordings.

| Catalogue track | Language | Provider channel | Video |
|---|---|---|---|
| Lover — Diljit Dosanjh | Punjabi | Diljit Dosanjh (official artist channel) | https://www.youtube.com/watch?v=mH_LFkWxpI0 |
| Amar Mon Maney Na — Arindom | Bengali | SVF Music (verified channel) | https://www.youtube.com/watch?v=hVOd3u9R8uU |
| Jalso (Title Track) | Gujarati | Tips Gujarati (verified channel) | https://www.youtube.com/watch?v=N4Q3HSmpDMc |
| Samajavaragamana — Sid Sriram | Telugu | Aditya Music (verified channel) | https://www.youtube.com/watch?v=aFl7e6f4Qlg |

New tracks are added through the idempotent catalogue seed routine. Existing records, user feedback, and playlist relationships are not overwritten. Additional languages are recognised by the assistant intent parser, but no track is fabricated when the local catalogue has no verified match.

Before adding future records, verify the video on the artist/label's official channel, confirm the language and performer metadata, and use the exact video ID as the provider track ID.
