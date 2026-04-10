"""
Android Media API → HarmonyOS AVSession / AVPlayer 转换

覆盖范围：
  - MediaSessionCompat       → avSession.AVSession
  - MediaBrowserServiceCompat→ ServiceExtensionAbility + AVSessionManager stub
  - MediaBrowserCompat       → avSession.AVSessionManager (client)
  - MediaControllerCompat    → avSession.AVSessionController
  - PlaybackStateCompat      → avSession.AVPlaybackState / PLAYBACK_STATE_*
  - MediaMetadataCompat      → avSession.AVMediaDescription
  - ExoPlayer / SimpleExoPlayer → media.AVPlayer
  - Player.EventListener     → AVPlayer.on('stateChange', ...)
  - AudioFocusRequest        → audio.AudioCapturer focus API
  - PlayerNotificationManager→ HarmonyOS Notification (stub)
  - CastPlayer               → TODO stub (无 HarmonyOS 等价)
"""
import re
from typing import Optional


# ── 是否需要转换 ──────────────────────────────────────────────────────────────

_MEDIA_INDICATORS = (
    "MediaSession", "ExoPlayer", "SimpleExoPlayer",
    "PlaybackStateCompat", "MediaBrowserServiceCompat", "MediaBrowserCompat",
    "MediaControllerCompat", "MediaMetadataCompat", "AudioFocusRequest",
    "PlayerNotificationManager", "MediaSessionConnector",
)


def is_media_file(code: str) -> bool:
    return any(ind in code for ind in _MEDIA_INDICATORS)


# ── import 替换表 ─────────────────────────────────────────────────────────────

_IMPORT_MAP = [
    # ExoPlayer → AVPlayer
    (r"^import com\.google\.android\.exoplayer2\.ExoPlayer.*$",
     "import media from '@ohos.multimedia.media'"),
    (r"^import com\.google\.android\.exoplayer2\.SimpleExoPlayer.*$",
     "import media from '@ohos.multimedia.media'"),
    (r"^import com\.google\.android\.exoplayer2\.Player.*$",
     "// AVPlayer: use media.AVPlayer"),
    (r"^import com\.google\.android\.exoplayer2\.PlaybackException.*$",
     "// PlaybackException → media.BusinessError"),
    (r"^import com\.google\.android\.exoplayer2\.(audio\.)?AudioAttributes.*$",
     "import audio from '@ohos.audio'"),
    (r"^import com\.google\.android\.exoplayer2\.ext\.cast\.(CastPlayer|DefaultCastOptionsProvider|DefaultMediaItemConverter|MediaItemConverter|SessionAvailabilityListener).*$",
     "// CastPlayer → no HarmonyOS equivalent; remove or stub"),
    (r"^import com\.google\.android\.exoplayer2\.ext\.mediasession\..*$",
     "// MediaSessionConnector → AVSession handles this natively"),
    (r"^import com\.google\.android\.exoplayer2\.ui\.PlayerNotificationManager.*$",
     "import notificationManager from '@ohos.notificationManager'"),
    (r"^import com\.google\.android\.exoplayer2\..*$",
     "import media from '@ohos.multimedia.media'  // ExoPlayer → AVPlayer"),

    # MediaSession / MediaBrowser compat
    (r"^import android\.support\.v4\.media\.session\.MediaSessionCompat.*$",
     "import avSession from '@ohos.multimedia.avsession'"),
    (r"^import android\.support\.v4\.media\.session\.MediaControllerCompat.*$",
     "import avSession from '@ohos.multimedia.avsession'"),
    (r"^import android\.support\.v4\.media\.session\.PlaybackStateCompat.*$",
     "import avSession from '@ohos.multimedia.avsession'"),
    (r"^import android\.support\.v4\.media\.MediaMetadataCompat.*$",
     "import avSession from '@ohos.multimedia.avsession'"),
    (r"^import android\.support\.v4\.media\.MediaBrowserCompat.*$",
     "import avSession from '@ohos.multimedia.avsession'"),
    (r"^import android\.support\.v4\.media\.MediaDescriptionCompat.*$",
     "import avSession from '@ohos.multimedia.avsession'"),
    (r"^import android\.support\.v4\.media\..*$",
     "import avSession from '@ohos.multimedia.avsession'"),
    (r"^import androidx\.media\.MediaBrowserServiceCompat.*$",
     "import avSession from '@ohos.multimedia.avsession'"),
    (r"^import androidx\.media2?\..*$",
     "import avSession from '@ohos.multimedia.avsession'"),

    # AudioManager
    (r"^import android\.media\.AudioManager.*$",
     "import audio from '@ohos.audio'"),
    (r"^import android\.media\.AudioFocusRequest.*$",
     "import audio from '@ohos.audio'"),
    (r"^import android\.media\.AudioAttributes.*$",
     "import audio from '@ohos.audio'"),
]

