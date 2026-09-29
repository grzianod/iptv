import importlib.util
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "update_rai4", Path(__file__).resolve().parents[1] / "scripts" / "update_rai4.py"
)
rai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rai)


class PlaylistTests(unittest.TestCase):
    def test_all_relative_references_preserve_their_own_tokens(self):
        text = (
            '#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aac",'
            'URI="audio/live.m3u8?tk2=media&tend=2000000000"\n'
            '#EXT-X-I-FRAME-STREAM-INF:BANDWIDTH=100,URI="/iframe.m3u8?tk2=frame"\n'
            '#EXT-X-STREAM-INF:BANDWIDTH=200,AUDIO="aac"\n'
            'video/live.m3u8?tk2=video&tend=2000000000\n'
        )
        output = rai.rewrite_master(text, 'https://cdn.example/hls/master.m3u8?tk2=short')
        self.assertEqual(rai.references(output), [
            'https://cdn.example/hls/audio/live.m3u8?tk2=media&tend=2000000000',
            'https://cdn.example/iframe.m3u8?tk2=frame',
            'https://cdn.example/hls/video/live.m3u8?tk2=video&tend=2000000000',
        ])
        self.assertIn('AUDIO="aac"', output)
        self.assertNotIn('tk2=short', output)

    def test_html_and_media_playlist_are_rejected(self):
        with self.assertRaises(ValueError):
            rai.decode_playlist(b'<html>Access denied</html>')
        with self.assertRaises(ValueError):
            rai.rewrite_master('#EXTM3U\n#EXTINF:6\nsegment.ts\n', 'https://cdn.example/')

    def test_nearly_expired_token_rejected_before_network_requests(self):
        master = '#EXTM3U\nhttps://cdn.example/live.m3u8?tk2=x&tend=' + str(int(time.time()) + 60)
        with patch.object(rai, 'fetch') as fetch:
            with self.assertRaises(ValueError):
                rai.validate_master(master, 6)
            fetch.assert_not_called()

    def test_failed_validation_does_not_replace_last_good_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'rai4.m3u8'
            output.write_bytes(b'previous valid playlist')
            with patch.object(rai, 'fetch', return_value=(
                'https://cdn.example/master.m3u8',
                b'#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=200\nvideo.m3u8\n',
            )), patch.object(rai, 'validate_master', side_effect=ValueError('HTTP 403')):
                with self.assertRaises(ValueError):
                    rai.refresh(output)
            self.assertEqual(output.read_bytes(), b'previous valid playlist')


if __name__ == '__main__':
    unittest.main()
