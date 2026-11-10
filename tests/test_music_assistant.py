import json
import unittest
from unittest.mock import patch

from music_assistant import _request_provider_intent, extract_music_intent


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


if __name__ == "__main__":
    unittest.main()