# ── PlaybackState 常量映射 ─────────────────────────────────────────────────────

_PLAYBACK_STATE_MAP = {
    "PlaybackStateCompat.STATE_PLAYING":   "avSession.PlaybackState.PLAYBACK_STATE_PLAY",
    "PlaybackStateCompat.STATE_PAUSED":    "avSession.PlaybackState.PLAYBACK_STATE_PAUSE",
    "PlaybackStateCompat.STATE_STOPPED":   "avSession.PlaybackState.PLAYBACK_STATE_STOP",
    "PlaybackStateCompat.STATE_BUFFERING": "avSession.PlaybackState.PLAYBACK_STATE_BUFFERING",
    "PlaybackStateCompat.STATE_NONE":      "avSession.PlaybackState.PLAYBACK_STATE_INITIAL",
    "PlaybackStateCompat.STATE_ERROR":     "avSession.PlaybackState.PLAYBACK_STATE_ERROR",
    "PlaybackStateCompat.STATE_CONNECTING":"avSession.PlaybackState.PLAYBACK_STATE_INITIAL",
    "PlaybackStateCompat.STATE_FAST_FORWARDING": "avSession.PlaybackState.PLAYBACK_STATE_FAST_FORWARD",
    "PlaybackStateCompat.STATE_REWINDING": "avSession.PlaybackState.PLAYBACK_STATE_REWIND",
    # Actions
    "PlaybackStateCompat.ACTION_PLAY":      "avSession.AVControlCommandType.AVSESSION_COMMAND_PLAY",
    "PlaybackStateCompat.ACTION_PAUSE":     "avSession.AVControlCommandType.AVSESSION_COMMAND_PAUSE",
    "PlaybackStateCompat.ACTION_STOP":      "avSession.AVControlCommandType.AVSESSION_COMMAND_STOP",
    "PlaybackStateCompat.ACTION_SKIP_TO_NEXT":     "avSession.AVControlCommandType.AVSESSION_COMMAND_PLAY_NEXT",
    "PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS": "avSession.AVControlCommandType.AVSESSION_COMMAND_PLAY_PREVIOUS",
    "PlaybackStateCompat.ACTION_SEEK_TO":   "avSession.AVControlCommandType.AVSESSION_COMMAND_SEEK",
    "PlaybackStateCompat.ACTION_PLAY_PAUSE":"avSession.AVControlCommandType.AVSESSION_COMMAND_TOGGLE_FAVORITE",
    "PlaybackStateCompat.ACTION_PLAY_FROM_MEDIA_ID": "0",
    "PlaybackStateCompat.ACTION_PLAY_FROM_SEARCH":   "0",
    "PlaybackStateCompat.ACTION_PREPARE_FROM_MEDIA_ID": "0",
    "PlaybackStateCompat.ACTION_PREPARE_FROM_SEARCH":   "0",
    "EMPTY_PLAYBACK_STATE": "{ state: avSession.PlaybackState.PLAYBACK_STATE_INITIAL, speed: 1.0, position: { elapsedTime: 0, updateTime: 0 } } as avSession.AVPlaybackState",
}

