import json
import unittest
from unittest.mock import patch

from music_assistant import LANGUAGES, _request_provider_intent, extract_music_intent


class MusicAssistantIntentTests(unittest.TestCase):
    def test_rule_parser_extracts_supported_request_fields(self):
        intent, provider = extract_music_intent(
            "Suggest relaxing Hindi songs for the evening",
            ["Arijit Singh"],
        )

        self.assertEqual(provider, "rules")
        self.assertEqual(intent["mood"], "relaxed")
        self.assertEqual(intent["language"], "Hindi")
        self.assertEqual(intent["context"], "evening")

    def test_follow_up_reuses_only_validated_previous_intent(self):
        intent, _provider = extract_music_intent(
            "More like that",
            ["Arijit Singh"],
            {
                "mood": "relaxed",
                "language": "Hindi",
                "genre": "invented",
                "artist": "Unknown Artist",
            },
        )

        self.assertEqual(intent["mood"], "relaxed")
        self.assertEqual(intent["language"], "Hindi")
        self.assertIsNone(intent["genre"])
        self.assertIsNone(intent["artist"])

    def test_artist_is_only_recognized_from_the_available_catalogue(self):
        with patch.dict("os.environ", {"AI_ASSISTANT_API_KEY": ""}):
            intent, _provider = extract_music_intent(
                "Play something by Arijit Singh", ["Arijit Singh"]
            )
        self.assertEqual(intent["artist"], "Arijit Singh")

    def test_provider_output_is_restricted_to_supported_intents(self):
        with (
            patch.dict("os.environ", {"AI_ASSISTANT_API_KEY": "test-key"}),
            patch(
                "music_assistant._request_provider_intent",
                return_value={
                    "mood": "relaxed",
                    "genre": "not-a-supported-genre",
                    "language": "Hindi",
                    "artist": "Invented Artist",
                    "context": "evening",
                },
            ),
        ):
            intent, provider = extract_music_intent(
                "I want music", ["Arijit Singh"]
            )

        self.assertEqual(provider, "ai")
        self.assertEqual(intent["mood"], "relaxed")
        self.assertEqual(intent["language"], "Hindi")
        self.assertEqual(intent["context"], "evening")
        self.assertIsNone(intent["genre"])
        self.assertIsNone(intent["artist"])

    def test_hinglish_requests_extract_mood_language_and_context(self):
        intent, provider = extract_music_intent(
            "Mujhe padhai ke liye sukoon wale Hindi gaane suggest karo",
            [],
        )

        self.assertEqual(provider, "rules")
        self.assertEqual(intent["mood"], "relaxed")
        self.assertEqual(intent["language"], "Hindi")
        self.assertEqual(intent["context"], "studying")

    def test_devanagari_requests_extract_mood_language_and_context(self):
        intent, provider = extract_music_intent(
            "मुझे शाम के लिए शांत हिंदी गाने चाहिए",
            [],
        )

        self.assertEqual(provider, "rules")
        self.assertEqual(intent["mood"], "relaxed")
        self.assertEqual(intent["language"], "Hindi")
        self.assertEqual(intent["context"], "evening")

    def test_native_script_regional_language_is_recognized(self):
        cases = {
            "ਪੰਜਾਬੀ": "Punjabi",
            "தமிழ்": "Tamil",
            "తెలుగు": "Telugu",
            "বাংলা": "Bengali",
            "मराठी": "Marathi",
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                intent, _provider = extract_music_intent(f"{phrase} music", [])
                self.assertEqual(intent["language"], expected)

    def test_provider_timeout_falls_back_to_local_intent_parsing(self):
        with (
            patch.dict("os.environ", {"AI_ASSISTANT_API_KEY": "test-key"}),
            patch("music_assistant.urllib.request.urlopen", side_effect=TimeoutError),
        ):
            intent, provider = extract_music_intent(
                "relaxing music for sleep", ["Arijit Singh"]
            )

        self.assertEqual(provider, "rules")
        self.assertEqual(intent["mood"], "relaxed")
        self.assertEqual(intent["context"], "sleep")

    def test_provider_request_uses_the_configured_api_key(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"choices": [{"message": {"content": '{"mood":"relaxed"}'}}]}
        ).encode("utf-8")
        with (
            patch.dict("os.environ", {"AI_ASSISTANT_API_KEY": "test-key"}),
            patch("music_assistant.urllib.request.urlopen", return_value=response) as urlopen,
        ):
            intent = _request_provider_intent("relaxing music")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(intent, {"mood": "relaxed"})

    def test_indian_regional_languages_are_supported_by_local_intent_parser(self):
        cases = {
            "Punjabi": "Recommend Punjabi music",
            "Tamil": "Play Tamil songs",
            "Telugu": "Find Telugu tracks",
            "Bengali": "Suggest Bengali songs",
            "Marathi": "Play Marathi music",
            "Gujarati": "Find Gujarati songs",
            "Malayalam": "Recommend Malayalam music",
            "Kannada": "Play Kannada tracks",
            "Urdu": "Suggest Urdu songs",
        }
        for language, message in cases.items():
            with self.subTest(language=language):
                intent, provider = extract_music_intent(message, [])
                self.assertEqual(provider, "rules")
                self.assertEqual(intent["language"], language)
        self.assertEqual(LANGUAGES["punjabi"], "Punjabi")



if __name__ == "__main__":
    unittest.main()
