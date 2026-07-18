"""Cekirdek mantik testleri: ayristirici ve format secimi.

Calistirma:  .venv/bin/python -m pytest -q
(pytest yoksa) .venv/bin/python tests/test_core.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from youtube_downloader.core.downloader import Downloader, ResolvedEntry  # noqa: E402
from youtube_downloader.core.models import MediaFormat  # noqa: E402
from youtube_downloader.core.parser import parse_input  # noqa: E402


def test_format_aliases():
    assert MediaFormat.from_text("MP3") is MediaFormat.MP3
    assert MediaFormat.from_text(" ses ") is MediaFormat.MP3
    assert MediaFormat.from_text("video") is MediaFormat.VIDEO
    assert MediaFormat.from_text("mp4") is MediaFormat.VIDEO
    try:
        MediaFormat.from_text("flac")
        assert False, "bilinmeyen format ValueError vermeliydi"
    except ValueError:
        pass


def test_parse_explicit_and_default_format():
    text = (
        "https://youtu.be/aaa | mp3\n"
        "https://www.youtube.com/watch?v=bbb | video\n"
        "https://youtu.be/ccc\n"  # format yok -> varsayilan
    )
    result = parse_input(text, default_format=MediaFormat.VIDEO)
    assert not result.errors
    assert [j.media_format for j in result.jobs] == [
        MediaFormat.MP3,
        MediaFormat.VIDEO,
        MediaFormat.VIDEO,
    ]
    assert [j.line_number for j in result.jobs] == [1, 2, 3]


def test_parse_skips_comments_and_blanks():
    text = "# yorum\n\nhttps://youtu.be/x | mp3\n   \n"
    result = parse_input(text, default_format=MediaFormat.MP3)
    assert len(result.jobs) == 1
    assert result.jobs[0].line_number == 3


def test_parse_reports_errors():
    text = "not-a-url | mp3\nhttps://youtu.be/ok | flac\nhttps://youtu.be/fine"
    result = parse_input(text, default_format=MediaFormat.VIDEO)
    assert len(result.jobs) == 1  # sadece son satir gecerli
    assert len(result.errors) == 2
    assert result.errors[0].line_number == 1
    assert result.errors[1].line_number == 2


def test_alternate_separators():
    text = "https://youtu.be/a; mp3\nhttps://youtu.be/b, video"
    result = parse_input(text, default_format=MediaFormat.VIDEO)
    assert [j.media_format for j in result.jobs] == [MediaFormat.MP3, MediaFormat.VIDEO]


def test_video_format_selector_prefers_avc1_and_caps_height():
    dl = Downloader(output_dir="/tmp", max_height=1080)
    selector = dl._video_format_selector()
    assert "avc1" in selector  # H.264 onceligi
    assert "height<=1080" in selector  # kalite siniri
    assert "mp4a" in selector  # AAC ses onceligi


def test_video_opts_force_mp4_and_faststart():
    dl = Downloader(output_dir="/tmp")
    from youtube_downloader.core.models import DownloadJob

    job = DownloadJob(url="https://youtu.be/x", media_format=MediaFormat.VIDEO, line_number=1)
    opts = dl._build_opts(job, progress_hook=lambda d: None)
    assert opts["merge_output_format"] == "mp4"
    assert opts["postprocessor_args"]["merger"] == ["-movflags", "+faststart"]
    keys = [pp["key"] for pp in opts["postprocessors"]]
    assert "FFmpegVideoRemuxer" in keys


def test_mp3_opts_extract_with_metadata_and_thumbnail():
    dl = Downloader(output_dir="/tmp", mp3_quality="320")
    from youtube_downloader.core.models import DownloadJob

    job = DownloadJob(url="https://youtu.be/x", media_format=MediaFormat.MP3, line_number=1)
    opts = dl._build_opts(job, progress_hook=lambda d: None)
    assert opts["writethumbnail"] is True
    pps = {pp["key"]: pp for pp in opts["postprocessors"]}
    assert pps["FFmpegExtractAudio"]["preferredcodec"] == "mp3"
    assert pps["FFmpegExtractAudio"]["preferredquality"] == "320"
    assert "FFmpegMetadata" in pps
    assert "EmbedThumbnail" in pps


def test_cookies_option_set_when_browser_given():
    dl = Downloader(output_dir="/tmp", cookies_from_browser="firefox")
    opts = dl._base_opts(progress_hook=lambda d: None)
    assert opts["cookiesfrombrowser"] == ("firefox",)

    dl_off = Downloader(output_dir="/tmp", cookies_from_browser=None)
    assert "cookiesfrombrowser" not in dl_off._base_opts(progress_hook=lambda d: None)


def test_js_runtime_opts_injected_when_runtime_available(monkeypatch=None):
    # available_js_runtimes'i taklit et: bir ortam varmis gibi davran.
    import youtube_downloader.core.downloader as dl_mod

    original = dl_mod.available_js_runtimes
    dl_mod.available_js_runtimes = lambda: {"node": {"path": "/usr/bin/node"}}
    try:
        dl = Downloader(output_dir="/tmp")
        opts = dl._base_opts(progress_hook=lambda d: None)
        assert opts["js_runtimes"] == {"node": {"path": "/usr/bin/node"}}
        # Ortam yoksa anahtar hic eklenmemeli (yt-dlp varsayilanini bozmasin).
        dl_mod.available_js_runtimes = lambda: {}
        opts_off = dl._base_opts(progress_hook=lambda d: None)
        assert "js_runtimes" not in opts_off
    finally:
        dl_mod.available_js_runtimes = original


def test_entries_from_single_video_info():
    info = {"id": "abc123", "title": "Tek Video"}  # 'entries' yok -> tekil
    entries = Downloader._entries_from_info(info)
    assert len(entries) == 1
    assert entries[0].url == "https://www.youtube.com/watch?v=abc123"
    assert entries[0].title == "Tek Video"
    assert entries[0].playlist_title == ""


def test_entries_from_playlist_info():
    info = {
        "title": "Benim Listem",
        "entries": [
            {"id": "v1", "title": "Şarkı 1"},
            {"id": "v2", "title": "Şarkı 2"},
            None,  # silinmis/erisilemez oge atlanmali
            {"id": "v3", "title": "Şarkı 3"},
        ],
    }
    entries = Downloader._entries_from_info(info)
    assert [e.title for e in entries] == ["Şarkı 1", "Şarkı 2", "Şarkı 3"]
    assert all(e.playlist_title == "Benim Listem" for e in entries)
    assert entries[0].url == "https://www.youtube.com/watch?v=v1"


def test_entries_from_nested_playlist():
    info = {
        "title": "Üst Liste",
        "entries": [
            {"title": "Alt Liste", "entries": [{"id": "x"}, {"id": "y"}]},
            {"id": "z", "title": "Tekil"},
        ],
    }
    entries = Downloader._entries_from_info(info)
    assert [e.url.split("=")[-1] for e in entries] == ["x", "y", "z"]


def test_clean_video_url_prefers_id():
    assert Downloader._clean_video_url({"id": "ID1"}) == "https://www.youtube.com/watch?v=ID1"
    assert Downloader._clean_video_url({"webpage_url": "https://x/y"}) == "https://x/y"


if __name__ == "__main__":
    # pytest olmadan da calisabilsin.
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(funcs) - failed}/{len(funcs)} test geçti.")
    sys.exit(1 if failed else 0)