# ── MediaMetadata key 常量 ─────────────────────────────────────────────────────

_METADATA_KEY_MAP = {
    "MediaMetadataCompat.METADATA_KEY_TITLE":       "'title'",
    "MediaMetadataCompat.METADATA_KEY_ARTIST":      "'artist'",
    "MediaMetadataCompat.METADATA_KEY_ALBUM":       "'album'",
    "MediaMetadataCompat.METADATA_KEY_ALBUM_ARTIST":"'albumArtist'",
    "MediaMetadataCompat.METADATA_KEY_COMPOSER":    "'composer'",
    "MediaMetadataCompat.METADATA_KEY_DURATION":    "'duration'",
    "MediaMetadataCompat.METADATA_KEY_GENRE":       "'genre'",
    "MediaMetadataCompat.METADATA_KEY_TRACK_NUMBER":"'trackNumber'",
    "MediaMetadataCompat.METADATA_KEY_DISC_NUMBER": "'discNumber'",
    "MediaMetadataCompat.METADATA_KEY_YEAR":        "'releaseTime'",
    "MediaMetadataCompat.METADATA_KEY_ART_URI":     "'mediaImage'",
    "MediaMetadataCompat.METADATA_KEY_ALBUM_ART_URI": "'mediaImage'",
    "MediaMetadataCompat.METADATA_KEY_DISPLAY_TITLE":  "'title'",
    "MediaMetadataCompat.METADATA_KEY_DISPLAY_SUBTITLE": "'subtitle'",
    "MediaMetadataCompat.METADATA_KEY_DISPLAY_DESCRIPTION": "'description'",
    "MediaMetadataCompat.METADATA_KEY_MEDIA_URI":    "'mediaUri'",
    "MediaMetadataCompat.METADATA_KEY_MEDIA_ID":     "'mediaId'",
    "MediaMetadata.KEY_TITLE":       "'title'",
    "MediaMetadata.KEY_ARTIST":      "'artist'",
    "MediaMetadata.KEY_ALBUM_TITLE": "'album'",
    "MediaMetadata.KEY_ALBUM_ARTIST":"'albumArtist'",
    "MediaMetadata.KEY_COMPOSER":    "'composer'",
    "MediaMetadata.KEY_SUBTITLE":    "'subtitle'",
    "MediaMetadata.KEY_DISC_NUMBER": "'discNumber'",
    "MediaMetadata.KEY_TRACK_NUMBER":"'trackNumber'",
    "NOTHING_PLAYING": "{ title: '', artist: '', mediaImage: '' } as avSession.AVMediaDescription",
}


class MediaTransform:
    """Android 媒体 API → HarmonyOS AVSession / AVPlayer 转换器。"""

    def transform(self, code: str) -> str:
        if not is_media_file(code):
            return code

        code = self._transform_imports(code)
        code = self._transform_class_decl(code)
        code = self._transform_playback_state(code)
        code = self._transform_metadata_keys(code)
        code = self._transform_media_session(code)
        code = self._transform_exoplayer(code)
        code = self._transform_audio_focus(code)
        code = self._transform_notification(code)
        code = self._transform_cast_player(code)
        code = self._add_media_header(code)
        return code

    # ── imports ─────────────────────────────────────────────────────────────

    def _transform_imports(self, code: str) -> str:
        seen_imports: set = set()
        lines = code.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            replaced = False
            if stripped.startswith("import ") and not stripped.startswith("import {"):
                for pattern, replacement in _IMPORT_MAP:
                    if re.match(pattern, stripped):
                        if replacement:
                            # Normalize key for dedup: strip trailing comments
                            key = replacement.split("//")[0].strip() or replacement
                            if key not in seen_imports:
                                clean = replacement.split("//")[0].strip() or replacement
                                result.append(clean if clean else replacement)
                                seen_imports.add(key)
                        replaced = True
                        break
            if not replaced:
                result.append(line)
        return "\n".join(result)

    def _skip_comment_line(self, line: str) -> bool:
        """True if line is a comment and should not be transformed."""
        s = line.lstrip()
        return s.startswith("//") or s.startswith("*") or s.startswith("/*")

    # ── class declaration ────────────────────────────────────────────────────

    def _sub_code_only(self, pattern: str, repl, code: str, **kwargs) -> str:
        """Apply re.sub only on non-comment lines."""
        lines = code.split("\n")
        result = []
        for line in lines:
            if self._skip_comment_line(line):
                result.append(line)
            else:
                result.append(re.sub(pattern, repl, line, **kwargs))
        return "\n".join(result)

    def _replace_code_only(self, old: str, new: str, code: str) -> str:
        """str.replace only on non-comment lines."""
        lines = code.split("\n")
        result = []
        for line in lines:
            if self._skip_comment_line(line):
                result.append(line)
            else:
                result.append(line.replace(old, new))
        return "\n".join(result)

    def _transform_class_decl(self, code: str) -> str:
        # MediaBrowserServiceCompat → ServiceExtensionAbility
        code = re.sub(
            r'\bclass\s+(\w+)\s*(?::\s*)?MediaBrowserServiceCompat\s*\(\s*\)',
            lambda m: (
                f"// TODO: MediaBrowserService → HarmonyOS AVSessionManager server\n"
                f"// Implement onGetRoot/onLoadChildren → AVSessionManager.on('sessionCreate')\n"
                f"export class {m.group(1)} extends ServiceExtensionAbility"
            ),
            code,
        )
        # implements/extends Player.Listener / Player.EventListener
        code = re.sub(
            r'\bimplements\s+Player\.(?:Listener|EventListener)\b',
            '/* implements AVPlayer.on("stateChange") — register in onConnect */',
            code,
        )
        return code

    # ── PlaybackState ────────────────────────────────────────────────────────

    def _transform_playback_state(self, code: str) -> str:
        for android_const, ohos_const in _PLAYBACK_STATE_MAP.items():
            code = self._replace_code_only(android_const, ohos_const, code)
        # PlaybackStateCompat.Builder() → plain object
        code = re.sub(
            r'PlaybackStateCompat\.Builder\(\)',
            '/* AVPlaybackState */ ({} as any)',
            code,
        )
        # .setState(state, pos, speed) → avPlaybackState stub
        code = re.sub(
            r'\.setState\s*\(\s*(\w[\w.]*)\s*,\s*([^,)]+)\s*,\s*([^)]+)\)',
            lambda m: (
                f".setState(/* state */ {m.group(1)}, "
                f"/* pos */ {m.group(2).strip()}, "
                f"/* speed */ {m.group(3).strip()})"
            ),
            code,
        )
        # .setActions(actions) → comment
        code = re.sub(
            r'\.setActions\s*\([^)]+\)',
            '/* .setActions() — set via AVSession.setValidCommands([...]) */',
            code,
        )
        return code

    # ── MediaMetadata keys ───────────────────────────────────────────────────

    def _transform_metadata_keys(self, code: str) -> str:
        for android_key, ohos_key in _METADATA_KEY_MAP.items():
            code = self._replace_code_only(android_key, ohos_key, code)
        # MediaMetadataCompat.Builder() → AVMediaDescription builder
        code = re.sub(
            r'\bMediaMetadataCompat\.Builder\(\)',
            '/* AVMediaDescription */ ({} as avSession.AVMediaDescription)',
            code,
        )
        # .putString(key, val) / .putLong(key, val) → spread assignment hint
        code = re.sub(
            r'\.put(?:String|Long|Bitmap|Uri|Float|Rating)\s*\(\s*([^,)]+)\s*,\s*([^)]+)\)',
            lambda m: f'/* .put({m.group(1).strip()}: {m.group(2).strip()}) */',
            code,
        )
        return code

    # ── MediaSession ─────────────────────────────────────────────────────────

    def _transform_media_session(self, code: str) -> str:
        # new MediaSessionCompat(ctx, "tag") → avSession.createAVSession(ctx, 'audio')
        code = re.sub(
            r'\bnew\s+MediaSessionCompat\s*\([^)]+\)',
            "/* await */ avSession.createAVSession(this.context, 'audio')",
            code,
        )
        # mediaSession.isActive = true/false
        code = re.sub(
            r'(\w+)\.isActive\s*=\s*true\b',
            r'\1.activate()',
            code,
        )
        code = re.sub(
            r'(\w+)\.isActive\s*=\s*false\b',
            r'\1.deactivate()',
            code,
        )
        # mediaSession.setPlaybackState(state) → session.setAVPlaybackState(state)
        code = re.sub(
            r'(\w+)\.setPlaybackState\s*\(([^)]+)\)',
            r'/* await */ \1.setAVPlaybackState(\2)',
            code,
        )
        # mediaSession.setMetadata(meta) → session.setAVMetadata(meta)
        code = re.sub(
            r'(\w+)\.setMetadata\s*\(([^)]+)\)',
            r'/* await */ \1.setAVMetadata(\2)',
            code,
        )
        # mediaSession.release() → session.destroy()
        code = re.sub(
            r'(\w+)\.release\s*\(\s*\)(?=\s*[;\n])',
            r'\1.destroy()',
            code,
        )
        # mediaSession.sessionToken → session.sessionId
        code = re.sub(r'(\w+)\.sessionToken\b', r'\1.sessionId', code)
        # mediaSession.setCallback(cb) → TODO
        code = re.sub(
            r'(\w+)\.setCallback\s*\([^)]+\)',
            r'// TODO: use session.on("play", cb) / session.on("pause", cb) etc.',
            code,
        )
        # MediaSessionConnector → comment
        code = re.sub(
            r'\bMediaSessionConnector\s*\([^)]+\)',
            '/* MediaSessionConnector removed — AVSession handles this natively */(null as any)',
            code,
        )
        # TimelineQueueNavigator → comment
        code = re.sub(
            r'\bTimelineQueueNavigator\b[^{]*\{[^}]*\}',
            '/* TimelineQueueNavigator → implement avSession queue via setAVQueueItems() */',
            code,
            flags=re.DOTALL,
        )
        # MediaControllerCompat.getTransportControls() → sessionController.getOutputDevice()
        code = re.sub(
            r'(\w+)\.getTransportControls\(\)',
            r'/* AVSessionController */ \1',
            code,
        )
        # controller.transportControls.play/pause/stop/seekTo
        for action in ('play', 'pause', 'stop', 'skipToNext', 'skipToPrevious'):
            ohos = {'skipToNext': 'playNext', 'skipToPrevious': 'playPrevious'}.get(action, action)
            code = re.sub(
                rf'\.transportControls\.{action}\s*\(\)',
                f'.sendControlCommand("{ohos}")',
                code,
            )
        code = re.sub(
            r'\.transportControls\.seekTo\s*\(([^)]+)\)',
            r'.sendControlCommand("seek", { parameter: \1 })',
            code,
        )
        return code

    # ── ExoPlayer → AVPlayer ─────────────────────────────────────────────────

    def _transform_exoplayer(self, code: str) -> str:
        # ExoPlayer.Builder(ctx).build() / SimpleExoPlayer.Builder(ctx).build()
        code = re.sub(
            r'(?:ExoPlayer|SimpleExoPlayer)\.Builder\s*\([^)]*\)(?:\.[^(]+\([^)]*\))*\.build\(\)',
            '/* await */ media.createAVPlayer()',
            code,
        )
        # player.playWhenReady = true/false
        code = re.sub(r'(\w+)\.playWhenReady\s*=\s*true\b', r'\1.play()', code)
        code = re.sub(r'(\w+)\.playWhenReady\s*=\s*false\b', r'\1.pause()', code)
        # player.playWhenReady (getter) → player.state === 'playing'
        code = re.sub(
            r'(\w+)\.playWhenReady\b',
            r"(\1.state === 'playing')",
            code,
        )
        # player.pause() / play() / stop() / prepare() — already AVPlayer API
        # player.seekTo(pos) → player.seek(pos)
        code = re.sub(
            r'(\w+)\.seekTo\s*\(\s*(\d+)\s*,\s*([^)]+)\)',
            r'/* multi-window */ \1.seek(\3)  // TODO: window index \2 ignored',
            code,
        )
        code = re.sub(
            r'(\w+)\.seekTo\s*\(([^)]+)\)',
            r'\1.seek(\2)',
            code,
        )
        # player.currentPosition → Math.round(player.currentTime * 1000)
        code = re.sub(
            r'(\w+)\.currentPosition\b',
            r'Math.round(\1.currentTime * 1000)',
            code,
        )
        # player.duration → Math.round(player.duration * 1000)
        # (AVPlayer.duration is in seconds, Android is ms)
        code = re.sub(
            r'(\w+)\.duration\b(?!\s*\*)',
            r'Math.round(\1.duration * 1000)',
            code,
        )
        # player.addListener / removeListener
        code = re.sub(
            r'(\w+)\.addListener\s*\(([^)]+)\)',
            r"// TODO: \1.on('stateChange', (state) => { /* handle \2 */ })",
            code,
        )
        code = re.sub(
            r'(\w+)\.removeListener\s*\(([^)]+)\)',
            r"// TODO: \1.off('stateChange')",
            code,
        )
        # player.setMediaItem(item) → player.url = ...
        code = re.sub(
            r'(\w+)\.setMediaItem\s*\(([^)]+)\)',
            r'// TODO: \1.url = \2.localConfiguration?.uri?.toString() ?? ""; await \1.prepare()',
            code,
        )
        # player.setMediaItems(items) → TODO
        code = re.sub(
            r'(\w+)\.setMediaItems\s*\([^)]+\)',
            r'// TODO: set playlist — loop setMediaSources or use AVPlayer queue',
            code,
        )
        # player.currentMediaItem
        code = re.sub(
            r'(\w+)\.currentMediaItem\b',
            r'/* currentMediaItem → use avSession queue state */ \1',
            code,
        )
        # Player.STATE_IDLE / BUFFERING / READY / ENDED
        code = self._replace_code_only("Player.STATE_IDLE",      "/* idle */    'idle'",      code)
        code = self._replace_code_only("Player.STATE_BUFFERING",  "/* buffering */'prepared'", code)
        code = self._replace_code_only("Player.STATE_READY",      "/* ready */   'prepared'",  code)
        code = self._replace_code_only("Player.STATE_ENDED",      "/* ended */   'completed'", code)
        # ExoPlayer C.TIME_UNSET → -1
        code = self._sub_code_only(r'\bC\.TIME_UNSET\b', '-1', code)
        # MimeTypes.APPLICATION_M3U8 etc → string literals
        code = re.sub(
            r'\bMimeTypes\.(\w+)\b',
            lambda m: f"'application/{m.group(1).lower().replace('_', '/')}'",
            code,
        )
        return code

    # ── AudioFocus ───────────────────────────────────────────────────────────

    def _transform_audio_focus(self, code: str) -> str:
        # AudioFocusRequest.Builder(AUDIOFOCUS_GAIN) → audio.InterruptRequestType
        code = re.sub(
            r'\bAudioFocusRequest\.Builder\s*\([^)]+\)(?:\.[^;]+)?\.build\(\)',
            "{ contentType: audio.ContentType.CONTENT_TYPE_MUSIC, "
            "usage: audio.StreamUsage.STREAM_USAGE_MEDIA, "
            "pauseWhenDucked: false } as audio.AudioFocusInfoForTest",
            code,
        )
        # audioManager.requestAudioFocus(...)
        code = re.sub(
            r'(\w+)\.requestAudioFocus\s*\([^)]+\)',
            r'// TODO: await audioMgr.requestAudioFocus({ contentType: audio.ContentType.CONTENT_TYPE_MUSIC, streamUsage: audio.StreamUsage.STREAM_USAGE_MEDIA })',
            code,
        )
        # audioManager.abandonAudioFocusRequest(...)
        code = re.sub(
            r'(\w+)\.abandonAudioFocus(?:Request)?\s*\([^)]*\)',
            r'// TODO: await audioMgr.abandonAudioFocus(focusInfo)',
            code,
        )
        # AudioManager.AUDIOFOCUS_GAIN/LOSS constants
        for android_const, ohos_const in {
            "AUDIOFOCUS_GAIN":             "audio.InterruptHint.INTERRUPT_HINT_NONE",
            "AUDIOFOCUS_GAIN_TRANSIENT":   "audio.InterruptHint.INTERRUPT_HINT_PAUSE",
            "AUDIOFOCUS_LOSS":             "audio.InterruptHint.INTERRUPT_HINT_STOP",
            "AUDIOFOCUS_LOSS_TRANSIENT":   "audio.InterruptHint.INTERRUPT_HINT_PAUSE",
            "AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK": "audio.InterruptHint.INTERRUPT_HINT_DUCK",
        }.items():
            code = code.replace(f"AudioManager.{android_const}", ohos_const)
        return code

    # ── PlayerNotificationManager → HarmonyOS Notification ──────────────────

    def _transform_notification(self, code: str) -> str:
        code = re.sub(
            r'\bPlayerNotificationManager\.Builder\s*\([^)]*\)(?:\.[^;{]+)?',
            '/* PlayerNotificationManager → notificationManager.publish() with AVSession media template */(null as any)',
            code,
        )
        code = re.sub(
            r'\bPlayerNotificationManager\b',
            '/* PlayerNotificationManager — use notificationManager + AVSession */ any',
            code,
        )
        return code

    # ── CastPlayer → stub ────────────────────────────────────────────────────

    def _transform_cast_player(self, code: str) -> str:
        code = self._sub_code_only(
            r'\bCastPlayer\s*\([^)]*\)(?:\.[^;{]+)?',
            '/* CastPlayer — no HarmonyOS equivalent; remove Cast support */(null as any)',
            code,
        )
        code = self._sub_code_only(
            r'\bCastPlayer\b',
            '/* CastPlayer — no HarmonyOS equivalent */ any',
            code,
        )
        code = self._sub_code_only(
            r'\bSessionAvailabilityListener\b',
            '/* SessionAvailabilityListener — remove */',
            code,
        )
        return code

    # ── header ───────────────────────────────────────────────────────────────

    def _add_media_header(self, code: str) -> str:
        header = (
            "// MEDIA-CONVERTED: Android MediaSession/ExoPlayer → HarmonyOS AVSession/AVPlayer\n"
            "// Key API changes:\n"
            "//   MediaSessionCompat → avSession.createAVSession()\n"
            "//   ExoPlayer → media.createAVPlayer()\n"
            "//   PlaybackStateCompat.STATE_* → avSession.PlaybackState.PLAYBACK_STATE_*\n"
            "//   MediaMetadataCompat key → AVMediaDescription field\n"
            "// Ref: https://developer.huawei.com/consumer/cn/doc/harmonyos-guides/avsession-overview\n\n"
        )
        if "MEDIA-CONVERTED" not in code:
            return header + code
        return code
